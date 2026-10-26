import { defineStore } from 'pinia'
import { db } from '../db'
import { writeRecord } from '../sync/engine'

export const DEFAULT_LEARNING_SETTINGS = Object.freeze({
  bulletEnabled: true, focusMin: 25, shortBreakMin: 5, longBreakMin: 15, longBreakEvery: 4,
})
export function validateLearningSettings(value) {
  const bounds = { focusMin: [5, 180], shortBreakMin: [1, 60], longBreakMin: [1, 180], longBreakEvery: [1, 8] }
  if (value.bulletEnabled !== undefined && typeof value.bulletEnabled !== 'boolean') throw new Error('弹幕开关必须为布尔值')
  const clean = { bulletEnabled: value.bulletEnabled ?? true }
  for (const [key, [min, max]] of Object.entries(bounds)) {
    const number = Number(value[key])
    if (!Number.isInteger(number) || number < min || number > max) throw new Error('请按显示的范围填写整数')
    clean[key] = number
  }
  return clean
}
export const useLearningSettingsStore = defineStore('learningSettings', {
  state: () => ({ value: { ...DEFAULT_LEARNING_SETTINGS }, loaded: false }),
  actions: {
    async load(force = false) {
      if (this.loaded && !force) return
      const row = await db.kv.get('learning-settings')
      this.value = row ? validateLearningSettings({ ...DEFAULT_LEARNING_SETTINGS, ...row.value }) : { ...DEFAULT_LEARNING_SETTINGS }
      this.loaded = true
    },
    async save(value) {
      const clean = validateLearningSettings(value)
      const old = await db.kv.get('learning-settings')
      await writeRecord('kv', { key: 'learning-settings', id: 'learning-settings',
        syncType: 'preferences', value: clean, _rev: old?._rev || 0, updatedAt: Date.now() })
      this.value = clean
    },
  },
})
