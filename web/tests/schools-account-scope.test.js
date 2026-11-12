// @vitest-environment happy-dom
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { db, activateAccount, localAccountScope } from '../src/db';
import { useSchoolsStore } from '../src/stores/schools';
import { useAuthStore } from '../src/stores/auth';
import { afterLogin, afterLogout } from '../src/sync/account';
import { schoolApi } from '../src/api';
vi.mock('../src/api', () => ({
  schoolApi: { list: vi.fn() },
  timeNodeApi: { list: vi.fn(async () => []) },
  authApi: {},
}));
vi.mock('../src/sync/engine', () => ({
  resetSyncRuntime: vi.fn(),
  initSyncForUser: vi.fn(),
  writeRecord: vi.fn(),
  patchRecord: vi.fn(),
  enqueueDelete: vi.fn(),
}));
const row = (key) => ({ key, name: key, logo_key: '', album_keys: [] });
beforeEach(() => {
  schoolApi.list.mockReset();
});
afterEach(async () => {
  await db.delete();
  await activateAccount(null);
});

it('真实换号流程清空 A 的私人目录，并加载 B；登出不保留目录', async () => {
  const auth = useAuthStore(),
    schools = useSchoolsStore();
  auth.user = { id: 881 };
  await afterLogin(881);
  schoolApi.list.mockResolvedValueOnce([row('a-private')]);
  await schools.load();
  auth.user = { id: 882 };
  await afterLogin(882);
  expect(schools.rows).toEqual([]);
  schoolApi.list.mockResolvedValueOnce([row('b-private')]);
  await schools.load();
  expect(schools.rows.map((r) => r.key)).toEqual(['b-private']);
  expect(schoolApi.list).toHaveBeenCalledTimes(2);
  auth.user = null;
  await afterLogout();
  expect(schools.rows).toEqual([]);
});

it('保存与删除统一更新已打开的房间选项以及本机目录', async () => {
  await activateAccount(883);
  const schools = useSchoolsStore();
  schoolApi.list.mockResolvedValueOnce([row('old')]);
  await schools.load();
  await schools.updateCatalog([row('new')]);
  expect(schools.choices.some((r) => r.key === 'old')).toBe(false);
  expect(schools.choices.some((r) => r.key === 'new')).toBe(true);
  expect((await db.kv.get('schools:catalog')).value).toEqual([row('new')]);
  await schools.updateCatalog([]);
  expect(schools.choices.some((r) => r.key === 'new')).toBe(false);
});

it('延迟的 A 请求不能覆盖 B 的目录或写入 B 的数据库', async () => {
  await activateAccount(884);
  const schools = useSchoolsStore();
  let finishA;
  schoolApi.list.mockReturnValueOnce(
    new Promise((resolve) => {
      finishA = resolve;
    }),
  );
  const requestA = schools.load();
  await vi.waitFor(() => expect(schoolApi.list).toHaveBeenCalledTimes(1));
  await activateAccount(885);
  schools.resetForAccount();
  schoolApi.list.mockResolvedValueOnce([row('B')]);
  await schools.load();
  finishA([row('A')]);
  await requestA;
  expect(schools.rows).toEqual([row('B')]);
  expect((await db.kv.get('schools:catalog')).value).toEqual([row('B')]);
});

it('A→B→A 的旧请求和旧编辑作用域仍然失效', async () => {
  await activateAccount(886);
  const scope = localAccountScope(),
    schools = useSchoolsStore();
  let finishA;
  schoolApi.list.mockReturnValueOnce(
    new Promise((resolve) => {
      finishA = resolve;
    }),
  );
  const old = schools.load();
  await vi.waitFor(() => expect(schoolApi.list).toHaveBeenCalledTimes(1));
  await activateAccount(887);
  schools.resetForAccount();
  await activateAccount(886);
  schools.resetForAccount();
  schoolApi.list.mockResolvedValueOnce([row('current-A')]);
  await schools.load();
  finishA([row('stale-A')]);
  await old;
  await expect(schools.updateCatalog([row('stale-edit')], scope)).rejects.toThrow('账号已切换');
  expect(schools.rows).toEqual([row('current-A')]);
});

it('断网保留本账号缓存，下一次加载能够恢复网络结果', async () => {
  await activateAccount(888);
  await db.kv.put({ key: 'schools:catalog', value: [row('cached')] });
  const schools = useSchoolsStore();
  schoolApi.list.mockRejectedValueOnce(new Error('offline'));
  await schools.load();
  expect(schools.rows).toEqual([row('cached')]);
  expect(schools.loaded).toBe(false);
  schoolApi.list.mockResolvedValueOnce([row('online')]);
  await schools.load();
  expect(schools.rows).toEqual([row('online')]);
  expect(schools.loaded).toBe(true);
});

it('刚保存的目录不会被保存前发出的读取请求覆盖', async () => {
  await activateAccount(889);
  const schools = useSchoolsStore();
  let finish;
  schoolApi.list.mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const old = schools.load();
  await vi.waitFor(() => expect(schoolApi.list).toHaveBeenCalledTimes(1));
  await schools.updateCatalog([row('saved')]);
  finish([row('stale')]);
  await old;
  expect(schools.rows).toEqual([row('saved')]);
});
