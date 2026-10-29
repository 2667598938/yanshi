import { afterEach, expect, it, vi } from 'vitest'
import { calibrateClock, clockNow, resetClockAnchor } from '../src/utils/clock'
afterEach(resetClockAnchor)

it('校准后修改系统时间不会改变有效计时，使用单调时钟推进', () => {
  let monotonic = 100
  vi.stubGlobal('performance', { now: () => monotonic })
  vi.spyOn(Date, 'now').mockReturnValue(1000000)
  calibrateClock(2000000)
  vi.spyOn(Date, 'now').mockReturnValue(999999999)
  monotonic += 5000
  expect(clockNow()).toBe(2005000)
})

it('刷新后先用设备校正偏差，联网后重新校准', () => {
  vi.spyOn(Date, 'now').mockReturnValue(1000000)
  calibrateClock(1005000)
  resetClockAnchor()
  expect(clockNow()).toBe(1005000)
  calibrateClock(1007000)
  expect(clockNow()).toBeCloseTo(1007000, -1)
})
