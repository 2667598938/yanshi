import { defineStore } from 'pinia'
import { db } from '../db'
import { writeRecord } from '../sync/engine'
import { useAuthStore } from './auth'
import { useAppStore } from './app'
import { DEFAULT_SCHOOL_KEY, EXAM_DATE } from '../data/schools'

const FIELDS = ['nickname', 'target_school', 'signature', 'figure_id', 'daily_goal_min',
  'exam_date', 'notify_enabled', 'custom_motto']
export const useProfileStore = defineStore('profile', {
  state: () => ({ value: {}, loaded: false }),
  actions: {
    async load(force = false) {
      if (this.loaded && !force) return
      const auth = useAuthStore()
      const row = await db.kv.get('profile')
      const base = Object.fromEntries(FIELDS.filter((field) => auth.user?.[field] !== undefined)
        .map((field) => [field, auth.user[field]]))
      this.value = { ...base, ...Object.fromEntries(Object.entries(row?.value || {}).filter(([key]) => FIELDS.includes(key))) }
      if (auth.user && auth.setUser) auth.setUser({ ...auth.user, ...this.value })
      const app = useAppStore()
      app.$patch({ nickname: this.value.nickname || '追梦人', dreamSchool: this.value.target_school || DEFAULT_SCHOOL_KEY,
        dailyGoalMin: this.value.daily_goal_min || 300, notifyEnabled: !!this.value.notify_enabled,
        examDate: this.value.exam_date || EXAM_DATE })
      app.persist()
      this.loaded = true
    },
    async save(patch) {
      const auth = useAuthStore()
      if (!auth.user) throw new Error('请先登录')
      if (Object.keys(patch).some((key) => !FIELDS.includes(key))) throw new Error('资料字段无效')
      if (patch.nickname !== undefined && (patch.nickname.trim().length < 2 || patch.nickname.length > 40)) throw new Error('昵称需为2–40个字')
      if (patch.signature?.length > 80) throw new Error('签名最多80个字')
      const old = await db.kv.get('profile')
      const value = { ...Object.fromEntries(FIELDS.filter((key) => auth.user[key] !== undefined)
        .map((key) => [key, auth.user[key]])), ...Object.fromEntries(Object.entries(old?.value || {}).filter(([key]) => FIELDS.includes(key))), ...patch }
      await writeRecord('kv', { key: 'profile', id: 'profile', syncType: 'profile',
        value, _rev: old?._rev || 0, updatedAt: Date.now() })
      await this.load(true)
    },
  },
})
