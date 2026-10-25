import { defineStore } from 'pinia'
import { authApi } from '../api'

const AUTH_KEY = 'yanshi:auth'

function load() {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    return raw ? JSON.parse(raw) : { accessToken: '', refreshToken: '', user: null }
  } catch {
    return { accessToken: '', refreshToken: '', user: null }
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: load().accessToken || '',
    refreshToken: load().refreshToken || '',
    user: load().user || null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.accessToken && !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
    isVip: (s) => !!s.user?.vip_until && new Date(s.user.vip_until) > new Date(),
  },
  actions: {
    persist() {
      localStorage.setItem(
        AUTH_KEY,
        JSON.stringify({
          accessToken: this.accessToken,
          refreshToken: this.refreshToken,
          user: this.user,
        })
      )
    },
    setSession({ access_token, refresh_token, user }) {
      this.accessToken = access_token
      this.refreshToken = refresh_token
      this.user = user
      this.persist()
    },
    setUser(user) {
      this.user = user
      this.persist()
    },
    async login(email, password) {
      const data = await authApi.login(email, password)
      this.setSession(data)
      return data
    },
    async emailLogin(payload) {
      const data = await authApi.emailLogin(payload)
      this.setSession(data)
      return data
    },
    async exchangeOAuth(ticket) {
      const data = await authApi.oauthExchange(ticket)
      this.setSession(data)
      return data
    },
    async phoneLogin(phone, code) {
      const data = await authApi.phoneVerify(phone, code)
      this.setSession(data)
      return data
    },
    async register(payload) {
      const data = await authApi.register(payload)
      this.setSession(data)
      return data
    },
    // 用 refresh_token 换新 access，成功返回 true
    async tryRefresh() {
      if (!this.refreshToken) return false
      try {
        const data = await authApi.refresh(this.refreshToken)
        this.accessToken = data.access_token
        if (data.refresh_token) this.refreshToken = data.refresh_token
        if (data.user) this.user = data.user
        this.persist()
        return true
      } catch {
        this.clear()
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
        if (this.accessToken) await authApi.logout()
      } catch {
        /* 忽略网络错误，本地照常登出 */
      }
      this.clear()
    },
    clear() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem(AUTH_KEY)
    },
  },
})
