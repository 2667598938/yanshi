import Dexie from 'dexie';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/sync/engine', () => ({
  enqueueRecord: vi.fn(),
  enqueueDelete: vi.fn(),
  initSyncForUser: vi.fn(),
  resetSyncRuntime: vi.fn(),
}));

let database;
beforeEach(async () => {
  vi.resetModules();
  database = await import('../src/db');
  await database.activateAccount(null);
});
afterEach(async () => {
  database.db.close();
  for (const name of await Dexie.getDatabaseNames()) await Dexie.delete(name);
});

describe('账号独立本地库', () => {
  it('A 直接切到首次登录 B，不迁移或清除 A 的未同步数据', async () => {
    const { db, activateAccount, currentKey, CUR_KEY } = database;
    await activateAccount(1);
    await db.tasks.add({ id: 'a-local', title: 'A 未同步' });
    await db.outbox.add({ recordId: 'a-local', type: 'task' });
    localStorage.setItem(currentKey(), 'A 计时');
    localStorage.setItem(CUR_KEY, '独立游客计时');
    await activateAccount(2, { migrateGuest: true });
    expect(await db.tasks.count()).toBe(0);
    expect(await db.outbox.count()).toBe(0);
    expect(localStorage.getItem(currentKey())).toBeNull();
    expect(localStorage.getItem(CUR_KEY)).toBe('独立游客计时');
    await activateAccount(1, { migrateGuest: true });
    expect((await db.tasks.get('a-local')).title).toBe('A 未同步');
    expect(await db.outbox.count()).toBe(1);
    expect(localStorage.getItem(currentKey())).toBe('A 计时');
  });

  it('游客首次认领完整迁移，包含队列、解析图、社区记录和计时', async () => {
    const { db, activateAccount, CUR_KEY, currentKey } = database;
    await db.mistakes.add({ id: 'guest', answerImages: [new Blob(['answer'])] });
    await db.outbox.add({ recordId: 'guest', type: 'mistake' });
    await db.localPosts.add({ id: 'post' });
    await db.localFavs.add({ resourceId: 1 });
    await db.kv.put({ key: 'school', value: 'pku' });
    localStorage.setItem(CUR_KEY, '游客计时');
    await activateAccount(3, { migrateGuest: true });
    expect(await (await db.mistakes.get('guest')).answerImages[0].text()).toBe('answer');
    expect(await db.outbox.count()).toBe(1);
    expect(await db.localPosts.count()).toBe(1);
    expect(await db.localFavs.count()).toBe(1);
    expect((await db.kv.get('school')).value).toBe('pku');
    expect(localStorage.getItem(currentKey())).toBe('游客计时');
    expect(localStorage.getItem(CUR_KEY)).toBeNull();
    await activateAccount(null);
    expect(await db.mistakes.count()).toBe(0);
    expect(await db.outbox.count()).toBe(0);
  });

  it('直接切换到已有账号只读取目标账号自己的记录', async () => {
    const { db, activateAccount } = database;
    await activateAccount(6);
    await db.tasks.add({ id: 'b-task' });
    await activateAccount(7);
    await db.tasks.add({ id: 'a-task' });
    await activateAccount(6, { migrateGuest: true });
    expect((await db.tasks.toArray()).map((row) => row.id)).toEqual(['b-task']);
    await activateAccount(7);
    expect((await db.tasks.toArray()).map((row) => row.id)).toEqual(['a-task']);
  });

  it('已有账号（包括仅 kv）不混入游客记录或计时', async () => {
    const { db, activateAccount, CUR_KEY, currentKey } = database;
    await activateAccount(4);
    await db.kv.put({ key: 'own', value: 'keep' });
    await activateAccount(null);
    await db.tasks.add({ id: 'guest' });
    localStorage.setItem(CUR_KEY, 'guest timer');
    await activateAccount(4, { migrateGuest: true });
    expect(await db.tasks.count()).toBe(0);
    expect((await db.kv.get('own')).value).toBe('keep');
    expect(localStorage.getItem(currentKey())).toBeNull();
    await activateAccount(null);
    expect(await db.tasks.count()).toBe(1);
    expect(localStorage.getItem(CUR_KEY)).toBe('guest timer');
  });

  it('目标写入失败时回滚整个迁移并保留游客库', async () => {
    const { db, activateAccount, activeAccountId } = database;
    await db.tasks.add({ id: 'guest' });
    await db.sessions.add({ id: 'session' });
    const failTargetWrite = (instance) => {
      if (instance.name === 'yanshi_db_u5')
        instance.on('ready', () => {
          instance.tasks.hook('creating', () => {
            throw new Error('disk full');
          });
        });
    };
    Dexie.addons.push(failTargetWrite);
    try {
      await expect(activateAccount(5, { migrateGuest: true })).rejects.toThrow('disk full');
    } finally {
      Dexie.addons.splice(Dexie.addons.indexOf(failTargetWrite), 1);
    }
    expect(activeAccountId()).toBeNull();
    expect(await db.tasks.count()).toBe(1);
    expect(await db.sessions.count()).toBe(1);
    await activateAccount(5, { migrateGuest: true });
    expect(await db.tasks.count()).toBe(1);
    expect(await db.sessions.count()).toBe(1);
  });
});
