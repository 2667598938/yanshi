import { defineStore } from 'pinia'
import { db, uid } from '../db'
import { todayKey, addDaysKey } from '../utils/date'
import { REVIEW_INTERVALS } from '../data/subjects'
import { enqueueRecord, enqueueDelete } from '../sync/engine'

// 错题本：图片以 Blob 存 IndexedDB；艾宾浩斯 1/2/4/7/15/30 天复习
export const useMistakesStore = defineStore('mistakes', {
  state: () => ({ list: [], loaded: false }),
  getters: {
    sorted: (s) => [...s.list].sort((a, b) => b.createdAt - a.createdAt),
    // 今日待复习（含已逾期未复习）
    dueReview() {
      const t = todayKey()
      return this.sorted
        .filter((x) => !x.mastered && x.nextReviewAt && x.nextReviewAt <= t)
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
    async load() {
      if (this.loaded) return
      this.list = await db.mistakes.toArray()
      this.loaded = true
    },
    async add(payload) {
      const item = {
        id: uid('mk_'),
        subjectId: payload.subjectId || 'other',
        chapter: payload.chapter || '',
        reason: payload.reason || 'other',
        tags: payload.tags || [],
        content: payload.content || '',
        images: payload.images || [],
        sessionId: payload.sessionId || null,
        sourceDate: payload.sourceDate || todayKey(),
        stage: 0,
        mastered: 0,
        nextReviewAt: addDaysKey(todayKey(), REVIEW_INTERVALS[0]),
        history: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      }
      await db.mistakes.add(item)
      this.list.push(item)
      await enqueueRecord('mistakes', item)
      return item
    },
    async update(id, patch) {
      patch.updatedAt = Date.now()
      await db.mistakes.update(id, patch)
      const i = this.list.findIndex((x) => x.id === id)
      if (i >= 0) {
        this.list[i] = { ...this.list[i], ...patch }
        await enqueueRecord('mistakes', this.list[i])
      }
    },
    async remove(id) {
      await enqueueDelete('mistakes', id)
      this.list = this.list.filter((x) => x.id !== id)
    },
    // 复习：remembered=true 进入下一间隔；false 重置回第 1 天
    async review(id, remembered = true) {
      const m = this.list.find((x) => x.id === id)
      if (!m) return
      const t = todayKey()
      const history = [...(m.history || []), { date: t, remembered, at: Date.now() }]
      let stage = m.stage
      let mastered = 0
      let nextReviewAt
      if (remembered) {
        stage = m.stage + 1
        if (stage >= REVIEW_INTERVALS.length) {
          mastered = 1
          nextReviewAt = null
        } else {
          nextReviewAt = addDaysKey(t, REVIEW_INTERVALS[stage])
        }
      } else {
        stage = 0
        nextReviewAt = addDaysKey(t, REVIEW_INTERVALS[0])
      }
      const patch = { stage, mastered, nextReviewAt, history }
      await db.mistakes.update(id, patch)
      Object.assign(m, patch)
      await enqueueRecord('mistakes', m)
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
      const t = todayKey()
      return this.list.filter(
        (x) => !x.mastered && x.nextReviewAt && x.nextReviewAt <= t
      ).length
    },
  },
})
