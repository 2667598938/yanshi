<script setup>
import { useRoute } from 'vue-router'
import { Home, Timer, ListChecks, NotebookPen, BarChart3, Users, Sparkles,
  BookOpen, MessageSquare, GraduationCap, User, ShieldCheck, Mail } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { useNotificationsStore } from '../stores/notifications'
import { BRAND } from '../config/brand'
const route = useRoute()
const auth = useAuthStore()
const notifications = useNotificationsStore()
const groups = [
  { title: '学习工作台', links: [
    { to: '/', label: '今日', icon: Home },
    { to: '/focus', label: '专注计时', icon: Timer },
    { to: '/tasks', label: '任务计划', icon: ListChecks },
    { to: '/mistakes', label: '错题与复习', icon: NotebookPen },
    { to: '/stats', label: '学习统计', icon: BarChart3 },
    { to: '/ai', label: 'AI 助教', icon: Sparkles },
  ] },
  { title: '与研友同行', links: [
    { to: '/rooms', label: '自习室', icon: Users },
    { to: '/group', label: '小组学习', icon: Users },
    { to: '/resources', label: '资料库', icon: BookOpen },
    { to: '/posts', label: '研友动态', icon: MessageSquare },
    { to: '/dream-wall', label: '我的梦校', icon: GraduationCap },
  ] },
]
function active(to) {
  if (to === '/') return route.path === '/'
  if (to === '/rooms') return route.path === '/room' || route.path.startsWith('/rooms')
  if (to === '/mistakes') return route.path.startsWith('/mistake')
  return route.path === to || route.path.startsWith(to + '/')
}
</script>
<template>
  <aside class="desktop-nav" aria-label="电脑端导航">
    <router-link to="/" class="desktop-brand"><img class="brand-mark" :src="BRAND.iconSrc" alt="" /><span>研时<small>沉潜一日，功不唐捐</small></span></router-link>
    <nav aria-label="主要功能">
      <section v-for="group in groups" :key="group.title" class="desktop-nav-group">
        <div class="desktop-nav-caption">{{ group.title }}</div>
        <router-link v-for="link in group.links" :key="link.to" :to="link.to" class="desktop-link" :class="{ active: active(link.to) }" :aria-current="active(link.to) ? 'page' : undefined">
          <component :is="link.icon" :size="18" /><span>{{ link.label }}</span>
        </router-link>
      </section>
      <section class="desktop-nav-group">
        <div class="desktop-nav-caption">账号与设置</div>
        <router-link to="/messages" class="desktop-link" :class="{ active: active('/messages') }"><Mail :size="18" /><span>消息中心</span><span v-if="notifications.unread" class="desktop-count">{{ notifications.unread > 99 ? '99+' : notifications.unread }}</span></router-link>
        <router-link to="/me" class="desktop-link" :class="{ active: active('/me') }"><User :size="18" /><span>我的设置</span></router-link>
        <router-link v-if="auth.isAdmin" to="/admin" class="desktop-link" :class="{ active: active('/admin') }"><ShieldCheck :size="18" /><span>管理后台</span></router-link>
      </section>
    </nav>
  </aside>
</template>
