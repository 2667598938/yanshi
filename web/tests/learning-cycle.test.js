import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { db } from '../src/db'
import { useTimerStore } from '../src/stores/timer'
import { useLearningSettingsStore } from '../src/stores/learningSettings'
import { filterSessions, contentBreakdown, periodBounds } from '../src/utils/stats'
vi.mock('../src/sync/engine', () => ({ enqueueRecord: vi.fn(), enqueueDelete: vi.fn(), writeRecord: vi.fn() }))
const base = 1700000000000
let timer
beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(base)
  await db.open()
  timer = useTimerStore()
})
afterEach(async () => { timer.current = null; timer.rest = null; timer.stopTicker(); await db.delete() })

it('按自定义间隔进入短休/长休，休息不计学习记录且不自动开始下一次', async () => {
  useLearningSettingsStore().value = { focusMin: 25, shortBreakMin: 2, longBreakMin: 7, longBreakEvery: 2 }
  timer.start({ subjectId: 'math', learningContent: '第三章', plannedMin: 25 })
  vi.setSystemTime(base + 25 * 60000)
  await timer.finish(true)
  expect(timer.rest).toMatchObject({ kind: 'short', plannedSec: 120 })
  expect(timer.sessions).toHaveLength(1)
  vi.setSystemTime(base + 60 * 60000); timer.now = Date.now(); timer.checkLimits()
  expect(timer.rest.finished).toBe(true)
  expect(timer.current).toBeNull()
  vi.setSystemTime(base + 90 * 60000); timer.now = Date.now(); timer.checkLimits()
  expect(timer.current).toBeNull()
  timer.startNext()
  expect(timer.current).toMatchObject({ learningContent: '第三章', plannedMin: 25 })
  vi.setSystemTime(base + 115 * 60000)
  await timer.finish(true)
  expect(timer.rest).toMatchObject({ kind: 'long', plannedSec: 420 })
  expect(await db.sessions.count()).toBe(2)
})

it('休息刷新恢复，不因后台归零产生学习时长', async () => {
  timer.start({ subjectId: 'math', mode: 'stopwatch' })
  vi.setSystemTime(base + 60000)
  await timer.finish(false)
  expect(timer.rest).not.toBeNull()
  vi.setSystemTime(base + 3600000)
  timer.resetForAccount()
  expect(timer.rest.finished).toBe(true)
  expect(timer.current).toBeNull()
  expect(await db.sessions.count()).toBe(1)
})

it('自由内容和关联任务持久化，历史候选去重', async () => {
  timer.start({ subjectId: 'math', learningContent: ' 高数题 ', taskId: 'task-one', mode: 'stopwatch' })
  vi.setSystemTime(base + 60000)
  const result = await timer.finish(false)
  expect(result).toMatchObject({ learningContent: '高数题', taskId: 'task-one' })
  expect(timer.contentHistory).toEqual(['高数题'])
})

it('日周月年范围与内容占比按秒求和，包含quit、排除无效状态', () => {
  expect(periodBounds('week', '2026-10-25')).toEqual({ start: '2026-10-19', end: '2026-10-25' })
  expect(periodBounds('month', '2024-02-20')).toEqual({ start: '2024-02-01', end: '2024-02-29' })
  expect(periodBounds('year', '2026-10-25')).toEqual({ start: '2026-01-01', end: '2026-12-31' })
  const rows = filterSessions([
    { date: '2026-10-25', status: 'done', actualSec: 120, learningContent: '高数' },
    { date: '2026-10-25', status: 'quit', actualSec: 60, learningContent: '英语' },
    { date: '2026-10-24', status: 'done', actualSec: 300, learningContent: '高数' },
    { date: '2026-10-25', status: 'invalid', actualSec: 300, learningContent: '错误' },
  ], periodBounds('day', '2026-10-25'))
  const parts = contentBreakdown(rows)
  expect(parts.map((row) => row.sec)).toEqual([120, 60])
  expect(parts.reduce((sum, row) => sum + row.pct, 0)).toBeCloseTo(100)
})
