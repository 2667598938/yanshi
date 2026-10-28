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

it('输入、真实等待、首个delta、停止后，四种视觉状态与业务流程对应', async () => {
  let callback, finish
  aiApi.chatStream.mockImplementationOnce((_body, cb, options) => {
    callback = cb
    return new Promise(resolve => { finish = resolve; options.signal.addEventListener('abort', resolve) })
  })
  await render()
  expect(wrapper.classes()).toContain('state-idle')
  await wrapper.get('.composer input').trigger('focus')
  expect(wrapper.classes()).toContain('state-listening')
  await wrapper.get('.composer input').setValue('复盘今天')
  await wrapper.get('.send-btn').trigger('click'); await flushPromises()
  expect(wrapper.classes()).toContain('state-thinking')
  expect(wrapper.find('.thinking-row').exists()).toBe(true)
  callback({ type: 'delta', text: '**先复盘完成的任务。**' }); await flushPromises()
  expect(wrapper.classes()).toContain('state-delivering')
  expect(wrapper.find('.thinking-row').exists()).toBe(false)
  expect(wrapper.get('.answer strong').text()).toBe('先复盘完成的任务。')
  await wrapper.get('.send-btn.stop').trigger('click'); finish(); await flushPromises()
  expect(wrapper.classes()).toContain('state-idle')
})

it('图标按钮有可访问名称，空态提供文字动效入口且不伪造真实对话', async () => {
  await render()
  expect(wrapper.get('button[title="AI 设置"]').attributes('aria-label')).toBe('AI 设置')
  expect(wrapper.get('button[title="新建对话"]').attributes('aria-label')).toBe('新建对话')
  expect(wrapper.get('button[title="历史对话"]').attributes('aria-label')).toBe('历史对话')
  expect(wrapper.get('button[title="刷新会话列表"]').attributes('aria-label')).toBe('刷新会话列表')
  const themeButton = wrapper.findAll('.nav-actions button').find(b => b.attributes('title')?.startsWith('主题'))
  expect(themeButton.attributes('aria-label')).toContain('切换主题')
  const navDemo = wrapper.get('a[title="视觉动效演示"]')
  expect(navDemo.attributes('aria-label')).toBe('打开视觉动效演示')
  expect(navDemo.attributes('href')).toBe('/previews/ai-neural.html')
  const emptyDemo = wrapper.get('a[title="打开独立动效演示"]')
  expect(emptyDemo.attributes('href')).toBe('/previews/ai-neural.html')
  expect(emptyDemo.text()).toContain('看动效演示')
  expect(wrapper.text()).not.toContain('模拟生成')
})

it('中文输入法组合回车不误发，普通回车才提交；视觉演示独立于真实对话', async () => {
  aiApi.chatStream.mockResolvedValueOnce(undefined)
  await render(); await wrapper.get('.composer input').setValue('考研问题')
  await wrapper.get('.composer input').trigger('keyup', { key: 'Enter', isComposing: true }); await flushPromises()
  expect(aiApi.chatStream).not.toHaveBeenCalled()
  expect(wrapper.get('a[title="视觉动效演示"]').attributes('href')).toBe('/previews/ai-neural.html')
  expect(wrapper.text()).not.toContain('模拟生成')
  await wrapper.get('.composer input').trigger('keyup', { key: 'Enter', isComposing: false }); await flushPromises()
  expect(aiApi.chatStream).toHaveBeenCalledTimes(1)
})

it('软键盘缩小可见视口时收起底栏预留，卸载移除视口监听', async () => {
  const original = Object.getOwnPropertyDescriptor(window, 'visualViewport')
  const viewport = { height: window.innerHeight, addEventListener: vi.fn(), removeEventListener: vi.fn() }
  Object.defineProperty(window, 'visualViewport', { configurable: true, value: viewport })
  try {
    await render()
    const resize = viewport.addEventListener.mock.calls[0][1]
    viewport.height = window.innerHeight - 300; resize(); await flushPromises()
    expect(wrapper.attributes('style')).toContain('--ai-bottom-gap: 0px')
    expect(wrapper.attributes('style')).toContain('--ai-visible-height: ' + viewport.height + 'px')
    wrapper.unmount(); wrapper = null
    expect(viewport.removeEventListener).toHaveBeenCalledWith('resize', resize)
  } finally {
    if (original) Object.defineProperty(window, 'visualViewport', original)
    else delete window.visualViewport
  }
})

it('减少动态效果和系统主题改变可即时响应，卸载清理监听', async () => {
  const listeners = new Map()
  const createMedia = matches => ({ matches, addEventListener: vi.fn((_type, fn) => listeners.set(fn, true)), removeEventListener: vi.fn((_type, fn) => listeners.delete(fn)) })
  const motion = createMedia(false), color = createMedia(false)
  const media = vi.spyOn(window, 'matchMedia').mockImplementation(query => query.includes('reduced-motion') ? motion : query.includes('color-scheme') ? color : { matches: false })
  await render()
  motion.matches = true; motion.addEventListener.mock.calls[0][1]({ matches: true }); await flushPromises()
  expect(wrapper.classes()).toContain('reduce-motion')
  const themeButton = wrapper.findAll('.nav-actions button').at(-1)
  await themeButton.trigger('click'); expect(wrapper.classes()).toContain('theme-light')
  await themeButton.trigger('click'); expect(wrapper.classes()).toContain('theme-auto')
  color.matches = true; color.addEventListener.mock.calls[0][1]({ matches: true })
  expect(document.documentElement.classList.contains('ai-neural-dark')).toBe(false)
  wrapper.unmount(); wrapper = null
  expect(listeners.size).toBe(0)
  media.mockRestore()
})

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


it('新建对话后，旧历史请求不能覆盖新会话', async () => {
  aiApi.conversations.mockResolvedValue([{ id: 11, title: '旧会话' }])
  let resolve
  aiApi.conversation.mockImplementation(() => new Promise(r => { resolve = r }))
  await render()
  await wrapper.findAll('.nav-actions button')[2].trigger('click'); await flushPromises()
  await wrapper.get('.hist-row').trigger('click')
  await wrapper.findAll('.nav-actions button')[1].trigger('click')
  resolve({ id: 11, title: '过期历史标题', messages: [{ role: 'assistant', content: '过期历史正文' }] })
  await flushPromises()
  expect(wrapper.text()).not.toContain('过期历史标题')
  expect(wrapper.text()).not.toContain('过期历史正文')
})

it('先选A再选B，迟到的A历史响应不能覆盖B', async () => {
  aiApi.conversations.mockResolvedValue([{ id: 11, title: '会话A' }, { id: 12, title: '会话B' }])
  let resolve
  aiApi.conversation.mockImplementationOnce(() => new Promise(r => { resolve = r }))
    .mockResolvedValueOnce({ id: 12, title: '当前B', messages: [] })
  await render()
  await wrapper.findAll('.nav-actions button')[2].trigger('click'); await flushPromises()
  await wrapper.findAll('.hist-row')[0].trigger('click')
  await wrapper.findAll('.hist-row')[1].trigger('click'); await flushPromises()
  resolve({ id: 11, title: '旧A', messages: [] }); await flushPromises()
  expect(wrapper.text()).toContain('当前B'); expect(wrapper.text()).not.toContain('旧A')
})

it('确认任务导入后切到新对话，导入成功仍正常同步和提示',async()=>{
 aiApi.chatStream.mockImplementationOnce(async(_body,cb)=>cb({type:'done',message_id:101,suggested_tasks:[{title:'复习数学',estimated_min:30}]}))
 let resolve;aiApi.importTasks.mockImplementationOnce(()=>new Promise(r=>{resolve=r}))
 await render();await wrapper.get('.composer input').setValue('安排任务');await wrapper.get('.send-btn').trigger('click');await flushPromises()
 await wrapper.findAll('button').find(b=>b.text()==='一键导入为系统任务').trigger('click')
 await wrapper.findAll('button').find(b=>b.text()==='确认批量导入').trigger('click');await flushPromises()
 await wrapper.findAll('.nav-actions button')[1].trigger('click')
 resolve({state:'imported',imported_count:1});await flushPromises()
 expect(mocks.toast).toHaveBeenCalledWith(expect.stringContaining('任务已导入'))
})

it('配置读取失败时提示重新连接，不误导去配 Key',async()=>{
 aiApi.enabled.mockRejectedValueOnce(new Error('网络不可用'))
 await render()
 expect(wrapper.text()).toContain('AI 服务暂时连不上')
 expect(wrapper.text()).toContain('重新连接')
 expect(wrapper.text()).not.toContain('还差一步：配置你的 API Key')
 expect(wrapper.find('.composer').exists()).toBe(false)
 // 网络恢复后重试能回到正常对话
 aiApi.enabled.mockResolvedValue({enabled:true,access:true,v1_readonly:true})
 await wrapper.findAll('button').find(b=>b.text().includes('重新连接')).trigger('click')
 await flushPromises()
 expect(wrapper.find('.composer').exists()).toBe(true)
})

it('空态起步问题点一下填入输入框',async()=>{
 await render()
 const starter=wrapper.find('.starter')
 expect(starter.exists()).toBe(true)
 const text=starter.text().trim()
 await starter.trigger('click')
 expect(wrapper.get('.composer input').element.value).toBe(text)
})

it('生成结束不抢历史滚动位置，也不删除用户已经输入的下一条草稿', async () => {
  let callback, finish
  aiApi.chatStream.mockImplementationOnce((_body, cb) => {
    callback = cb
    return new Promise(resolve => { finish = resolve })
  })
  await render()
  await wrapper.get('.composer input').setValue('第一题')
  await wrapper.get('.send-btn').trigger('click'); await flushPromises()
  const scroll = wrapper.get('.chat-scroll')
  Object.defineProperties(scroll.element, { scrollHeight: { configurable: true, value: 1500 }, clientHeight: { configurable: true, value: 400 } })
  scroll.element.scrollTop = 100
  await scroll.trigger('scroll')
  await wrapper.get('.composer input').setValue('我正在写下一题')
  await db.kv.put({ key: 'ai:draft', value: { content: '我正在写下一题', images: [] } })
  callback({ type: 'done', message_id: 125 })
  finish(); await flushPromises()
  expect(scroll.element.scrollTop).toBe(100)
  expect((await db.kv.get('ai:draft'))?.value.content).toBe('我正在写下一题')
  expect(wrapper.get('.composer input').element.value).toBe('我正在写下一题')
})

it('打开历史对话立即显示加载骨架，返回后渲染列表',async()=>{
 let resolve
 aiApi.conversations.mockImplementation(()=>new Promise(r=>{resolve=r}))
 await render()
 await wrapper.findAll('.nav-actions button')[2].trigger('click')
 expect(wrapper.find('.hist-loading').exists()).toBe(true)
 resolve([{id:11,title:'旧会话'}])
 await flushPromises()
 expect(wrapper.find('.hist-loading').exists()).toBe(false)
 expect(wrapper.get('.hist-row').text()).toContain('旧会话')
})
