<script setup>
import { watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import TabBar from './components/TabBar.vue'
import ToastLayer from './components/ToastLayer.vue'
import ConflictDialog from './components/ConflictDialog.vue'
import CommunityIssues from './components/CommunityIssues.vue'
import OfflineBanner from './components/OfflineBanner.vue'
import { useTimerStore } from './stores/timer'
import { useAppStore } from './stores/app'
import { useSubjectsStore } from './stores/subjects'
import { useAuthStore } from './stores/auth'
import { useTimerOwnership } from './composables/useTimerOwnership'
import SessionIssues from './components/SessionIssues.vue'
import { useGroupPresence } from './composables/useGroupPresence'
import { useNotificationsStore } from './stores/notifications'

const timer = useTimerStore()
const app = useAppStore()
const subjects = useSubjectsStore()
const route = useRoute()
const auth = useAuthStore()
const notifications = useNotificationsStore()
useGroupPresence()
useTimerOwnership()
watch(() => auth.user?.id, (id) => { if (id) notifications.start(); else notifications.stop() }, { immediate: true })
onBeforeUnmount(() => notifications.stop())

// 番茄完成提示音（Web Audio 合成，无需音频文件）
function playChime() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    const ctx = new Ctx()
    const notes = [523.25, 659.25, 783.99] // C5-E5-G5 上行音
    notes.forEach((f, i) => {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.value = f
      const t = ctx.currentTime + i * 0.18
      gain.gain.setValueAtTime(0, t)
      gain.gain.linearRampToValueAtTime(0.22, t + 0.03)
      gain.gain.exponentialRampToValueAtTime(0.001, t + 1.2)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start(t)
      osc.stop(t + 1.25)
    })
    setTimeout(() => ctx.close().catch(() => {}), 2000)
  } catch {
    /* 音频不可用时静默 */
  }
}

let lastHandled = 0
watch(
  () => timer.lastFinished?.at,
  (at) => {
    if (!at || at === lastHandled) return
    lastHandled = at
    const session = timer.lastFinished.session
    const subj = subjects.byId[session.subjectId]?.name || ''
    playChime()
    if (app.notifyEnabled && 'Notification' in window && Notification.permission === 'granted') {
      new Notification('研时 · 一次专注完成', {
        body: `${subj} ${Math.round(session.actualSec / 60)} 分钟，大雪深埋，静候春来。`,
      })
    }
  }
)
</script>

<template>
  <div class="app-shell">
    <div v-if="auth.user?.is_private_mode" class="privacy-banner">隐私模式已开启，小组内其他人看不到你的学习数据</div>
    <div v-if="timer.remoteLease && !timer.current" class="privacy-banner">另一设备正在主计时：{{timer.remoteLease.label||'专注中'}}，本机仅查看。</div>
    <div v-if="timer.leaseLost" class="privacy-banner">本机已失去主计时权限并暂停。<button @click="timer.abort()">结束本机记录并同步检查冲突</button></div>
    <SessionIssues />
    <OfflineBanner />
    <CommunityIssues />
    <main class="app-main" :class="{ 'no-tab': route.meta.hideTabbar }">
      <router-view />
    </main>
    <TabBar v-if="!route.meta.hideTabbar" />
    <ToastLayer />
    <ConflictDialog />
  </div>
</template>

<style>
.privacy-banner{position:sticky;top:0;z-index:220;background:#eee9f5;color:#67527d;font-size:12px;padding:7px 12px;text-align:center}
</style>
