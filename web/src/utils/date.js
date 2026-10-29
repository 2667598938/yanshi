// 学习业务日期统一 UTC+8，与后端 session、房间和 AI 摘要一致。
import { clockNow } from './clock'

// 本地日期 key：YYYY-MM-DD
export function dayKey(d = new Date()) {
  const cn = new Date(d.getTime() + 8 * 3600000)
  const y = cn.getUTCFullYear()
  const m = String(cn.getUTCMonth() + 1).padStart(2, '0')
  const day = String(cn.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function todayKey() {
  return dayKey(new Date(clockNow()))
}

// 两个日期 key 相差天数（b - a）
export function diffDayKeys(a, b) {
  const da = new Date(a + 'T00:00:00Z')
  const db = new Date(b + 'T00:00:00Z')
  return Math.round((db - da) / 86400000)
}

// 距目标日期还有多少个完整自然日（今天到目标日 0 点）
export function daysUntil(targetStr) {
  return diffDayKeys(todayKey(), targetStr)
}

// 取最近 n 天的日期 key（含今天，旧 -> 新）
export function lastNDays(n) {
  const arr = []
  const base = todayKey()
  for (let i = n - 1; i >= 0; i--) {
    arr.push(addDaysKey(base, -i))
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
  let cursor = todayKey()
  // 今天还没打卡时，从昨天起算（不中断已有 streak）
  if (!activeDaySet.has(cursor)) {
    cursor = addDaysKey(cursor, -1)
  }
  let streak = 0
  while (activeDaySet.has(cursor)) {
    streak++
    cursor = addDaysKey(cursor, -1)
  }
  return streak
}

// 星期几（中文）
export function weekLabel(d = new Date()) {
  return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][new Date(d.getTime()+8*3600000).getUTCDay()]
}

// 友好日期 M月D日
export function mdLabel(key) {
  return `${Number(key.slice(5,7))}月${Number(key.slice(8,10))}日`
}

// 日期 key 加 n 天
export function addDaysKey(key, n) {
  const d = new Date(key + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0,10)
}

// 今天加 n 天的 key
export function todayAddDays(n) {
  return addDaysKey(todayKey(), n)
}

// 中文完整日期：M月D日 周X
export function mdWeekLabel(key) {
  const d = new Date(key + 'T00:00:00Z')
  return `${mdLabel(key)} ${weekLabel(d)}`
}
