import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { db } from '../src/db'
import { syncApi, attachmentApi } from '../src/api'
import { enqueueRecord, syncNow, resetSyncRuntime } from '../src/sync/engine'
import { useMistakesStore } from '../src/stores/mistakes'

vi.mock('../src/api', () => ({
  syncApi: { commands: vi.fn(), records: vi.fn() },
  attachmentApi: { uploadImage: vi.fn() },
}))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ isLoggedIn: true }) }))
vi.mock('../src/sync/community', () => ({ flushCommunity: vi.fn() }))
beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  await db.open()
  syncApi.commands.mockResolvedValue({ changed: [] })
  syncApi.records.mockResolvedValue({ records: [] })
})
afterEach(async () => {
  resetSyncRuntime()
  vi.clearAllTimers()
  await db.delete()
})

it('图片失败时保留队列并阻止不完整记录推送/回拉覆盖；重试后整条同步', async () => {
  const row = { id: 'm', images: [new Blob(['q']), new Blob(['q2'])], answerImages: [new Blob(['a'])] }
  await db.mistakes.add(row)
  await enqueueRecord('mistakes', row)
  attachmentApi.uploadImage.mockRejectedValue(new Error('offline'))
  syncApi.records.mockResolvedValue({ records: [{ id: 'm', revision: 1,
    record: { id: 'm', type: 'mistake', images: [], answerImages: [] } }] })
  expect(await syncNow()).toBe(true)
  expect(syncApi.commands).not.toHaveBeenCalled()
  expect(await db.outbox.count()).toBe(1)
  expect((await db.mistakes.get('m')).images).toHaveLength(2)
  attachmentApi.uploadImage.mockResolvedValueOnce({ key: 'key/q' })
    .mockResolvedValueOnce({ key: 'key/q2' }).mockResolvedValueOnce({ key: 'key/a' })
  syncApi.commands.mockImplementation(async (_operationId, changes) => ({
    changed: changes.map((change) => ({ ...change, revision: 2 })),
  }))
  expect(await syncNow()).toBe(true)
  const record = syncApi.commands.mock.calls[0][1][0].record
  expect(record.images).toEqual(['key/q', 'key/q2'])
  expect(record.answerImages).toEqual(['key/a'])
  expect(await db.outbox.count()).toBe(0)
})

it('云端拉取旧错题后实际刷新路径完成迁移并按当前 revision 入队', async () => {
  syncApi.records.mockResolvedValue({ records: [{ id: 'old-cloud', revision: 4,
    record: { id: 'old-cloud', type: 'mistake', stage: 1, mastered: 0, nextReviewAt: '2020-01-01' } }] })
  expect(await syncNow()).toBe(true)
  const row = await db.mistakes.get('old-cloud')
  expect(row).toMatchObject({ stage: 4, _rev: 4 })
  expect(typeof row.nextReviewAt).toBe('number')
  expect(useMistakesStore().dueReview.map((x) => x.id)).toEqual(['old-cloud'])
  const pending = await db.outbox.where('recordId').equals('old-cloud').first()
  expect(pending.expectedRevision).toBe(4)
})

it('实际错题 store 保存后原子入队，题图和解析图补传完成再同步', async () => {
  const row = await useMistakesStore().add(reactive({ content: '收录按钮回归', tags: ['真题'],
    images: [new Blob(['q1']), new Blob(['q2'])], answerImages: [new Blob(['a'])] }))
  expect(await db.mistakes.count()).toBe(1)
  expect(await db.outbox.count()).toBe(1)
  attachmentApi.uploadImage.mockResolvedValueOnce({ key: 'key/q1' })
    .mockResolvedValueOnce({ key: 'key/q2' }).mockResolvedValueOnce({ key: 'key/a' })
  syncApi.commands.mockImplementation(async (_op, changes) => ({
    changed: changes.map((change) => ({ ...change, revision: 1 })),
  }))
  expect(await syncNow()).toBe(true)
  expect(await db.mistakes.get(row.id)).toMatchObject({
    tags: ['真题'], images: ['key/q1', 'key/q2'], answerImages: ['key/a'], _rev: 1,
  })
  expect(await db.outbox.count()).toBe(0)
})

it('实际 outbox 写入失败时错题新增也回滚，重试不会重复收录', async () => {
  const fail = () => { throw new Error('outbox unavailable') }
  db.outbox.hook('creating', fail)
  try {
    await expect(useMistakesStore().add({ content: '原子写入' })).rejects.toThrow('outbox unavailable')
  } finally {
    db.outbox.hook('creating').unsubscribe(fail)
  }
  expect(await db.mistakes.count()).toBe(0)
  expect(await db.outbox.count()).toBe(0)
  expect(useMistakesStore().list).toHaveLength(0)
  await useMistakesStore().add({ content: '原子写入' })
  expect(await db.mistakes.count()).toBe(1)
  expect(await db.outbox.count()).toBe(1)
})
