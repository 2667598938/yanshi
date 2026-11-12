// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils';
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { db, activateAccount, localAccountScope } from '../src/db';
import { useTasksStore } from '../src/stores/tasks';
import { useLearningSettingsStore } from '../src/stores/learningSettings';
import { useProfileStore } from '../src/stores/profile';
import { writeRecord } from '../src/sync/engine';
import { timeNodeApi } from '../src/api';
import { useTimeNodesStore } from '../src/stores/timeNodes';
import TasksView from '../src/views/TasksView.vue';
import { todayKey } from '../src/utils/date';
vi.mock('../src/sync/engine', () => ({
  writeRecord: vi.fn(),
  patchRecord: vi.fn(),
  enqueueDelete: vi.fn(),
}));
vi.mock('../src/api', () => ({ timeNodeApi: { list: vi.fn() } }));
vi.mock('vue-router', () => ({ useRouter: () => ({ back: vi.fn(), push: vi.fn() }) }));
let wrapper;
beforeEach(async () => {
  await activateAccount(701);
  await db.open();
  vi.clearAllMocks();
});
afterEach(async () => {
  wrapper?.unmount();
  wrapper = null;
  vi.restoreAllMocks();
  await db.delete();
  await activateAccount(null);
});
it('明确清空日期的新任务保留无截止日期', async () => {
  const tasks = useTasksStore();
  const row = await tasks.add({ title: '无日期', dueDate: '' });
  expect(row.dueDate).toBe('');
});
it('今日已完成数量与比例一致，编辑无日期任务不暗改日期', async () => {
  const tasks = useTasksStore();
  tasks.list = [
    { id: 'a', title: '已完成', done: 1, dueDate: todayKey(), createdAt: 1 },
    { id: 'b', title: '未完成', done: 0, dueDate: todayKey(), createdAt: 2 },
    { id: 'c', title: '不设截止', done: 0, dueDate: '', createdAt: 3 },
  ];
  wrapper = mount(TasksView);
  expect(wrapper.text()).toContain('今天 1/2 项');
  expect(wrapper.text()).toContain('50%');
  await wrapper
    .findAll('.task-body')
    .find((row) => row.text().includes('不设截止'))
    .trigger('click');
  expect(wrapper.get('input[type="date"]').element.value).toBe('');
});
it('换账号后旧学习设置读取不能覆盖当前设置', async () => {
  let resolve;
  vi.spyOn(db.kv, 'get').mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const settings = useLearningSettingsStore();
  const pending = settings.load(true);
  await activateAccount(702);
  settings.value = {
    focusMin: 30,
    shortBreakMin: 5,
    longBreakMin: 15,
    longBreakEvery: 4,
    bulletEnabled: false,
  };
  resolve({ value: { focusMin: 99, shortBreakMin: 5, longBreakMin: 15, longBreakEvery: 4 } });
  await pending;
  expect(settings.value.focusMin).toBe(30);
});
it('换账号期间的旧个人资料保存不能写进新账号库', async () => {
  const { useAuthStore } = await import('../src/stores/auth');
  const auth = useAuthStore();
  auth.user = { id: 701, nickname: '原同学' };
  let resolve;
  vi.spyOn(db.kv, 'get').mockImplementationOnce(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const pending = useProfileStore()
    .save({ signature: '旧账号签名' })
    .catch((e) => e);
  await activateAccount(702);
  auth.user = { id: 702, nickname: '新同学' };
  resolve(undefined);
  await pending;
  expect(writeRecord).not.toHaveBeenCalled();
});

it('时间节点刷新保留待裁决的本地冲突版本', async () => {
  const { useAuthStore } = await import('../src/stores/auth');
  useAuthStore().user = { id: 701 };
  const value = {
    node_name: '本地改名',
    target_date: '2027-12-01',
    show_on_home: true,
    custom_msg: '',
  };
  await db.timeNodes.put({ id: 'node', value, _rev: 1 });
  await db.syncMeta.put({
    key: 'conflict:node',
    value: { id: 'node', localRecord: { type: 'timeNode', value } },
  });
  timeNodeApi.list.mockResolvedValue([{ id: 'node', _rev: 2, ...value, node_name: '云端改名' }]);
  await useTimeNodesStore().load(true);
  expect((await db.timeNodes.get('node')).value.node_name).toBe('本地改名');
});

it('账号切换开始即使旧库仍打开，也废止旧本地操作作用域', async () => {
  const scope = localAccountScope();
  const switching = activateAccount(702);
  expect(scope.isCurrent()).toBe(false);
  await switching;
  await activateAccount(701);
  expect(scope.isCurrent()).toBe(false);
  expect(() => scope.assertCurrent()).toThrow('账号已切换');
});

it('已完成历史按完成时间排列，不按未来截止日期倒排', async () => {
  const tasks = useTasksStore();
  tasks.list = [
    { id: 'a', title: '更早完成', done: 1, dueDate: '2030-01-01', doneAt: 100, createdAt: 1 },
    { id: 'b', title: '最近完成', done: 1, dueDate: '2026-01-01', doneAt: 200, createdAt: 2 },
  ];
  wrapper = mount(TasksView);
  expect(wrapper.findAll('.task-row.done').map((row) => row.text())).toEqual([
    expect.stringContaining('最近完成'),
    expect.stringContaining('更早完成'),
  ]);
});
