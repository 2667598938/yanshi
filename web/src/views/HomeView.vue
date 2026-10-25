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
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
import { useTasksStore } from '../stores/tasks'
import { useMistakesStore } from '../stores/mistakes'
import { useAppStore } from '../stores/app'
import { fmtMinutes, fmtClock, todayKey, mdLabel, weekLabel } from '../utils/date'

const router = useRouter()
const timer = useTimerStore()
const subjects = useSubjectsStore()
const tasks = useTasksStore()
const mistakes = useMistakesStore()
const app = useAppStore()

const today = computed(() => {
  const d = new Date()
  return `${mdLabel(todayKey())} ${weekLabel(d)}`
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
  <div>
    <SchoolHero />

    <div class="page">
      <div class="hello">
        <div>
          <div class="hello-date">{{ today }}</div>
          <div class="hello-name">{{ app.nickname }}，沉潜一日，功不唐捐</div>
        </div>
      </div>

      <!-- 错题复习提醒 -->
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
            <div class="quick-sub">计划 · 验收 · 完成率</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/mistakes" class="quick-card">
          <div class="quick-ic q3"><NotebookPen :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">错题本</div>
            <div class="quick-sub">艾宾浩斯 · 复习提醒</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/stats" class="quick-card">
          <div class="quick-ic q4"><BarChart3 :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">数据仪表盘</div>
            <div class="quick-sub">热力图 · 占比 · 趋势</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/rooms" class="quick-card">
          <div class="quick-ic q2"><Users :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">四人自习室</div>
            <div class="quick-sub">并肩打卡 · 互相监督</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/resources" class="quick-card">
          <div class="quick-ic q5"><BookOpen :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">资料库</div>
            <div class="quick-sub">网盘分享 · VIP 完整链接</div>
          </div>
          <ChevronRight :size="18" class="quick-arrow" />
        </router-link>
        <router-link to="/posts" class="quick-card">
          <div class="quick-ic q6"><MessageSquare :size="20" /></div>
          <div class="quick-txt">
            <div class="quick-name">研友动态</div>
            <div class="quick-sub">记录 · 评论 · 互相打气</div>
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
.hello {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin: 16px 2px 10px;
}
.hello-date {
  font-size: 12px;
  color: var(--faint);
}
.hello-name {
  font-size: 17px;
  font-weight: 800;
  margin-top: 2px;
}
.review-banner {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 16px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, #fff3e6, #ffe1d0);
  color: var(--tomato-deep);
  font-size: 13.5px;
  font-weight: 700;
  margin-bottom: 12px;
  cursor: pointer;
}
.rb-txt {
  flex: 1;
  text-align: left;
}

.stat-card {
  padding: 16px 14px 14px;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}
.stat-item {
  text-align: center;
}
.stat-ic {
  width: 34px;
  height: 34px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
}
.stat-ic.c1 {
  background: #e6f0fb;
  color: var(--primary);
}
.stat-ic.c2 {
  background: #fdece8;
  color: var(--tomato);
}
.stat-ic.c3 {
  background: #fff3df;
  color: var(--accent-deep);
}
.stat-num {
  font-size: 17px;
  font-weight: 800;
  color: var(--ink);
}
.stat-num .unit {
  font-size: 12px;
  font-weight: 600;
  margin-left: 1px;
}
.stat-label {
  font-size: 12px;
  color: var(--faint);
  margin-top: 2px;
}
.goal {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.goal-top {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  color: var(--sub);
  margin-bottom: 7px;
}
.goal-bar {
  height: 9px;
  border-radius: 999px;
  background: var(--line);
  overflow: hidden;
}
.goal-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), var(--tomato));
  transition: width 0.5s ease;
}
.big-focus {
  margin-top: 14px;
  padding: 16px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 1px;
}

.mini-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.more {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  cursor: pointer;
}
.mini-empty {
  font-size: 13px;
  color: var(--faint);
  padding: 4px 0 8px;
}
.mini-task {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  cursor: pointer;
}
.mini-task + .mini-task {
  border-top: 1px solid var(--line);
}
.mini-check {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: 2px solid var(--faint);
  background: #fff;
  color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
}
.mini-check.on {
  background: var(--green);
  border-color: var(--green);
  color: #fff;
}
.mini-task-name {
  font-size: 14px;
  font-weight: 500;
  flex: 1;
}
.mini-task-name.done {
  color: var(--faint);
  text-decoration: line-through;
}
.add-task {
  margin-top: 8px;
  border: none;
  background: none;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 0;
}

.subj-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.subj-row:last-child {
  margin-bottom: 0;
}
.subj-name {
  width: 72px;
  font-size: 12.5px;
  font-weight: 700;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.subj-track {
  flex: 1;
  height: 8px;
  background: var(--line);
  border-radius: 999px;
  overflow: hidden;
}
.subj-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.5s ease;
}
.subj-min {
  width: 60px;
  text-align: right;
  font-size: 12px;
  color: var(--sub);
  flex-shrink: 0;
}

.quick-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 14px;
}
.quick-card {
  background: var(--card);
  border-radius: var(--radius);
  box-shadow: var(--shadow-soft);
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: var(--ink);
}
.quick-ic {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.quick-ic.q1 {
  background: #e6f0fb;
  color: var(--primary);
}
.quick-ic.q2 {
  background: #e7f6f0;
  color: var(--green);
}
.quick-ic.q3 {
  background: #fdecec;
  color: var(--tomato);
}
.quick-ic.q4 {
  background: #eef0fe;
  color: var(--purple);
}
.quick-ic.q5 {
  background: #e6f7fb;
  color: #0d8a9e;
}
.quick-ic.q6 {
  background: #fdf0e8;
  color: #d97706;
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
  font-size: 11px;
  color: var(--faint);
  margin-top: 2px;
}
.quick-arrow {
  color: var(--faint);
  flex-shrink: 0;
}

.snow-card {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius);
  background: linear-gradient(135deg, var(--night2), var(--night));
  color: #e9f0ff;
  font-size: 13.5px;
  font-weight: 500;
  box-shadow: var(--shadow);
}
.snow-card svg {
  color: #cfe0ff;
  flex-shrink: 0;
}
</style>
