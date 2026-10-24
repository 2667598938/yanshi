import { defineStore } from 'pinia'
import { db, uid } from '../db'
import { todayKey, dayKey } from '../utils/date'
import { enqueueRecord, enqueueDelete } from '../sync/engine'

// 学习计划 / 任务清单。任务完成与否是"真学会"的指标之一，与时长并列。
export const useTasksStore = defineStore('tasks', {
  state: () => ({ list: [], loaded: false }),
  getters: {
    sorted: (s) =>
      [...s.list].sort(
        (a, b) =>
          (a.dueDate || '9999').localeCompare(b.dueDate || '9999') ||
          a.createdAt - b.createdAt
      ),
    open: (s) => s.list.filter((t) => !t.done),
    // 今日到期 + 已逾期（未完成）
    dueToday() {
      const t = todayKey()
      return this.open
        .filter((x) => x.dueDate && x.dueDate <= t)
        .sort((a, b) => (a.dueDate || '').localeCompare(b.dueDate || ''))
    },
    overdueCount() {
      const t = todayKey()
      return this.open.filter((x) => x.dueDate && x.dueDate < t).length
    },
    // 今日到期的全部任务（含已完成，用于今日完成率）
    todayAll() {
      const t = todayKey()
      return this.sorted.filter((x) => x.dueDate === t)
    },
  },
  actions: {
    async load() {
      if (this.loaded) return
      this.list = await db.tasks.toArray()
      this.loaded = true
    },
    async add(payload) {
      const title = (payload.title || '').trim()
      if (!title) return null
      const item = {
        id: uid('task_'),
        title,
        subjectId: payload.subjectId || 'other',
        phase: payload.phase || 'custom',
        acceptCriteria: payload.acceptCriteria || '',
        dueDate: payload.dueDate || todayKey(),
        done: 0,
        doneAt: null,
        createdAt: Date.now(),
      }
      await db.tasks.add(item)
      this.list.push(item)
      await enqueueRecord('tasks', item)
      return item
    },
    async update(id, patch) {
      await db.tasks.update(id, patch)
      const i = this.list.findIndex((x) => x.id === id)
      if (i >= 0) {
        this.list[i] = { ...this.list[i], ...patch }
        await enqueueRecord('tasks', this.list[i])
      }
    },
    async toggle(id) {
      const t = this.list.find((x) => x.id === id)
      if (!t) return
      const done = t.done ? 0 : 1
      const doneAt = done ? Date.now() : null
      await db.tasks.update(id, { done, doneAt })
      t.done = done
      t.doneAt = doneAt
      await enqueueRecord('tasks', t)
    },
    async remove(id) {
      await enqueueDelete('tasks', id)
      this.list = this.list.filter((x) => x.id !== id)
    },
    // 某日期区间内（按到期日）任务完成率
    rangeRate(startKey, endKey) {
      const rows = this.list.filter(
        (x) => x.dueDate && x.dueDate >= startKey && x.dueDate <= endKey
      )
      if (!rows.length) return null
      return Math.round((rows.filter((x) => x.done).length / rows.length) * 100)
    },
    // 某区间内完成的任务数（按完成时间）
    doneCountBetween(startKey, endKey) {
      return this.list
        .filter((x) => x.done && x.doneAt)
        .filter((x) => {
          const k = dayKey(new Date(x.doneAt))
          return k >= startKey && k <= endKey
        }).length
    },
  },
})
