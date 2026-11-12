import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useClockStore } from '../src/stores/clock';
import { useMistakesStore } from '../src/stores/mistakes';
import { useTasksStore } from '../src/stores/tasks';

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  setActivePinia(createPinia());
});
afterEach(() => {
  useClockStore().stop();
  vi.useRealTimers();
});

it('时钟推进后，跨日任务和到期错题无需刷新就重新计算', () => {
  vi.setSystemTime(new Date('2026-10-26T23:59:30+08:00'));
  const clock = useClockStore();
  const tasks = useTasksStore();
  const mistakes = useMistakesStore();
  clock.tick();
  tasks.list = [{ id: 't1', title: '今日任务', dueDate: '2026-10-26', done: 0, createdAt: 1 }];
  mistakes.list = [
    {
      id: 'm1',
      mastered: 0,
      nextReviewAt: new Date('2026-10-27T00:00:05+08:00').getTime(),
      createdAt: 1,
      sourceDate: '2026-10-26',
    },
  ];
  expect(tasks.todayAll.map((x) => x.id)).toEqual(['t1']);
  expect(mistakes.dueReview).toEqual([]);

  vi.setSystemTime(new Date('2026-10-27T00:00:10+08:00'));
  clock.tick();
  expect(clock.today).toBe('2026-10-27');
  expect(tasks.todayAll).toEqual([]);
  expect(tasks.overdueCount).toBe(1);
  expect(mistakes.dueReview.map((x) => x.id)).toEqual(['m1']);
});
