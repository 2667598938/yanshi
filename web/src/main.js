import { createApp, h, reactive } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './assets/styles/main.css'
import './assets/styles/responsive.css'
import './assets/styles/tokens.css'
import 'katex/dist/katex.min.css'
import { useAuthStore } from './stores/auth'
import { useTimerStore } from './stores/timer'
import { afterLogin, afterLogout } from './sync/account'
import { useProfileStore } from './stores/profile'
import BrandOpening from './components/BrandOpening.vue'
import { BRAND, brandColorVars } from './config/brand'
import { claimBrandOpening } from './utils/openingPolicy'
import { publicApi } from './api'
import { requestPersistentStorage } from './db/imageCache'

const app = createApp(App)
app.use(createPinia())

const auth = useAuthStore()
window.addEventListener('online', () => { void auth.retryPendingLogout() })
for (const [key, value] of Object.entries(brandColorVars())) document.documentElement.style.setProperty(key, value)
const openingState = reactive({ siteName: BRAND.name })
let openingApp = null
// 只在本地开发允许显式回放；生产与正常访问始终遵守session策略。
const previewOpening = import.meta.env.DEV && new URLSearchParams(location.search).get('preview_intro') === '1'
if (previewOpening || claimBrandOpening(BRAND.opening)) {
  // 独立的轻量覆盖层先播放，账号恢复、路由和业务数据在下面同时准备。
  openingApp = createApp({ render: () => h(BrandOpening, { siteName: openingState.siteName,
    onDone: () => queueMicrotask(() => { openingApp?.unmount(); openingApp = null }) }) })
  openingApp.mount('#brand-opening')
}
publicApi.config().then(config => {
  if (config.site_name?.trim()) {
    openingState.siteName = config.site_name.trim()
    document.title = `${config.site_name.trim()} · 考研学习平台`
  }
}).catch(() => {})
let routerInstalled = false
async function mountApplication() {
  // 首次导航必须等账号恢复结束，避免旧缓存或有效Cookie被错误分流。
  if (!routerInstalled) { app.use(router); routerInstalled = true }
  await router.isReady()
  app.mount('#app')
}

// 先用 refresh Cookie 恢复会话，再切换该账号的本地库并载入数据，最后挂载
async function boot() {
  await auth.restore().catch(() => {})
  if (auth.user) {
    await afterLogin(auth.user.id)
    try {
      await auth.fetchMe()
      if (!auth.isSuperAdmin) await useProfileStore().load(true)
    } catch (e) {
      // access 确实失效：清理登录态；纯离线/网络错误则保留缓存用户
      if (e.status && e.status < 500) {
        auth.clear()
        await afterLogout()
      }
    }
  } else {
    await afterLogout()
  }
  if (!auth.isSuperAdmin) useTimerStore().resumeOnLoad()
  void requestPersistentStorage()
  await mountApplication()
}

boot().catch(async (e) => {
  console.error('本地数据初始化失败', e)
  auth.clear()
  void requestPersistentStorage()
  await mountApplication()
})

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch((error) => {
      console.warn('离线页面缓存暂不可用', error)
    })
  })
}
