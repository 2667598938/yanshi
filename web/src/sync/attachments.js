// 离线图片补传：把错题题目图/解析图里尚未上传的 Blob 先传附件，成功后再同步记录
import { db, localAccountScope } from '../db'
import { cacheImage } from '../db/imageCache'
import { attachmentApi } from '../api'

async function uploadList(list, scope) {
  const out = []
  let failed = false
  for (const [index, item] of list.entries()) {
    if (typeof item === 'string') {
      out.push(item)
      continue
    }
    try {
      const file = item instanceof File
        ? item
        : new File([item], 'mistake.jpg', { type: item?.type || 'image/jpeg' })
      const res = await attachmentApi.uploadImage(file, 'mistake')
      scope.assertCurrent()
      await cacheImage(res.key,item,scope)
      out.push(res.key)
    } catch (e) {
      scope.assertCurrent()
      failed = true
      out.push(item)
      // 网络/服务不可用：保留 Blob，下次同步继续补传
      if (!e.status || e.status >= 500) {
        out.push(...list.slice(index + 1))
        break
      }
    }
  }
  return { out, failed }
}

export async function flushMistakeImages() {
  const uploaded = []
  const scope = localAccountScope()
  const rows = await scope.db.mistakes.toArray()
  scope.assertCurrent()
  for (const row of rows) {
    const patch = {}
    let failed = false
    for (const field of ['images', 'answerImages']) {
      const list = Array.isArray(row[field]) ? row[field] : []
      if (!list.some((x) => typeof x !== 'string')) continue
      const res = await uploadList(list, scope)
      patch[field] = res.out
      if (res.failed) failed = true
    }
    if (!Object.keys(patch).length) continue
    scope.assertCurrent()
    await scope.db.mistakes.update(row.id, patch)
    if (!failed) uploaded.push({ ...row, ...patch })
    if (failed) break
  }
  return uploaded
}
