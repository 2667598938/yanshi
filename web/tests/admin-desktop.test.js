// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils';
import { it, expect, vi, beforeEach, afterEach } from 'vitest';
import AdminView from '../src/views/AdminView.vue';
import { adminApi } from '../src/api';
vi.mock('vue-router', () => ({
  useRouter: () => ({ back: vi.fn(), push: vi.fn(), replace: vi.fn() }),
}));
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ isAdmin: true }) }));
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock('../src/api', () => ({
  adminApi: { overview: vi.fn(), members: vi.fn(), invites: vi.fn(), announcements: vi.fn() },
  inspirationApi: {},
}));
let wrapper;
beforeEach(() => {
  adminApi.overview.mockResolvedValue({ member_count: 25 });
  adminApi.members.mockResolvedValue(
    Array.from({ length: 25 }, (_, i) => ({
      id: i + 1,
      nickname: '成员' + (i + 1),
      email: `member${i + 1}@example.com`,
      role: i ? 'member' : 'admin',
      status: 'active',
    })),
  );
  adminApi.invites.mockResolvedValue([]);
  adminApi.announcements.mockResolvedValue([]);
});
afterEach(() => wrapper?.unmount());
it('电脑表格可搜索与分页，账号操作仍使用同一个成员', async () => {
  wrapper = mount(AdminView, {
    global: { stubs: { RouterLink: true, BlobImage: true, CopyFallback: true } },
  });
  await flushPromises();
  await wrapper.findAll('.tabs button')[1].trigger('click');
  expect(wrapper.findAll('.desktop-table tbody tr')).toHaveLength(20);
  await wrapper
    .findAll('button')
    .find((b) => b.text() === '下一页')
    .trigger('click');
  expect(wrapper.findAll('.desktop-table tbody tr')).toHaveLength(5);
  expect(wrapper.get('.desktop-table tbody').text()).toContain('成员25');
  await wrapper.get('input[type="search"]').setValue('member25@');
  expect(wrapper.findAll('.desktop-table tbody tr')).toHaveLength(1);
  expect(wrapper.get('.admin-pagination').text()).toContain('第 1 / 1 页');
  await wrapper.get('.desktop-table button[title="会员调整"]').trigger('click');
  expect(wrapper.get('.sheet-title').text()).toContain('成员25');
});
