import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { db } from '../src/db'
import { syncApi } from '../src/api'
import { writeRecord, patchRecord, enqueueDelete, syncNow, syncState,
  resetSyncRuntime, initSyncForUser, resolveConflict } from '../src/sync/engine'

vi.mock('../src/api', () => ({ syncApi: { commands: vi.fn(), records: vi.fn() }, attachmentApi: {} }))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ isLoggedIn: true }) }))
vi.mock('../src/sync/community', () => ({ flushCommunity: vi.fn() }))
const ack = (changes) => ({ changed: changes.map((item) => ({
  id: item.id, record: item.record, revision: item.expectedRevision + 1,
})) })
beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
  vi.stubGlobal('document', { addEventListener: vi.fn() })
  await db.open()
  syncApi.records.mockResolvedValue({ records: [], cursor: 0 })
  syncApi.commands.mockImplementation(async (_id, changes) => ack(changes))
})
afterEach(async () => {
  resetSyncRuntime()
  vi.clearAllTimers()
  await db.delete()
})

it('响应丢失后使用同一个持久化 operationId 和相同命令重试', async () => {
  await writeRecord('tasks', { id: 't', title: 'pending' }, { create: true })
  syncApi.commands.mockRejectedValueOnce(new Error('response lost'))
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  expect(await syncNow()).toBe(false)
  const pending = await db.syncMeta.get('pendingLearningCommand')
  expect(pending.value.operationId).toBe(syncApi.commands.mock.calls[0][0])
  resetSyncRuntime()
  expect(await syncNow()).toBe(true)
  expect(syncApi.commands.mock.calls[1]).toEqual(syncApi.commands.mock.calls[0])
  expect(await db.outbox.count()).toBe(0)
  expect(await db.syncMeta.get('pendingLearningCommand')).toBeUndefined()
})

it('请求期间再次编辑，旧响应不覆盖新内容或删除新队列，并正确 rebase', async () => {
  await writeRecord('tasks', { id: 't', title: 'old' }, { create: true })
  let release
  syncApi.commands.mockImplementationOnce((_id, changes) => new Promise((resolve) => {
    release = () => resolve(ack(changes))
  }))
  const running = syncNow()
  await vi.waitFor(() => expect(release).toBeTypeOf('function'))
  await patchRecord('tasks', 't', { title: 'latest' })
  release()
  await running
  expect(await db.tasks.get('t')).toMatchObject({ title: 'latest', _rev: 1 })
  const pending = await db.outbox.where('recordId').equals('t').first()
  expect(pending).toMatchObject({ expectedRevision: 1, record: { title: 'latest' } })
  await syncNow()
  expect(await db.tasks.get('t')).toMatchObject({ title: 'latest', _rev: 2 })
  expect(await db.outbox.count()).toBe(0)
})

it('首次上传尚未返回时删除，仍发送基于已确认版本的墓碑', async () => {
  await writeRecord('tasks', { id: 't', title: 'delete during request' }, { create: true })
  let release
  syncApi.commands.mockImplementationOnce((_id, changes) => new Promise((resolve) => {
    release = () => resolve(ack(changes))
  }))
  const running = syncNow()
  await vi.waitFor(() => expect(release).toBeTypeOf('function'))
  await enqueueDelete('tasks', 't')
  release()
  await running
  expect(await db.tasks.get('t')).toBeUndefined()
  expect(await db.outbox.where('recordId').equals('t').first()).toMatchObject({ expectedRevision: 1, record: null })
  await syncNow()
  expect(syncApi.commands.mock.calls[1][1][0]).toMatchObject({ id: 't', expectedRevision: 1, record: null })
  expect(await db.outbox.count()).toBe(0)
})

it('冲突在刷新后仍保留，等待裁决时不会被云端覆盖', async () => {
  await writeRecord('tasks', { id: 't', title: 'local' }, { create: true })
  const cloud = { id: 't', type: 'task', title: 'cloud' }
  syncApi.commands.mockRejectedValueOnce({ code: 40902,
    data: { conflicts: [{ id: 't', revision: 2, record: cloud }] } })
  syncApi.records.mockResolvedValue({ records: [{ id: 't', revision: 2, record: cloud }], cursor: 2 })
  await syncNow()
  expect(syncState.pendingConflicts).toHaveLength(1)
  expect((await db.tasks.get('t')).title).toBe('local')
  resetSyncRuntime()
  await initSyncForUser()
  expect(syncState.pendingConflicts).toHaveLength(1)
  expect((await db.tasks.get('t')).title).toBe('local')
  await resolveConflict('t', 'cloud')
  expect((await db.tasks.get('t')).title).toBe('cloud')
  expect(await db.outbox.count()).toBe(0)
  expect(await db.syncMeta.get('conflict:t')).toBeUndefined()
})

it('冲突挂起后继续编辑，选择本机时保留最新本机内容', async () => {
  await writeRecord('tasks', { id: 't', title: 'local' }, { create: true })
  syncApi.commands.mockRejectedValueOnce({ code: 40902,
    data: { conflicts: [{ id: 't', revision: 3, record: { id: 't', type: 'task', title: 'cloud' } }] } })
  await syncNow()
  await patchRecord('tasks', 't', { title: 'newest local' })
  expect(await db.outbox.count()).toBe(0)
  await resolveConflict('t', 'local')
  expect(await db.outbox.where('recordId').equals('t').first()).toMatchObject({
    expectedRevision: 3, record: { title: 'newest local' },
  })
  await syncNow()
  expect(await db.tasks.get('t')).toMatchObject({ title: 'newest local', _rev: 4 })
})

it('使用服务端游标增量拉取，并应用删除墓碑', async () => {
  await db.tasks.put({ id: 't', title: 'remove', _rev: 1 })
  await db.syncMeta.put({ key: 'pullCursor', value: 12 })
  syncApi.records.mockResolvedValue({ records: [{ id: 't', record: null, revision: 2 }], cursor: 15 })
  await syncNow()
  expect(syncApi.records).toHaveBeenCalledWith({ since: 12 })
  expect(await db.tasks.get('t')).toBeUndefined()
  expect((await db.syncMeta.get('pullCursor')).value).toBe(15)
})
