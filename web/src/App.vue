<script setup>
import { watch } from 'vue'
import { useRoute } from 'vue-router'
import TabBar from './components/TabBar.vue'
import ToastLayer from './components/ToastLayer.vue'
import ConflictDialog from './components/ConflictDialog.vue'
import { useTimerStore } from './stores/timer'
import { useAppStore } from './stores/app'
import { useSubjectsStore } from './stores/subjects'

const timer = useTimerStore()
const app = useAppStore()
const subjects = useSubjectsStore()
const route = useRoute()

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
    <main class="app-main" :class="{ 'no-tab': route.meta.hideTabbar }">
      <router-view />
    </main>
    <TabBar v-if="!route.meta.hideTabbar" />
    <ToastLayer />
    <ConflictDialog />
  </div>
</template>
