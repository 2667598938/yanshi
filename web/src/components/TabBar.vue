<script setup>
import { useRoute } from 'vue-router'
import { Home, BarChart3, Users, User, Timer, Sparkles } from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'

const route = useRoute()
const timer = useTimerStore()

const tabs = [
  { to: '/', label: '今日', icon: Home },
  { to: '/stats', label: '统计', icon: BarChart3 },
  { to: '/focus', label: '专注', icon: Timer, focus: true },
  { to: '/room', label: '自习室', icon: Users },
  { to: '/ai', label: 'AI', icon: Sparkles },
  { to: '/me', label: '我的', icon: User },
]
</script>

<template>
  <nav class="tabbar">
    <router-link
      v-for="t in tabs"
      :key="t.to"
      :to="t.to"
      class="tab-item"
      :class="[t.focus ? 'tab-focus' : '', route.path === t.to ? 'is-active' : '']"
    >
      <span v-if="t.focus" class="tab-fab">
        <component :is="t.icon" :size="25" :stroke-width="2.4" />
        <span v-if="timer.isActive" class="run-dot"></span>
      </span>
      <template v-else>
        <component :is="t.icon" :size="21" :stroke-width="2.1" />
        <span>{{ t.label }}</span>
      </template>
    </router-link>
  </nav>
</template>

<style scoped>
.tab-item.is-active {
  color: var(--primary);
}
</style>
