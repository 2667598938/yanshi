import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { reactive } from 'vue';
import { db } from '../src/db';
import { syncApi, attachmentApi } from '../src/api';
import {
  enqueueRecord,
  initSyncForUser,
  syncNow,
  resetSyncRuntime,
  syncState,
  waitForSync,
} from '../src/sync/engine';
import { useMistakesStore } from '../src/stores/mistakes';
import {
  useLearningSettingsStore,
  DEFAULT_LEARNING_SETTINGS,
} from '../src/stores/learningSettings';
import { DEFAULT_SUBJECTS } from '../src/data/subjects';

vi.mock('../src/api', () => ({
  syncApi: { commands: vi.fn(), records: vi.fn() },
  attachmentApi: { uploadImage: vi.fn() },
}));
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ isLoggedIn: true }) }));
vi.mock('../src/sync/community', () => ({ flushCommunity: vi.fn() }));
beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
  await db.open();
  syncApi.commands.mockResolvedValue({ changed: [] });
  syncApi.records.mockResolvedValue({ records: [] });
});
afterEach(async () => {
  resetSyncRuntime();
  vi.clearAllTimers();
  await db.delete();
});

it('已失败的完整偏好批次可原样重试，保留任务并继续后续同步', async () => {
  const task = { id: 'prefs-mixed-task', title: '保留待同步任务' };
  await db.tasks.put(task);
  await enqueueRecord('tasks', task);
  await useLearningSettingsStore().save({ ...DEFAULT_LEARNING_SETTINGS, bulletText: '本人寄语' });
  syncApi.commands.mockRejectedValueOnce({ status: 400, code: 40004, message: '个人设置内容无效' });
  expect(await syncNow()).toBe(false);
  const first = syncApi.commands.mock.calls[0];
  expect(first[1].find((c) => c.id === 'learning-settings').record.value.bulletText).toBe(
    '本人寄语',
  );
  expect(await db.outbox.count()).toBe(2);
  syncApi.commands.mockImplementation(async (_op, changes) => ({
    changed: changes.map((c) => ({ ...c, revision: 1 })),
  }));
  expect(await syncNow()).toBe(true);
  expect(syncApi.commands.mock.calls[1]).toEqual(first);
  expect((await db.tasks.get(task.id))._rev).toBe(1);
  expect(await db.outbox.count()).toBe(0);
  await db.tasks.put({ id: 'after-recovery', title: '后续任务' });
  await enqueueRecord('tasks', { id: 'after-recovery', title: '后续任务' });
  expect(await syncNow()).toBe(true);
  expect((await db.tasks.get('after-recovery'))._rev).toBe(1);
});

it('图片失败时保留队列并阻止不完整记录推送/回拉覆盖；重试后整条同步', async () => {
  const row = {
    id: 'm',
    images: [new Blob(['q']), new Blob(['q2'])],
    answerImages: [new Blob(['a'])],
  };
  await db.mistakes.add(row);
  await enqueueRecord('mistakes', row);
  attachmentApi.uploadImage.mockRejectedValue(new Error('offline'));
  syncApi.records.mockResolvedValue({
    records: [
      { id: 'm', revision: 1, record: { id: 'm', type: 'mistake', images: [], answerImages: [] } },
    ],
  });
  expect(await syncNow()).toBe(true);
  expect(syncApi.commands).not.toHaveBeenCalled();
  expect(await db.outbox.count()).toBe(1);
  expect((await db.mistakes.get('m')).images).toHaveLength(2);
  attachmentApi.uploadImage
    .mockResolvedValueOnce({ key: 'key/q' })
    .mockResolvedValueOnce({ key: 'key/q2' })
    .mockResolvedValueOnce({ key: 'key/a' });
  syncApi.commands.mockImplementation(async (_operationId, changes) => ({
    changed: changes.map((change) => ({ ...change, revision: 2 })),
  }));
  expect(await syncNow()).toBe(true);
  const record = syncApi.commands.mock.calls[0][1][0].record;
  expect(record.images).toEqual(['key/q', 'key/q2']);
  expect(record.answerImages).toEqual(['key/a']);
  expect(await db.outbox.count()).toBe(0);
});

it('云端拉取旧错题后实际刷新路径完成迁移并按当前 revision 入队', async () => {
  syncApi.records.mockResolvedValue({
    records: [
      {
        id: 'old-cloud',
        revision: 4,
        record: {
          id: 'old-cloud',
          type: 'mistake',
          stage: 1,
          mastered: 0,
          nextReviewAt: '2020-01-01',
        },
      },
    ],
  });
  expect(await syncNow()).toBe(true);
  const row = await db.mistakes.get('old-cloud');
  expect(row).toMatchObject({ stage: 4, _rev: 4 });
  expect(typeof row.nextReviewAt).toBe('number');
  expect(useMistakesStore().dueReview.map((x) => x.id)).toEqual(['old-cloud']);
  const pending = await db.outbox.where('recordId').equals('old-cloud').first();
  expect(pending.expectedRevision).toBe(4);
});

it('实际错题 store 保存后原子入队，题图和解析图补传完成再同步', async () => {
  const row = await useMistakesStore().add(
    reactive({
      content: '收录按钮回归',
      tags: ['真题'],
      images: [new Blob(['q1']), new Blob(['q2'])],
      answerImages: [new Blob(['a'])],
    }),
  );
  expect(await db.mistakes.count()).toBe(1);
  expect(await db.outbox.count()).toBe(1);
  attachmentApi.uploadImage
    .mockResolvedValueOnce({ key: 'key/q1' })
    .mockResolvedValueOnce({ key: 'key/q2' })
    .mockResolvedValueOnce({ key: 'key/a' });
  syncApi.commands.mockImplementation(async (_op, changes) => ({
    changed: changes.map((change) => ({ ...change, revision: 1 })),
  }));
  expect(await syncNow()).toBe(true);
  expect(await db.mistakes.get(row.id)).toMatchObject({
    tags: ['真题'],
    images: ['key/q1', 'key/q2'],
    answerImages: ['key/a'],
    _rev: 1,
  });
  expect(await db.outbox.count()).toBe(0);
});

it('错题图片上传完成时保留期间的文字与图片修改', async () => {
  const store = useMistakesStore();
  const row = await store.add({ content: '旧文字', images: [new Blob(['旧图片'])] });
  attachmentApi.uploadImage.mockImplementationOnce(async () => {
    await store.update(row.id, { content: '新文字', images: [new Blob(['新图片'])] });
    return { key: 'key/old' };
  });
  await syncNow();
  const saved = await db.mistakes.get(row.id);
  expect(saved.content).toBe('新文字');
  expect(await saved.images[0].text()).toBe('新图片');
  expect(syncApi.commands).not.toHaveBeenCalled();
});

it('错题图片上传完成时不重新提交已删除的记录', async () => {
  const store = useMistakesStore();
  const row = await store.add({ content: '即将删除', images: [new Blob(['图片'])] });
  attachmentApi.uploadImage.mockImplementationOnce(async () => {
    await store.remove(row.id);
    return { key: 'key/deleted' };
  });
  await syncNow();
  expect(await db.mistakes.get(row.id)).toBeUndefined();
  expect(await db.outbox.count()).toBe(0);
  expect(syncApi.commands).not.toHaveBeenCalled();
});

it('实际 outbox 写入失败时错题新增也回滚，重试不会重复收录', async () => {
  const fail = () => {
    throw new Error('outbox unavailable');
  };
  db.outbox.hook('creating', fail);
  try {
    await expect(useMistakesStore().add({ content: '原子写入' })).rejects.toThrow(
      'outbox unavailable',
    );
  } finally {
    db.outbox.hook('creating').unsubscribe(fail);
  }
  expect(await db.mistakes.count()).toBe(0);
  expect(await db.outbox.count()).toBe(0);
  expect(useMistakesStore().list).toHaveLength(0);
  await useMistakesStore().add({ content: '原子写入' });
  expect(await db.mistakes.count()).toBe(1);
  expect(await db.outbox.count()).toBe(1);
});

it('非法旧计时挂起待人工确认，其他任务继续同步且不计入本机时长', async () => {
  const bad = { id: 'invalid-old-session', status: 'done', actualSec: 999999 };
  await db.sessions.put(bad);
  await enqueueRecord('sessions', bad);
  await db.tasks.put({ id: 'healthy-task', title: '正常任务' });
  await enqueueRecord('tasks', { id: 'healthy-task', title: '正常任务' });
  syncApi.commands.mockRejectedValueOnce({
    code: 42201,
    status: 422,
    message: '计时起止时间不合法',
    data: { record_id: bad.id },
  });
  syncApi.commands.mockImplementation(async (_id, changes) => ({
    changed: changes.map((c) => ({ ...c, revision: 1 })),
  }));
  expect(await syncNow()).toBe(true);
  await waitForSync();
  expect(syncState.pendingConflicts.find((c) => c.id === bad.id).invalidSession).toBe(true);
  expect((await db.sessions.get(bad.id)).actualSec).toBe(0);
  expect((await db.sessions.get(bad.id)).validation_issue).toContain('不合法');
  expect((await db.tasks.get('healthy-task'))._rev).toBe(1);
  expect(await db.sessions.count()).toBe(1);
});

function seedDefaults() {
  return DEFAULT_SUBJECTS.map((s, i) => ({
    id: s.id,
    name: s.name,
    color: s.color,
    icon: s.icon,
    tags: [],
    order: i,
    archived: 0,
    builtin: 1,
    createdAt: 1,
  }));
}

it('新设备首登先拉云端科目，不把默认科目当冲突推送', async () => {
  const seeds = seedDefaults();
  await db.subjects.bulkAdd(seeds);
  const server = seeds.map((row, i) => ({
    id: row.id,
    revision: i + 3,
    record: { ...row, type: 'subject' },
  }));
  syncApi.records.mockResolvedValue({ records: server });
  await initSyncForUser();
  expect(syncApi.commands).not.toHaveBeenCalled();
  expect(await db.subjects.count()).toBe(8);
  expect((await db.subjects.get('math'))._rev).toBe(3);
  expect(syncState.pendingConflicts).toHaveLength(0);
  expect(await db.syncMeta.get('bootstrapDone')).toBeTruthy();
});

it('新账号云端为空时默认科目仍会上传，保留AI可用科目目录', async () => {
  const seeds = seedDefaults();
  await db.subjects.bulkAdd(seeds);
  syncApi.records.mockResolvedValue({ records: [] });
  syncApi.commands.mockImplementation(async (_operation, changes) => ({
    changed: changes.map((change) => ({ ...change, revision: 1 })),
  }));
  await initSyncForUser();
  expect(syncApi.commands).toHaveBeenCalledTimes(1);
  const sent = syncApi.commands.mock.calls[0][1];
  expect(sent.map((item) => item.id).sort()).toEqual(seeds.map((row) => row.id).sort());
  expect((await db.subjects.get('math'))._rev).toBe(1);
  expect(await db.syncMeta.get('bootstrapDone')).toBeTruthy();
});
