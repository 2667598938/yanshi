import { defineStore } from 'pinia'
import { db, uid } from '../db'
import { enqueueRecord } from '../sync/engine'

// 科目：统一软删除（归档），不物理删除，保证历史番茄记录的统计仍能找到科目
export const useSubjectsStore = defineStore('subjects', {
  state: () => ({ list: [], loaded: false }),
  getters: {
    active: (s) =>
      s.list
        .filter((x) => !x.archived)
        .sort((a, b) => a.order - b.order),
    byId: (s) => Object.fromEntries(s.list.map((x) => [x.id, x])),
  },
  actions: {
    async load() {
      if (this.loaded) return
      this.list = await db.subjects.toArray()
      this.loaded = true
    },
    async add({ name, color, icon }) {
      const orders = this.list.map((x) => x.order)
      const order = orders.length ? Math.max(...orders) + 1 : 0
      const item = {
        id: uid('sub_'),
        name: (name || '').trim() || '新科目',
        color,
        icon,
        tags: [],
        order,
        archived: 0,
        builtin: 0,
        createdAt: Date.now(),
      }
      await db.subjects.add(item)
      this.list.push(item)
      await enqueueRecord('subjects', item)
      return item
    },
    async update(id, patch) {
      await db.subjects.update(id, patch)
      const i = this.list.findIndex((x) => x.id === id)
      if (i >= 0) {
        this.list[i] = { ...this.list[i], ...patch }
        await enqueueRecord('subjects', this.list[i])
      }
    },
    // 归档（隐藏但保留历史统计）；已归档的可恢复
    async setArchived(id, archived) {
      await db.subjects.update(id, { archived: archived ? 1 : 0 })
      const item = this.list.find((x) => x.id === id)
      if (item) {
        item.archived = archived ? 1 : 0
        await enqueueRecord('subjects', item)
      }
    },
    nameOf(id) {
      return this.byId[id]?.name || '未分类'
    },
    colorOf(id) {
      return this.byId[id]?.color || '#97a4b6'
    },
  },
})
