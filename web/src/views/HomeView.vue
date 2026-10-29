<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Flame,
  Timer as TimerIcon,
  Clock3,
  Play,
  BarChart3,
  Users,
  ChevronRight,
  Snowflake,
  Check,
  ListChecks,
  NotebookPen,
  AlarmClock,
  Plus,
  BookOpen,
  MessageSquare,
} from 'lucide-vue-next'
import SubjectIcon from '../components/SubjectIcon.vue'
import SchoolHero from '../components/SchoolHero.vue'
import TimeNodesHome from '../components/TimeNodesHome.vue'
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
import { useTasksStore } from '../stores/tasks'
import { useMistakesStore } from '../stores/mistakes'
import { useAppStore } from '../stores/app'
import { useClockStore } from '../stores/clock'
import { fmtMinutes, fmtClock, mdLabel, weekLabel } from '../utils/date'

const router = useRouter()
const timer = useTimerStore()
const subjects = useSubjectsStore()
const tasks = useTasksStore()
const mistakes = useMistakesStore()
const app = useAppStore()
const clock = useClockStore()

const today = computed(() => {
  const d = new Date(clock.now)
  return `${mdLabel(clock.today)} ${weekLabel(d)}`
})

const goalPercent = computed(() =>
  Math.min(100, Math.round((timer.todayMin / app.dailyGoalMin) * 100))
)

const todayBySubj = computed(() => {
  const m = {}
  timer.todaySessions.forEach((x) => {
    m[x.subjectId] = (m[x.subjectId] || 0) + x.actualSec / 60
  })
  return Object.entries(m)
    .map(([id, min]) => ({ subj: subjects.byId[id], min: Math.round(min) }))
    .filter((x) => x.subj && x.min > 0)
    .sort((a, b) => b.min - a.min)
})
const maxSubjMin = computed(() => todayBySubj.value.reduce((a, x) => Math.max(a, x.min), 0))

const todayTasks = computed(() => {
  const all = tasks.todayAll
  return [...all].sort((a, b) => a.done - b.done).slice(0, 4)
})
const dueMistakes = computed(() => mistakes.dueReview)

const encourage = computed(() => {
  if (timer.todayMin <= 0) return '今天还没有开始，埋下第一颗种子吧。'
  if (goalPercent.value < 50) return '大雪深埋，你正在悄悄扎根。'
  if (goalPercent.value < 100) return '保持节奏，今天的目标近在眼前。'
  return '今日目标已达成，你比昨天更接近梦校。'
})
</script>

<template>
  <div class="home-layout" :class="{ 'hero-collapsed': app.heroCollapsed }">
    <SchoolHero v-if="!app.heroCollapsed" />

    <div class="page">
      <div class="hello">
        <div>
          <div class="hello-date">{{ today }}</div>
          <div class="hello-name">{{ app.nickname }}，沉潜一日，功不唐捐</div>
        </div>
        <button class="hero-toggle" :aria-expanded="!app.heroCollapsed" @click="app.setHeroCollapsed(!app.heroCollapsed)">
          {{ app.heroCollapsed ? '展开梦校' : '收起梦校' }}
        </button>
      </div>

      <!-- 错题复习提醒 -->
      <TimeNodesHome />
      <button v-if="dueMistakes.length" class="review-banner" @click="router.push('/mistakes')">
        <AlarmClock :size="18" />
        <span class="rb-txt">{{ dueMistakes.length }} 道错题今天该复习</span>
        <ChevronRight :size="18" />
      </button>

      <!-- 今日数据 -->
      <div class="card stat-card">
        <div class="stat-grid">
          <div class="stat-item">
            <div class="stat-ic c1"><Clock3 :size="16" /></div>
            <div class="stat-num tnum">{{ fmtMinutes(timer.todayMin) }}</div>
            <div class="stat-label">今日时长</div>
          </div>
          <div class="stat-item">
            <div class="stat-ic c2"><TimerIcon :size="16" /></div>
            <div class="stat-num tnum">{{ timer.todayCount }}</div>
            <div class="stat-label">今日专注</div>
          </div>
          <div class="stat-item">
            <div class="stat-ic c3"><Flame :size="16" /></div>
            <div class="stat-num tnum">{{ timer.streak }}<span class="unit">天</span></div>
            <div class="stat-label">连续打卡</div>
          </div>
        </div>
        <div class="goal">
          <div class="goal-top">
            <span>今日目标</span>
            <span class="tnum">{{ fmtMinutes(timer.todayMin) }} / {{ fmtMinutes(app.dailyGoalMin) }}</span>
          </div>
          <div class="goal-bar">
            <div class="goal-fill" :style="{ width: goalPercent + '%' }"></div>
          </div>
        </div>
      </div>

      <!-- 开始专注 -->
      <button
        class="btn btn-tomato btn-block big-focus"
        @click="router.push('/focus')"
      >
        <component :is="timer.isActive ? TimerIcon : Play" :size="20" :stroke-width="2.4" />
        <span v-if="timer.isResting">{{ timer.rest?.finished ? '休息结束 · 开始下一次' : `休息中 · 剩余 ${fmtClock(timer.restRemainingSec)}` }}</span>
        <span v-else-if="timer.isActive && timer.isStopwatch">
          正向计时 · 已学 {{ fmtClock(timer.elapsedSec) }}
        </span>
        <span v-else-if="timer.isActive">
          专注中 · 剩余 {{ fmtClock(timer.remainingSec) }}
        </span>
        <span v-else>开始一次专注</span>
      </button>

      <!-- 今日任务 -->
      <div class="card">
        <div class="mini-title">
          今日任务
          <span class="more" @click="router.push('/tasks')">全部 ›</span>
        </div>
        <div v-if="!tasks.todayAll.length" class="mini-empty">
          今天还没有任务，定一个有验收标准的小目标
        </div>
        <div
          v-for="t in todayTasks"
          :key="t.id"
          class="mini-task"
          @click="router.push('/tasks')"
        >
          <button class="mini-check" :class="{ on: t.done }" @click.stop="tasks.toggle(t.id)">
            <Check :size="13" :stroke-width="3" />
          </button>
          <span class="mini-task-name" :class="{ done: t.done }">{{ t.title }}</span>
        </div>
        <button class="add-task" @click="router.push('/tasks')">
          <Plus :size="14" />添加任务
        </button>
      </div>

      <!-- 今日科目分布 -->
      <div v-if="todayBySubj.length" class="card">
        <div class="mini-title">今日科目分布</div>
        <div v-for="s in todayBySubj" :key="s.subj.id" class="subj-row">
          <span class="subj-name" :style="{ color: s.subj.color }">
            <SubjectIcon :name="s.subj.icon" :size="13" />
            {{ s.subj.name }}
          </span>
          <div class="subj-track">
            <div
              class="subj-fill"
              :style="{ width: (s.min / maxSubjMin) * 100 + '%', background: s.subj.color }"
            ></div>
          </div>
          <span class="subj-min tnum">{{ fmtMinutes(s.min) }}</span>
        </div>
      </div>

      <!-- 快捷入口 -->
      <div class="quick-grid">
        <router-link to="/tasks" class="quick-card">
          <div class="quick-ic q1"><ListChecks :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">任务清单</div>
            <div class="quick-sub">计划 · 验收</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/mistakes" class="quick-card">
          <div class="quick-ic q3"><NotebookPen :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">错题本</div>
            <div class="quick-sub">艾宾浩斯复习</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/stats" class="quick-card">
          <div class="quick-ic q4"><BarChart3 :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">数据仪表盘</div>
            <div class="quick-sub">热力图 · 趋势</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/rooms" class="quick-card">
          <div class="quick-ic q2"><Users :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">好友自习室</div>
            <div class="quick-sub">并肩打卡监督</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/resources" class="quick-card">
          <div class="quick-ic q5"><BookOpen :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">资料库</div>
            <div class="quick-sub">网盘 · VIP 链接</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/posts" class="quick-card">
          <div class="quick-ic q6"><MessageSquare :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">研友动态</div>
            <div class="quick-sub">记录 · 打气</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
      </div>

      <!-- 大雪深埋 -->
      <div class="snow-card">
        <Snowflake :size="18" />
        <span>{{ encourage }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 首页视觉：蓝紫渐变 + 玻璃拟态，仅调整样式层，不改动业务逻辑 */
.page {
  /* 配色与阴影变量集中管理，便于后续统一换肤 */
  --p1: #4f46e5;
  --p2: #8b5cf6;
  --ink-1: #111827;
  --ink-2: #4b5563;
  --ink-3: #9ca3af;
  --glass: rgba(255, 255, 255, 0.7);
  --hairline: rgba(79, 70, 229, 0.1);
  --shadow-card: 0 8px 24px rgba(79, 70, 229, 0.08), 0 2px 8px rgba(17, 24, 39, 0.04);
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 16px calc(var(--tabbar-h) + 24px);
  font-size: 14px;
  color: var(--ink-1);
}

/* 问候区：标题使用柔和渐变文字 */
.hello {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin: 24px 0 16px;
}
.hello-date {
  font-size: 12px;
  color: var(--ink-3);
  letter-spacing: 0.4px;
}
.hello-name {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 800;
  line-height: 1.4;
  color: var(--p1);
  background: linear-gradient(120deg, var(--p1), var(--p2));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hero-toggle {
  flex-shrink: 0;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--sub);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 11px;
  cursor: pointer;
}

/* 错题复习提醒：暖色玻璃条，克制不刺眼 */
.review-banner {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 16px;
  border: 1px solid rgba(245, 158, 11, 0.28);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(255, 251, 235, 0.92), rgba(255, 241, 242, 0.86));
  color: #b45309;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 4px 16px rgba(245, 158, 11, 0.12);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  cursor: pointer;
  transition: transform 0.24s ease, box-shadow 0.24s ease;
}
.review-banner svg {
  color: #f59e0b;
}
.rb-txt {
  flex: 1;
  text-align: left;
}

/* 玻璃卡片：统一圆角、16px 内边距与多层柔和阴影 */
.card {
  position: relative;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.85);
  border-radius: 12px;
  background: var(--glass);
  box-shadow: var(--shadow-card), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: box-shadow 0.24s ease;
}
.card + .card {
  margin-top: 16px;
}

/* 今日数据 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}
.stat-item {
  text-align: center;
}
.stat-ic {
  width: 40px;
  height: 40px;
  margin: 0 auto 8px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stat-ic.c1 {
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  color: #4f46e5;
}
.stat-ic.c2 {
  background: linear-gradient(135deg, #f5f3ff, #ede9fe);
  color: #8b5cf6;
}
.stat-ic.c3 {
  background: linear-gradient(135deg, #fff7ed, #fef3c7);
  color: #f59e0b;
}
.stat-num {
  font-size: 20px;
  font-weight: 800;
  color: var(--ink-1);
}
.stat-num .unit {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-2);
}
.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-3);
}

/* 今日目标进度 */
.goal {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--hairline);
}
.goal-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--ink-2);
}
.goal-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.1);
}
.goal-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--p1), var(--p2));
  box-shadow: 0 0 12px rgba(139, 92, 246, 0.35);
  transition: width 0.5s ease;
}

/* 主按钮：蓝紫渐变 + 柔和辉光 */
.big-focus {
  margin-top: 16px;
  padding: 16px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--p1), var(--p2));
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.5px;
  box-shadow: 0 12px 24px rgba(79, 70, 229, 0.26), 0 4px 8px rgba(79, 70, 229, 0.16);
  transition: transform 0.24s ease, box-shadow 0.24s ease, filter 0.24s ease;
}
.big-focus:active {
  transform: scale(0.99);
}

/* 卡片小标题 */
.mini-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-1);
}
.more {
  font-size: 12px;
  font-weight: 600;
  color: var(--p1);
  cursor: pointer;
}
.mini-empty {
  padding: 4px 0 8px;
  font-size: 12px;
  color: var(--ink-3);
}
.mini-task {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  cursor: pointer;
}
.mini-task + .mini-task {
  border-top: 1px solid var(--hairline);
}
.mini-check {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid rgba(79, 70, 229, 0.28);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  color: transparent;
  cursor: pointer;
  transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
}
.mini-check.on {
  border-color: transparent;
  background: linear-gradient(135deg, #10b981, #34d399);
  color: #fff;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.28);
}
.mini-task-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-1);
}
.mini-task-name.done {
  color: var(--ink-3);
  text-decoration: line-through;
}
.add-task {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 0;
  border: none;
  background: none;
  color: var(--p1);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

/* 科目分布 */
.subj-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.subj-row:last-child {
  margin-bottom: 0;
}
.subj-name {
  width: 72px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 700;
}
.subj-track {
  flex: 1;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(79, 70, 229, 0.08);
}
.subj-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.5s ease;
}
.subj-min {
  width: 56px;
  flex-shrink: 0;
  text-align: right;
  font-size: 12px;
  color: var(--ink-2);
}

/* 快捷入口 */
.quick-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 16px;
}
.quick-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.85);
  border-radius: 12px;
  background: var(--glass);
  color: var(--ink-1);
  text-decoration: none;
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: transform 0.24s ease, box-shadow 0.24s ease;
}
.quick-ic {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}
.quick-ic.q1 {
  background: linear-gradient(135deg, #eef2ff, #e0e7ff);
  color: #4f46e5;
}
.quick-ic.q2 {
  background: linear-gradient(135deg, #ecfdf5, #d1fae5);
  color: #10b981;
}
.quick-ic.q3 {
  background: linear-gradient(135deg, #f5f3ff, #ede9fe);
  color: #8b5cf6;
}
.quick-ic.q4 {
  background: linear-gradient(135deg, #eef2ff, #ede9fe);
  color: #6366f1;
}
.quick-ic.q5 {
  background: linear-gradient(135deg, #ecfeff, #cffafe);
  color: #0891b2;
}
.quick-ic.q6 {
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
  color: #f59e0b;
}
.quick-txt {
  flex: 1;
  min-width: 0;
}
.quick-name {
  font-size: 14px;
  font-weight: 700;
}
.quick-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-3);
  /* 单行展示，避免窄屏出现「单字换行」 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.quick-arrow {
  flex-shrink: 0;
  color: #c7d2fe;
}
/* 窄屏优先保证入口名称不被拆行，隐藏装饰箭头 */
@media (max-width: 420px) {
  .quick-arrow {
    display: none;
  }
}

/* 底部鼓励条：淡化玻璃，避免大面积重色 */
.snow-card {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 16px;
  border: 1px solid rgba(139, 92, 246, 0.18);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(238, 242, 255, 0.9), rgba(245, 243, 255, 0.86));
  color: var(--ink-2);
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 8px 24px rgba(79, 70, 229, 0.08);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
.snow-card svg {
  flex-shrink: 0;
  color: var(--p2);
}

/* 柔和交互：仅在支持悬停的设备启用，240ms 内完成 */
@media (hover: hover) and (pointer: fine) {
  .big-focus:hover {
    transform: translateY(-2px) scale(1.03);
    filter: brightness(1.06);
    box-shadow: 0 16px 32px rgba(79, 70, 229, 0.3), 0 6px 12px rgba(79, 70, 229, 0.18);
  }
  .review-banner:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(245, 158, 11, 0.18);
  }
  .quick-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(79, 70, 229, 0.14);
  }
  .mini-check:hover {
    transform: scale(1.06);
    border-color: rgba(79, 70, 229, 0.5);
  }
  .card:hover {
    box-shadow: 0 12px 32px rgba(79, 70, 229, 0.12);
  }
}

/* 键盘可达性 */
.big-focus:focus-visible,
.review-banner:focus-visible,
.mini-check:focus-visible,
.add-task:focus-visible,
.quick-card:focus-visible {
  outline: 2px solid rgba(79, 70, 229, 0.45);
  outline-offset: 2px;
}

/* 进入动画：只做透明度，避免与 hover 变换冲突 */
@media (prefers-reduced-motion: no-preference) {
  .page > * {
    animation: home-fade 0.2s ease-out;
  }
}
@keyframes home-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
