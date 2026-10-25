import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './assets/styles/main.css'
import { useAuthStore } from './stores/auth'
import { useTimerStore } from './stores/timer'
import { afterLogin, afterLogout } from './sync/account'

const app = createApp(App)
app.use(createPinia())
app.use(router)

const auth = useAuthStore()

// 先用 refresh Cookie 恢复会话，再切换该账号的本地库并载入数据，最后挂载
async function boot() {
  await auth.restore().catch(() => {})
  if (auth.user) {
    await afterLogin(auth.user.id)
    try {
      await auth.fetchMe()
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
  useTimerStore().resumeOnLoad()
  app.mount('#app')
}

boot().catch((e) => {
  console.error('本地数据初始化失败', e)
  app.mount('#app')
})
