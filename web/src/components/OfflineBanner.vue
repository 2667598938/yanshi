<script setup>
// 全局离线提示：首次断网提醒可用功能，联网后自动隐藏
import { ref, onMounted, onUnmounted } from 'vue'
import { WifiOff } from 'lucide-vue-next'
import { syncNow } from '../sync/engine'

const offline = ref(!navigator.onLine)

function onOffline() {
  offline.value = true
}
function onOnline() {
  offline.value = false
  syncNow()
}

onMounted(() => {
  window.addEventListener('offline', onOffline)
  window.addEventListener('online', onOnline)
})
onUnmounted(() => {
  window.removeEventListener('offline', onOffline)
  window.removeEventListener('online', onOnline)
})
</script>

<template>
  <div v-if="offline" class="offline-bar">
    <WifiOff :size="14" />
    离线中 · 番茄、错题、收藏可正常使用，联网后自动同步
  </div>
</template>

<style scoped>
.offline-bar {
  position: sticky;
  top: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: calc(6px + env(safe-area-inset-top)) 12px 6px;
  background: #3b3425;
  color: #f6e7c4;
  font-size: 12px;
  letter-spacing: 0.2px;
}
</style>
