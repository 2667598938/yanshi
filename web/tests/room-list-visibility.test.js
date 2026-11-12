// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils';
import { it, expect, vi } from 'vitest';
import RoomsView from '../src/views/RoomsView.vue';
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn(), back: vi.fn() }) }));
vi.mock('../src/api', () => ({
  publicApi: { config: vi.fn().mockResolvedValue({ features: ['text_room', 'av_room'] }) },
  roomApi: {
    list: vi.fn().mockResolvedValue([
      { id: 1, name: '已经加入的私密房', visibility: 'private', joined: true, capacity: 50 },
      { id: 2, name: '公开研友房', visibility: 'public', joined: false, capacity: 50 },
      { id: 3, name: '他人的秘密房', visibility: 'private', joined: false, capacity: 50 },
    ]),
  },
}));
it('我的私密房可见，同时不将未加入的私密房放入公开列表', async () => {
  const wrapper = mount(RoomsView);
  await flushPromises();
  expect(wrapper.text()).toContain('我的房间');
  expect(wrapper.text()).toContain('已经加入的私密房');
  expect(wrapper.text()).toContain('公开房间');
  expect(wrapper.text()).toContain('公开研友房');
  expect(wrapper.text()).not.toContain('他人的秘密房');
  wrapper.unmount();
});
