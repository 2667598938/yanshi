import { defineStore } from 'pinia'
import { DEFAULT_SCHOOL_KEY, EXAM_DATE } from '../data/schools'

const APP_KEY = 'yanshi:app'

const DEFAULTS = {
  nickname: '追梦人',
  dreamSchool: DEFAULT_SCHOOL_KEY,
  dailyGoalMin: 300, // 每日专注目标，默认 5 小时
  examDate: EXAM_DATE,
  notifyEnabled: false,
  heroCollapsed: false,
}

function load() {
  try {
    const raw = localStorage.getItem(APP_KEY)
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS }
  } catch {
    return { ...DEFAULTS }
  }
}

export const useAppStore = defineStore('app', {
  state: () => load(),
  actions: {
    persist() {
      const { nickname, dreamSchool, dailyGoalMin, examDate, notifyEnabled, heroCollapsed } = this
      localStorage.setItem(
        APP_KEY,
        JSON.stringify({ nickname, dreamSchool, dailyGoalMin, examDate, notifyEnabled, heroCollapsed })
      )
    },
    setDreamSchool(key) {
      this.dreamSchool = key
      this.persist()
    },
    setNickname(name) {
      this.nickname = (name || '').trim() || '追梦人'
      this.persist()
    },
    setDailyGoal(min) {
      this.dailyGoalMin = min
      this.persist()
    },
    setNotifyEnabled(v) {
      this.notifyEnabled = v
      this.persist()
    },
    setHeroCollapsed(v) {
      this.heroCollapsed = !!v
      this.persist()
    },
  },
})
