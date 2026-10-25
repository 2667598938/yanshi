import { defineStore } from 'pinia'
import { dayKey, todayKey, calcStreak, lastNDays } from '../utils/date'
import { db, currentKey, uid } from '../db'
import { enqueueRecord, enqueueDelete } from '../sync/engine'
import { useLearningSettingsStore } from './learningSettings'
import { clockNow } from '../utils/clock'

let ticker = null
let pendingSave = Promise.resolve()
export async function waitForTimerPersistence() {
  await pendingSave.catch(() => {})
}
const MAX_FOCUS_SEC = 180 * 60          // 单颗上限 180 分钟
const MAX_PAUSE_MS = 30 * 60 * 1000    // 单次暂停上限 30 分钟

function loadCurrent() {
  try {
    return JSON.parse(localStorage.getItem(currentKey())) || null
  } catch {
    return null
  }
}

function loadCycle() {
  try {
    const value = JSON.parse(localStorage.getItem(`${currentKey()}:cycle`))
    return { rest: value?.rest || null, cycleCount: Math.max(0, Number(value?.cycleCount) || 0) }
  } catch { return { rest: null, cycleCount: 0 } }
}

// 模式：timer 倒计时（到点自动完成）；stopwatch 正向计时（手动结束）
// 状态：idle → focusing ⇄ paused；180 分钟 / 暂停 30 分钟自动 quit；放弃保留实际时长
export const useTimerStore = defineStore('timer', {
  state: () => ({
    sessions: [],
    loaded: false,
    current: loadCurrent(),
    now: clockNow(),
    lastFinished: null, // { session, at, auto }
    ...loadCycle(),
    persisting: false,
  }),

  getters: {
    isActive: (s) => !!s.current || !!s.rest,
    isResting: (s) => !!s.rest,
    restRemainingSec: (s) => s.rest ? Math.max(0, Math.ceil((s.rest.startedAt + s.rest.plannedSec * 1000 - s.now) / 1000)) : 0,
    contentHistory: (s) => [...new Set([...s.sessions].reverse().map((row) => row.learningContent).filter(Boolean))].slice(0, 50),
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
        this.now = clockNow()
        this.checkLimits()
      }, 500)
    },
    // 统一结束判定：暂停超 30 分钟 quit；专注超 180 分钟 quit；倒计时到点 done
    checkLimits() {
      if (this.rest) {
        if (this.restRemainingSec === 0 && !this.rest.finished) {
          this.rest.finished = true
          this.saveCycle()
          this.stopTicker()
        }
        return
      }
      const c = this.current
      if (!c) return
      if (c.paused) {
        if (this.now - c.pausedAt >= MAX_PAUSE_MS) this.finish(false, '', 'pause_timeout')
        return
      }
      // 恢复后台计时：按先到的边界结算；25 分钟倒计时早于 180 分钟上限。
      if (c.mode === 'timer' && this.plannedSec < MAX_FOCUS_SEC && this.remainingSec <= 0) {
        this.finish(true)
        return
      }
      if (this.elapsedSec >= MAX_FOCUS_SEC) {
        this.finish(false, '', 'timeout')
        return
      }
      if (c.mode === 'timer' && this.remainingSec <= 0) this.finish(true)
    },
    stopTicker() {
      if (ticker && !this.current && (!this.rest || this.rest.finished)) {
        clearInterval(ticker)
        ticker = null
      }
    },
    saveCurrent() {
      if (this.current) localStorage.setItem(currentKey(), JSON.stringify(this.current))
      else localStorage.removeItem(currentKey())
    },
    saveCycle() {
      localStorage.setItem(`${currentKey()}:cycle`, JSON.stringify({ rest: this.rest, cycleCount: this.cycleCount }))
    },
    startRest(previous) {
      const settings = useLearningSettingsStore().value
      const long = this.cycleCount % settings.longBreakEvery === 0
      this.rest = { kind: long ? 'long' : 'short', startedAt: clockNow(), finished: false,
        plannedSec: (long ? settings.longBreakMin : settings.shortBreakMin) * 60,
        nextFocus: { subjectId: previous.subjectId, mode: previous.mode,
          activityType: previous.activityType, learningContent: previous.learningContent || '' } }
      this.now = clockNow()
      this.saveCycle()
      this.ensureTicker()
    },
    endRest() {
      this.rest = null
      this.saveCycle()
      this.stopTicker()
    },
    startNext() {
      if (!this.rest?.finished) return
      const next = { ...this.rest.nextFocus, plannedMin: useLearningSettingsStore().value.focusMin }
      this.endRest()
      this.start(next)
    },
    resumeOnLoad() {
      this.current = loadCurrent()
      Object.assign(this, loadCycle())
      this.now = clockNow()
      if (this.current) {
        this.ensureTicker()
        this.checkLimits() // 息屏/挂起恢复后立即校正
      }
      if (this.rest && !this.rest.finished) { this.ensureTicker(); this.checkLimits() }
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
      Object.assign(this, loadCycle())
      this.now = clockNow()
      if (this.current) this.ensureTicker()
      if (this.rest && !this.rest.finished) { this.ensureTicker(); this.checkLimits() }
    },

    start({ subjectId, mode = 'timer', plannedMin = 25, activityType = '', learningContent = '', taskId = null }) {
      if (this.current || this.rest || this.persisting) return
      this.current = {
        id: uid('s_'),
        subjectId,
        mode,
        activityType,
        learningContent: String(learningContent).trim().slice(0, 100),
        taskId,
        plannedMin: mode === 'stopwatch' ? 0 : plannedMin,
        startedAt: clockNow(),
        pauseAccum: 0,
        maxPauseMs: 0,
        pausedAt: null,
        paused: false,
      }
      this.now = clockNow()
      this.saveCurrent()
      this.ensureTicker()
    },
    pause() {
      if (this.current && !this.current.paused) {
        this.current.paused = true
        this.current.pausedAt = clockNow()
        this.saveCurrent()
      }
    },
    resume() {
      if (this.current && this.current.paused) {
        const pauseMs = Math.max(0, clockNow() - this.current.pausedAt)
        if (pauseMs >= MAX_PAUSE_MS) return this.finish(false, '', 'pause_timeout')
        this.current.pauseAccum += pauseMs
        this.current.maxPauseMs = Math.max(this.current.maxPauseMs || 0, pauseMs)
        this.current.paused = false
        this.current.pausedAt = null
        this.now = clockNow()
        this.saveCurrent()
      }
    },
    // auto=true 到点自动完成；reason: completed | timeout | pause_timeout | abandoned
    // note 为本颗番茄备注
    async finish(auto, note = '', reason = 'completed') {
      const c = this.current
      if (!c || this.persisting) return
      this.persisting = true
      // 到点后 500ms ticker 可能在本函数 await 期间再次触发；先同步摘除当前计时并停表，
      // 保证一次专注只落库一次（避免重复进入导致同 id 再写 sessions 触发 Dexie 主键冲突）
      this.current = null
      this.saveCurrent()
      this.stopTicker()
      const rawSec = Math.max(
        0,
        Math.floor(
          ((c.paused ? c.pausedAt : clockNow()) - c.startedAt - c.pauseAccum) / 1000
        )
      )
      let actualSec = rawSec
      if (auto && c.mode === 'timer') actualSec = c.plannedMin * 60
      // 规则：真实时长封顶 180 分钟；超时/暂停超时/放弃均记为 quit
      actualSec = Math.min(actualSec, MAX_FOCUS_SEC)
      const status = ['timeout', 'pause_timeout', 'abandoned'].includes(reason) ? 'quit' : 'done'
      // 倒计时在挂起后恢复时仍以原定完成时刻结算，避免回拉重算为挂起时长。
      const endedAt = auto && c.mode === 'timer'
        ? c.startedAt + (c.pauseAccum || 0) + actualSec * 1000
        : c.paused ? c.pausedAt : clockNow()
      const session = {
        id: c.id,
        subjectId: c.subjectId,
        mode: c.mode,
        activityType: c.activityType || '',
        learningContent: c.learningContent || '',
        taskId: c.taskId || null,
        plannedMin: c.plannedMin || 0,
        actualSec,
        status,
        end_reason: reason,
        startedAt: c.startedAt,
        endedAt,
        pauseAccum: c.pauseAccum || 0, // 毫秒，累计已恢复的暂停，用于时长扣减
        maxPauseMs: Math.max(c.maxPauseMs || 0,
          c.paused ? Math.max(0, clockNow() - c.pausedAt) : 0),
        date: dayKey(new Date(c.startedAt)), // 跨零点按开始时刻归日
        note: (note || '').trim(),
        createdAt: endedAt,
      }
      let duplicated = false
      pendingSave = db.transaction('rw', db.sessions, db.outbox, db.syncMeta, async () => {
        await db.sessions.add(session)
        await enqueueRecord('sessions', session)
      })
      await pendingSave.catch((e) => {
        // 极端情况下同 id 已存在（不应发生，摘除已防重入），则不重复入队
        if (e?.name === 'ConstraintError') duplicated = true
        else {
          this.current = c
          this.saveCurrent()
          this.ensureTicker()
          this.persisting = false
          throw e
        }
      })
      if (!duplicated) {
        this.sessions.push(session)
        if (status === 'done' && actualSec > 0) {
          this.cycleCount += 1
          this.startRest(c)
        } else if (status === 'quit') {
          this.cycleCount = 0
          this.saveCycle()
        }
      }
      this.lastFinished = { session, at: clockNow(), auto: !!auto }
      this.persisting = false
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
      const { patchRecord } = await import('../sync/engine')
      const row = await patchRecord('sessions', id, patch)
      const i = this.sessions.findIndex((x) => x.id === id)
      if (i >= 0) {
        if (row) this.sessions[i] = row
      }
    },
    async clearAll() {
      await db.sessions.clear()
      this.sessions = []
      this.current = null
      this.rest = null
      this.cycleCount = 0
      this.saveCycle()
      this.lastFinished = null
      this.saveCurrent()
      this.stopTicker()
    },
  },
})
