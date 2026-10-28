// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { readFileSync } from 'node:fs'
import { parse, compileStyle } from '@vue/compiler-sfc'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../src/App.vue'
import AuthView from '../src/views/auth/AuthView.vue'
vi.mock('../src/composables/useGroupPresence', () => ({ useGroupPresence: vi.fn() }))
vi.mock('../src/composables/useTimerOwnership', () => ({ useTimerOwnership: vi.fn() }))
vi.mock('../src/stores/timer', () => ({ useTimerStore: () => ({}) }))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ user: null }) }))
vi.mock('../src/stores/notifications', () => ({ useNotificationsStore: () => ({ unread: 0, start: vi.fn(), stop: vi.fn() }) }))
vi.mock('../src/stores/subjects', () => ({ useSubjectsStore: () => ({ byId: {} }) }))
vi.mock('../src/sync/engine', () => ({ initSyncForUser: vi.fn() }))
vi.mock('../src/api', () => ({ authApi: {}, publicApi: { config: vi.fn(async () => ({ enabled_auth_channels: ['email'] })) } }))
const globalCSS = readFileSync('src/assets/styles/main.css', 'utf8') + '\n' + readFileSync('src/assets/styles/responsive.css', 'utf8')
const authStyles = parse(readFileSync('src/views/auth/AuthView.vue', 'utf8')).descriptor.styles
const authCSS = authStyles.map(style => compileStyle({ source: style.content, id: AuthView.__scopeId, scoped: style.scoped }).code).join('\n')
let wrapper, styles
afterEach(() => { wrapper?.unmount(); styles?.remove(); window.happyDOM.setViewport({ width: 1024, height: 768 }) })
async function render(width) {
  window.happyDOM.settings.disableComputedStyleRendering = false
  window.happyDOM.setViewport({ width, height: 768 })
  styles = document.createElement('style'); styles.textContent = globalCSS + '\n' + authCSS; document.head.append(styles)
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/login', name: 'login', component: AuthView, meta: { hideTabbar: true } },
    { path: '/', name: 'home', component: { template: '<div>今日</div>' } },
  ] })
  await router.push('/login'); await router.isReady()
  wrapper = mount(App, { attachTo: document.body, global: { plugins: [router], stubs: {
    SessionIssues: true, CommunityIssues: true, OfflineBanner: true, ToastLayer: true, ConflictDialog: true } } })
  await flushPromises()
}
it.each([1024, 1093, 1366, 1440, 1920])('电脑有效宽度 %ipx 登录外壳全宽，品牌与表单并排', async width => {
  await render(width)
  expect(wrapper.get('.app-shell').classes()).toContain('login-shell')
  expect(getComputedStyle(wrapper.get('.app-shell').element).maxWidth).toBe('none')
  expect(getComputedStyle(wrapper.get('.auth-layout').element).gridTemplateColumns).toContain('1.12fr')
  expect(getComputedStyle(wrapper.get('.auth-intro').element).display).not.toBe('none')
  expect(getComputedStyle(wrapper.get('.mobile-brand').element).display).toBe('none')
  expect(wrapper.find('.desktop-nav').exists()).toBe(false)
})
it.each([320, 360, 390, 430, 768])('窄屏有效宽度 %ipx 显示紧凑表单，注册内容可继续滚动', async width => {
  await render(width)
  expect(getComputedStyle(wrapper.get('.auth-intro').element).display).toBe('none')
  expect(getComputedStyle(wrapper.get('.mobile-brand').element).display).toBe('flex')
  expect(getComputedStyle(wrapper.get('.auth-layout').element).gridTemplateColumns).not.toContain('1.12fr')
  await wrapper.findAll('.tabs button')[1].trigger('click')
  expect(wrapper.find('#auth-confirm').exists()).toBe(true)
  expect(getComputedStyle(wrapper.get('.auth-card').element).overflowY).not.toBe('hidden')
  expect(getComputedStyle(wrapper.get('.code-row input').element).minWidth).toBe('0')
})
// happy-dom 的计算样式在 resize 后存在缓存，不能用于证明真实窗口缩放。
// 上面各宽度使用独立组件与样式表；实际拖动窗口、像素与触控另行验收。
