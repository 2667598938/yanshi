// 本地优先同步引擎：分表(subjects/sessions/tasks/mistakes) ↔ 通用 record。
// - 本地写库后 enqueueRecord/enqueueDelete，进入 outbox（同一条记录的多次改动合并为一条）
// - syncNow：先 push outbox（expectedRevision 乐观并发 + operationId 幂等），再 pull 全量按 revision 合并
// - 错题图片 Blob 不进同步体，只同步附件 key（图片上传见 api/attachment）
import { reactive } from 'vue'
import { db, uid } from '../db'
import { syncApi } from '../api'
import { flushCommunity } from './community'
import { flushMistakeImages } from './attachments'
import { useAuthStore } from '../stores/auth'
import { toPlain as plain } from '../utils/plain'

const TYPE_BY_TABLE = {
  subjects: 'subject',
  sessions: 'session',
  tasks: 'task',
  mistakes: 'mistake',
}
const TABLE_BY_TYPE = {
  subject: 'subjects',
  session: 'sessions',
  task: 'tasks',
  mistake: 'mistakes',
  userSchool: null, // 梦校关系存 kv，不进分表
}
const SYNCABLE_TABLES = ['subjects', 'sessions', 'tasks', 'mistakes']
// 帖子/收藏走各自的服务端接口，不能混入学习数据的通用同步命令
const COMMUNITY_TYPES = new Set(['post', 'favorite'])
const TYPE_LABEL = {
  subject: '科目',
  session: '专注记录',
  task: '任务',
  mistake: '错题',
  userSchool: '梦校',
}

// 冲突挂起：等待用户裁决的记录 id（这些记录在裁决前既不重发、也不被 pull 覆盖）
const heldIds = new Set()
// 待裁决冲突列表（由全局 ConflictDialog 组件观察并弹窗）
export const syncState = reactive({ pendingConflicts: [] })

function stripLocal(row, type) {
  const { _rev, ...clean } = row
  if (type === 'mistake') {
    // Blob 无法 JSON 化，只同步已上传的附件 key
    for (const field of ['images', 'answerImages']) {
      if (Array.isArray(clean[field])) {
        clean[field] = clean[field].filter((x) => typeof x === 'string')
      }
    }
  }
  clean.type = type
  return clean
}

async function upsertOutbox(recordId, type, expectedRevision, record) {
  const clean = record ? plain(record) : null
  const existing = await db.outbox.where('recordId').equals(recordId).first()
  if (existing) {
    await db.outbox.update(existing, { record: clean, expectedRevision })
  } else {
    await db.outbox.add({
      recordId,
      type,
      expectedRevision,
      record: clean,
      opId: '',
      createdAt: Date.now(),
    })
  }
}

// 记录新增/修改后调用
export async function enqueueRecord(table, row) {
  const type = TYPE_BY_TABLE[table]
  if (!type || !row || !row.id) return
  await upsertOutbox(row.id, type, row._rev || 0, stripLocal(row, type))
  scheduleSync()
}

// 记录删除后调用（本地立即删；未推送过的记录无需通知服务器）
export async function enqueueDelete(table, id) {
  const type = TYPE_BY_TABLE[table]
  if (!type || !id) return
  const live = await db[table].get(id)
  const expectedRevision = live?._rev || 0
  await db[table].delete(id)
  const existing = await db.outbox.where('recordId').equals(id).first()
  if (expectedRevision === 0) {
    // 服务器从未有过这条：直接丢弃本地未推送变更
    if (existing) await db.outbox.delete(existing.id)
    scheduleSync()
    return
  }
  if (existing) {
    await db.outbox.update(existing, { record: null, expectedRevision })
  } else {
    await db.outbox.add({
      recordId: id,
      type,
      expectedRevision,
      record: null,
      opId: '',
      createdAt: Date.now(),
    })
  }
  scheduleSync()
}

async function applyRevision(id, revision, record) {
  const table = record ? TABLE_BY_TYPE[record.type] : null
  if (!table) return
  const local = await db[table].get(id)
  if (local) {
    local._rev = revision
    await db[table].put(local)
  }
}

// 把一条 40902 冲突移出 outbox、挂起等待用户裁决；其余记录下一轮继续推送
async function holdConflict(conflict, items) {
  const { id, revision: serverRevision, record: serverRecord } = conflict
  if (heldIds.has(id)) return
  const local = items.find((x) => x.recordId === id)
  if (!local) return
  heldIds.add(id)
  const it = await db.outbox.where('recordId').equals(id).first()
  if (it) await db.outbox.delete(it.id)
  syncState.pendingConflicts.push({
    id,
    type: local.type,
    label: TYPE_LABEL[local.type] || '学习记录',
    localRecord: local.record, // 本地待发内容；null 表示本地删除（墓碑）
    expectedRevision: local.expectedRevision,
    serverRevision, // 服务端当前版本
    serverRecord, // 服务端当前内容；null 表示云端已删除
  })
}

// 用户裁决单条冲突：
//   'local' 保留本机：把本地待发改动 rebase 到服务端最新 revision 后重发（覆盖云端）
//   'cloud' 采用云端：丢弃本地待发改动，本地直接采用服务端记录
export async function resolveConflict(id, choice) {
  const idx = syncState.pendingConflicts.findIndex((c) => c.id === id)
  if (idx < 0) return
  const c = syncState.pendingConflicts[idx]
  heldIds.delete(id)
  if (choice === 'local') {
    if (c.localRecord) {
      await upsertOutbox(c.id, c.type, c.serverRevision, c.localRecord)
    } else {
      // 本地删除：以服务端最新 revision 重新入队删除墓碑
      const it = await db.outbox.where('recordId').equals(c.id).first()
      if (it) {
        await db.outbox.update(it, { record: null, expectedRevision: c.serverRevision })
      } else {
        await db.outbox.add({
          recordId: c.id,
          type: c.type,
          expectedRevision: c.serverRevision,
          record: null,
          opId: '',
          createdAt: Date.now(),
        })
      }
    }
  } else {
    await applyServerRecord(c.id, c.serverRevision, c.serverRecord)
  }
  syncState.pendingConflicts.splice(idx, 1)
  await reloadStores()
  scheduleSync()
}

// 直接采用服务端记录（record 为 null 表示云端已删除，物理删除本地对应行）
async function applyServerRecord(id, revision, record) {
  if (record) {
    const table = TABLE_BY_TYPE[record.type]
    if (table) {
      const rest = plain(record)
      delete rest.type
      rest._rev = revision
      await db[table].put(rest)
    }
  } else {
    for (const table of SYNCABLE_TABLES) {
      const local = await db[table].get(id)
      if (local) await db[table].delete(id)
    }
  }
}

async function pushOutbox() {
  const all = await db.outbox.orderBy('createdAt').limit(200).toArray()
  const items = []
  for (const it of all) {
    if (COMMUNITY_TYPES.has(it.type)) continue
    if (it.type === 'mistake' && it.record) {
      const local = await db.mistakes.get(it.recordId)
      // 图片未全部补传时保留队列，避免云端不完整记录回拉覆盖本机 Blob。
      if (local && ['images', 'answerImages'].some((field) =>
        (local[field] || []).some((image) => typeof image !== 'string'))) continue
    }
    items.push(it)
  }
  if (!items.length) return
  const changes = items.map((it) => ({
    id: it.recordId,
    expectedRevision: it.expectedRevision,
    record: it.record,
  }))
  try {
    const data = await syncApi.commands(uid('op-'), changes)
    for (const ch of data.changed || []) {
      await applyRevision(ch.id, ch.revision, ch.record)
      const it = await db.outbox.where('recordId').equals(ch.id).first()
      if (it) await db.outbox.delete(it.id)
    }
  } catch (e) {
    if (e.code === 40902) {
      // 服务端在首个冲突处整批回滚、只回该条冲突；挂起它交用户裁决，其余下一轮再推
      const conflict = e?.data?.conflicts?.[0]
      if (conflict) await holdConflict(conflict, items)
      else console.warn('同步冲突缺少明细，稍后重试')
    } else if (e.code === 40903) {
      // 操作 ID 复用：下轮换新 opId 即可（outbox 保留）
      console.warn('操作 ID 复用，下轮换新 opId 重试')
    } else {
      throw e
    }
  }
}

async function pullAll() {
  const data = await syncApi.records()
  const records = data.records || []
  let changed = false
  for (const { id, record, revision } of records) {
    if (!record) continue
    if (heldIds.has(id)) continue // 冲突待裁决，裁决前不覆盖本地改动
    const table = TABLE_BY_TYPE[record.type]
    if (!table) continue
    const pending = await db.outbox.where('recordId').equals(id).first()
    if (pending) continue // 本地有未推送改动，先不覆盖
    const local = await db[table].get(id)
    if (!local || (local._rev || 0) < revision) {
      const { type: _t, ...rest } = record
      rest._rev = revision
      await db[table].put(rest)
      changed = true
    }
  }
  // 软删（record 为 null）
  for (const { id, record } of records) {
    if (record) continue
    if (heldIds.has(id)) continue // 冲突待裁决，裁决前不物理删除
    for (const table of SYNCABLE_TABLES) {
      const local = await db[table].get(id)
      if (!local) continue
      const pending = await db.outbox.where('recordId').equals(id).first()
      if (pending) continue
      await db[table].delete(id)
      changed = true
    }
  }
  await db.syncMeta.put({ key: 'lastPullAt', value: Date.now() })
  return changed
}

// 拉取合并后刷新 Pinia 内存（动态 import，避免与 store 顶层循环依赖）
async function reloadStores() {
  const [s, t, k, m] = await Promise.all([
    import('../stores/subjects'),
    import('../stores/timer'),
    import('../stores/tasks'),
    import('../stores/mistakes'),
  ])
  const ss = s.useSubjectsStore()
  ss.list = await db.subjects.toArray()
  ss.loaded = true
  const tm = t.useTimerStore()
  tm.sessions = await db.sessions.toArray()
  tm.loaded = true
  const tk = k.useTasksStore()
  tk.list = await db.tasks.toArray()
  tk.loaded = true
  const ms = m.useMistakesStore()
  await ms.load(true)
}

// 首次登录：把本地所有未同步记录入队（换设备也能恢复）
async function bootstrapLocal() {
  for (const table of SYNCABLE_TABLES) {
    const rows = await db[table].toArray()
    for (const row of rows) {
      if (row._rev) continue
      const existing = await db.outbox.where('recordId').equals(row.id).first()
      if (!existing) {
        await db.outbox.add({
          recordId: row.id,
          type: TYPE_BY_TABLE[table],
          expectedRevision: 0,
          record: stripLocal(row, TYPE_BY_TABLE[table]),
          opId: '',
          createdAt: Date.now(),
        })
      }
    }
  }
}

let syncing = false
let queued = false
let timer = null
let periodicStarted = false
let accountSwitches = 0
let syncCompletion = Promise.resolve()

// 换号前等待当前批次结束，期间禁止新批次；旧请求始终在旧账号/旧库下收尾。
export async function pauseSyncForAccountSwitch() {
  accountSwitches += 1
  clearTimeout(timer)
  queued = false
  await syncCompletion
}

export function resumeSyncAfterAccountSwitch() {
  accountSwitches = Math.max(0, accountSwitches - 1)
  if (!accountSwitches) scheduleSync(0)
}

export async function syncNow() {
  const auth = useAuthStore()
  if (!auth.isLoggedIn || accountSwitches) return
  if (syncing) {
    queued = true
    return
  }
  syncing = true
  let completeSync
  syncCompletion = new Promise((resolve) => { completeSync = resolve })
  try {
    // 先把离线拍的错题图补传为附件 key，再推送记录
    const uploaded = await flushMistakeImages()
    for (const row of uploaded) await enqueueRecord('mistakes', row)
    await flushCommunity()
    await pushOutbox()
    const changed = await pullAll()
    if (changed) await reloadStores()
    await db.syncMeta.put({ key: 'lastSyncAt', value: Date.now() })
    return true
  } catch (e) {
    console.warn('同步失败，下次再试', e?.message || e)
    return false
  } finally {
    syncing = false
    completeSync()
    if (queued) {
      queued = false
      syncNow()
    }
  }
}

export function scheduleSync(delay = 1500) {
  const auth = useAuthStore()
  if (!auth.isLoggedIn || accountSwitches) return
  clearTimeout(timer)
  timer = setTimeout(() => syncNow(), delay)
}

// 登录后调用：首登全量 + 定时 + 回到前台时同步
export async function initSyncForUser() {
  const auth = useAuthStore()
  if (!auth.isLoggedIn) return
  const bootDone = await db.syncMeta.get('bootstrapDone')
  if (!bootDone) {
    await bootstrapLocal()
    await db.syncMeta.put({ key: 'bootstrapDone', value: 1 })
  }
  await syncNow()
  if (!periodicStarted) {
    periodicStarted = true
    setInterval(() => syncNow(), 30000)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') syncNow()
    })
  }
}

// 账号切换时清空内存中的冲突裁决状态（数据本身按账号分库保留）
export function resetSyncRuntime() {
  clearTimeout(timer)
  heldIds.clear()
  syncState.pendingConflicts.splice(0, syncState.pendingConflicts.length)
  queued = false
}

// 登出/换号时清理当前库的待发队列（仅在明确「清空本地记录」时使用）
export async function resetSyncState() {
  await db.outbox.clear()
  await db.syncMeta.clear()
  await db.localPosts.clear()
  await db.localFavs.clear()
  resetSyncRuntime()
}
