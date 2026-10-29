// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import MessagesView from '../src/views/MessagesView.vue'
import { messageApi } from '../src/api'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn(), back: vi.fn() }) }))
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ toast: vi.fn() }) }))
vi.mock('../src/stores/notifications', () => ({
  useNotificationsStore: () => ({ unread: 55, refresh: vi.fn() }),
}))
vi.mock('../src/api', () => ({
  messageApi: { list: vi.fn(), read: vi.fn(), readAll: vi.fn() },
}))

it('消息中心可加载更早消息，并说明未读数与全部已读的范围', async () => {
  const newest = Array.from({ length: 50 }, (_, i) => ({
    id: 55 - i, title: `消息${55 - i}`, content: '内容', kind: 'system', is_read: false,
    created_at: '2026-10-26T00:00:00Z',
  }))
  const older = Array.from({ length: 5 }, (_, i) => ({
    id: 5 - i, title: `消息${5 - i}`, content: '内容', kind: 'system', is_read: false,
    created_at: '2026-10-25T00:00:00Z',
  }))
  messageApi.list.mockResolvedValueOnce(newest).mockResolvedValueOnce(older)
  const wrapper = mount(MessagesView)
  await flushPromises()
  expect(wrapper.text()).toContain('当前显示最近 50 条')
  expect(wrapper.text()).toContain('全部已读”会标记账号内全部消息')
  expect(wrapper.text()).toContain('包含尚未加载的更早消息')
  const more = wrapper.findAll('button').find((b) => b.text() === '加载更早消息')
  expect(more).toBeTruthy()
  await more.trigger('click')
  await flushPromises()
  expect(messageApi.list).toHaveBeenLastCalledWith(50, 6)
  expect(wrapper.findAll('.msg-row')).toHaveLength(55)
  expect(wrapper.text()).toContain('消息1')
  wrapper.unmount()
})
