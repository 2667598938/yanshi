// @vitest-environment happy-dom
// 只验证实际组件的媒体规则与导航/编辑交互；像素、触控仍由真实浏览器验收。
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../src/App.vue'
import TasksView from '../src/views/TasksView.vue'
import { readFileSync } from 'node:fs'
const baseCSS = readFileSync('src/assets/styles/main.css', 'utf8')
const responsiveCSS = readFileSync('src/assets/styles/responsive.css', 'utf8')
vi.mock('../src/composables/useGroupPresence', () => ({ useGroupPresence: vi.fn() }))
vi.mock('../src/composables/useTimerOwnership', () => ({ useTimerOwnership: vi.fn() }))
vi.mock('../src/stores/timer', () => ({ useTimerStore: () => ({}) }))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 1 }, isAdmin: true, isLoggedIn: true }) }))
vi.mock('../src/stores/notifications', () => ({ useNotificationsStore: () => ({ unread: 0, start: vi.fn(), stop: vi.fn() }) }))
vi.mock('../src/stores/subjects', () => ({ useSubjectsStore: () => ({ active: [], byId: {} }) }))
let wrapper, style
afterEach(() => { wrapper?.unmount(); style?.remove(); window.happyDOM.setViewport({ width: 1024, height: 768 }) })
async function render(width) {
  window.happyDOM.settings.disableComputedStyleRendering = false
  window.happyDOM.setViewport({ width, height: 900 })
  style = document.createElement('style'); style.textContent = baseCSS + '\n' + responsiveCSS; document.head.append(style)
  const placeholder = { template: '<div class="page">页面内容</div>' }
  const paths = ['/', '/focus', '/tasks', '/mistakes', '/stats', '/ai', '/rooms', '/group', '/resources', '/posts', '/dream-wall', '/messages', '/me', '/admin', '/login']
  const router = createRouter({ history: createMemoryHistory(), routes: paths.map(path => ({ path,
    name: path === '/' ? 'home' : path.slice(1), component: path === '/tasks' ? TasksView : placeholder,
    meta: { hideTabbar: path === '/tasks' || path === '/login' } })) })
  await router.push('/tasks'); await router.isReady()
  wrapper = mount(App, { attachTo: document.body, global: { plugins: [router], stubs: {
    SessionIssues: true, CommunityIssues: true, OfflineBanner: true, ToastLayer: true, ConflictDialog: true } } })
  await flushPromises()
  return router
}
it.each([1024, 1366, 1440, 1920])('电脑宽度 %ipx 能通过导航进入二级页，编辑区与列表同时保留', async (width) => {
  const router = await render(width)
  expect(getComputedStyle(wrapper.get('.desktop-nav').element).display).not.toBe('none')
  expect(getComputedStyle(wrapper.get('.task-workspace').element).display).toBe('grid')
  await wrapper.findAll('button').find(b => b.text().includes('新建任务')).trigger('click')
  expect(wrapper.find('.task-editor-mask').exists()).toBe(true)
  expect(getComputedStyle(wrapper.get('.task-editor-mask').element).position).toBe('sticky')
  expect(wrapper.find('.rate-card').exists()).toBe(true)
  await wrapper.get('.desktop-nav a[href="/stats"]').trigger('click'); await flushPromises()
  expect(router.currentRoute.value.path).toBe('/stats')
  expect(wrapper.get('.app-main').attributes('data-view')).toBe('stats')
})
it.each([360, 390, 430])('手机宽度 %ipx 隐藏侧栏，任务编辑仍能打开与取消', async (width) => {
  await render(width)
  expect(getComputedStyle(wrapper.get('.desktop-nav').element).display).toBe('none')
  await wrapper.findAll('button').find(b => b.text().includes('新建任务')).trigger('click')
  expect(wrapper.find('.sheet').exists()).toBe(true)
  expect(getComputedStyle(wrapper.get('.task-editor-mask').element).position).not.toBe('sticky')
  await wrapper.findAll('.sheet button').find(b => b.text() === '取消').trigger('click')
  expect(wrapper.find('.sheet').exists()).toBe(false)
})
