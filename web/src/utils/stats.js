// 学习数据聚合（仪表盘 / 热力图 / 趋势共用）
import { dayKey, todayKey, addDaysKey } from './date'
import { ACTIVITY_MAP } from '../data/subjects'

export function filterSessions(sessions, { start, end, subjectId, activityType } = {}) {
  return sessions.filter(
    (s) =>
      (s.status === 'done' || s.status === 'quit') &&
      (!start || s.date >= start) &&
      (!end || s.date <= end) &&
      (!subjectId || s.subjectId === subjectId) &&
      (!activityType || (s.activityType || '') === activityType)
  )
}

export function periodBounds(period, key = todayKey()) {
  const date = new Date(key + 'T00:00:00')
  if (!Number.isFinite(date.getTime())) throw new Error('日期无效')
  const year = date.getFullYear(), month = date.getMonth()
  if (period === 'day') return { start: key, end: key }
  if (period === 'week') { const start = weekStartKey(key); return { start, end: addDaysKey(start, 6) } }
  if (period === 'month') return { start: dayKey(new Date(year, month, 1)), end: dayKey(new Date(year, month + 1, 0)) }
  if (period === 'year') return { start: `${year}-01-01`, end: `${year}-12-31` }
  throw new Error('统计周期无效')
}

export function contentBreakdown(rows) {
  const grouped = new Map()
  for (const row of rows) {
    const name = row.learningContent?.trim() || '未填写学习内容'
    grouped.set(name, (grouped.get(name) || 0) + Math.max(0, Number(row.actualSec) || 0))
  }
  const total = [...grouped.values()].reduce((sum, sec) => sum + sec, 0)
  const colors = ['#f2705b', '#3a7fc4', '#1f9d63', '#8b6ccc', '#d49b32', '#d265a1', '#379a9a', '#76859b']
  return [...grouped].map(([name, sec]) => ({ name, sec, pct: total ? sec / total * 100 : 0,
    color: colors[[...name].reduce((hash, char) => hash + char.codePointAt(0), 0) % colors.length] }))
    .filter((row) => row.sec > 0).sort((a, b) => b.sec - a.sec || a.name.localeCompare(b.name))
}

export function sumMin(rows) {
  return rows.reduce((a, x) => a + x.actualSec / 60, 0)
}

export function minByDateMap(rows) {
  const m = {}
  rows.forEach((x) => {
    m[x.date] = (m[x.date] || 0) + x.actualSec / 60
  })
  return m
}

// 连续日期区间序列（含无记录日）
export function dailySeries(rows, startKey, endKey) {
  const m = minByDateMap(rows)
  const out = []
  let cur = startKey
  while(cur <= endKey) {
    out.push({ date: cur, min: Math.round(m[cur] || 0) })
    cur = addDaysKey(cur, 1)
  }
  return out
}

// 某日期所在周的周一 key
export function weekStartKey(key) {
  const d = new Date(key + 'T00:00:00')
  const day = (d.getDay() + 6) % 7 // 周一=0
  d.setDate(d.getDate() - day)
  return dayKey(d)
}

// 最近 n 周按周聚合（周一开始）
export function weeklySeries(rows, nWeeks) {
  const thisWeek = weekStartKey(todayKey())
  const starts = []
  for (let i = nWeeks - 1; i >= 0; i--) starts.push(addDaysKey(thisWeek, -i * 7))
  const map = Object.fromEntries(starts.map((s) => [s, 0]))
  rows.forEach((x) => {
    const ws = weekStartKey(x.date)
    if (ws in map) map[ws] += x.actualSec / 60
  })
  return starts.map((s) => ({ weekStart: s, min: Math.round(map[s]) }))
}

// 各科占比
export function subjectBreakdown(rows, subjectStore) {
  const m = {}
  rows.forEach((x) => {
    m[x.subjectId] = (m[x.subjectId] || 0) + x.actualSec / 60
  })
  const total = Object.values(m).reduce((a, b) => a + b, 0)
  return Object.entries(m)
    .map(([id, min]) => ({
      subjectId: id,
      min,
      pct: total ? Math.round((min / total) * 100) : 0,
      name: subjectStore?.byId?.[id]?.name || '未分类',
      color: subjectStore?.byId?.[id]?.color || '#97a4b6',
    }))
    .sort((a, b) => b.min - a.min)
}

// 学习类型占比（听课/刷题/复盘/背诵/未标）
export function activityBreakdown(rows) {
  const m = {}
  rows.forEach((x) => {
    const k = x.activityType || 'none'
    m[k] = (m[k] || 0) + x.actualSec / 60
  })
  const total = Object.values(m).reduce((a, b) => a + b, 0)
  return Object.entries(m).map(([id, min]) => ({
    id,
    name: id === 'none' ? '未标类型' : ACTIVITY_MAP[id]?.name || '其他',
    color: id === 'none' ? '#97a4b6' : ACTIVITY_MAP[id]?.color || '#97a4b6',
    min,
    pct: total ? Math.round((min / total) * 100) : 0,
  })).sort((a, b) => b.min - a.min)
}

export function longestSec(rows) {
  return rows.reduce((m, x) => Math.max(m, x.actualSec || 0), 0)
}

// 全部记录中的最早日期
export function firstDate(sessions) {
  const dates = sessions.map((x) => x.date).filter(Boolean).sort()
  return dates[0] || todayKey()
}

// ===== 热力图网格 =====
// 年视图：周一对齐，返回若干列（每列 7 天，周一→周日）
export function buildYearWeeks(year, minMap) {
  const jan1 = dayKey(new Date(year, 0, 1))
  const ws = weekStartKey(jan1)
  const dec31 = dayKey(new Date(year, 11, 31))
  const today = todayKey()
  const weeks = []
  let cur = ws
  while (weeks.length <= 60) {
    const col = []
    for (let i = 0; i < 7; i++) {
      col.push({
        key: cur,
        min: Math.round(minMap[cur] || 0),
        inYear: cur.slice(0, 4) === String(year),
        future: cur > today,
      })
      cur = addDaysKey(cur, 1)
    }
    weeks.push(col)
    if (col[6].key >= dec31) break
  }
  return weeks
}

// 月份标签：每个月首次出现的列位置
export function monthLabels(weeks) {
  const labels = []
  let lastMonth = ''
  weeks.forEach((col, i) => {
    const cell = col.find((c) => c.inYear)
    if (!cell) return
    const m = cell.key.slice(5, 7)
    if (m !== lastMonth) {
      labels.push({ col: i, name: Number(m) + '月' })
      lastMonth = m
    }
  })
  return labels
}

// 月视图：返回若干列（同结构，组件展平后按 7 列日历排）
export function buildMonthWeeks(year, month, minMap) {
  const first = dayKey(new Date(year, month, 1))
  const ws = weekStartKey(first)
  const lastDay = dayKey(new Date(year, month + 1, 0))
  const today = todayKey()
  const weeks = []
  let cur = ws
  while (weeks.length <= 6) {
    const col = []
    for (let i = 0; i < 7; i++) {
      col.push({
        key: cur,
        min: Math.round(minMap[cur] || 0),
        inMonth: cur.slice(0, 7) === first.slice(0, 7),
        future: cur > today,
      })
      cur = addDaysKey(cur, 1)
    }
    weeks.push(col)
    if (col[6].key >= lastDay) break
  }
  return weeks
}

// 周视图：7 天（周一→周日）
export function buildWeekDays(weekStart, minMap) {
  const today = todayKey()
  const out = []
  for (let i = 0; i < 7; i++) {
    const k = addDaysKey(weekStart, i)
    out.push({ key: k, min: Math.round(minMap[k] || 0), future: k > today })
  }
  return out
}

// 某一天的各科明细
export function daySubjectDetail(sessions, date) {
  const m = {}
  sessions
    .filter((s) => (s.status === 'done' || s.status === 'quit') && s.date === date)
    .forEach((s) => {
      if (!m[s.subjectId]) m[s.subjectId] = 0
      m[s.subjectId] += s.actualSec / 60
    })
  return m
}

// 某一天的总时长（含 quit 保留的实际时长）
export function dayTotalMin(sessions, date) {
  return sessions
    .filter((s) => (s.status === 'done' || s.status === 'quit') && s.date === date)
    .reduce((a, s) => a + s.actualSec / 60, 0)
}

// 某一天的番茄数
export function dayCount(sessions, date) {
  return sessions.filter((s) => s.status === 'done' && s.date === date).length
}
