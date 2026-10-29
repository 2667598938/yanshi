import { defineStore } from 'pinia'
import { db, localAccountScope, uid } from '../db'
import { todayKey } from '../utils/date'
import { REVIEW_INTERVALS } from '../data/subjects'
import { enqueueRecord, enqueueDelete } from '../sync/engine'
import { toPlain } from '../utils/plain'
import { useClockStore } from './clock'

// 错题本：图片以 Blob 存 IndexedDB；艾宾浩斯 8 节点（5min → 15d）
const OLD_TO_NEW_STAGE = [3, 4, 5, 6, 7, 7]

function scheduleAt(stage, base = Date.now()) {
  return base + REVIEW_INTERVALS[Math.min(stage, REVIEW_INTERVALS.length - 1)] * 60000
}

// 旧版按「天」+ 日期字符串存复习计划，载入时迁移为毫秒时间戳与 8 节点阶段
async function migrateRows(rows, scope) {
  let changed = false
  for (const row of rows) {
    if (typeof row.nextReviewAt !== 'string') continue
    const dueMs = new Date(`${row.nextReviewAt}T00:00:00`).getTime()
    row.stage = row.mastered ? REVIEW_INTERVALS.length : OLD_TO_NEW_STAGE[Math.min(Math.max(row.stage || 0, 0), 5)]
    row.nextReviewAt = row.mastered ? null : (Number.isFinite(dueMs) ? dueMs : Date.now())
    changed = true
    scope.assertCurrent()
    await scope.db.mistakes.put(row)
    scope.assertCurrent()
    await enqueueRecord('mistakes', row)
  }
  return changed
}

export const useMistakesStore = defineStore('mistakes', {
  state: () => ({ list: [], loaded: false }),
  getters: {
    sorted: (s) => [...s.list].sort((a, b) => b.createdAt - a.createdAt),
    // 今日待复习（含已逾期）
    dueReview() {
      const now = useClockStore().now
      return this.sorted.filter(
        (x) => !x.mastered && x.nextReviewAt && x.nextReviewAt <= now
      )
    },
    // 仍在复习周期内（未掌握）
    active: (s) => s.list.filter((x) => !x.mastered),
    // 按来源日期聚合（用于点击热力格子看当天错题）
    byDate: (s) => {
      const m = {}
      for (const x of s.list) {
        const k = x.sourceDate
        if (!m[k]) m[k] = []
        m[k].push(x)
      }
      return m
    },
  },
  actions: {
    async load(force = false) {
      const scope = localAccountScope()
      if (this.loaded && !force) return
      const rows = await scope.db.mistakes.toArray()
      if (!scope.isCurrent()) return
      // 迁移持久化完成后再交给 Pinia，避免把响应式 Proxy 写入 IndexedDB。
      await migrateRows(rows, scope)
      if (!scope.isCurrent()) return
      this.list = rows
      this.loaded = true
    },
    async add(payload) {
      const scope = localAccountScope()
      const item = toPlain({
        id: uid('mk_'),
        subjectId: payload.subjectId || 'other',
        chapter: payload.chapter || '',
        reason: payload.reason || 'other',
        tags: payload.tags || [],
        content: payload.content || '',
        idea: payload.idea || '',
        analysis: payload.analysis || '',
        images: payload.images || [],
        answerImages: payload.answerImages || [],
        sessionId: payload.sessionId || null,
        sourceDate: payload.sourceDate || todayKey(),
        stage: 0,
        mastered: 0,
        nextReviewAt: scheduleAt(0),
        history: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      })
      await db.transaction('rw', db.mistakes, db.outbox, db.syncMeta, async () => {
        await db.mistakes.add(item)
        await enqueueRecord('mistakes', item)
      })
      scope.assertCurrent()
      this.list.push(item)
      return item
    },
    async update(id, patch) {
      const scope = localAccountScope()
      const changes = toPlain({ ...patch, updatedAt: Date.now() })
      await db.transaction('rw', db.mistakes, db.outbox, db.syncMeta, async () => {
        await db.mistakes.update(id, changes)
        const row = await db.mistakes.get(id)
        if (row) await enqueueRecord('mistakes', row)
      })
      scope.assertCurrent()
      const i = this.list.findIndex((x) => x.id === id)
      if (i >= 0) {
        this.list[i] = { ...this.list[i], ...changes }
      }
    },
    async remove(id) {
      const scope = localAccountScope()
      await enqueueDelete('mistakes', id)
      scope.assertCurrent()
      this.list = this.list.filter((x) => x.id !== id)
    },
    // 复习：记住进入下一节点；需巩固回退上一节点（不再重置到 0）
    async review(id, remembered = true) {
      const scope = localAccountScope()
      const m = this.list.find((x) => x.id === id)
      if (!m) return
      const now = Date.now()
      // A due review advances at most once. Free practice remains available in
      // the detail view; it cannot compress spaced repetition into eight taps.
      if (m.mastered || (m.nextReviewAt && m.nextReviewAt > now)) return { advanced: false }
      const history = [...(m.history || []), {
        date: todayKey(), remembered, at: now,
        fromStage: m.stage, intervalMinutes: REVIEW_INTERVALS[m.stage],
      }]
      let stage = m.stage || 0
      let mastered = 0
      let nextReviewAt
      if (remembered) {
        stage = stage + 1
        if (stage >= REVIEW_INTERVALS.length) {
          mastered = 1
          nextReviewAt = null
        } else {
          nextReviewAt = scheduleAt(stage, now)
        }
      } else {
        stage = Math.max(0, stage - 1)
        nextReviewAt = scheduleAt(stage, now)
      }
      const patch = toPlain({ stage, mastered, nextReviewAt, history })
      let advanced = false
      await db.transaction('rw', db.mistakes, db.outbox, db.syncMeta, async () => {
        const current = await db.mistakes.get(id)
        if (!current || current.mastered || (current.nextReviewAt && current.nextReviewAt > now)) return
        if (current.stage !== m.stage) return
        await db.mistakes.update(id, patch)
        await enqueueRecord('mistakes', { ...toPlain(m), ...patch })
        advanced = true
      })
      scope.assertCurrent()
      if (advanced) Object.assign(m, patch)
      return { advanced }
    },
    // 某日期新增错题数（仪表盘用）
    countByDateRange(startKey, endKey) {
      return this.list.filter((x) => {
        const k = x.sourceDate
        return k >= startKey && k <= endKey
      }).length
    },
    totalCount() {
      return this.list.length
    },
    unreviewedCount() {
      const now = Date.now()
      return this.list.filter(
        (x) => !x.mastered && x.nextReviewAt && x.nextReviewAt <= now
      ).length
    },
  },
})
