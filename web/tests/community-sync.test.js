import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { reactive } from 'vue';
import { db } from '../src/db';
import { postApi, resourceApi } from '../src/api';
import {
  queuePost,
  queueFavorite,
  queuePostEdit,
  flushCommunity,
  favoriteRows,
  cachedPosts,
  resolveCommunityIssue,
} from '../src/sync/community';
vi.mock('../src/api', () => ({
  postApi: { create: vi.fn(), update: vi.fn(), mirror: vi.fn() },
  resourceApi: { setFavorite: vi.fn(), favoriteMirror: vi.fn() },
}));
beforeEach(async () => {
  await db.open();
  postApi.mirror.mockResolvedValue({ items: [], next: null });
  resourceApi.favoriteMirror.mockResolvedValue({ items: [], next: null });
});
afterEach(async () => {
  await db.delete();
  vi.clearAllMocks();
});

it('收藏响应晚到时保留新操作，并推进其云端版本', async () => {
  const resource = reactive({ id: 8, title: 'book', owner: { id: 1 }, favorite_revision: 2 });
  await queueFavorite(8, true, resource);
  let finish;
  resourceApi.setFavorite.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const running = flushCommunity();
  await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
  await queueFavorite(8, false, resource);
  finish({ favorited: true, revision: 3 });
  await running;
  const pending = await db.outbox.toArray();
  expect(pending).toHaveLength(1);
  expect(pending[0].record.favorited).toBe(false);
  expect(pending[0].expectedRevision).toBe(3);
});

it('镜像保留离线编辑，收藏全量拉取覆盖已取消项；支持新设备恢复', async () => {
  const post = { id: 3, content: 'cloud', revision: 1 };
  await queuePostEdit(reactive(post), 'local edit');
  postApi.update.mockRejectedValue({ status: 503 });
  postApi.mirror.mockResolvedValue({ items: [post], next: null });
  await db.localFavs.put({ resourceId: 9, favorited: true, resource: { id: 9 } });
  resourceApi.favoriteMirror.mockResolvedValue({
    items: [{ resourceId: 7, favorited: true, revision: 4, resource: { id: 7 } }],
    next: null,
  });
  await flushCommunity();
  expect((await cachedPosts())[0].content).toBe('local edit');
  expect((await favoriteRows()).map((r) => r.id)).toEqual([7]);
});

it('校验失败不丢稿，用户修改后可以重新提交', async () => {
  const row = await queuePost('draft');
  postApi.create.mockRejectedValueOnce({ status: 400, message: 'invalid' });
  await flushCommunity();
  expect((await db.localPosts.get(row.id)).content).toBe('draft');
  const issue = (await db.outbox.toArray())[0];
  await resolveCommunityIssue(issue.id, 'local', 'corrected draft');
  postApi.create.mockResolvedValueOnce({ id: 11, revision: 1 });
  await flushCommunity();
  expect(postApi.create).toHaveBeenLastCalledWith('corrected draft', row.id);
  expect(await db.localPosts.count()).toBe(0);
});
