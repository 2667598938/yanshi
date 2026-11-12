// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils';
import { it, expect, vi } from 'vitest';
import TimeNodesHome from '../src/components/TimeNodesHome.vue';
import { useClockStore } from '../src/stores/clock';
import { dayKey, diffDayKeys } from '../src/utils/date';
import HomeView from '../src/views/HomeView.vue';
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('../src/stores/auth', () => ({
  useAuthStore: () => ({ user: { exam_date: '2026-10-30' } }),
}));
vi.mock('../src/stores/timeNodes', () => ({
  useTimeNodesStore: () => ({
    load: vi.fn().mockResolvedValue(),
    list: [
      {
        id: 'exam',
        value: {
          node_name: '模拟考试',
          target_date: '2026-10-30',
          show_on_home: true,
          custom_msg: '',
        },
      },
    ],
  }),
}));
it('跨北京时间午夜，节点刷新且首页仅保留紧凑初试倒计时', async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
  vi.setSystemTime(new Date('2026-10-29T15:59:59Z'));
  const clock = useClockStore();
  clock.start();
  const wrapper = mount(TimeNodesHome, { global: { stubs: { RouterLink: true } } });
  try {
    await flushPromises();
    expect(wrapper.get('strong').text()).toBe('还有 1 天');
    await vi.advanceTimersByTimeAsync(16000);
    await flushPromises();
    expect(wrapper.get('strong').text()).toBe('还有 0 天');
    const home = mount(HomeView, {
      global: { stubs: { SchoolHero: true, RouterLink: { template: '<a><slot/></a>' } } },
    });
    try {
      expect(home.findComponent(TimeNodesHome).exists()).toBe(false);
      expect(home.get('.exam-strip').text()).toContain('还有 0 天');
      expect(home.find('.hero-toggle').exists()).toBe(false);
      expect(home.text()).toContain('开始一次专注');
    } finally {
      home.unmount();
    }
  } finally {
    wrapper.unmount();
    clock.stop();
    vi.useRealTimers();
  }
});
it('业务归日按北京时间，日期差不受设备夏令时影响', () => {
  expect(dayKey(new Date('2026-10-29T16:01:00Z'))).toBe('2026-10-30');
  expect(diffDayKeys('2026-03-08', '2026-03-09')).toBe(1);
});
