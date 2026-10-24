import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/HomeView.vue'), meta: { title: '今日' } },
  { path: '/stats', name: 'stats', component: () => import('../views/StatsView.vue'), meta: { title: '统计' } },
  { path: '/focus', name: 'focus', component: () => import('../views/FocusView.vue'), meta: { title: '专注' } },
  { path: '/room', name: 'room', component: () => import('../views/RoomView.vue'), meta: { title: '自习室', requiresAuth: true } },
  { path: '/ai', name: 'ai', component: () => import('../views/AiView.vue'), meta: { title: 'AI', requiresAuth: true } },
  { path: '/me', name: 'me', component: () => import('../views/MeView.vue'), meta: { title: '我的', requiresAuth: true } },

  // 登录 / 注册 / 找回（无底部导航）
  { path: '/login', name: 'login', component: () => import('../views/auth/AuthView.vue'), meta: { title: '登录', hideTabbar: true } },
  // 后台管理（仅管理员，页面内二次校验）
  { path: '/admin', name: 'admin', component: () => import('../views/AdminView.vue'), meta: { title: '后台管理', requiresAuth: true, hideTabbar: true } },

  // 二级页（隐藏底部导航）
  { path: '/tasks', name: 'tasks', component: () => import('../views/TasksView.vue'), meta: { title: '任务计划', hideTabbar: true } },
  { path: '/mistakes', name: 'mistakes', component: () => import('../views/MistakesView.vue'), meta: { title: '错题本', hideTabbar: true } },
  { path: '/mistake/edit', name: 'mistake-edit', component: () => import('../views/MistakeEditView.vue'), meta: { title: '记一道错题', hideTabbar: true } },
  { path: '/subjects', name: 'subjects', component: () => import('../views/SubjectManageView.vue'), meta: { title: '科目管理', hideTabbar: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

// 云功能（自习室/AI/我的）需要登录；核心学习页可离线
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
