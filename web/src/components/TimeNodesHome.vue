<script setup>
import { onMounted, computed } from 'vue';
import { useTimeNodesStore } from '../stores/timeNodes';
import { useAuthStore } from '../stores/auth';
import { randomQuote } from '../data/quotes';
import { useClockStore } from '../stores/clock';
import { diffDayKeys } from '../utils/date';
const nodes = useTimeNodesStore();
const auth = useAuthStore();
const clock = useClockStore();
const quote = randomQuote();
onMounted(() => nodes.load(true));
const shown = computed(() => nodes.list.filter((row) => row.value.show_on_home));
function distance(day) {
  return diffDayKeys(clock.today, day);
}
</script>
<template>
  <div class="time-nodes">
    <div v-for="row in shown" :key="row.id" class="time-node">
      <div>{{ row.value.node_name }} · {{ row.value.target_date }}</div>
      <strong
        >{{ distance(row.value.target_date) < 0 ? '已过去' : '还有' }}
        {{ Math.abs(distance(row.value.target_date)) }} 天</strong
      >
      <p>{{ row.value.custom_msg || quote }}</p>
    </div>
    <p v-if="!shown.length">还没有展示的时间节点，可在“我的 → 时间节点管理”添加。</p>
    <p v-if="auth.user?.custom_motto" class="motto">{{ auth.user.custom_motto }}</p>
    <router-link to="/settings/time-nodes">管理我的倒计时与寄语</router-link>
  </div>
</template>
<style scoped>
/* 首屏紧凑：压低倒计时区高度，让今日数据更早出现 */
.time-nodes {
  margin: 16px 0;
  padding: 16px;
  background: var(--card, #fff);
  border: 1px solid var(--line);
  border-radius: 18px;
  color: var(--ink);
}
.time-node {
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}
strong {
  font-size: 20px;
  display: block;
  margin-top: 4px;
  line-height: 1.2;
}
p {
  font-size: 14px;
  line-height: 1.6;
  margin: 4px 0;
  white-space: pre-wrap;
  color: var(--sub);
}
a {
  color: inherit;
  font-size: 14px;
  opacity: 0.78;
}
.motto {
  border-left: 2px solid var(--primary);
  padding-left: 8px;
}
</style>
