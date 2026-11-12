// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils';
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import RoomView from '../src/views/RoomView.vue';
import { roomApi } from '../src/api';
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '7' }, name: 'room-detail' }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), back: vi.fn() }),
}));
vi.mock('../src/api', () => ({
  roomApi: {
    get: vi.fn(),
    preview: vi.fn(),
    join: vi.fn(),
    apply: vi.fn(),
    confirmSharing: vi.fn(),
    applies: vi.fn(),
  },
}));
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 2 }, isAdmin: true }) }));
vi.mock('../src/stores/timer', () => ({ useTimerStore: () => ({ current: null }) }));
vi.mock('../src/stores/subjects', () => ({ useSubjectsStore: () => ({ byId: {} }) }));
let wrapper;
beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  vi.stubGlobal('confirm', vi.fn().mockReturnValue(false));
});
afterEach(() => {
  wrapper?.unmount();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it('旧成员先看到共享说明，取消不提交，确认后重新拉取房间状态', async () => {
  roomApi.get.mockResolvedValue({
    room: { id: 7, name: '旧好友房', my_role: 'member', capacity: 0, sharing_confirmed: false },
    joined: true,
    members: [],
    messages: [],
  });
  roomApi.confirmSharing.mockResolvedValue({});
  wrapper = mount(RoomView, { global: { stubs: { BlobImage: true } } });
  await flushPromises();
  expect(wrapper.text()).toContain('旧房间需要重新确认共享');
  expect(wrapper.text()).toContain('不限人数');
  const button = wrapper.findAll('button').find((b) => b.text() === '了解并开启本房间共享');
  await button.trigger('click');
  expect(roomApi.confirmSharing).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  await button.trigger('click');
  await flushPromises();
  expect(roomApi.confirmSharing).toHaveBeenCalledExactlyOnceWith(7);
  expect(roomApi.get).toHaveBeenCalledTimes(2);
  expect(wrapper.findAll('button').some((b) => b.text() === '房间管理')).toBe(false);
});
it('公开预览也走申请，取消共享确认不会提交申请', async () => {
  roomApi.get.mockRejectedValue({ status: 403 });
  roomApi.preview.mockResolvedValue({
    room: { id: 7, name: '公开房间', visibility: 'public', capacity: 0 },
    joined: false,
    join_required: true,
    apply: null,
  });
  roomApi.apply.mockResolvedValue({});
  wrapper = mount(RoomView, { global: { stubs: { BlobImage: true } } });
  await flushPromises();
  expect(wrapper.text()).toContain('凭邀请或审批加入');
  const button = wrapper.findAll('button').find((b) => b.text() === '提交入房申请');
  await button.trigger('click');
  expect(roomApi.apply).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  await button.trigger('click');
  await flushPromises();
  expect(roomApi.apply).toHaveBeenCalledExactlyOnceWith(7, '', true);
});
