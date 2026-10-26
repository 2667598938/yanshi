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
vi.mock('../src/api', () => ({ aiApi: { enabled: vi.fn(), key: vi.fn(), scenes: vi.fn(), createConversation: vi.fn(), chatStream: vi.fn(), importTasks: vi.fn(), undoTasks: vi.fn(), conversations: vi.fn(), conversation: vi.fn() },
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


it('任务建议必须预览并再次确认；取消不会写入，隐藏通用工具', async () => {
  aiApi.enabled.mockResolvedValue({enabled:true,access:true,v1_readonly:true})
  aiApi.chatStream.mockImplementationOnce(async (_body,cb)=>{
    cb({type:'delta',text:'明天复习数学'})
    cb({type:'done',message_id:72,suggested_tasks:[{title:'复习积分',due_date:'2026-10-26',estimated_min:40}]})
  })
  aiApi.importTasks.mockResolvedValue({})
  await render()
  expect(wrapper.text()).not.toContain('只读学习工具')
  await wrapper.get('.composer input').setValue('生成明天计划')
  await wrapper.get('.send-btn').trigger('click');await flushPromises()
  const click=async(text)=>{await wrapper.findAll('button').find(b=>b.text()===text).trigger('click');await flushPromises()}
  await click('一键导入为系统任务')
  expect(wrapper.text()).toContain('复习积分')
  expect(aiApi.importTasks).not.toHaveBeenCalled()
  await click('取消')
  expect(aiApi.importTasks).not.toHaveBeenCalled()
  await click('一键导入为系统任务');await click('确认批量导入')
  expect(aiApi.importTasks).toHaveBeenCalledExactlyOnceWith(72,[0])
})

it('无有效结构化建议时保持普通文本回复且不出现导入按钮', async () => {
  aiApi.chatStream.mockImplementationOnce(async(_body,cb)=>{cb({type:'delta',text:'```json broken```'});cb({type:'done',message_id:73,suggested_tasks:[]})})
  await render();await wrapper.get('.composer input').setValue('复盘');await wrapper.get('.send-btn').trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('broken')
  expect(wrapper.text()).not.toContain('一键导入为系统任务')
})

it('可选部分任务导入，撤销必须确认并展示保留成果', async()=>{
 aiApi.chatStream.mockImplementationOnce(async(_body,cb)=>cb({type:'done',message_id:80,suggested_tasks:[{title:'数学',estimated_min:30},{title:'英语',estimated_min:20}]}))
 aiApi.importTasks.mockResolvedValue({state:'imported',imported_count:1})
 aiApi.undoTasks.mockResolvedValue({state:'undone',imported_count:1,undo:{deleted:0,kept:[{reason:'已完成'}]}})
 await render();await wrapper.get('.composer input').setValue('安排计划');await wrapper.get('.send-btn').trigger('click');await flushPromises()
 const click=async(text)=>{await wrapper.findAll('button').find(b=>b.text()===text).trigger('click');await flushPromises()}
 await click('一键导入为系统任务');await wrapper.findAll('.sheet input[type="checkbox"]')[1].setValue(false);await click('确认批量导入')
 expect(aiApi.importTasks).toHaveBeenCalledExactlyOnceWith(80,[0]);expect(wrapper.text()).toContain('已导入 1 项任务')
 const confirmation=vi.fn().mockReturnValue(false);vi.stubGlobal('confirm',confirmation)
 await click('撤销本次导入');expect(aiApi.undoTasks).not.toHaveBeenCalled()
 confirmation.mockReturnValue(true);await click('撤销本次导入');expect(aiApi.undoTasks).toHaveBeenCalledExactlyOnceWith(80)
 expect(wrapper.text()).toContain('保留 1 项');vi.unstubAllGlobals()
})

it('权限到期或未配Key仍可打开并阅读本人历史，不能发送新请求',async()=>{
 aiApi.enabled.mockResolvedValue({enabled:false,access:false,v1_readonly:true})
 aiApi.conversations.mockResolvedValue([{id:91,title:'本人旧会话'}])
 aiApi.conversation.mockResolvedValue({id:91,title:'本人旧会话',messages:[{id:92,role:'assistant',content:'这是我保存的学习复盘'}]})
 await render();expect(wrapper.find('.composer').exists()).toBe(false)
 await wrapper.findAll('.nav-actions .icon-btn')[2].trigger('click');await flushPromises()
 await wrapper.get('.hist-row').trigger('click');await flushPromises()
 expect(wrapper.get('.chat-scroll').text()).toContain('这是我保存的学习复盘')
 expect(wrapper.find('.composer').exists()).toBe(false)
 expect(aiApi.chatStream).not.toHaveBeenCalled()
})
