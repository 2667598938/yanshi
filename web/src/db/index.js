// 本地主库：IndexedDB（Dexie）。学习数据全部先落地本地，可离线使用；
// 后端上线后再通过 /sync 增量同步。设置与"当前这颗番茄"仍存 localStorage。
import Dexie from 'dexie'
import { DEFAULT_SUBJECTS } from '../data/subjects'

export const LEGACY_SESS_KEY = 'yanshi:sessions'
export const CUR_KEY = 'yanshi:current'
export const MIGRATE_FLAG = 'yanshi:db_migrated_v1'

export function uid(prefix = '') {
  return (
    prefix +
    Date.now().toString(36) +
    Math.random().toString(36).slice(2, 8)
  )
}

export const db = new Dexie('yanshi_db')

db.version(1).stores({
  // 科目：id 主键，order 排序，archived 归档
  subjects: 'id, archived, order',
  // 番茄记录：date 用于按天聚合，subjectId / activityType 用于筛选
  sessions: 'id, date, subjectId, startedAt, activityType',
  // 任务：done / dueDate / createdAt / subjectId
  tasks: 'id, done, dueDate, createdAt, subjectId',
  // 错题：nextReviewAt 复习到期，*tags 多标签索引
  mistakes: 'id, subjectId, nextReviewAt, createdAt, *tags',
  // 键值（头像等）
  kv: 'key',
})

// v0.3 同步：outbox 待发变更、syncMeta 同步状态（增量声明，不影响已有表）
db.version(2).stores({
  outbox: '++id, recordId, type, createdAt',
  syncMeta: 'key',
})

// 首次启动：写入默认科目
async function seedSubjects() {
  const count = await db.subjects.count()
  if (count === 0) {
    await db.subjects.bulkAdd(
      DEFAULT_SUBJECTS.map((s, i) => ({
        id: s.id,
        name: s.name,
        color: s.color,
        icon: s.icon,
        tags: [],
        order: i,
        archived: 0,
        builtin: 1,
        createdAt: Date.now(),
      }))
    )
  }
}

// 一次性迁移旧 localStorage 番茄记录
async function migrateLegacy() {
  if (localStorage.getItem(MIGRATE_FLAG)) return
  try {
    const raw = localStorage.getItem(LEGACY_SESS_KEY)
    const old = raw ? JSON.parse(raw) : []
    if (Array.isArray(old) && old.length) {
      const validIds = new Set((await db.subjects.toArray()).map((s) => s.id))
      const rows = old
        .filter((x) => x.status === 'done')
        .map((x) => ({
          id: String(x.id ?? uid('s')),
          subjectId: validIds.has(x.subject) ? x.subject : 'other',
          mode: 'timer',
          activityType: '',
          plannedMin: x.plannedMin ?? 25,
          actualSec: x.actualSec ?? 0,
          status: 'done',
          startedAt: x.startedAt ?? Date.now(),
          endedAt: x.endedAt ?? Date.now(),
          date: x.date,
          note: x.note || '',
          createdAt: x.endedAt ?? Date.now(),
        }))
      if (rows.length) await db.sessions.bulkPut(rows)
    }
  } catch (e) {
    console.warn('旧数据迁移失败', e)
  }
  localStorage.setItem(MIGRATE_FLAG, '1')
}

export async function initDb() {
  await seedSubjects()
  await migrateLegacy()
}
