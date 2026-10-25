import Dexie from 'dexie'
import { reactive } from 'vue'
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

it('实际表单传入的响应式标签和两类图片可保存到 IndexedDB', async () => {
  const payload = reactive({ content: '图片同步测试', tags: ['真题'],
    images: [new Blob(['question'])], answerImages: [new Blob(['answer'])] })
  const row = await useMistakesStore().add(payload)
  const saved = await db.mistakes.get(row.id)
  expect(saved.tags).toEqual(['真题'])
  expect(await saved.images[0].text()).toBe('question')
  expect(await saved.answerImages[0].text()).toBe('answer')
  expect(enqueueRecord).toHaveBeenCalledWith('mistakes', expect.objectContaining({ id: row.id }))
})

it('编辑时响应式数组也可写入，保留原记录而不重复新增', async () => {
  const store = useMistakesStore()
  const row = await store.add({ content: '原记录' })
  await store.update(row.id, reactive({ tags: ['高频'], images: [new Blob(['new'])], content: '已修改' }))
  const saved = await db.mistakes.get(row.id)
  expect(saved).toMatchObject({ content: '已修改', tags: ['高频'] })
  expect(await saved.images[0].text()).toBe('new')
  expect(await db.mistakes.count()).toBe(1)
})

it('已有复习历史的响应式记录可连续复习并保存历史', async () => {
  const store = useMistakesStore()
  const row = await store.add({ content: '复习' })
  await store.review(row.id, true)
  await store.review(row.id, false)
  const saved = await db.mistakes.get(row.id)
  expect(saved.history).toHaveLength(2)
  expect(saved.history.map((entry) => entry.remembered)).toEqual([true, false])
})

it('入队失败时新增整体回滚，重试只保存一条', async () => {
  const store = useMistakesStore()
  enqueueRecord.mockRejectedValueOnce(new Error('queue full'))
  await expect(store.add({ content: '重试' })).rejects.toThrow('queue full')
  expect(await db.mistakes.count()).toBe(0)
  expect(store.list).toHaveLength(0)
  await store.add({ content: '重试' })
  expect(await db.mistakes.count()).toBe(1)
})

it('编辑入队失败时原始内容仍在，内存与数据库保持一致', async () => {
  const store = useMistakesStore()
  const row = await store.add({ content: '原始内容' })
  enqueueRecord.mockRejectedValueOnce(new Error('queue full'))
  await expect(store.update(row.id, { content: '新内容' })).rejects.toThrow('queue full')
  expect((await db.mistakes.get(row.id)).content).toBe('原始内容')
  expect(store.list[0].content).toBe('原始内容')
})
