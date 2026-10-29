// @vitest-environment happy-dom
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { copyText } from '../src/utils/clipboard'
import RoomsView from '../src/views/RoomsView.vue'
import RoomView from '../src/views/RoomView.vue'
import { roomApi } from '../src/api'

const mocks = vi.hoisted(() => ({ toast: vi.fn(), push: vi.fn(), replace: vi.fn(), timer: { current: null, rest: null } }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push, replace: mocks.replace, back: vi.fn() }),
  useRoute: () => ({ params: { id: '2' } }),
}))
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ toast: mocks.toast }) }))
vi.mock('../src/stores/timer', () => ({ useTimerStore: () => mocks.timer }))
vi.mock('../src/stores/subjects', () => ({ useSubjectsStore: () => ({ byId: {} }) }))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 2 }, isAdmin: false }) }))
vi.mock('../src/api', () => ({ publicApi: { config: vi.fn().mockResolvedValue({ features: ['checkin_room'] }) }, roomApi: { get: vi.fn(), list: vi.fn(), heartbeat: vi.fn(), putGoal: vi.fn(), leave: vi.fn() } }))

let wrapper
let originalClipboard
let originalExecCommand
const room = { id: 2, name: '私密验收001', visibility: 'private', joined: true,
  code: 'AB12CD', my_role: 'owner', capacity: 4, member_count: 1, owner: { nickname: 'A' } }

function clipboard(value) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value })
}
beforeEach(() => {
  mocks.timer.current = null
  mocks.timer.rest = null
  originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
  originalExecCommand = Object.getOwnPropertyDescriptor(document, 'execCommand')
  clipboard(undefined) // 模拟局域网 HTTP 下没有现代 Clipboard API
  Object.defineProperty(document, 'execCommand', { configurable: true, value: vi.fn(() => false) })
  roomApi.list.mockResolvedValue([room])
  roomApi.get.mockResolvedValue({ room, joined: true, members: [], messages: [], ranking: {} })
  roomApi.heartbeat.mockResolvedValue({})
  roomApi.putGoal.mockResolvedValue({})
  roomApi.leave.mockResolvedValue({ left: true })
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard)
  else delete navigator.clipboard
  if (originalExecCommand) Object.defineProperty(document, 'execCommand', originalExecCommand)
  else delete document.execCommand
  document.body.innerHTML = ''
})

it('现代剪贴板可用时写入原文，不创建兼容节点', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  clipboard({ writeText })
  expect(await copyText('AB12CD')).toBe(true)
  expect(writeText).toHaveBeenCalledWith('AB12CD')
  expect(document.execCommand).not.toHaveBeenCalled()
  expect(document.querySelector('textarea')).toBeNull()
})

it('HTTP 无现代接口时选中完整文本复制，并清理节点、恢复原输入焦点与光标', async () => {
  const previous = document.createElement('input')
  previous.value = 'previous input'
  document.body.appendChild(previous)
  previous.focus()
  previous.setSelectionRange(1, 4)
  document.execCommand.mockImplementation((command) => {
    const input = document.activeElement
    expect(command).toBe('copy')
    expect(input.value).toBe('AB12CD')
    expect(input.readOnly).toBe(true)
    expect(input.selectionStart).toBe(0)
    expect(input.selectionEnd).toBe(6)
    return true
  })
  expect(await copyText('AB12CD')).toBe(true)
  expect(document.querySelector('textarea')).toBeNull()
  expect(document.activeElement).toBe(previous)
  expect(previous.selectionStart).toBe(1)
  expect(previous.selectionEnd).toBe(4)
})

it('现代接口拒绝权限时仍尝试兼容复制', async () => {
  clipboard({ writeText: vi.fn().mockRejectedValue(new Error('denied')) })
  document.execCommand.mockReturnValue(true)
  expect(await copyText('邀请码')).toBe(true)
  expect(document.execCommand).toHaveBeenCalledWith('copy')
})

it('浏览器复制报错时返回失败并清理临时节点', async () => {
  document.execCommand.mockImplementation(() => { throw new Error('unsupported') })
  expect(await copyText('链接')).toBe(false)
  expect(document.querySelector('textarea')).toBeNull()
})

it('没有任一复制接口和空内容均不误报成功', async () => {
  delete document.execCommand
  expect(await copyText('AB12CD')).toBe(false)
  expect(await copyText(null)).toBe(false)
  expect(await copyText('')).toBe(false)
})

it.each([
  ['房间列表', RoomsView, '.rc-code'],
  ['房间详情', RoomView, '.room-code'],
])('%s 在 HTTP 环境点击房间码可以走兼容复制', async (_name, component, selector) => {
  document.execCommand.mockReturnValue(true)
  wrapper = mount(component, { global: { stubs: { BlobImage: true } } })
  await flushPromises()
  await wrapper.get(selector).trigger('click')
  await flushPromises()
  expect(document.execCommand).toHaveBeenCalledWith('copy')
  expect(mocks.toast).toHaveBeenCalledWith(expect.stringContaining('房间码已复制'))
  expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  expect(mocks.push).not.toHaveBeenCalled() // 列表复制不应触发进入房间
})

it.each([
  ['房间列表', RoomsView, '.rc-code'],
  ['房间详情', RoomView, '.room-code'],
])('%s 复制受限时显示可选择的房间码，关闭后仍在原页面', async (_name, component, selector) => {
  wrapper = mount(component, { attachTo: document.body, global: { stubs: { BlobImage: true } } })
  await flushPromises()
  await wrapper.get(selector).trigger('click')
  await flushPromises()
  expect(wrapper.get('[role="dialog"]').attributes('aria-label')).toBe('手动复制')
  const field = wrapper.get('textarea[aria-label="待复制内容"]')
  expect(field.element.value).toBe('AB12CD')
  expect(field.element.readOnly).toBe(true)
  expect(field.element.selectionStart).toBe(0)
  expect(field.element.selectionEnd).toBe(6)
  expect(mocks.toast).not.toHaveBeenCalledWith(expect.stringContaining('已复制'))
  await wrapper.findAll('button').find((button) => button.text() === '全选').trigger('click')
  expect(field.element.selectionEnd).toBe(6)
  await wrapper.findAll('button').find((button) => button.text() === '关闭').trigger('click')
  expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
})

it('房间展示选定形象和休息状态，心跳也上报休息', async () => {
  mocks.timer.rest = { finished: false }
  roomApi.get.mockResolvedValue({ room: { ...room, online_count: 1 }, joined: true,
    members: [{ user_id: 2, nickname: 'A', figure_id: 'figure-8', online: true,
      role: 'owner', presence: { status: 'resting' } }], messages: [], ranking: {} })
  wrapper = mount(RoomView, { global: { stubs: { BlobImage: true } } })
  await flushPromises()
  expect(wrapper.text()).toContain('🌲')
  expect(wrapper.text()).toContain('休息中')
  expect(roomApi.heartbeat).not.toHaveBeenCalled() // 站点按设备统一上报，避免房间页面覆盖其他设备
})

it('目标分数字段提交字符串，空字段不传null', async () => {
  wrapper = mount(RoomView, { global: { stubs: { BlobImage: true } } })
  await flushPromises()
  await wrapper.findAll('button').find((button) => button.text() === '填写我的目标').trigger('click')
  await wrapper.get('input[placeholder="如 400"]').setValue('400')
  await wrapper.findAll('button').find((button) => button.text() === '保存').trigger('click')
  await flushPromises()
  expect(roomApi.putGoal).toHaveBeenCalledWith({ target_school: '', target_score: '400', words: '' }, 2)
})

it('申请分享链接只暴露预览入口，不附带房间码', async () => {
  wrapper = mount(RoomView, { global: { stubs: { BlobImage: true } } })
  await flushPromises()
  await wrapper.findAll('button').find((button) => button.text() === '申请链接').trigger('click')
  await flushPromises()
  const value = wrapper.get('textarea[aria-label="待复制内容"]').element.value
  expect(new URL(value).pathname).toBe('/rooms/2')
  expect(value).not.toContain('AB12CD')
})

it('普通成员可退出房间，立即停止以成员身份继续参与', async () => {
  vi.stubGlobal('confirm', vi.fn(() => true))
  roomApi.get.mockResolvedValue({ room: { ...room, my_role: 'member' }, joined: true,
    members: [], messages: [], ranking: {} })
  wrapper = mount(RoomView, { global: { stubs: { BlobImage: true } } })
  await flushPromises()
  await wrapper.findAll('button').find((button) => button.text() === '退出房间').trigger('click')
  await flushPromises()
  expect(roomApi.leave).toHaveBeenCalledWith(2)
  expect(mocks.replace).toHaveBeenCalledWith('/rooms')
})
