import { defineStore } from 'pinia'
import { messageApi } from '../api'
import { useAuthStore } from './auth'

let interval = null
let visibilityHandler = null
export const useNotificationsStore = defineStore('notifications', {
  state: () => ({ unread: 0, sequence: 0 }),
  actions: {
    async refresh() {
      const sequence = ++this.sequence
      const auth = useAuthStore()
      const account = auth.user?.id
      if (!account) { this.unread = 0; return }
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      try {
        const data = await messageApi.unread()
        if (auth.user?.id === account && sequence === this.sequence) this.unread = data.count || 0
      } catch { /* 离线保留当前计数，下次恢复可见时刷新 */ }
    },
    start() {
      this.stop()
      this.refresh()
      interval = setInterval(() => this.refresh(), 60000)
      visibilityHandler = () => this.refresh()
      document.addEventListener('visibilitychange', visibilityHandler)
    },
    stop() {
      this.sequence += 1
      clearInterval(interval)
      interval = null
      if (visibilityHandler && typeof document !== 'undefined') document.removeEventListener('visibilitychange', visibilityHandler)
      visibilityHandler = null
      this.unread = 0
    },
  },
})
