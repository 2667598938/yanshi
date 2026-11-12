// 社区离线队列与账号内镜像。网络请求之外的本地状态变更均在同一事务内完成。
import { reactive } from 'vue';
import { db, uid, activeAccountId } from '../db';
import { postApi, resourceApi } from '../api';

export const SYNCED_EVENT = 'yanshi:community-synced';
export const communityState = reactive({ accountId: null, issues: [] });
const plain = (value) => JSON.parse(JSON.stringify(value));
const emit = () => {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(SYNCED_EVENT));
};

export async function queuePost(content) {
  const row = { id: uid('p-'), content: content.trim(), createdAt: Date.now() };
  await db.transaction('rw', db.localPosts, db.outbox, async () => {
    await db.localPosts.add(row);
    await db.outbox.add({
      recordId: row.id,
      type: 'post',
      version: uid(),
      record: { client_id: row.id, content: row.content },
      createdAt: row.createdAt,
    });
  });
  return row;
}

export async function queuePostEdit(post, content) {
  post = plain(post);
  const key = `post-${post.id}`;
  await db.transaction('rw', db.kv, db.outbox, async () => {
    const existing = await db.outbox.where('recordId').equals(key).first();
    const value = {
      recordId: key,
      type: 'postEdit',
      version: uid(),
      expectedRevision: existing?.expectedRevision ?? post.revision,
      record: { id: post.id, content: content.trim() },
      createdAt: Date.now(),
    };
    if (existing) await db.outbox.update(existing.id, value);
    else await db.outbox.add(value);
    const cache = await db.kv.get('postMirror');
    const rows = cache?.value || [];
    await db.kv.put({
      key: 'postMirror',
      value: [
        ...rows.filter((p) => p.id !== post.id),
        { ...post, content: value.record.content, pending: true },
      ],
    });
  });
}

export async function queuePostDelete(post) {
  post = plain(post);
  const key = `post-${post.id}`;
  await db.transaction('rw', db.kv, db.outbox, async () => {
    const existing = await db.outbox.where('recordId').equals(key).first();
    const value = {
      recordId: key,
      type: 'postDelete',
      version: uid(),
      expectedRevision: existing?.expectedRevision ?? post.revision,
      record: { id: post.id, content: post.content },
      createdAt: Date.now(),
    };
    if (existing) await db.outbox.update(existing.id, value);
    else await db.outbox.add(value);
    const cache = await db.kv.get('postMirror');
    await db.kv.put({
      key: 'postMirror',
      value: (cache?.value || []).map((p) =>
        p.id === post.id ? { ...p, deleted_at: new Date().toISOString(), pending: true } : p,
      ),
    });
  });
}

export async function queueFavorite(resourceId, favorited, resource = null) {
  if (resource) resource = plain(resource);
  const key = `fav-${resourceId}`;
  await db.transaction('rw', db.localFavs, db.outbox, async () => {
    const old = await db.localFavs.get(resourceId);
    const existing = await db.outbox.where('recordId').equals(key).first();
    const revision =
      existing?.expectedRevision ?? old?.revision ?? resource?.favorite_revision ?? 0;
    await db.localFavs.put({
      ...old,
      resourceId,
      favorited,
      revision,
      resource: resource || old?.resource,
      updatedAt: Date.now(),
    });
    const row = {
      recordId: key,
      type: 'favorite',
      version: uid(),
      expectedRevision: revision,
      record: { resourceId, favorited },
      createdAt: Date.now(),
    };
    if (existing) await db.outbox.update(existing.id, row);
    else await db.outbox.add(row);
  });
}

export const pendingPosts = () => db.localPosts.orderBy('createdAt').reverse().toArray();
export const pendingFavorites = () => db.localFavs.toArray();
export async function cachedPosts() {
  return ((await db.kv.get('postMirror'))?.value || [])
    .filter((p) => !p.deleted_at)
    .sort((a, b) => b.id - a.id);
}
export async function favoriteRows() {
  return (await db.localFavs.toArray())
    .filter((s) => s.favorited && s.resource)
    .map((s) => ({ ...s.resource, favorited: true, favorite_revision: s.revision }));
}

async function allPages(fetch) {
  const rows = [];
  let after = 0;
  for (;;) {
    const data = await fetch(after);
    rows.push(...data.items);
    if (data.next == null) return rows;
    if (data.next <= after) throw new Error('镜像游标未前进');
    after = data.next;
  }
}

export async function pullCommunityMirrors() {
  const account = activeAccountId();
  const [posts, favorites] = await Promise.all([
    allPages(postApi.mirror),
    allPages(resourceApi.favoriteMirror),
  ]);
  if (account !== activeAccountId()) return;
  await db.transaction('rw', db.kv, db.localFavs, db.outbox, async () => {
    const pending = await db.outbox.toArray();
    const edits = new Map(
      pending
        .filter((p) => ['postEdit', 'postDelete'].includes(p.type))
        .map((p) => [p.record.id, p]),
    );
    await db.kv.put({
      key: 'postMirror',
      value: posts.map((p) =>
        edits.has(p.id)
          ? {
              ...p,
              content: edits.get(p.id).record.content,
              pending: true,
              deleted_at:
                edits.get(p.id).type === 'postDelete' ? new Date().toISOString() : p.deleted_at,
            }
          : p,
      ),
    });
    const held = new Set(
      pending.filter((p) => p.type === 'favorite').map((p) => p.record.resourceId),
    );
    for (const row of await db.localFavs.toArray())
      if (!held.has(row.resourceId)) await db.localFavs.delete(row.resourceId);
    for (const row of favorites) if (!held.has(row.resourceId)) await db.localFavs.put(row);
  });
}

async function refreshIssues() {
  communityState.accountId = activeAccountId();
  communityState.issues = (await db.outbox.toArray()).filter(
    (p) => p.error && ['post', 'postEdit', 'postDelete', 'favorite'].includes(p.type),
  );
}

export async function resolveCommunityIssue(id, choice, content) {
  const item = await db.outbox.get(id);
  if (!item) return;
  if (choice === 'local' && item.type === 'postEdit' && item.errorStatus === 404) {
    await queuePost(content || item.record.content);
    choice = 'cloud'; // 云端已删除时以新帖保存，不复活原帖。
  }
  await db.transaction('rw', db.outbox, db.localPosts, db.localFavs, db.kv, async () => {
    if (choice === 'local') {
      await db.outbox.update(id, {
        error: '',
        cloud: null,
        record: content != null ? { ...item.record, content: content.trim() } : item.record,
        expectedRevision: item.cloud?.revision ?? item.expectedRevision,
        version: uid(),
      });
      if (item.type === 'post' && content != null)
        await db.localPosts.update(item.recordId, { content: content.trim() });
    } else {
      await db.outbox.delete(id);
      if (item.type === 'post') await db.localPosts.delete(item.recordId);
      if (item.type === 'favorite' && item.cloud)
        await db.localFavs.put({
          ...item.cloud,
          resourceId: item.record.resourceId,
          resource: (await db.localFavs.get(item.record.resourceId))?.resource,
        });
      if (['postEdit', 'postDelete'].includes(item.type)) {
        const cache = await db.kv.get('postMirror');
        await db.kv.put({
          key: 'postMirror',
          value: (cache?.value || []).map((p) =>
            p.id === item.record.id ? item.cloud || { ...p, pending: false } : p,
          ),
        });
      }
    }
  });
  await refreshIssues();
  emit();
}

export async function flushCommunity() {
  let changed = false;
  const rateLimited = new Set();
  const items = (await db.outbox.toArray()).filter((p) =>
    ['post', 'postEdit', 'postDelete', 'favorite'].includes(p.type),
  );
  for (const item of items) {
    if (item.error || rateLimited.has(item.type)) continue;
    try {
      let response;
      if (item.type === 'post')
        response = await postApi.create(item.record.content, item.record.client_id);
      else if (item.type === 'postEdit')
        response = await postApi.update(item.record.id, item.record.content, item.expectedRevision);
      else if (item.type === 'postDelete') {
        await postApi.remove(item.record.id, '', item.expectedRevision);
        response = { revision: item.expectedRevision + 1 };
      } else
        response = await resourceApi.setFavorite(
          item.record.resourceId,
          item.record.favorited,
          item.expectedRevision,
        );
      await db.transaction('rw', db.outbox, db.localPosts, db.localFavs, async () => {
        const current = await db.outbox.get(item.id);
        if (!current) return;
        if (current.version !== item.version) {
          await db.outbox.update(item.id, { expectedRevision: response.revision });
          return; // 请求过程中发生了新修改；只推进基线，不删除新队列。
        }
        await db.outbox.delete(item.id);
        if (item.type === 'post') await db.localPosts.delete(item.recordId);
        if (item.type === 'favorite') {
          const local = await db.localFavs.get(item.record.resourceId);
          await db.localFavs.put({ ...local, ...response, resourceId: item.record.resourceId });
        }
      });
      changed = true;
    } catch (e) {
      if (!e.status) break;
      if (e.status === 429) {
        rateLimited.add(item.type);
        continue;
      }
      if ([400, 404, 409, 422].includes(e.status)) {
        // 保留原文与队列，由用户明确选择；不因校验或删除目标而悄悄丢稿。
        let cloud = e.data?.current || null;
        if (!cloud && e.status === 409) {
          try {
            if (item.type === 'favorite') {
              const remote = await resourceApi.get(item.record.resourceId);
              cloud = {
                resourceId: remote.id,
                favorited: remote.favorited,
                revision: remote.favorite_revision,
              };
            } else if (item.type === 'postEdit') cloud = await postApi.get(item.record.id);
          } catch {
            /* 下次重试仍保留本机内容 */
          }
        }
        const current = await db.outbox.get(item.id);
        if (current?.version === item.version)
          await db.outbox.update(item.id, {
            error: e.message || '同步失败',
            errorStatus: e.status,
            cloud,
          });
      }
    }
  }
  try {
    await pullCommunityMirrors();
  } catch {
    /* 离线保留上次完整镜像，学习同步可继续 */
  }
  await refreshIssues();
  if (changed) emit();
  return changed;
}
