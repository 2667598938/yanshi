// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils';
import { expect, it, vi } from 'vitest';
import ResourcesView from '../src/views/ResourcesView.vue';
import { resourceApi } from '../src/api';

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}));
vi.mock('../src/api', () => ({ resourceApi: { list: vi.fn() } }));
vi.mock('../src/sync/community', () => ({
  favoriteRows: vi.fn(),
  pullCommunityMirrors: vi.fn(),
}));

it('加载更多追加旧资料，搜索从第一页重新开始', async () => {
  resourceApi.list
    .mockResolvedValueOnce({ items: [{ id: 9, title: '最新资料' }], next: 9 })
    .mockResolvedValueOnce({ items: [{ id: 8, title: '旧资料' }], next: null })
    .mockResolvedValueOnce({ items: [{ id: 5, title: '数学资料' }], next: null });
  const wrapper = mount(ResourcesView);
  try {
    await flushPromises();
    expect(wrapper.text()).toContain('最新资料');
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '加载更多')
      .trigger('click');
    await flushPromises();
    expect(resourceApi.list).toHaveBeenNthCalledWith(2, { page_size: 20, before_id: 9 });
    expect(wrapper.text()).toContain('最新资料');
    expect(wrapper.text()).toContain('旧资料');
    await wrapper.get('input[type="search"]').setValue('数学');
    await wrapper.get('form').trigger('submit');
    await flushPromises();
    expect(resourceApi.list).toHaveBeenNthCalledWith(3, { page_size: 20, q: '数学' });
    expect(wrapper.text()).toContain('数学资料');
    expect(wrapper.text()).not.toContain('旧资料');
  } finally {
    wrapper.unmount();
  }
});
