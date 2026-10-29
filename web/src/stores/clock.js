import { defineStore } from 'pinia'
import { clockNow } from '../utils/clock'
import { todayKey } from '../utils/date'

let timer = null
let started = false

function refresh(store) {
  store.now = clockNow()
  store.today = todayKey()
}

function onVisible(store) {
  if (document.visibilityState === 'visible') refresh(store)
}

// 全局响应式时钟：日期、到期提醒和跨天统计都依赖它，而不是只在页面创建时取一次时间。
export const useClockStore = defineStore('clock', {
  state: () => ({ now: clockNow(), today: todayKey() }),
  actions: {
    tick() {
      refresh(this)
    },
    start() {
      refresh(this)
      if (started) return
      started = true
      timer = setInterval(() => refresh(this), 15000)
      if (typeof document !== 'undefined') {
        document.addEventListener('visibilitychange', () => onVisible(this))
      }
      if (typeof window !== 'undefined') {
        window.addEventListener('focus', () => refresh(this))
      }
    },
    stop() {
      if (timer) clearInterval(timer)
      timer = null
      started = false
    },
  },
})
