import { defineStore } from 'pinia'
import { localAccountScope } from '../db'
import { writeRecord } from '../sync/engine'

export const DEFAULT_LEARNING_SETTINGS = Object.freeze({
  bulletEnabled: true, bulletText: '', focusMin: 25, shortBreakMin: 5, longBreakMin: 15, longBreakEvery: 4,
  dailyReminder: false,
})
export function validateLearningSettings(value) {
  const bounds = { focusMin: [5, 180], shortBreakMin: [1, 60], longBreakMin: [1, 180], longBreakEvery: [1, 8] }
  if (value.bulletEnabled !== undefined && typeof value.bulletEnabled !== 'boolean') throw new Error('弹幕开关必须为布尔值')
  if (value.bulletText !== undefined && typeof value.bulletText !== 'string') throw new Error('弹幕内容必须是文字')
  if (value.dailyReminder !== undefined && typeof value.dailyReminder !== 'boolean') throw new Error('每日学习提醒设置无效')
  const bulletText = String(value.bulletText || '').trim()
  if (bulletText.length > 80) throw new Error('弹幕最多 80 个字')
  const clean = { bulletEnabled: value.bulletEnabled ?? true, bulletText, dailyReminder: value.dailyReminder ?? false }
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
      const scope = localAccountScope()
      if (this.loaded && !force) return
      const row = await scope.db.kv.get('learning-settings')
      if (!scope.isCurrent()) return
      this.value = row ? validateLearningSettings({ ...DEFAULT_LEARNING_SETTINGS, ...row.value }) : { ...DEFAULT_LEARNING_SETTINGS }
      this.loaded = true
    },
    async save(value) {
      const scope = localAccountScope()
      const clean = validateLearningSettings(value)
      const old = await scope.db.kv.get('learning-settings')
      scope.assertCurrent()
      await writeRecord('kv', { key: 'learning-settings', id: 'learning-settings',
        syncType: 'preferences', value: clean, _rev: old?._rev || 0, updatedAt: Date.now() })
      scope.assertCurrent()
      this.value = clean
    },
  },
})
