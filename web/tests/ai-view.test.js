// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import AiView from '../src/views/AiView.vue'
import { aiApi, attachmentApi } from '../src/api'
import { db } from '../src/db'
const mocks = vi.hoisted(() => ({ toast: vi.fn(), push: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 2 } }) }))
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ toast: mocks.toast }) }))
vi.mock('../src/api', () => ({ aiApi: { enabled: vi.fn(), key: vi.fn(), scenes: vi.fn(), createConversation: vi.fn(), chatStream: vi.fn() },
  attachmentApi: { uploadImage: vi.fn() } }))
let wrapper
beforeEach(async () => {
  await db.open()
  aiApi.enabled.mockResolvedValue({ enabled: true, access: true, vision: true, tools: true,
    model_vision: true, model_tools: true, search: true })
  aiApi.key.mockResolvedValue({ configured: true })
  aiApi.scenes.mockResolvedValue([])
  aiApi.createConversation.mockResolvedValue({ id: 41 })
})
afterEach(async () => { wrapper?.unmount(); await db.delete() })
async function render() {
  wrapper = mount(AiView, { global: { stubs: { BlobImage: true } } })
  await flushPromises()
}

it('首次发送创建会话，真实逐段回调会立即更新文字，后续发送复用会话', async () => {
  let callback, finish
  aiApi.chatStream.mockImplementationOnce((_body, cb) => {
    callback = cb
    return new Promise((resolve) => { finish = resolve })
  })
  await render()
  await wrapper.get('.composer input').setValue('第一题')
  await wrapper.get('.send-btn').trigger('click')
  await flushPromises()
  expect(aiApi.createConversation).toHaveBeenCalledTimes(1)
  expect(aiApi.chatStream.mock.calls[0][0].conversation_id).toBe(41)
  callback({ type: 'delta', text: '正在解释' })
  await flushPromises()
  expect(wrapper.text()).toContain('正在解释')
  callback({ type: 'done', conversation_id: 41, title: '第一题' })
  finish(); await flushPromises()
  aiApi.chatStream.mockResolvedValueOnce(undefined)
  await wrapper.get('.composer input').setValue('继续')
  await wrapper.get('.send-btn').trigger('click'); await flushPromises()
  expect(aiApi.createConversation).toHaveBeenCalledTimes(1)
})

it('部分图片上传失败保留所有选择，重试后按原顺序发送；回答失败保留问题与图片', async () => {
  let failed = false
  attachmentApi.uploadImage.mockImplementation(async (file) => {
    if (file.name === 'first.jpg' && !failed) { failed = true; throw new Error('first failed') }
    return { key: 'ai/' + file.name }
  })
  await render()
  const picker = wrapper.get('input[type="file"]')
  Object.defineProperty(picker.element, 'files', { configurable: true, value: [
    new File(['a'], 'first.jpg', { type: 'image/jpeg' }), new File(['b'], 'second.jpg', { type: 'image/jpeg' })] })
  await picker.trigger('change'); await flushPromises()
  expect(wrapper.findAll('.ai-images > div')).toHaveLength(2)
  await wrapper.get('.composer input').setValue('分析这两题')
  await wrapper.get('.send-btn').trigger('click'); await flushPromises()
  expect(aiApi.chatStream).not.toHaveBeenCalled()
  await wrapper.findAll('button').find((button) => button.text() === '上传/重试').trigger('click')
  await flushPromises()
  aiApi.chatStream.mockImplementationOnce(async (_body, cb) => cb({ type: 'error', message: 'upstream failed' }))
  await wrapper.get('.send-btn').trigger('click'); await flushPromises()
  expect(aiApi.chatStream.mock.calls[0][0].image_keys).toEqual(['ai/first.jpg', 'ai/second.jpg'])
  expect(wrapper.get('.composer input').element.value).toBe('分析这两题')
  expect(wrapper.findAll('.ai-options .ai-images > div')).toHaveLength(2)
})
