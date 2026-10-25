import { db, activeAccountId } from '../db'
import { writeRecord } from '../sync/engine'
import { validateLearningSettings } from '../stores/learningSettings'

const TABLES = ['subjects', 'sessions', 'tasks', 'mistakes', 'timeNodes']
const PROFILE_FIELDS = new Set(['nickname', 'target_school', 'signature', 'figure_id',
  'daily_goal_min', 'exam_date', 'notify_enabled', 'privacy_mode', 'custom_motto'])

export function inspectBackup(backup) {
  if (!backup || backup.app !== 'yanshi' || ![3, 4, 5].includes(backup.version)) throw new Error('不是支持的研时备份文件')
  if (backup.ownerId && String(backup.ownerId) !== String(activeAccountId())) throw new Error('请登录备份所属账号后恢复')
  const ids = new Set()
  const counts = {}
  for (const table of TABLES) {
    const rows = backup[table] ?? (table==='timeNodes' && backup.version<5 ? [] : undefined)
    if (!Array.isArray(rows)) throw new Error('备份数据不完整')
    counts[table] = rows.length
    for (const row of rows) {
      if (!row || typeof row.id !== 'string' || !row.id || row.id.length > 500 || ids.has(row.id)) throw new Error('备份记录标识无效或重复')
      if (['user_id', 'userId', 'password', 'token', 'apiKey', 'owner'].some((key) => key in row)) throw new Error('备份包含不允许恢复的字段')
      ids.add(row.id)
    }
  }
  if (ids.size > 20000) throw new Error('单次恢复最多20000条记录')
  if (backup.learningSettings) validateLearningSettings(backup.learningSettings)
  if (backup.profile && Object.keys(backup.profile).some((key) => !PROFILE_FIELDS.has(key))) throw new Error('个人资料字段无效')
  return counts
}

function restoreImage(value) {
  if (typeof value !== 'string' || value.length > 8 * 1024 * 1024) throw new Error('备份图片无效或过大')
  if (!value.startsWith('data:')) {
    if (!value || value.length > 2048 || /^javascript:/i.test(value)) throw new Error('图片引用无效')
    return value
  }
  const match = /^data:(image\/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\r\n]+)$/.exec(value)
  if (!match) throw new Error('备份图片格式无效')
  let bytes
  try { bytes = Uint8Array.from(atob(match[2]), (char) => char.charCodeAt(0)) }
  catch { throw new Error('备份图片损坏') }
  if (!bytes.length || bytes.length > 5 * 1024 * 1024) throw new Error('备份图片为空或过大')
  return new Blob([bytes], { type: match[1] })
}

export async function restoreBackup(backup, { overwrite = false } = {}) {
  inspectBackup(backup)
  // 在进入事务前完成所有图片解码；任何损坏图片都会阻止整次恢复。
  const prepared = {}
  for (const table of TABLES) {
    prepared[table] = (backup[table] || []).map((source) => {
      const { _rev, type, ...row } = source
      if (table === 'mistakes') {
        for (const field of ['images', 'answerImages']) {
          if (row[field] && (!Array.isArray(row[field]) || row[field].length > 9)) throw new Error('每组图片最多9张')
          row[field] = (row[field] || []).map(restoreImage)
        }
      }
      return row
    })
  }
  const result = { imported: 0, skipped: 0 }
  await db.transaction('rw', ...TABLES.map((table) => db[table]), db.kv, db.outbox, db.syncMeta, async () => {
    for (const table of TABLES) {
      for (const row of prepared[table]) {
        const current = await db[table].get(row.id)
        if (current && !overwrite) { result.skipped += 1; continue }
        await writeRecord(table, { ...row, _rev: current?._rev || 0 })
        result.imported += 1
      }
    }
    for (let [key, type, value] of [
      ['learning-settings', 'preferences', backup.learningSettings],
      ['profile', 'profile', backup.profile],
    ]) {
      if (!value) continue
      if (type==='profile') { value = Object.fromEntries(Object.entries(value).filter(([key])=>key!=='privacy_mode')) }
      const current = await db.kv.get(key)
      if (current && !overwrite) continue
      await writeRecord('kv', { key, id: key, syncType: type, value,
        _rev: current?._rev || 0, updatedAt: Date.now() })
    }
  })
  return result
}
