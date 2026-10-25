import { defineStore } from 'pinia'
import { dayKey, todayKey, calcStreak, lastNDays } from '../utils/date'
import { db, currentKey, uid } from '../db'
import { enqueueRecord, enqueueDelete } from '../sync/engine'

let ticker = null
const MAX_FOCUS_SEC = 180 * 60          // 单颗上限 180 分钟
const MAX_PAUSE_MS = 30 * 60 * 1000    // 单次暂停上限 30 分钟

function loadCurrent() {
  try {
    return JSON.parse(localStorage.getItem(currentKey())) || null
  } catch {
    return null
  }
}

// 模式：timer 倒计时（到点自动完成）；stopwatch 正向计时（手动结束）
// 状态：idle → focusing ⇄ paused；180 分钟 / 暂停 30 分钟自动 quit；放弃保留实际时长
export const useTimerStore = defineStore('timer', {
  state: () => ({
    sessions: [],
    loaded: false,
    current: loadCurrent(),
    now: Date.now(),
    lastFinished: null, // { session, at, auto }
  }),

  getters: {
    isActive: (s) => !!s.current,
    isPaused: (s) => !!s.current?.paused,
    isStopwatch: (s) => s.current?.mode === 'stopwatch',

    elapsedSec(s) {
      if (!s.current) return 0
      const c = s.current
      const end = c.paused ? c.pausedAt : s.now
      return Math.max(0, Math.floor((end - c.startedAt - c.pauseAccum) / 1000))
    },
    plannedSec(s) {
      return s.current && s.current.mode === 'timer' ? s.current.plannedMin * 60 : 0
    },
    remainingSec() {
      if (this.isStopwatch) return 0
      return Math.max(0, this.plannedSec - this.elapsedSec)
    },
    progress() {
      if (this.isStopwatch) return 0
      return this.plannedSec ? Math.min(1, this.elapsedSec / this.plannedSec) : 0
    },

    doneSessions: (s) => s.sessions.filter((x) => x.status === 'done'),
    // 有效时长包含 done 与 quit（超时/放弃仍计入学习时长）
    effectiveSessions: (s) => s.sessions.filter((x) => x.status === 'done' || x.status === 'quit'),
    todaySessions() {
      return this.effectiveSessions.filter((x) => x.date === todayKey())
    },
    todayDone() {
      return this.doneSessions.filter((x) => x.date === todayKey())
    },
    todayMin() {
      return this.todaySessions.reduce((a, x) => a + x.actualSec / 60, 0)
    },
    todayCount() {
      return this.todayDone.length
    },
    totalMin() {
      return this.effectiveSessions.reduce((a, x) => a + x.actualSec / 60, 0)
    },
    totalCount() {
      return this.doneSessions.length
    },
    longestSec() {
      return this.effectiveSessions.reduce((m, x) => Math.max(m, x.actualSec || 0), 0)
    },
    streak() {
      return calcStreak(new Set(this.doneSessions.map((x) => x.date)))
    },
    last30() {
      const days = lastNDays(30)
      const map = Object.fromEntries(days.map((d) => [d, 0]))
      this.effectiveSessions.forEach((x) => {
        if (x.date in map) map[x.date] += x.actualSec / 60
      })
      return days.map((d) => ({ date: d, min: Math.round(map[d]) }))
    },
    subjectMin() {
      const m = {}
      this.effectiveSessions.forEach((x) => {
        m[x.subjectId] = (m[x.subjectId] || 0) + x.actualSec / 60
      })
      return m
    },
    activeDaySet() {
      return new Set(this.effectiveSessions.map((x) => x.date))
    },
  },

  actions: {
    async load() {
      if (this.loaded) return
      this.sessions = await db.sessions.toArray()
      this.loaded = true
    },
    ensureTicker() {
      if (ticker) return
      ticker = setInterval(() => {
        this.now = Date.now()
        this.checkLimits()
      }, 500)
    },
    // 统一结束判定：暂停超 30 分钟 quit；专注超 180 分钟 quit；倒计时到点 done
    checkLimits() {
      const c = this.current
      if (!c) return
      if (c.paused) {
        if (this.now - c.pausedAt >= MAX_PAUSE_MS) this.finish(false, '', 'pause_timeout')
        return
      }
      if (this.elapsedSec >= MAX_FOCUS_SEC) {
        this.finish(false, '', 'timeout')
        return
      }
      if (c.mode === 'timer' && this.remainingSec <= 0) this.finish(true)
    },
    stopTicker() {
      if (ticker && !this.current) {
        clearInterval(ticker)
        ticker = null
      }
    },
    saveCurrent() {
      if (this.current) localStorage.setItem(currentKey(), JSON.stringify(this.current))
      else localStorage.removeItem(currentKey())
    },
    resumeOnLoad() {
      this.current = loadCurrent()
      if (this.current) {
        this.ensureTicker()
        this.checkLimits() // 息屏/挂起恢复后立即校正
      }
    },
    // 切换账号后重建计时状态（每个账号的进行中番茄互不影响）
    resetForAccount() {
      if (ticker) {
        clearInterval(ticker)
        ticker = null
      }
      this.sessions = []
      this.loaded = false
      this.lastFinished = null
      this.current = loadCurrent()
      this.now = Date.now()
      if (this.current) this.ensureTicker()
    },

    start({ subjectId, mode = 'timer', plannedMin = 25, activityType = '' }) {
      if (this.current) return
      this.current = {
        id: uid('s_'),
        subjectId,
        mode,
        activityType,
        plannedMin: mode === 'stopwatch' ? 0 : plannedMin,
        startedAt: Date.now(),
        pauseAccum: 0,
        pausedAt: null,
        paused: false,
      }
      this.now = Date.now()
      this.saveCurrent()
      this.ensureTicker()
    },
    pause() {
      if (this.current && !this.current.paused) {
        this.current.paused = true
        this.current.pausedAt = Date.now()
        this.saveCurrent()
      }
    },
    resume() {
      if (this.current && this.current.paused) {
        this.current.pauseAccum += Date.now() - this.current.pausedAt
        this.current.paused = false
        this.current.pausedAt = null
        this.now = Date.now()
        this.saveCurrent()
      }
    },
    // auto=true 到点自动完成；reason: completed | timeout | pause_timeout | abandoned
    // note 为本颗番茄备注
    async finish(auto, note = '', reason = 'completed') {
      const c = this.current
      if (!c) return
      // 到点后 500ms ticker 可能在本函数 await 期间再次触发；先同步摘除当前计时并停表，
      // 保证一次专注只落库一次（避免重复进入导致同 id 再写 sessions 触发 Dexie 主键冲突）
      this.current = null
      this.saveCurrent()
      this.stopTicker()
      const rawSec = Math.max(
        0,
        Math.floor(
          ((c.paused ? c.pausedAt : Date.now()) - c.startedAt - c.pauseAccum) / 1000
        )
      )
      let actualSec = rawSec
      if (auto && c.mode === 'timer') actualSec = c.plannedMin * 60
      // 规则：真实时长封顶 180 分钟；超时/暂停超时/放弃均记为 quit
      actualSec = Math.min(actualSec, MAX_FOCUS_SEC)
      const status = ['timeout', 'pause_timeout', 'abandoned'].includes(reason) ? 'quit' : 'done'
      const endedAt = c.paused && !auto ? c.pausedAt : Date.now()
      const session = {
        id: c.id,
        subjectId: c.subjectId,
        mode: c.mode,
        activityType: c.activityType || '',
        plannedMin: c.plannedMin || 0,
        actualSec,
        status,
        end_reason: reason,
        startedAt: c.startedAt,
        endedAt,
        date: dayKey(new Date(c.startedAt)), // 跨零点按开始时刻归日
        note: (note || '').trim(),
        createdAt: endedAt,
      }
      let duplicated = false
      await db.sessions.add(session).catch((e) => {
        // 极端情况下同 id 已存在（不应发生，摘除已防重入），则不重复入队
        if (e?.name === 'ConstraintError') duplicated = true
        else throw e
      })
      if (!duplicated) {
        this.sessions.push(session)
        await enqueueRecord('sessions', session)
      }
      this.lastFinished = { session, at: Date.now(), auto: !!auto }
      return session
    },
    // 放弃本颗：保留实际专注时长，记为 quit（不再直接丢弃）
    async abort() {
      if (!this.current) return null
      return this.finish(false, '', 'abandoned')
    },
    async removeSession(id) {
      await enqueueDelete('sessions', id)
      this.sessions = this.sessions.filter((x) => x.id !== id)
    },
    async updateSession(id, patch) {
      await db.sessions.update(id, patch)
      const i = this.sessions.findIndex((x) => x.id === id)
      if (i >= 0) {
        this.sessions[i] = { ...this.sessions[i], ...patch }
        await enqueueRecord('sessions', this.sessions[i])
      }
    },
    async clearAll() {
      await db.sessions.clear()
      this.sessions = []
      this.current = null
      this.lastFinished = null
      this.saveCurrent()
      this.stopTicker()
    },
  },
})
