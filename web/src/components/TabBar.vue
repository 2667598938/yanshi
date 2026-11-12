<script setup>
import { useRoute } from 'vue-router';
import { Home, BarChart3, Users, User, Timer, Sparkles } from 'lucide-vue-next';
import { useTimerStore } from '../stores/timer';
import { useNotificationsStore } from '../stores/notifications';

const route = useRoute();
const timer = useTimerStore();
const notifications = useNotificationsStore();

const tabs = [
  { to: '/', label: '今日', icon: Home },
  { to: '/stats', label: '统计', icon: BarChart3 },
  { to: '/rooms', label: '自习室', icon: Users },
  { to: '/ai', label: 'AI', icon: Sparkles },
  { to: '/me', label: '我的', icon: User },
];

function isActive(t) {
  if (t.to === '/') return route.path === '/';
  return route.path === t.to || route.path.startsWith(t.to + '/');
}
</script>

<template>
  <nav class="tabbar">
    <router-link
      v-for="t in tabs"
      :key="t.to"
      :to="t.to"
      class="tab-item"
      :class="{ 'is-active': isActive(t) }"
    >
      <component :is="t.icon" :size="21" :stroke-width="2.1" />
      <span>{{ t.label }}</span>
      <span v-if="t.to === '/me' && notifications.unread" class="notification-count">{{
        notifications.unread > 99 ? '99+' : notifications.unread
      }}</span>
    </router-link>
  </nav>
</template>

<style scoped>
.tab-item {
  position: relative;
}
.notification-count {
  position: absolute;
  top: 3px;
  right: 12%;
  background: var(--tomato);
  color: #fff;
  border-radius: 12px;
  font-size: 12px;
  padding: 1px 5px;
}
.tab-item.is-active {
  color: var(--primary);
}
</style>
