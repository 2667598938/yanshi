import { defineStore } from 'pinia'
import { dayKey, todayKey, calcStreak, lastNDays } from '../utils/date'
import { db, CUR_KEY, uid } from '../db'
import { enqueueRecord, enqueueDelete } from '../sync/engine'

let ticker = null

function loadCurrent() {
  try {
    return JSON.parse(localStorage.getItem(CUR_KEY)) || null
  } catch {
    return null
  }
}

// 模式：timer 倒计时（到点自动完成）；stopwatch 正向计时（无上限，手动结束）
// 状态：idle → focusing ⇄ paused；到点自动 done；手动可记 done / abort(不记录)
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
    todaySessions() {
      return this.doneSessions.filter((x) => x.date === todayKey())
    },
    todayMin() {
      return this.todaySessions.reduce((a, x) => a + x.actualSec / 60, 0)
    },
    todayCount() {
      return this.todaySessions.length
    },
    totalMin() {
      return this.doneSessions.reduce((a, x) => a + x.actualSec / 60, 0)
    },
    totalCount() {
      return this.doneSessions.length
    },
    longestSec() {
      return this.doneSessions.reduce((m, x) => Math.max(m, x.actualSec || 0), 0)
    },
    streak() {
      return calcStreak(new Set(this.doneSessions.map((x) => x.date)))
    },
    last30() {
      const days = lastNDays(30)
      const map = Object.fromEntries(days.map((d) => [d, 0]))
      this.doneSessions.forEach((x) => {
        if (x.date in map) map[x.date] += x.actualSec / 60
      })
      return days.map((d) => ({ date: d, min: Math.round(map[d]) }))
    },
    subjectMin() {
      const m = {}
      this.doneSessions.forEach((x) => {
        m[x.subjectId] = (m[x.subjectId] || 0) + x.actualSec / 60
      })
      return m
    },
    activeDaySet() {
      return new Set(this.doneSessions.map((x) => x.date))
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
        if (
          this.current &&
          !this.current.paused &&
          this.current.mode === 'timer' &&
          this.remainingSec <= 0
        ) {
          this.finish(true)
        }
      }, 500)
    },
    stopTicker() {
      if (ticker && !this.current) {
        clearInterval(ticker)
        ticker = null
      }
    },
    saveCurrent() {
      if (this.current) localStorage.setItem(CUR_KEY, JSON.stringify(this.current))
      else localStorage.removeItem(CUR_KEY)
    },
    resumeOnLoad() {
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
    // auto=true 到点自动完成（倒计时计满计划时长，避免忘关记成几小时）
    // note 为本颗番茄备注
    async finish(auto, note = '') {
      const c = this.current
      if (!c) return
      // 到点后 500ms ticker 可能在本函数 await 期间再次触发；先同步摘除当前计时并停表，
      // 保证一次专注只落库一次（避免重复进入导致同 id 再写 sessions 触发 Dexie 主键冲突）
      this.current = null
      this.saveCurrent()
      this.stopTicker()
      const actualSec =
        auto && c.mode === 'timer'
          ? c.plannedMin * 60
          : Math.max(
              0,
              Math.floor(
                ((c.paused ? c.pausedAt : Date.now()) - c.startedAt - c.pauseAccum) / 1000
              )
            )
      const endedAt = c.paused && !auto ? c.pausedAt : Date.now()
      const session = {
        id: c.id,
        subjectId: c.subjectId,
        mode: c.mode,
        activityType: c.activityType || '',
        plannedMin: c.plannedMin || 0,
        actualSec,
        status: 'done',
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
    // 放弃本颗，不写入记录
    abort() {
      if (!this.current) return
      this.current = null
      this.saveCurrent()
      this.stopTicker()
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
