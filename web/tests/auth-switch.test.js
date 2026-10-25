import Dexie from 'dexie'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { db, activateAccount, activeAccountId } from '../src/db'
import { useAuthStore } from '../src/stores/auth'
import { authApi, syncApi } from '../src/api'
import { enqueueRecord, syncNow, resetSyncRuntime } from '../src/sync/engine'

vi.mock('../src/api', () => ({
  authApi: { login: vi.fn(), logout: vi.fn() },
  syncApi: { commands: vi.fn(), records: vi.fn() },
  attachmentApi: { uploadImage: vi.fn() },
}))
vi.mock('../src/sync/community', () => ({ flushCommunity: vi.fn() }))

beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval'] })
  vi.stubGlobal('document', { addEventListener: vi.fn() })
  await activateAccount(31)
  const auth = useAuthStore()
  auth.user = { id: 31 }
  auth.accessToken = 'account-a'
  syncApi.records.mockResolvedValue({ records: [] })
  authApi.login.mockResolvedValue({ access_token: 'account-b', user: { id: 32 } })
})
afterEach(async () => {
  resetSyncRuntime()
  vi.clearAllTimers()
  db.close()
  for (const name of await Dexie.getDatabaseNames()) await Dexie.delete(name)
  await activateAccount(null)
})

it.each(['login', 'logout'])('%s 等待旧同步批次结束，再切换凭证和本地库', async (action) => {
  const auth = useAuthStore()
  const row = { id: 'a-pending', title: 'A 的未同步任务' }
  await db.tasks.put(row)
  await enqueueRecord('tasks', row)
  let release
  syncApi.commands.mockImplementation(() => new Promise((resolve) => { release = resolve }))
  const running = syncNow()
  await vi.waitFor(() => expect(release).toBeTypeOf('function'))
  const switching = action === 'login' ? auth.login('b@example.com', 'password') : auth.logout()
  await new Promise((resolve) => setImmediate(resolve))
  expect(authApi[action]).not.toHaveBeenCalled()
  expect(auth.user.id).toBe(31)
  expect(activeAccountId()).toBe(31)
  release({ changed: [] })
  await running
  await switching
  expect(activeAccountId()).toBe(action === 'login' ? 32 : null)
  expect(await db.tasks.get('a-pending')).toBeUndefined()
  await activateAccount(31)
  expect((await db.tasks.get('a-pending')).title).toBe('A 的未同步任务')
  expect(await db.outbox.where('recordId').equals('a-pending').count()).toBe(1)
})
