import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { db, currentKey } from '../src/db'
import { useTimerStore } from '../src/stores/timer'

vi.mock('../src/sync/engine', () => ({ enqueueRecord: vi.fn(), enqueueDelete: vi.fn() }))
const base = 1767268800000
let timer
beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(base)
  await db.open()
  timer = useTimerStore()
})
afterEach(async () => {
  timer.current = null
  timer.stopTicker()
  await db.delete()
})
const atMinute = (n) => vi.setSystemTime(base + n * 60000)

it('25 分钟有效专注和 10 分钟暂停序列化一致', async () => {
  timer.start({ subjectId: 'math', mode: 'stopwatch' })
  atMinute(10); timer.pause()
  atMinute(20); timer.resume()
  atMinute(35)
  const result = await timer.finish(false)
  expect(result.actualSec).toBe(1500)
  expect(result.pauseAccum).toBe(600000)
  expect(result.maxPauseMs).toBe(600000)
  expect((result.endedAt - result.startedAt - result.pauseAccum) / 1000).toBe(1500)
})

it('多次暂停累计 35 分钟，每次小于 30 分钟仍正常完成', async () => {
  timer.start({ subjectId: 'math', mode: 'stopwatch' })
  atMinute(5); timer.pause()
  atMinute(15); timer.resume()
  atMinute(20); timer.pause()
  atMinute(45); timer.resume()
  atMinute(50)
  const result = await timer.finish(false)
  expect(result.status).toBe('done')
  expect(result.actualSec).toBe(900)
  expect(result.pauseAccum).toBe(35 * 60000)
  expect(result.maxPauseMs).toBe(25 * 60000)
})

it('后台暂停超过上限直接恢复也会判为暂停超时', async () => {
  timer.start({ subjectId: 'math', mode: 'stopwatch' })
  atMinute(5); timer.pause()
  atMinute(36)
  const result = await timer.resume()
  expect(result.status).toBe('quit')
  expect(result.end_reason).toBe('pause_timeout')
  expect(result.actualSec).toBe(300)
  expect(result.maxPauseMs).toBe(31 * 60000)
})

it('暂停中手动结束不计入尚未恢复的暂停', async () => {
  timer.start({ subjectId: 'math', mode: 'stopwatch' })
  atMinute(5); timer.pause()
  atMinute(15)
  const result = await timer.finish(false)
  expect(result.actualSec).toBe(300)
  expect(result.endedAt).toBe(base + 5 * 60000)
  expect(result.pauseAccum).toBe(0)
})

it('倒计时挂起 5 小时后按先到的 25 分钟完成时刻落库', async () => {
  timer.start({ subjectId: 'math', plannedMin: 25 })
  atMinute(300)
  timer.resumeOnLoad()
  await vi.waitFor(() => expect(timer.lastFinished).not.toBeNull())
  expect(timer.lastFinished.session.actualSec).toBe(1500)
  expect(timer.lastFinished.session.status).toBe('done')
  expect(timer.lastFinished.session.endedAt).toBe(base + 25 * 60000)
  expect(localStorage.getItem(currentKey())).toBeNull()
})

it('180 分钟倒计时到计划时长按正常完成结算', async () => {
  timer.start({ subjectId: 'math', mode: 'timer', plannedMin: 180 })
  atMinute(180)
  timer.now = Date.now()
  timer.checkLimits()
  await vi.waitFor(() => expect(timer.lastFinished).not.toBeNull())
  expect(timer.lastFinished.session).toMatchObject({
    actualSec: 10800,
    status: 'done',
    plannedMin: 180,
  })
  expect(timer.lastFinished.session.end_reason).not.toBe('timeout')
})

it('正向计时超 180 分钟和主动放弃保留时长', async () => {
  timer.start({ subjectId: 'math', mode: 'stopwatch' })
  atMinute(181); timer.now = Date.now(); timer.checkLimits()
  await vi.waitFor(() => expect(timer.lastFinished).not.toBeNull())
  expect(timer.lastFinished.session).toMatchObject({ actualSec: 10800, status: 'quit', end_reason: 'timeout' })
  timer.start({ subjectId: 'math', mode: 'stopwatch' })
  vi.setSystemTime(Date.now() + 5 * 60000)
  expect(await timer.abort()).toMatchObject({ actualSec: 300, status: 'quit', end_reason: 'abandoned' })
})
