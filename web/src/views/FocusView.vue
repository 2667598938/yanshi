<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  Pause, Play, Bell, BellOff, Check, X, Minus, Plus,
  Settings2, NotebookPen, Timer, Hourglass,
  Headphones, PenLine, RotateCcw, BookMarked,
} from 'lucide-vue-next'
import FocusRing from '../components/FocusRing.vue'
import SubjectIcon from '../components/SubjectIcon.vue'
import { useTimerStore } from '../stores/timer'
import { useAppStore } from '../stores/app'
import { useSubjectsStore } from '../stores/subjects'
import { useLearningSettingsStore } from '../stores/learningSettings'
import { useNotificationPreference } from '../composables/useNotificationPreference'
import { useTasksStore } from '../stores/tasks'
import {
  DURATIONS, MIN_DURATION, MAX_DURATION, ACTIVITIES,
} from '../data/subjects'
import { fmtClock } from '../utils/date'
import { useToast } from '../composables/useToast'

const timer = useTimerStore()
const app = useAppStore()
const subjects = useSubjectsStore()
const { toast } = useToast()
const router = useRouter()
const route = useRoute()
const settings = useLearningSettingsStore()
const { toggle: toggleNotify, busy: notifyBusy } = useNotificationPreference()
const tasks = useTasksStore()
const linkedTask = computed(() => tasks.list.find(t=>t.id===(timer.current?.taskId || route.query.taskId || timer.lastFinished?.session?.taskId)))
const completingTask = ref(false)
async function completeLinkedTask(){
  if(!linkedTask.value || linkedTask.value.done || completingTask.value)return
  completingTask.value=true
  try{await tasks.toggle(linkedTask.value.id);toast('任务已标记完成')}
  catch(e){toast(e.message || '任务状态未保存')}
  finally{completingTask.value=false}
}
const learningContent = ref(timer.current?.learningContent || String(route.query.content || ''))

const ACT_ICONS = { Headphones, PenLine, RotateCcw, BookMarked }

// idle 配置
const mode = ref(timer.current?.mode || 'timer')
const subjId = ref(timer.current?.subjectId || String(route.query.subjectId || ''))
const activity = ref(timer.current?.activityType || '')
const plan = ref(timer.current?.mode === 'timer' ? timer.current.plannedMin || settings.value.focusMin : settings.value.focusMin)
const customOpen = ref(false)
const customVal = ref(40)

const sheet = ref(false) // false | 'confirm' | 'done'
const note = ref('')
const finished = ref(null)

const phase = computed(() =>
  timer.rest ? (timer.rest.finished ? 'restReady' : 'resting') : !timer.current ? 'idle' : timer.isPaused ? 'paused' : 'focusing'
)
const currentSubject = computed(
  () =>
    subjects.byId[timer.current?.subjectId || subjId.value] ||
    subjects.active[0]
)
const currentActivity = computed(() =>
  ACTIVITIES.find((a) => a.id === (timer.current?.activityType ?? activity.value))
)
const isStopwatch = computed(() =>
  phase.value === 'idle' ? mode.value === 'stopwatch' : timer.current?.mode === 'stopwatch'
)
const ringColor = computed(() => {
  if (timer.rest) return '#10b981'
  if (phase.value === 'paused') return '#94a3b8'
  return isStopwatch.value ? '#6366f1' : '#8b5cf6'
})
const ringStart = computed(() => (isStopwatch.value ? '#a5b4fc' : '#c4b5fd'))
const ringProgress = computed(() => {
  if (timer.rest) return 1 - timer.restRemainingSec / timer.rest.plannedSec
  if (phase.value === 'idle') return 0
  if (timer.current?.mode === 'stopwatch') return (timer.elapsedSec % 60) / 60
  return timer.progress
})
const displayTime = computed(() => {
  if (timer.rest) return fmtClock(timer.restRemainingSec)
  if (phase.value === 'idle')
    return isStopwatch.value ? '00:00' : fmtClock(plan.value * 60)
  if (timer.current?.mode === 'stopwatch') return fmtClock(timer.elapsedSec)
  return fmtClock(timer.remainingSec)
})
const phaseText = computed(
  () => ({ idle: '准备开始', focusing: '专注中', paused: '已暂停',
    resting: timer.rest?.kind === 'long' ? '长休息' : '短休息', restReady: '休息结束，等待手动开始' }[phase.value])
)

async function start() {
  if (!subjects.active.length) {
    toast('请先添加一个科目')
    return
  }
  const subjectId = subjId.value || subjects.active[0].id
  const started = await timer.start({
    subjectId,
    mode: mode.value,
    plannedMin: plan.value,
    activityType: activity.value,
    learningContent: learningContent.value,
    taskId: route.query.taskId || null,
  })
  if(!started){if(timer.startError)toast(timer.startError);return}
  toast(mode.value === 'stopwatch' ? '开始正向计时，大雪深埋' : '开始专注，大雪深埋')
}
function toggle() {
  if (timer.leaseLost) { toast('本机已失去主计时权限，请结束本机记录后重新开始'); return }
  if (timer.isPaused) timer.resume()
  else timer.pause()
}
function openConfirm() {
  note.value = ''
  sheet.value = 'confirm'
}
async function record() {
  const s = await timer.finish(false, note.value)
  finished.value = s
  sheet.value = 'done'
  toast('已记录这次专注')
}
async function giveup() {
  const s = await timer.abort()
  sheet.value = false
  if (s && s.actualSec > 0) {
    toast(`已放弃，保留实际专注 ${Math.max(1, Math.round(s.actualSec / 60))} 分钟`)
  } else {
    toast('已放弃')
  }
}
function goMistake() {
  const s = finished.value
  sheet.value = false
  router.push({
    path: '/mistake/edit',
    query: {
      subjectId: s?.subjectId || '',
      sessionId: s?.id || '',
      date: s?.date || '',
    },
  })
}
function stepCustom(d) {
  let v = (Number(customVal.value) || 25) + d
  v = Math.min(MAX_DURATION, Math.max(MIN_DURATION, Math.round(v)))
  customVal.value = v
  plan.value = v
}
function applyCustom() {
  let v = Number(customVal.value)
  if (!Number.isFinite(v)) v = 25
  v = Math.min(MAX_DURATION, Math.max(MIN_DURATION, Math.round(v)))
  customVal.value = v
  plan.value = v
  customOpen.value = false
}

let lastAt = 0
watch(
  () => timer.lastFinished?.at,
  (at) => {
    if (!at || at === lastAt) return
    lastAt = at
    if (timer.lastFinished.auto) toast('一颗番茄完成，休息一下吧')
  }
)
</script>

<template>
  <div>
    <div class="nav">
      <div>
        <div class="nav-title">专注</div>
        <div class="nav-sub">沉潜一刻，静水流深</div>
      </div>
      <button class="notify-btn" :disabled="notifyBusy" :aria-pressed="app.notifyEnabled" aria-label="到点浏览器通知" @click="toggleNotify">
        <component :is="app.notifyEnabled ? Bell : BellOff" :size="18" :stroke-width="2.2" />
      </button>
      <button class="notify-btn" aria-label="专注与休息设置" @click="router.push('/settings/learning')"><Settings2 :size="18" /></button>
    </div>

    <div class="page focus-page">
      <!-- 计时环 -->
      <div class="focus-hero" :class="{ sw: isStopwatch && phase !== 'idle' }">
        <FocusRing
          :progress="ringProgress"
          :color="ringColor"
          :start-color="ringStart"
          :size="264"
        >
          <div class="clock tnum">{{ displayTime }}</div>
          <div class="clock-phase">
            <span class="phase-dot" :style="{ background: currentSubject?.color }"></span>
            {{ currentSubject?.name }}<template v-if="currentActivity"> · {{ currentActivity.name }}</template>
            · {{ phaseText }}
          </div>
        </FocusRing>

        <div v-if="timer.rest" class="active-controls">
          <button v-if="timer.rest.finished" class="ctl-main" @click="timer.startNext()"><Play :size="20" />开始下一个番茄</button>
          <button class="ctl-end" @click="timer.endRest()">{{ timer.rest.finished ? '返回设置' : '跳过休息' }}</button>
        </div>
        <template v-else-if="phase !== 'idle'">
          <div class="active-controls">
            <button class="ctl-main" :disabled="timer.leaseLost" @click="toggle">
              <component :is="timer.isPaused ? Play : Pause" :size="22" :stroke-width="2.4" />
              <span>{{ timer.leaseLost ? '主计时权限已失效' : timer.isPaused ? '继续' : '暂停' }}</span>
            </button>
            <button class="ctl-end" @click="openConfirm">结束</button>
          </div>
        </template>
      </div>

      <section class="focus-configuration" aria-label="专注配置与状态">
      <div v-if="linkedTask" class="card task-focus-result">
        <strong>关联任务：{{linkedTask.title}}</strong>
        <p>已投入 {{Math.round((timer.taskSeconds?.[linkedTask.id]||0)/60)}} 分钟 · 预估 {{linkedTask.estimatedMin||0}} 分钟</p>
        <p v-if="linkedTask.acceptCriteria">做完的标准：{{linkedTask.acceptCriteria}}</p>
        <button v-if="!timer.current && timer.lastFinished?.session?.taskId===linkedTask.id && !linkedTask.done" class="btn btn-primary" :disabled="completingTask" @click="completeLinkedTask">已达到标准，标记任务完成</button>
        <p v-else-if="linkedTask.done">此任务已完成。继续学习可选择新的任务。</p>
        <p v-else>计时结束不会自动完成任务，请按实际成果确认。</p>
      </div>
      <!-- idle 配置 -->
      <template v-if="phase === 'idle'">
        <!-- 模式切换 -->
        <div class="mode-switch">
          <button
            class="mode-btn"
            :class="{ active: mode === 'timer' }"
            @click="mode = 'timer'"
          >
            <Hourglass :size="16" />
            <span>倒计时</span>
            <small>到点自动结束</small>
          </button>
          <button
            class="mode-btn"
            :class="{ active: mode === 'stopwatch' }"
            @click="mode = 'stopwatch'"
          >
            <Timer :size="16" />
            <span>正向计时</span>
            <small>最多180分钟，手动结束</small>
          </button>
        </div>

        <!-- 科目 -->
        <div class="card">
          <div class="cfg-head">
            <div class="cfg-label">选择科目</div>
            <button class="cfg-manage" @click="router.push('/subjects')">
              <Settings2 :size="13" />管理
            </button>
          </div>
          <div class="pill-row">
            <button
              v-for="s in subjects.active"
              :key="s.id"
              class="pill"
              :class="{ active: (subjId || subjects.active[0]?.id) === s.id }"
              :style="(subjId || subjects.active[0]?.id) === s.id ? { background: s.color } : {}"
              @click="subjId = s.id"
            >
              <SubjectIcon :name="s.icon" :size="15" />
              <span>{{ s.name }}</span>
            </button>
          </div>
        </div>

        <!-- 学习类型 -->
        <div class="card">
          <div class="cfg-label">这次在做什么</div>
          <div class="pill-row">
            <button
              v-for="a in ACTIVITIES"
              :key="a.id"
              class="pill"
              :class="{ active: activity === a.id }"
              :style="activity === a.id ? { background: a.color } : {}"
              @click="activity = activity === a.id ? '' : a.id"
            >
              <component :is="ACT_ICONS[a.icon]" :size="14" />
              <span>{{ a.name }}</span>
            </button>
          </div>
        </div>

        <!-- 倒计时时长（正向计时不显示） -->
        <div class="card">
          <label class="cfg-label" for="learning-content">自由学习内容</label>
          <input id="learning-content" v-model="learningContent" class="input" maxlength="100" list="learning-history" placeholder="如：高数第三章课后题，可选择历史内容" />
          <datalist id="learning-history"><option v-for="item in timer.contentHistory" :key="item" :value="item" /></datalist>
        </div>
        <div v-if="mode === 'timer'" class="card">
          <div class="cfg-label">专注时长（分钟）</div>
          <div class="pill-row">
            <button
              v-for="d in DURATIONS"
              :key="d"
              class="pill"
              :class="{ active: !customOpen && plan === d }"
              :style="!customOpen && plan === d ? { background: 'var(--primary)' } : {}"
              @click="customOpen = false; plan = d"
            >
              {{ d }}
            </button>
            <button
              class="pill"
              :class="{ active: customOpen }"
              :style="customOpen ? { background: 'var(--primary)' } : {}"
              @click="customOpen = true; customVal = plan"
            >
              自定义
            </button>
          </div>
          <div v-if="customOpen" class="custom-box">
            <button class="step-btn" @click="stepCustom(-5)"><Minus :size="16" /></button>
            <input
              v-model.number="customVal"
              class="custom-input tnum"
              type="number"
              :min="MIN_DURATION"
              :max="MAX_DURATION"
              @keyup.enter="applyCustom"
            />
            <button class="step-btn" @click="stepCustom(5)"><Plus :size="16" /></button>
            <button class="btn btn-primary btn-sm" @click="applyCustom">
              <Check :size="15" />确定
            </button>
          </div>
          <div class="range-hint">可设 {{ MIN_DURATION }}–{{ MAX_DURATION }} 分钟</div>
        </div>

        <button
          class="btn btn-block start-btn"
            :disabled="timer.claiming || !!timer.remoteLease"
          :class="mode === 'stopwatch' ? 'btn-primary' : 'btn-tomato'"
          @click="start"
        >
          <Play :size="20" :stroke-width="2.6" />
          <span>{{ timer.claiming ? '正在获取主计时权限…' : timer.remoteLease ? '主计时设备正在运行，本机仅查看' : mode === 'stopwatch' ? '开始正向计时' : `开始 ${plan} 分钟专注` }}</span>
        </button>
      </template>

      <!-- 专注中的提示 -->
      <div v-else class="focus-tip">
        <span v-if="phase === 'focusing'">
          {{ isStopwatch ? '正向计时中，沉下心，慢慢啃。' : '保持专注，手机放下，世界与你无关。' }}
        </span>
        <span v-else>已暂停，随时继续。</span>
      </div>
      </section>
    </div>

    <!-- 结束确认 -->
    <div v-if="sheet" class="mask" @click.self="sheet = false">
      <div class="sheet">
        <!-- 记录前 -->
        <template v-if="sheet === 'confirm'">
          <div class="sheet-title">结束这次专注？</div>
          <div class="sheet-sub">
            你已专注 <b class="tnum">{{ Math.floor(timer.elapsedSec / 60) }} 分 {{ timer.elapsedSec % 60 }} 秒</b>
          </div>
          <textarea
            v-model="note"
            class="note-input"
            rows="2"
            placeholder="备注：做了哪套真题 / 哪一章（可选）"
          ></textarea>
          <button class="btn btn-tomato btn-block mt12" @click="record">
            <Check :size="18" />记录并结束（按实际时长）
          </button>
          <button class="btn btn-danger btn-block mt8" @click="giveup">
              <X :size="18" />放弃（保留已专注时长）
          </button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = false">继续专注</button>
        </template>

        <!-- 记录后 -->
        <template v-else>
          <div class="done-ic"><Check :size="30" :stroke-width="3" /></div>
          <div class="sheet-title">已记录</div>
          <div class="sheet-sub">
            实际专注 <b class="tnum">{{ Math.floor((finished?.actualSec || 0) / 60) }} 分 {{ (finished?.actualSec || 0) % 60 }} 秒</b>
          </div>
          <button class="btn btn-primary btn-block" @click="goMistake">
            <NotebookPen :size="18" />顺手记一道错题
          </button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = false">完成</button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.focus-page {
  padding-top: 4px;
}
.notify-btn {
  margin-left: auto;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--sub);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.focus-hero {
  background: linear-gradient(160deg, #4c1d95 0%, #312e81 55%, #1e1b4b 100%);
  border-radius: 26px;
  padding: 26px 18px 22px;
  box-shadow: 0 16px 34px rgba(22, 27, 46, 0.3);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.focus-hero.sw {
  background: linear-gradient(160deg, #4338ca 0%, #312e81 55%, #1e1b4b 100%);
}
.clock {
  font-size: 56px;
  font-weight: 800;
  color: #fff;
  letter-spacing: 1px;
  line-height: 1.1;
}
.clock-phase {
  margin-top: 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.72);
  display: flex;
  align-items: center;
  gap: 6px;
  text-align: center;
}
.phase-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
}
.active-controls {
  display: flex;
  gap: 14px;
  margin-top: 24px;
  width: 100%;
  padding: 0 10px;
}
.ctl-main {
  flex: 1;
  border: none;
  border-radius: 15px;
  padding: 14px;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  background: var(--primary-grad);
  box-shadow: 0 8px 20px rgba(79, 70, 229, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}
.ctl-end {
  width: 104px;
  border: 1.5px solid rgba(255, 255, 255, 0.3);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
}

/* 模式切换 */
.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}
.mode-btn {
  border: 1.5px solid var(--line);
  background: #fff;
  border-radius: 16px;
  padding: 13px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  color: var(--sub);
  cursor: pointer;
  transition: all 0.15s ease;
}
.mode-btn span {
  font-size: 14px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.mode-btn small {
  font-size: 12px;
  color: var(--faint);
  font-weight: 500;
}
.mode-btn.active {
  border-color: var(--primary);
  background: #eef5fd;
  color: var(--primary-deep);
}

.cfg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.cfg-label {
  font-size: 14px;
  font-weight: 700;
}
.cfg-manage {
  border: none;
  background: none;
  color: var(--faint);
  font-size: 14px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
}
.pill {
  padding: 9px 15px;
}
.custom-box {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}
.step-btn {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--sub);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.custom-input {
  flex: 1;
  min-width: 0;
  text-align: center;
  font-size: 16px;
  font-weight: 700;
}
.range-hint {
  margin-top: 10px;
  font-size: 14px;
  color: var(--faint);
}
.start-btn {
  margin-top: 14px;
  font-size: 16px;
  padding: 16px;
}
.focus-tip {
  text-align: center;
  color: var(--faint);
  font-size: 14px;
  margin-top: 18px;
}

.note-input {
  width: 100%;
  border: 1.5px solid var(--line);
  border-radius: 12px;
  padding: 11px 14px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  background: #f8fafc;
}
.note-input:focus {
  border-color: var(--primary);
}
.done-ic {
  width: 58px;
  height: 58px;
  margin: 4px auto 10px;
  border-radius: 50%;
  background: #e6f7ef;
  color: var(--green);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 底部弹层 */
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 150;
  animation: fade 0.15s ease;
}
@keyframes fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
.sheet {
  width: 100%;
  max-width: 520px;
  background: #fff;
  border-radius: 22px 22px 0 0;
  padding: 22px 18px calc(22px + env(safe-area-inset-bottom));
  animation: up 0.2s ease;
}
@keyframes up {
  from { transform: translateY(40px); }
  to { transform: translateY(0); }
}
.sheet-title {
  font-size: 16px;
  font-weight: 800;
  text-align: center;
}
.sheet-sub {
  text-align: center;
  color: var(--sub);
  font-size: 14px;
  margin: 8px 0 14px;
}
</style>
