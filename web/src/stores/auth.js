import { defineStore } from 'pinia'
import { authApi } from '../api'
import { afterLogin, afterLogout } from '../sync/account'

// 只缓存非敏感的展示资料；access token 常驻内存，refresh token 在 httpOnly Cookie
const SESSION_KEY = 'yanshi:session'
const LEGACY_KEY = 'yanshi:auth'

function loadCachedUser() {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: '',
    user: loadCachedUser(),
  }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    canRefresh: (s) => !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
    isVip: (s) => !!s.user?.vip_until && new Date(s.user.vip_until) > new Date(),
  },
  actions: {
    persist() {
      if (this.user) localStorage.setItem(SESSION_KEY, JSON.stringify(this.user))
      else localStorage.removeItem(SESSION_KEY)
    },
    async acceptSession({ access_token, user }) {
      this.accessToken = access_token
      this.user = user
      this.persist()
      await afterLogin(user.id)
    },
    setUser(user) {
      this.user = user
      this.persist()
    },
    async login(email, password) {
      const data = await authApi.login(email, password)
      await this.acceptSession(data)
      return data
    },
    async emailLogin(payload) {
      const data = await authApi.emailLogin(payload)
      await this.acceptSession(data)
      return data
    },
    async exchangeOAuth(ticket) {
      const data = await authApi.oauthExchange(ticket)
      await this.acceptSession(data)
      return data
    },
    async phoneLogin(phone, code) {
      const data = await authApi.phoneVerify(phone, code)
      await this.acceptSession(data)
      return data
    },
    async register(payload) {
      const data = await authApi.register(payload)
      await this.acceptSession(data)
      return data
    },
    // 启动/刷新时用 httpOnly Cookie 恢复会话；离线时保留本地缓存资料
    async restore() {
      localStorage.removeItem(LEGACY_KEY) // 清理旧版本遗留的 token
      try {
        const data = await authApi.refresh()
        this.accessToken = data.access_token
        if (data.user) this.user = data.user
        this.persist()
        return true
      } catch {
        this.accessToken = ''
        return false
      }
    },
    // 用 refresh Cookie 换新 access，成功返回 true
    async tryRefresh() {
      if (!this.user) return false
      try {
        const data = await authApi.refresh()
        this.accessToken = data.access_token
        if (data.user) this.user = data.user
        this.persist()
        return true
      } catch (e) {
        // 网络不可用时保留登录态，等联网后重试；只有明确失效才登出
        if (e.status && e.status < 500) this.clear()
        return false
      }
    },
    async fetchMe() {
      const data = await authApi.me()
      this.setUser(data)
      return data
    },
    async logout() {
      try {
        await authApi.logout()
      } catch {
        /* 忽略网络错误，本地照常登出 */
      }
      this.clear()
      await afterLogout()
    },
    clear() {
      this.accessToken = ''
      this.user = null
      localStorage.removeItem(SESSION_KEY)
      localStorage.removeItem(LEGACY_KEY)
    },
  },
})
