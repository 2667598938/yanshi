import Dexie from 'dexie'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { db, activateAccount } from '../src/db'
import { useMistakesStore } from '../src/stores/mistakes'
import { afterLogin } from '../src/sync/account'
import { enqueueRecord } from '../src/sync/engine'

vi.mock('../src/sync/engine', () => ({
  enqueueRecord: vi.fn(), enqueueDelete: vi.fn(),
  initSyncForUser: vi.fn(), resetSyncRuntime: vi.fn(),
}))
beforeEach(async () => { await activateAccount(null) })
afterEach(async () => {
  const { useTimerStore } = await import('../src/stores/timer')
  useTimerStore().current = null
  useTimerStore().stopTicker()
  db.close()
  for (const name of await Dexie.getDatabaseNames()) await Dexie.delete(name)
  await activateAccount(null)
})

it('实际登录载入路径迁移旧日期，待复习可见并加入同步队列', async () => {
  await db.mistakes.put({ id: 'old', stage: 0, nextReviewAt: '2020-01-01', mastered: 0, history: ['keep'] })
  await afterLogin(21)
  const store = useMistakesStore()
  expect(store.loaded).toBe(true)
  expect(store.dueReview.map((x) => x.id)).toEqual(['old'])
  expect(store.list[0]).toMatchObject({ stage: 3, history: ['keep'] })
  expect(typeof (await db.mistakes.get('old')).nextReviewAt).toBe('number')
  expect(enqueueRecord).toHaveBeenCalledWith('mistakes', expect.objectContaining({ id: 'old', stage: 3 }))
})

it('强制刷新用于账号切换/云端拉取，保留 revision，迁移只发生一次', async () => {
  const store = useMistakesStore()
  await store.load()
  await db.mistakes.put({ id: 'cloud', stage: 2, nextReviewAt: '2020-01-01', _rev: 7, mastered: 0 })
  await store.load(true)
  expect(store.dueReview[0]).toMatchObject({ id: 'cloud', stage: 5, _rev: 7 })
  await store.load(true)
  expect(enqueueRecord).toHaveBeenCalledTimes(1)
})

it('旧已掌握记录不重新排期，新格式记录保持原值', async () => {
  const future = Date.now() + 86400000
  await db.mistakes.bulkPut([
    { id: 'mastered', stage: 5, mastered: 1, nextReviewAt: '2020-01-01' },
    { id: 'new', stage: 4, mastered: 0, nextReviewAt: future },
  ])
  await useMistakesStore().load(true)
  expect(await db.mistakes.get('mastered')).toMatchObject({ nextReviewAt: null, mastered: 1, stage: 8 })
  expect(await db.mistakes.get('new')).toMatchObject({ stage: 4, nextReviewAt: future })
  expect(useMistakesStore().dueReview).toHaveLength(0)
})
