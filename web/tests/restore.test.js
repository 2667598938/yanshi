import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { db } from '../src/db'
import { restoreBackup, inspectBackup } from '../src/utils/restore'
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ isLoggedIn: true }) }))
vi.mock('../src/api', () => ({ syncApi: {}, attachmentApi: {} }))
vi.mock('../src/sync/community', () => ({ flushCommunity: vi.fn() }))
const backup = () => ({ app: 'yanshi', version: 4, subjects: [], sessions: [], tasks: [], mistakes: [] })
beforeEach(async () => { vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }); await db.open() })
afterEach(async () => { vi.clearAllTimers(); await db.delete() })

it('恢复两类本地图片及云端引用，数据与队列一起提交', async () => {
  const source = backup()
  source.mistakes = [{ id: 'm', content: '恢复', images: ['data:image/jpeg;base64,cXVlc3Rpb24=', 'mistake/cloud-key'],
    answerImages: ['data:image/png;base64,YW5zd2Vy'] }]
  expect(await restoreBackup(source)).toEqual({ imported: 1, skipped: 0 })
  const saved = await db.mistakes.get('m')
  expect(await saved.images[0].text()).toBe('question')
  expect(saved.images[1]).toBe('mistake/cloud-key')
  expect(await saved.answerImages[0].text()).toBe('answer')
  expect(await db.outbox.count()).toBe(1)
})

it('默认跳过同ID，覆盖时使用本机当前revision，不信备份中的版本', async () => {
  await db.tasks.put({ id: 't', title: 'keep', _rev: 5 })
  const source = backup(); source.tasks = [{ id: 't', title: 'restore', _rev: 99 }]
  expect(await restoreBackup(source)).toEqual({ imported: 0, skipped: 1 })
  expect((await db.tasks.get('t')).title).toBe('keep')
  await restoreBackup(source, { overwrite: true })
  expect(await db.outbox.where('recordId').equals('t').first()).toMatchObject({ expectedRevision: 5, record: { title: 'restore' } })
})

it('任一表写入失败时，已写入的科目和outbox均回滚', async () => {
  const source = backup(); source.subjects = [{ id: 'subject', name: '数学' }]; source.tasks = [{ id: 't', title: 'task' }]
  const fail = () => { throw new Error('disk full') }
  db.tasks.hook('creating', fail)
  try { await expect(restoreBackup(source)).rejects.toThrow('disk full') }
  finally { db.tasks.hook('creating').unsubscribe(fail) }
  expect(await db.subjects.count()).toBe(0)
  expect(await db.tasks.count()).toBe(0)
  expect(await db.outbox.count()).toBe(0)
})

it('损坏图片、重复ID、其他账号和敏感字段在导入前拒绝', async () => {
  const source = backup(); source.mistakes = [{ id: 'm', images: ['data:broken'] }]
  await expect(restoreBackup(source)).rejects.toThrow('图片格式')
  const duplicate = backup(); duplicate.tasks = [{ id: 't' }, { id: 't' }]
  expect(() => inspectBackup(duplicate)).toThrow('标识')
  expect(() => inspectBackup({ ...backup(), ownerId: 999 })).toThrow('所属账号')
  const sensitive = backup(); sensitive.tasks = [{ id: 't', token: 'secret' }]
  expect(() => inspectBackup(sensitive)).toThrow('不允许')
  expect(await db.mistakes.count()).toBe(0)
})
