// 离线图片补传：把错题题目图/解析图里尚未上传的 Blob 先传附件，成功后再同步记录
import { localAccountScope } from '../db';
import { cacheImage } from '../db/imageCache';
import { attachmentApi } from '../api';

const imageFields = ['images', 'answerImages'];

function hasPendingImages(row) {
  return imageFields.some(
    (field) => Array.isArray(row[field]) && row[field].some((item) => typeof item !== 'string'),
  );
}

async function uploadList(list, scope) {
  const out = [];
  let failed = false;
  let retryLater = false;
  for (const [index, item] of list.entries()) {
    if (typeof item === 'string') {
      out.push(item);
      continue;
    }
    try {
      const file =
        item instanceof File
          ? item
          : new File([item], 'mistake.jpg', { type: item?.type || 'image/jpeg' });
      const res = await attachmentApi.uploadImage(file, 'mistake');
      scope.assertCurrent();
      await cacheImage(res.key, item, scope);
      out.push(res.key);
    } catch (e) {
      scope.assertCurrent();
      failed = true;
      out.push(item);
      // 网络/服务不可用：保留 Blob，下次同步继续补传
      if (!e.status || e.status >= 500) {
        retryLater = true;
        out.push(...list.slice(index + 1));
        break;
      }
    }
  }
  return { out, failed, retryLater };
}

export async function flushMistakeImages(enqueueUploaded) {
  const uploaded = [];
  const scope = localAccountScope();
  const { mistakes, outbox, syncMeta } = scope.db;
  const ids = (await mistakes.toArray()).filter(hasPendingImages).map((row) => row.id);
  for (const id of ids) {
    scope.assertCurrent();
    const snapshot = await scope.db.transaction('r', mistakes, outbox, syncMeta, async () => {
      if (await syncMeta.get(`conflict:${id}`)) return null;
      const row = await mistakes.get(id);
      if (!row) return null;
      const pending = await outbox.where('recordId').equals(id).first();
      return { row, version: pending?.version };
    });
    if (!snapshot) continue;
    const { row, version } = snapshot;
    const patch = {};
    let failed = false;
    let retryLater = false;
    for (const field of imageFields) {
      const list = Array.isArray(row[field]) ? row[field] : [];
      if (!list.some((x) => typeof x !== 'string')) continue;
      const res = await uploadList(list, scope);
      patch[field] = res.out;
      if (res.failed) failed = true;
      if (res.retryLater) retryLater = true;
    }
    if (!Object.keys(patch).length) continue;
    scope.assertCurrent();
    const saved = await scope.db.transaction('rw', mistakes, outbox, syncMeta, async () => {
      scope.assertCurrent();
      const current = await mistakes.get(id);
      const pending = await outbox.where('recordId').equals(id).first();
      // The upload ran outside the transaction. A later edit, delete or pull wins.
      if (
        !current ||
        pending?.version !== version ||
        current._rev !== row._rev ||
        current.updatedAt !== row.updatedAt ||
        (await syncMeta.get(`conflict:${id}`))
      )
        return null;
      const next = { ...current, ...patch };
      await mistakes.put(next);
      if (!failed && enqueueUploaded) await enqueueUploaded(next);
      return failed ? null : next;
    });
    if (saved) uploaded.push(saved);
    if (retryLater) break;
  }
  return uploaded;
}
