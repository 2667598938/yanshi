// 离线社区：本地待上传动态与收藏状态，复用 outbox 作为队列。
// 与学习数据同步不同，帖子/收藏有各自的服务端接口，因此在 syncNow 前单独推送。
import { db, uid } from '../db'
import { postApi, resourceApi } from '../api'

export const SYNCED_EVENT = 'yanshi:community-synced'

// 离线发帖：先落本地草稿，联网后由 flushCommunity 上传（client_id 保证幂等）
export async function queuePost(content) {
  const now = Date.now()
  const id = uid('p-')
  const row = { id, content: content.trim(), createdAt: now }
  await db.localPosts.add(row)
  await db.outbox.add({
    recordId: id,
    type: 'post',
    expectedRevision: 0,
    record: { id, client_id: id, content: row.content, createdAt: now },
    opId: '',
    createdAt: now,
  })
  return row
}

// 离线收藏：同一资料的多次切换合并为一条，最终只同步最后状态
export async function queueFavorite(resourceId, favorited) {
  const key = `fav-${resourceId}`
  const now = Date.now()
  await db.localFavs.put({ resourceId, favorited, updatedAt: now })
  const existing = await db.outbox.where('recordId').equals(key).first()
  const record = { resourceId, favorited }
  if (existing) {
    await db.outbox.update(existing.id, { record, createdAt: now })
  } else {
    await db.outbox.add({
      recordId: key,
      type: 'favorite',
      expectedRevision: 0,
      record,
      opId: '',
      createdAt: now,
    })
  }
}

export function pendingPosts() {
  return db.localPosts.orderBy('createdAt').reverse().toArray()
}

export async function pendingFavorites() {
  return db.localFavs.toArray()
}

function isNetworkError(e) {
  return !e || !e.status
}

// 仅内容校验失败（400/422）或目标已不存在（404）才丢弃，401/403/5xx 等保留重试
function isDroppable(e) {
  return [400, 404, 422].includes(e.status)
}

// 推送离线队列；网络不可用时保留队列，等下次触发
export async function flushCommunity() {
  let changed = false

  const posts = await db.outbox.where('type').equals('post').toArray()
  for (const item of posts) {
    try {
      await postApi.create(item.record.content, item.record.client_id)
      await db.outbox.delete(item.id)
      await db.localPosts.delete(item.recordId)
      changed = true
    } catch (e) {
      if (isNetworkError(e)) return changed
      if (isDroppable(e)) {
        // 内容校验失败等不可恢复错误：丢弃草稿，避免队列永久卡住
        await db.outbox.delete(item.id)
        await db.localPosts.delete(item.recordId)
      }
    }
  }

  const favs = await db.outbox.where('type').equals('favorite').toArray()
  for (const item of favs) {
    try {
      await resourceApi.setFavorite(item.record.resourceId, item.record.favorited)
      await db.outbox.delete(item.id)
      await db.localFavs.delete(item.record.resourceId)
      changed = true
    } catch (e) {
      if (isNetworkError(e)) return changed
      if (isDroppable(e)) {
        await db.outbox.delete(item.id)
        await db.localFavs.delete(item.record.resourceId)
      }
    }
  }

  if (changed) window.dispatchEvent(new Event(SYNCED_EVENT))
  return changed
}
