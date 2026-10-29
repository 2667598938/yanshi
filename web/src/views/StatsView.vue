<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Clock3, Timer as TimerIcon, Flame, CalendarDays, Play,
  ChevronLeft, ChevronRight, Download, FileImage, CheckCircle2,
  NotebookPen, Target, ListChecks,
} from 'lucide-vue-next'
import Heatmap from '../components/Heatmap.vue'
import SubjectIcon from '../components/SubjectIcon.vue'
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
import { useTasksStore } from '../stores/tasks'
import { useMistakesStore } from '../stores/mistakes'
import { useAppStore } from '../stores/app'
import { useClockStore } from '../stores/clock'
import { ACTIVITIES } from '../data/subjects'
import {
  fmtMinutes, todayKey, addDaysKey, diffDayKeys, mdLabel,
} from '../utils/date'
import {
  filterSessions, sumMin, weeklySeries, subjectBreakdown,
  buildYearWeeks, buildMonthWeeks, buildWeekDays, monthLabels,
  daySubjectDetail, firstDate, weekStartKey,
  periodBounds, contentBreakdown,
} from '../utils/stats'
import { useToast } from '../composables/useToast'
import { buildSessionsCsv } from '../utils/csv'

const router = useRouter()
const timer = useTimerStore()
const subjects = useSubjectsStore()
const tasks = useTasksStore()
const mistakes = useMistakesStore()
const app = useAppStore()
const clock = useClockStore()
const { toast } = useToast()

const rows = computed(() => timer.effectiveSessions)
const today = computed(() => clock.today)
const thisMonday = computed(() => weekStartKey(today.value))
const isEmpty = computed(() => timer.totalMin === 0)
const contentPeriod = ref('day')
const contentDate = ref(today.value)
const contentStats = computed(() => contentBreakdown(filterSessions(rows.value, periodBounds(contentPeriod.value, contentDate.value || today.value))))
const contentTotal = computed(() => contentStats.value.reduce((sum, row) => sum + row.sec, 0))
const totalLabel = computed(() => `${Math.round(contentTotal.value / 60)} 分钟`)
const pieStyle = computed(() => {
  let offset = 0
  const slices = contentStats.value.map((row) => { const start = offset; offset += row.pct; return `${row.color} ${start}% ${offset}%` })
  return { background: slices.length ? `conic-gradient(${slices.join(',')})` : '#e2e8f0' }
})

// ===== 本周 =====
const weekRows = computed(() => filterSessions(rows.value, { start: thisMonday.value, end: today.value }))
const weekMin = computed(() => sumMin(weekRows.value))
const weekDaysPassed = computed(() => diffDayKeys(thisMonday.value, today.value) + 1)
const weekAvg = computed(() => Math.round(weekMin.value / weekDaysPassed.value))
const weekGoal = computed(() => app.dailyGoalMin * 7)
const weekRate = computed(() =>
  Math.min(100, Math.round((weekMin.value / weekGoal.value) * 100)))
const weekTaskRate = computed(() => tasks.rangeRate(thisMonday.value, today.value))
const weekMistakes = computed(() => mistakes.countByDateRange(thisMonday.value, today.value))

// ===== 科目占比 =====
const breakdown = computed(() =>
  subjectBreakdown(rows.value, subjects)
    .map((b) => ({ ...b, subject: subjects.byId[b.subjectId] }))
    .filter((b) => b.subject)
)

// ===== 学习类型占比 =====
const actStats = computed(() => {
  const m = {}
  rows.value.forEach((s) => {
    const k = s.activityType || '_none'
    m[k] = (m[k] || 0) + s.actualSec / 60
  })
  const total = Object.values(m).reduce((a, b) => a + b, 0)
  const arr = ACTIVITIES.map((a) => ({
    name: a.name,
    color: a.color,
    min: Math.round(m[a.id] || 0),
    pct: total ? Math.round(((m[a.id] || 0) / total) * 100) : 0,
  })).filter((x) => x.min > 0)
  const none = Math.round(m._none || 0)
  if (none > 0) arr.push({ name: '未标注', color: '#9aa7b8', min: none, pct: Math.round((none / total) * 100) })
  return arr.sort((a, b) => b.min - a.min)
})

// ===== 12 周趋势（可选科目）=====
const trendSub = ref('')
const trendRows = computed(() =>
  filterSessions(rows.value, { subjectId: trendSub.value || undefined }))
const trend = computed(() =>
  weeklySeries(trendRows.value, 12).map((w) => ({
    ...w,
    label: mdLabel(w.weekStart),
  }))
)
const trendMax = computed(() => Math.max(60, ...trend.value.map((x) => x.min)))

// ===== 热力图 =====
const view = ref('month')
const heatSub = ref('')
const now = new Date(today.value + 'T00:00:00')
const yCursor = ref(now.getFullYear())
const mCursor = ref({ year: now.getFullYear(), month: now.getMonth() })
const wCursor = ref(weekStartKey(today.value))
const selected = ref(today.value)
const heatShotRef = ref(null)

const minYear = computed(() => Number(firstDate(rows.value).slice(0, 4)))
const minWeek = computed(() => weekStartKey(firstDate(rows.value)))
const heatRows = computed(() =>
  filterSessions(rows.value, { subjectId: heatSub.value || undefined }))
const heatMinMap = computed(() => {
  const map = {}
  heatRows.value.forEach((s) => {
    map[s.date] = (map[s.date] || 0) + s.actualSec / 60
  })
  return map
})
const yearWeeks = computed(() =>
  view.value === 'year' ? buildYearWeeks(yCursor.value, heatMinMap.value) : [])
const yearLabs = computed(() => monthLabels(yearWeeks.value))
const monthWeeks = computed(() =>
  view.value === 'month'
    ? buildMonthWeeks(mCursor.value.year, mCursor.value.month, heatMinMap.value)
    : [])
const weekDays = computed(() =>
  view.value === 'week' ? buildWeekDays(wCursor.value, heatMinMap.value) : [])

const cursorLabel = computed(() => {
  if (view.value === 'year') return yCursor.value + '年'
  if (view.value === 'month') return mCursor.value.year + '年' + (mCursor.value.month + 1) + '月'
  const end = addDaysKey(wCursor.value, 6)
  return wCursor.value.slice(5).replace('-', '/') + ' – ' + end.slice(5).replace('-', '/')
})
function canPrev() {
  if (view.value === 'year') return yCursor.value > minYear.value
  if (view.value === 'month') return mCursor.value.year * 12 + mCursor.value.month > minYear.value * 12
  return wCursor.value > minWeek.value
}
function canNext() {
  if (view.value === 'year') return yCursor.value < Number(today.value.slice(0,4))
  if (view.value === 'month') {
    return mCursor.value.year * 12 + mCursor.value.month < Number(today.value.slice(0,4)) * 12 + Number(today.value.slice(5,7)) - 1
  }
  return wCursor.value < weekStartKey(today.value)
}
function prev() {
  if (!canPrev()) return
  if (view.value === 'year') yCursor.value -= 1
  else if (view.value === 'month') {
    let { year, month } = mCursor.value
    month -= 1
    if (month < 0) { month = 11; year -= 1 }
    mCursor.value = { year, month }
  } else {
    wCursor.value = weekStartKey(addDaysKey(wCursor.value, -7))
  }
}
function next() {
  if (!canNext()) return
  if (view.value === 'year') yCursor.value += 1
  else if (view.value === 'month') {
    let { year, month } = mCursor.value
    month += 1
    if (month > 11) { month = 0; year += 1 }
    mCursor.value = { year, month }
  } else {
    wCursor.value = weekStartKey(addDaysKey(wCursor.value, 7))
  }
}

// 选中当天详情
const selRows = computed(() => rows.value.filter((s) => s.date === selected.value))
const selMin = computed(() => Math.round(selRows.value.reduce((a, s) => a + s.actualSec / 60, 0)))
const selCount = computed(() => selRows.value.length)
const selDetail = computed(() => {
  const m = daySubjectDetail(rows.value, selected.value)
  return Object.entries(m)
    .map(([id, min]) => ({ subj: subjects.byId[id], min: Math.round(min) }))
    .filter((x) => x.subj)
    .sort((a, b) => b.min - a.min)
})
const selMistakes = computed(() => mistakes.byDate[selected.value] || [])
const selTasks = computed(() => tasks.list.filter((t) => t.dueDate === selected.value))
const selTitle = computed(() => {
  const d = new Date(selected.value + 'T00:00:00')
  const dow = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
  return selected.value.replace(/-/g, '/') + ' ' + dow
})

// 导出
function downloadFile(content, filename, mime, isDataUrl) {
  let href
  if (isDataUrl) href = content
  else {
    const blob = new Blob([content], { type: mime + ';charset=utf-8' })
    href = URL.createObjectURL(blob)
  }
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  a.click()
  if (!isDataUrl) setTimeout(() => URL.revokeObjectURL(href), 1000)
}
async function exportPng() {
  if (!heatShotRef.value) return
  try {
    const { toPng } = await import('html-to-image')
    const dataUrl = await toPng(heatShotRef.value, {
      backgroundColor: '#ffffff', pixelRatio: 2, cacheBust: false,
    })
    downloadFile(dataUrl, `研时热力图_${cursorLabel.value}.png`, '', true)
    toast('已导出热力图')
  } catch {
    toast('导出失败，请截图保存')
  }
}
function exportCsv() {
  // 导出范围：当前科目筛选下的全部有效计时；年/月/周定位只影响热力图展示。
  const csv = buildSessionsCsv(
    heatRows.value,
    (s) => subjects.byId[s.subjectId]?.name || '',
    (s) => ACTIVITIES.find((a) => a.id === s.activityType)?.name || '',
  )
  const suffix = heatSub.value ? (subjects.byId[heatSub.value]?.name || '所选科目') : '全部'
  downloadFile(csv, `研时学习记录_${suffix}.csv`, 'text/csv')
  toast(`已导出 ${heatRows.value.length} 条（当前科目筛选，全部日期）`)
}
</script>

<template>
  <div>
    <div class="nav">
      <div>
        <div class="nav-title">数据仪表盘</div>
        <div class="nav-sub">时长 + 任务 + 错题一起看，拒绝假努力</div>
      </div>
    </div>

    <div class="page stats-layout">
      <p v-if="timer.sessions.some(row=>row.conflict_flag||row.validation_issue)" class="card">有 {{timer.sessions.filter(row=>row.conflict_flag||row.validation_issue).length}} 条计时记录待本人处理，暂不计入统计。请联网后通过计时冲突提示处理。</p>
      <div class="card content-summary">
        <div class="card-title">学习内容分布</div>
        <div class="pill-row"><button v-for="[key, label] in [['day','日'],['week','周'],['month','月'],['year','年']]" :key="key" class="pill" :class="{ active: contentPeriod === key }" @click="contentPeriod = key">{{ label }}</button></div>
        <div class="date-field">
          <CalendarDays :size="16" />
          <input v-model="contentDate" aria-label="统计日期" type="date" class="input" />
          <button type="button" class="date-today" @click="contentDate = today">今天</button>
        </div>
        <div class="content-chart">
          <div class="content-pie-wrap">
            <div
              class="content-pie"
              :class="{ empty: !contentStats.length }"
              role="img"
              :aria-label="`本周期专注${Math.round(contentTotal / 60)}分钟`"
              :style="contentStats.length ? pieStyle : {}"
            />
            <div class="content-pie-center">
              <strong>{{ contentStats.length ? totalLabel : '暂无' }}</strong>
              <small>{{ contentStats.length ? '总专注' : '本周期' }}</small>
            </div>
          </div>
          <div v-if="contentStats.length" class="content-legend">
            <div v-for="item in contentStats" :key="item.name" class="legend-row">
              <span class="legend-name"><i :style="{ background: item.color }"></i>{{ item.name }}</span>
              <small>{{ (item.sec / 60).toFixed(1) }} 分钟 · {{ item.pct.toFixed(1) }}%</small>
            </div>
          </div>
          <p v-else class="content-empty">本周期还没有专注记录</p>
        </div>
      </div>
      <!-- 空态 -->
      <div v-if="isEmpty" class="card empty-block">
        <TimerIcon :size="40" :stroke-width="1.5" class="empty-ic" />
        <div class="empty-title">还没有专注记录</div>
        <div class="sub">开始第一次专注，数据会在这里慢慢长成森林。</div>
        <button class="btn btn-tomato btn-sm mt12" @click="router.push('/focus')">
          <Play :size="15" />去专注
        </button>
      </div>

      <template v-else>
        <!-- 核心指标 -->
        <div class="card overview">
          <div class="ov-item">
            <div class="ov-ic c1"><Clock3 :size="16" /></div>
            <div class="ov-num tnum">{{ fmtMinutes(timer.totalMin) }}</div>
            <div class="ov-label">累计专注</div>
          </div>
          <div class="ov-item">
            <div class="ov-ic c4"><CalendarDays :size="16" /></div>
            <div class="ov-num tnum">{{ fmtMinutes(weekAvg) }}</div>
            <div class="ov-label">本周日均</div>
          </div>
          <div class="ov-item">
            <div class="ov-ic c3"><Flame :size="16" /></div>
            <div class="ov-num tnum">{{ timer.streak }}</div>
            <div class="ov-label">连续天数</div>
          </div>
          <div class="ov-item">
            <div class="ov-ic c2"><TimerIcon :size="16" /></div>
            <div class="ov-num tnum">{{ fmtMinutes(Math.round(timer.longestSec / 60)) }}</div>
            <div class="ov-label">最长单次</div>
          </div>
        </div>

        <!-- 本周目标 -->
        <div class="goal-card">
          <div class="goal-top">
            <div>
              <div class="goal-label">本周目标（{{ fmtMinutes(weekGoal) }}）</div>
              <div class="goal-num tnum">{{ fmtMinutes(weekMin) }} <span class="goal-unit">/ {{ fmtMinutes(weekGoal) }}</span></div>
            </div>
            <div class="goal-ring" :style="{ background: `conic-gradient(var(--primary) ${weekRate * 3.6}deg, #e3edf7 0deg)` }">
              <div class="ring-inner tnum">{{ weekRate }}%</div>
            </div>
          </div>
          <div class="goal-bar">
            <div class="goal-fill" :style="{ width: weekRate + '%' }"></div>
          </div>
        </div>

        <!-- 防假努力三合一 -->
        <div class="triad">
          <div class="tri-card">
            <Clock3 :size="17" class="tri-ic t1" />
            <div class="tri-num tnum">{{ fmtMinutes(weekMin) }}</div>
            <div class="tri-cap">本周时长</div>
          </div>
          <div class="tri-card" @click="router.push('/tasks')">
            <ListChecks :size="17" class="tri-ic t2" />
            <div class="tri-num tnum">{{ weekTaskRate === null ? '—' : weekTaskRate + '%' }}</div>
            <div class="tri-cap">任务完成</div>
          </div>
          <div class="tri-card" @click="router.push('/mistakes')">
            <NotebookPen :size="17" class="tri-ic t3" />
            <div class="tri-num tnum">{{ weekMistakes }}</div>
            <div class="tri-cap">本周错题</div>
          </div>
        </div>

        <!-- 热力图 -->
        <div class="card heatmap-card">
          <div class="heat-toolbar">
            <div class="seg">
              <button :class="{ on: view === 'year' }" @click="view = 'year'">年</button>
              <button :class="{ on: view === 'month' }" @click="view = 'month'">月</button>
              <button :class="{ on: view === 'week' }" @click="view = 'week'">周</button>
            </div>
            <div class="export-btns">
              <button class="exp" @click="exportPng"><FileImage :size="15" />图片</button>
              <button class="exp" @click="exportCsv"><Download :size="15" />CSV</button>
            </div>
          </div>

          <!-- 科目筛选 -->
          <div class="filter-row">
            <button class="fpill" :class="{ on: !heatSub }" @click="heatSub = ''">全部</button>
            <button
              v-for="s in subjects.active"
              :key="s.id"
              class="fpill"
              :class="{ on: heatSub === s.id }"
              :style="heatSub === s.id ? { background: s.color } : {}"
              @click="heatSub = heatSub === s.id ? '' : s.id"
            >
              <SubjectIcon :name="s.icon" :size="12" />{{ s.name }}
            </button>
          </div>
          <p class="export-scope">CSV 导出当前科目筛选下的全部有效计时（不受年/月/周定位影响）。</p>

          <!-- 截图区域 -->
          <div ref="heatShotRef" class="heat-shot">
            <div class="shot-title">研时 · 专注热力</div>
            <div class="heat-nav">
              <button :disabled="!canPrev()" @click="prev"><ChevronLeft :size="16" /></button>
              <span class="heat-cur tnum">{{ cursorLabel }}</span>
              <button :disabled="!canNext()" @click="next"><ChevronRight :size="16" /></button>
            </div>
            <Heatmap
              :view="view"
              :year-weeks="yearWeeks"
              :month-weeks="monthWeeks"
              :month-labs="yearLabs"
              :week-days="weekDays"
              :selected="selected"
              @select="selected = $event"
            />
            <div class="shot-foot">大雪深埋，静候春来</div>
          </div>

          <!-- 当天详情 -->
          <div class="day-detail">
            <div class="dd-head">
              <span class="dd-date">{{ selTitle }}</span>
              <span class="dd-sum tnum">{{ fmtMinutes(selMin) }} · {{ selCount }} 次专注</span>
            </div>
            <div v-if="selDetail.length" class="dd-subs">
              <div v-for="d in selDetail" :key="d.subj.id" class="dd-sub">
                <span class="dot" :style="{ background: d.subj.color }"></span>
                <span class="dd-subj-name">{{ d.subj.name }}</span>
                <span class="dd-subj-min tnum">{{ fmtMinutes(d.min) }}</span>
              </div>
            </div>
            <div v-else class="dd-empty">这一天没有专注记录</div>

            <div v-if="selMistakes.length" class="dd-link" @click="router.push('/mistakes')">
              <NotebookPen :size="13" />当天收录 {{ selMistakes.length }} 道错题
            </div>
            <div v-if="selTasks.length" class="dd-link" @click="router.push('/tasks')">
              <ListChecks :size="13" />当天 {{ selTasks.length }} 项任务
              （{{ selTasks.filter((t) => t.done).length }} 已完成）
            </div>
          </div>
        </div>

        <!-- 科目占比 -->
        <div v-if="breakdown.length" class="card">
          <div class="card-title">各科投入占比</div>
          <div v-for="b in breakdown" :key="b.subject.id" class="subj-row">
            <div class="subj-head">
              <span class="subj-name" :style="{ color: b.subject.color }">
                <SubjectIcon :name="b.subject.icon" :size="14" />
                {{ b.subject.name }}
              </span>
              <span class="subj-val tnum">{{ fmtMinutes(b.min) }} · {{ b.pct }}%</span>
            </div>
            <div class="subj-track">
              <div class="subj-fill" :style="{ width: b.pct + '%', background: b.subject.color }"></div>
            </div>
          </div>
        </div>

        <!-- 学习类型 -->
        <div v-if="actStats.length" class="card">
          <div class="card-title">学习类型（别只听课，多做题）</div>
          <div class="type-track">
            <div
              v-for="a in actStats"
              :key="a.name"
              class="type-seg"
              :style="{ width: a.pct + '%', background: a.color }"
              :title="`${a.name} ${a.pct}%`"
            ></div>
          </div>
          <div class="type-legend">
            <span v-for="a in actStats" :key="a.name" class="tl-item">
              <i class="tl-dot" :style="{ background: a.color }"></i>{{ a.name }} {{ a.pct }}%
            </span>
          </div>
        </div>

        <!-- 12 周趋势 -->
        <div class="card">
          <div class="card-title">
            近 12 周投入
            <select v-model="trendSub" class="trend-select">
              <option value="">全部科目</option>
              <option v-for="s in subjects.active" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
          <div class="bars">
            <div v-for="(w, i) in trend" :key="i" class="bar-col" :title="`${w.label} · ${w.min} 分钟`">
              <div
                class="bar"
                :class="{ now: i === trend.length - 1 }"
                :style="{ height: Math.max(w.min ? 4 : 0, (w.min / trendMax) * 100) + '%' }"
              ></div>
            </div>
          </div>
          <div class="bars-x">
            <span>{{ trend[0]?.label }}</span>
            <span>{{ trend[trend.length - 1]?.label }}</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.content-summary { padding: 18px; }
.date-field { display: flex; align-items: center; gap: 8px; margin-top: 12px; color: var(--primary); }
.date-field .input { flex: 1; min-width: 0; margin-top: 0; height: 44px; }
.date-today { flex-shrink: 0; height: 40px; padding: 0 12px; border: 1px solid var(--line); border-radius: 10px; background: rgba(79, 70, 229, 0.06); color: var(--primary); font-size: 12px; font-weight: 600; cursor: pointer; }
.content-chart { display: flex; align-items: center; flex-wrap: wrap; gap: 20px; margin-top: 18px; }
.content-pie-wrap { position: relative; width: 144px; height: 144px; flex-shrink: 0; }
.content-pie { width: 100%; height: 100%; border-radius: 50%; position: relative; box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.04); }
.content-pie::after { content: ''; position: absolute; inset: 26%; border-radius: 50%; background: #fff; box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08); }
.content-pie.empty { background: #eef2f7; }
.content-pie.empty::after { inset: 24%; border: 1px dashed #cbd5e1; background: #fff; }
.content-pie-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; pointer-events: none; }
.content-pie-center strong { font-size: 16px; font-weight: 800; color: var(--ink); letter-spacing: -0.3px; }
.content-pie-center small { margin-top: 2px; font-size: 10px; color: var(--faint); }
.content-legend { flex: 1; min-width: 160px; display: grid; gap: 10px; font-size: 13px; }
.legend-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 7px 10px; border-radius: 10px; background: #f8faff; }
.legend-name { display: inline-flex; align-items: center; gap: 7px; min-width: 0; overflow-wrap: anywhere; color: var(--ink); font-weight: 600; }
.legend-name i { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.legend-row small { flex-shrink: 0; color: var(--sub); font-variant-numeric: tabular-nums; }
.content-empty { margin: 0; color: var(--faint); font-size: 12px; }
.empty-block {
  text-align: center;
  padding: 44px 20px;
}
.empty-ic {
  color: var(--faint);
  opacity: 0.5;
}
.empty-title {
  font-size: 16px;
  font-weight: 700;
  margin: 14px 0 6px;
}
.overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  padding: 16px 10px;
}
.ov-item {
  text-align: center;
}
.ov-ic {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 7px;
}
.ov-ic.c1 { background: #e6f0fb; color: var(--primary); }
.ov-ic.c2 { background: #fdece8; color: var(--tomato); }
.ov-ic.c3 { background: #fff3df; color: var(--accent-deep); }
.ov-ic.c4 { background: #eef0fe; color: var(--purple); }
.ov-num {
  font-size: 14px;
  font-weight: 800;
  line-height: 1.3;
}
.ov-label {
  font-size: 11px;
  color: var(--faint);
  margin-top: 2px;
}

.goal-card {
  background: linear-gradient(135deg, #eef5fb, #e3edf7);
  border-radius: 18px;
  padding: 16px 18px;
  margin-top: 12px;
}
.goal-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.goal-label {
  font-size: 12px;
  color: var(--sub);
}
.goal-num {
  font-size: 26px;
  font-weight: 800;
  color: var(--primary-deep);
  margin-top: 2px;
}
.goal-unit {
  font-size: 14px;
  font-weight: 600;
  color: var(--faint);
}
.goal-ring {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ring-inner {
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 800;
  color: var(--primary-deep);
}
.goal-bar {
  height: 7px;
  border-radius: 999px;
  background: #d7e3ef;
  margin-top: 12px;
  overflow: hidden;
}
.goal-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--primary), var(--primary-deep));
  transition: width 0.5s ease;
}

.triad {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 12px;
}
.tri-card {
  background: #fff;
  border-radius: 16px;
  padding: 14px 8px;
  text-align: center;
  box-shadow: var(--shadow-soft);
  cursor: pointer;
}
.tri-ic {
  margin: 0 auto 6px;
}
.tri-ic.t1 { color: var(--primary); }
.tri-ic.t2 { color: var(--green); }
.tri-ic.t3 { color: var(--tomato); }
.tri-num {
  font-size: 18px;
  font-weight: 800;
}
.tri-cap {
  font-size: 11px;
  color: var(--faint);
  margin-top: 2px;
}

.heat-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.seg {
  display: inline-flex;
  background: #eef2f7;
  border-radius: 10px;
  padding: 3px;
}
.seg button {
  border: none;
  background: none;
  font-size: 13px;
  font-weight: 600;
  color: var(--sub);
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
}
.seg button.on {
  background: #fff;
  color: var(--primary-deep);
  box-shadow: 0 2px 6px rgba(22, 41, 77, 0.1);
}
.export-btns {
  display: flex;
  gap: 7px;
}
.exp {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--sub);
  font-size: 12px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.filter-row {
  display: flex;
  gap: 7px;
  overflow-x: auto;
  scrollbar-width: none;
  margin-bottom: 12px;
}
.filter-row::-webkit-scrollbar {
  display: none;
}
.export-scope {
  margin: -4px 0 12px;
  font-size: 11px;
  line-height: 1.6;
  color: var(--faint);
}
.fpill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1.5px solid var(--line);
  background: #fff;
  color: var(--sub);
  font-size: 12px;
  font-weight: 600;
  padding: 6px 11px;
  border-radius: 999px;
  white-space: nowrap;
  cursor: pointer;
}
.fpill.on {
  color: #fff;
  border-color: transparent;
  background: var(--primary);
}
.heat-shot {
  background: #fff;
}
.shot-title {
  font-size: 14px;
  font-weight: 800;
  margin-bottom: 8px;
}
.heat-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 12px;
}
.heat-nav button {
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 8px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--sub);
}
.heat-nav button:disabled {
  opacity: 0.35;
  cursor: default;
}
.heat-cur {
  font-size: 14px;
  font-weight: 700;
  min-width: 110px;
  text-align: center;
}
.shot-foot {
  text-align: center;
  font-size: 11px;
  color: var(--faint);
  margin-top: 10px;
  letter-spacing: 1px;
}

.day-detail {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed var(--line);
}
.dd-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}
.dd-date {
  font-size: 14px;
  font-weight: 800;
}
.dd-sum {
  font-size: 13px;
  color: var(--primary);
  font-weight: 700;
}
.dd-subs {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.dd-sub {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}
.dd-subj-name {
  font-size: 13px;
  font-weight: 600;
  flex: 1;
}
.dd-subj-min {
  font-size: 13px;
  color: var(--sub);
}
.dd-empty {
  font-size: 13px;
  color: var(--faint);
  margin-top: 8px;
}
.dd-link {
  margin-top: 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--primary);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 16px;
  cursor: pointer;
}

.card-title {
  font-size: 14.5px;
  font-weight: 700;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.trend-select {
  font-size: 12px;
  font-weight: 600;
  color: var(--sub);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 4px 8px;
  background: #fff;
}
.subj-row {
  margin-bottom: 14px;
}
.subj-row:last-child {
  margin-bottom: 0;
}
.subj-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
}
.subj-name {
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.subj-val {
  font-size: 12px;
  color: var(--sub);
}
.subj-track {
  height: 8px;
  border-radius: 999px;
  background: var(--line);
  overflow: hidden;
}
.subj-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.5s ease;
}
.type-track {
  display: flex;
  height: 14px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--line);
}
.type-seg {
  height: 100%;
}
.type-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 10px;
}
.tl-item {
  font-size: 12px;
  color: var(--sub);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.tl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.bars {
  height: 120px;
  display: flex;
  align-items: flex-end;
  gap: 3px;
}
.bar-col {
  flex: 1;
  height: 100%;
  display: flex;
  align-items: flex-end;
}
.bar {
  width: 100%;
  background: #c7dcf0;
  border-radius: 3px 3px 0 0;
  transition: height 0.4s ease;
}
.bar.now {
  background: linear-gradient(180deg, #4a90d0, var(--primary-deep));
}
.bars-x {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--faint);
  margin-top: 6px;
}
</style>
