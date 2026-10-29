// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import RoomView from '../src/views/RoomView.vue'
import { roomApi } from '../src/api'
vi.mock('vue-router', () => ({ useRoute: () => ({ params: { id: '5' }, name: 'room-detail' }), useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }))
vi.mock('../src/api', () => ({ roomApi: { get: vi.fn(), preview: vi.fn() } }))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 1 }, isAdmin: false }) }))
vi.mock('../src/stores/timer', () => ({ useTimerStore: () => ({ current: null }) }))
vi.mock('../src/stores/subjects', () => ({ useSubjectsStore: () => ({ byId: {} }) }))
let wrapper
afterEach(() => { wrapper?.unmount(); vi.useRealTimers() })
it('详情请求被拒后恰好审批通过，预览显示已入房时不能永远卡在骨架屏', async () => {
  vi.useFakeTimers()
  roomApi.get.mockRejectedValueOnce({ status: 403, message: '尚未加入' }).mockResolvedValue({
    room: { id: 5, name: '审批通过的房间', capacity: 4 }, joined: true, members: [], messages: [],
  })
  roomApi.preview.mockResolvedValue({ joined: true, room: { id: 5 } })
  wrapper = mount(RoomView, { global: { stubs: { BlobImage: true } } })
  await flushPromises(); await flushPromises()
  expect(roomApi.get).toHaveBeenCalledTimes(2)
  expect(wrapper.find('.page-skeleton').exists()).toBe(false)
  expect(wrapper.text()).toContain('审批通过的房间')
})
