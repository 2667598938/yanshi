// 日期与计时工具（统一按本地时区，避免 UTC 跨零点问题）

// 本地日期 key：YYYY-MM-DD
export function dayKey(d = new Date()) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayKey() {
  return dayKey(new Date())
}

// 两个日期 key 相差天数（b - a）
export function diffDayKeys(a, b) {
  const da = new Date(a + 'T00:00:00')
  const db = new Date(b + 'T00:00:00')
  return Math.round((db - da) / 86400000)
}

// 距目标日期还有多少个完整自然日（今天到目标日 0 点）
export function daysUntil(targetStr) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(targetStr + 'T00:00:00')
  return Math.round((target - today) / 86400000)
}

// 取最近 n 天的日期 key（含今天，旧 -> 新）
export function lastNDays(n) {
  const arr = []
  const base = new Date()
  base.setHours(0, 0, 0, 0)
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(base - i * 86400000)
    arr.push(dayKey(d))
  }
  return arr
}

// 秒 -> mm:ss 或 hh:mm:ss
export function fmtClock(totalSec) {
  const s = Math.max(0, Math.floor(totalSec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(sec).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

// 分钟 -> "x小时y分"
export function fmtMinutes(min) {
  const m = Math.round(min)
  if (m < 60) return `${m} 分钟`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest === 0 ? `${h} 小时` : `${h} 小时 ${rest} 分`
}

// 计算连续打卡天数：给定有记录的日期 key 集合，从今天（或昨天）向前连续
export function calcStreak(activeDaySet) {
  let cursor = new Date()
  cursor.setHours(0, 0, 0, 0)
  // 今天还没打卡时，从昨天起算（不中断已有 streak）
  if (!activeDaySet.has(dayKey(cursor))) {
    cursor = new Date(cursor - 86400000)
  }
  let streak = 0
  while (activeDaySet.has(dayKey(cursor))) {
    streak++
    cursor = new Date(cursor - 86400000)
  }
  return streak
}

// 星期几（中文）
export function weekLabel(d = new Date()) {
  return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
}

// 友好日期 M月D日
export function mdLabel(key) {
  const d = new Date(key + 'T00:00:00')
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

// 日期 key 加 n 天
export function addDaysKey(key, n) {
  const d = new Date(key + 'T00:00:00')
  d.setDate(d.getDate() + n)
  return dayKey(d)
}

// 今天加 n 天的 key
export function todayAddDays(n) {
  return addDaysKey(dayKey(new Date()), n)
}

// 中文完整日期：M月D日 周X
export function mdWeekLabel(key) {
  const d = new Date(key + 'T00:00:00')
  return `${d.getMonth() + 1}月${d.getDate()}日 ${weekLabel(d)}`
}
