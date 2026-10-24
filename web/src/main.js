import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './assets/styles/main.css'
import { initDb } from './db'
import { useAuthStore } from './stores/auth'
import { useTimerStore } from './stores/timer'
import { useSubjectsStore } from './stores/subjects'
import { useTasksStore } from './stores/tasks'
import { useMistakesStore } from './stores/mistakes'
import { initSyncForUser } from './sync/engine'

const app = createApp(App)
app.use(createPinia())
app.use(router)

const auth = useAuthStore()

// 先初始化本地库并载入数据，再挂载，避免首屏闪烁；之后恢复未结束的番茄
initDb()
  .then(async () => {
    // 已登录：校验/刷新账号信息并启动云同步（不阻塞本地数据加载）
    if (auth.isLoggedIn) {
      try {
        await auth.fetchMe()
        initSyncForUser()
      } catch {
        auth.clear()
      }
    }
    await Promise.all([
      useSubjectsStore().load(),
      useTimerStore().load(),
      useTasksStore().load(),
      useMistakesStore().load(),
    ])
    useTimerStore().resumeOnLoad()
    app.mount('#app')
  })
  .catch((e) => {
    console.error('本地数据初始化失败', e)
    app.mount('#app')
  })
