// @vitest-environment happy-dom
import { beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
vi.mock('../src/api', () => ({ schoolApi: { list: vi.fn() } }));
vi.mock('../src/db', () => {
  const db = { kv: { get: vi.fn(), put: vi.fn() } };
  return {
    db,
    activeAccountId: () => null,
    localAccountScope: () => ({ db, isCurrent: () => true, assertCurrent() {} }),
  };
});
import { schoolApi } from '../src/api';
import { db } from '../src/db';
import { useSchoolsStore } from '../src/stores/schools';

beforeEach(() => {
  vi.clearAllMocks();
  setActivePinia(createPinia());
  db.kv.get.mockResolvedValue(undefined);
  db.kv.put.mockResolvedValue(undefined);
});

it('自定义梦校进入目标选择，保存的是院校名称而不是内部 key', async () => {
  schoolApi.list.mockResolvedValue([
    { key: 'custom_ustc2', name: '中国科学院大学', short: '国科大', logo_key: '' },
  ]);
  const store = useSchoolsStore();
  await store.load();
  expect(store.choices.some((row) => row.key === 'custom_ustc2')).toBe(true);
  expect(store.nameFor('custom_ustc2')).toBe('中国科学院大学');
  expect(store.nameFor('中国科学院大学')).toBe('中国科学院大学');
  expect(store.shortFor('custom_ustc2')).toBe('国科大');
});

it('断网时保留内置院校作为兜底，不暴露相册字段', async () => {
  schoolApi.list.mockRejectedValue(new Error('offline'));
  const store = useSchoolsStore();
  await store.load();
  expect(store.choices.length).toBeGreaterThanOrEqual(7);
  expect(store.nameFor('tsinghua')).toBe('清华大学');
  expect(store.choices.every((row) => !('album_keys' in row))).toBe(true);
});
