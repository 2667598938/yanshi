// @vitest-environment happy-dom
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { flushPromises } from '@vue/test-utils';
import { createRouter, createMemoryHistory } from 'vue-router';
import { authorizeRoute } from '../src/router/access';
import { useAuthStore } from '../src/stores/auth';
import { authApi } from '../src/api';
import { afterLogin } from '../src/sync/account';

const state = vi.hoisted(() => ({ router: null }));
vi.mock('../src/router', () => ({
  get default() {
    return state.router;
  },
}));
vi.mock('../src/api', () => ({
  authApi: { refresh: vi.fn(), me: vi.fn() },
  publicApi: { config: vi.fn(async () => ({ site_name: '研时' })) },
}));
vi.mock('../src/sync/account', () => ({ afterLogin: vi.fn(), afterLogout: vi.fn() }));
vi.mock('../src/stores/timer', () => ({ useTimerStore: () => ({ resumeOnLoad: vi.fn() }) }));
vi.mock('../src/stores/profile', () => ({ useProfileStore: () => ({ load: vi.fn() }) }));
vi.mock('../src/stores/subjects', () => ({ useSubjectsStore: () => ({ byId: {} }) }));
vi.mock('../src/stores/notifications', () => ({
  useNotificationsStore: () => ({ start: vi.fn(), stop: vi.fn() }),
}));
vi.mock('../src/stores/clock', () => ({
  useClockStore: () => ({ start: vi.fn(), stop: vi.fn() }),
}));
vi.mock('../src/composables/useGroupPresence', () => ({ useGroupPresence: vi.fn() }));
vi.mock('../src/composables/useTimerOwnership', () => ({ useTimerOwnership: vi.fn() }));
vi.mock('../src/components/DesktopNav.vue', () => ({ default: { template: '<div />' } }));
vi.mock('../src/components/TabBar.vue', () => ({ default: { template: '<div />' } }));
vi.mock('../src/components/SessionIssues.vue', () => ({ default: { template: '<div />' } }));
vi.mock('../src/components/CommunityIssues.vue', () => ({ default: { template: '<div />' } }));
vi.mock('../src/components/ToastLayer.vue', () => ({ default: { template: '<div />' } }));
vi.mock('../src/components/ConflictDialog.vue', () => ({ default: { template: '<div />' } }));
vi.mock('../src/components/OfflineBanner.vue', () => ({ default: { template: '<div />' } }));
beforeEach(() => {
  vi.resetAllMocks();
  document.body.innerHTML = '<div id="brand-opening"></div><div id="app">正在准备</div>';
  state.router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>本人学习工作台</div>' } },
      {
        path: '/login',
        name: 'login',
        component: { template: '<div>账号登录</div>' },
        meta: { hideTabbar: true },
      },
    ],
  });
  state.router.beforeEach((to) => authorizeRoute(to, useAuthStore()));
});
afterEach(async () => {
  document.getElementById('app')?.__vue_app__?.unmount();
  document.getElementById('brand-opening')?.__vue_app__?.unmount();
  await flushPromises();
  document.body.innerHTML = '';
});
it('真实启动入口并行播放品牌层，等Cookie恢复后才进入本人首页', async () => {
  let resolve;
  authApi.refresh.mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  authApi.me.mockResolvedValue({ id: 91, role: 'member' });
  await import('../src/main.js?startup=valid');
  await flushPromises();
  expect(document.querySelector('.brand-opening')).not.toBeNull();
  expect(state.router.currentRoute.value.matched).toHaveLength(0);
  expect(document.getElementById('app').textContent).toBe('正在准备');
  resolve({ access_token: 'test-access', user: { id: 91, role: 'member' } });
  await vi.waitFor(() =>
    expect(document.getElementById('app').textContent).toContain('本人学习工作台'),
  );
  expect(afterLogin).toHaveBeenCalledWith(91);
  expect(state.router.currentRoute.value.path).toBe('/');
});
it('真实启动清除已过期缓存，不曾渲染游客或旧账号首页', async () => {
  localStorage.setItem('yanshi:session', JSON.stringify({ id: 92, nickname: '过期账号' }));
  authApi.refresh.mockRejectedValueOnce({ status: 401 });
  await import('../src/main.js?startup=expired');
  await vi.waitFor(() => expect(document.getElementById('app').textContent).toContain('账号登录'));
  expect(document.getElementById('app').textContent).not.toContain('本人学习工作台');
  expect(afterLogin).not.toHaveBeenCalled();
});
it('已在首页时会话失效，立即卸载学习内容并返回登录', async () => {
  authApi.refresh.mockResolvedValueOnce({
    access_token: 'test-access',
    user: { id: 93, role: 'member' },
  });
  authApi.me.mockResolvedValueOnce({ id: 93, role: 'member' });
  await import('../src/main.js?startup=cleared');
  await vi.waitFor(() =>
    expect(document.getElementById('app').textContent).toContain('本人学习工作台'),
  );
  useAuthStore().clear();
  await vi.waitFor(() => expect(state.router.currentRoute.value.path).toBe('/login'));
  expect(document.getElementById('app').textContent).not.toContain('本人学习工作台');
});
