// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { parse, compileStyle } from '@vue/compiler-sfc'
import BrandOpening from '../src/components/BrandOpening.vue'
import { BRAND } from '../src/config/brand'
import { createOpeningGate } from '../src/utils/openingPolicy'
const source = parse(readFileSync('src/components/BrandOpening.vue', 'utf8')).descriptor.styles
const css = source.map(style => compileStyle({ source: style.content, id: BrandOpening.__scopeId, scoped: true }).code).join('\n')
let wrapper, root, styles, motion, media
const layer = () => document.querySelector('.brand-opening')
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
  motion = new Set()
  media = { matches: false, addEventListener: vi.fn((_name, fn) => motion.add(fn)), removeEventListener: vi.fn((_name, fn) => motion.delete(fn)) }
  vi.spyOn(window, 'matchMedia').mockReturnValue(media)
  root = document.createElement('div'); root.id = 'app'; root.innerHTML = '<main id="main-content" tabindex="-1">已预载页面</main>'
  document.body.append(root); document.body.style.overflow = 'auto'
  styles = document.createElement('style'); styles.textContent = css; document.head.append(styles)
})
afterEach(() => { wrapper?.unmount(); root?.remove(); styles?.remove(); document.body.style.overflow = ''; document.documentElement.classList.remove('brand-opening-active', 'brand-opening-leaving'); vi.useRealTimers(); window.happyDOM.setViewport({ width: 1024, height: 768 }) })
function render(props = {}) { wrapper = mount(BrandOpening, { props, attachTo: document.body }); return wrapper }

it('3.8秒节奏完成后移除覆盖层，恢复滚动与页面交互', async () => {
  render(); await nextTick()
  expect(layer().parentElement).toBe(document.body)
  expect(root.hasAttribute('inert')).toBe(true)
  expect(document.body.style.overflow).toBe('hidden')
  await vi.advanceTimersByTimeAsync(3099)
  expect(layer().classList.contains('is-leaving')).toBe(false)
  await vi.advanceTimersByTimeAsync(1)
  expect(layer().classList.contains('is-leaving')).toBe(true)
  expect(document.documentElement.classList.contains('brand-opening-leaving')).toBe(true)
  expect(root.hasAttribute('inert')).toBe(true)
  await vi.advanceTimersByTimeAsync(700)
  expect(layer()).toBeNull()
  expect(root.hasAttribute('inert')).toBe(false)
  expect(root.hasAttribute('aria-hidden')).toBe(false)
  expect(document.body.style.overflow).toBe('auto')
  expect(wrapper.emitted('done')).toHaveLength(1)
})
it('跳过在160毫秒内平滑结束，重复点击只完成一次', async () => {
  render(); await nextTick()
  await vi.advanceTimersByTimeAsync(350)
  document.querySelector('.opening-skip').click()
  document.querySelector('.opening-skip').click()
  await vi.advanceTimersByTimeAsync(159); expect(layer()).not.toBeNull()
  await vi.advanceTimersByTimeAsync(1); expect(layer()).toBeNull()
  await vi.advanceTimersByTimeAsync(4000)
  expect(wrapper.emitted('done')).toHaveLength(1)
  expect(vi.getTimerCount()).toBe(0)
})
it('减少动态效果时500毫秒结束，不播放微粒或光圈', async () => {
  media.matches = true; render(); await nextTick()
  expect(layer().classList.contains('is-reduced')).toBe(true)
  expect(getComputedStyle(document.querySelector('.opening-particles')).display).toBe('none')
  await vi.advanceTimersByTimeAsync(500)
  expect(layer()).toBeNull()
})
it('中途切换减少动态效果也会缩短，卸载清除计时器与监听', async () => {
  render(); await nextTick()
  for (const handler of motion) handler({ matches: true })
  await nextTick()
  expect(layer().classList.contains('is-reduced')).toBe(true)
  wrapper.unmount(); wrapper = null
  expect(document.body.style.overflow).toBe('auto')
  expect(root.hasAttribute('inert')).toBe(false)
  expect(motion.size).toBe(0)
  expect(vi.getTimerCount()).toBe(0)
})
it('键盘可跳过，背景页面不能通过Tab获得焦点', async () => {
  render(); await nextTick()
  const event = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true })
  document.dispatchEvent(event)
  expect(event.defaultPrevented).toBe(true)
  expect(document.activeElement).toBe(document.querySelector('.opening-skip'))
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', cancelable: true }))
  await vi.advanceTimersByTimeAsync(160)
  expect(layer()).toBeNull()
})
it('名称在字动画前完整占位，迟到的公共名称不会改变正在显示的行', async () => {
  render(); await nextTick()
  await wrapper.setProps({ siteName: '我的研时' })
  expect(document.querySelectorAll('.opening-name span')).toHaveLength(4)
  expect(document.querySelector('.opening-name').getAttribute('aria-label')).toBe('我的研时')
  await vi.advanceTimersByTimeAsync(1000)
  await wrapper.setProps({ siteName: '迟到名称' })
  expect(document.querySelector('.opening-name').textContent).toBe('我的研时')
})
it('Logo载入失败使用书本占位，不使用高校校徽', async () => {
  render(); await nextTick()
  document.querySelector('.opening-logo img').dispatchEvent(new Event('error'))
  await nextTick()
  expect(document.querySelector('.opening-logo img')).toBeNull()
  expect(document.querySelector('.opening-logo svg').getAttribute('aria-label')).toBe('书本标志')
})
it.each([[1920,1080],[1440,900],[1366,768],[1024,768],[768,1024],[430,932],[390,844],[320,568],[844,390],[960,300]])('视口 %i×%i 全屏且保留跳过与完整文字', async (width, height) => {
  window.happyDOM.setViewport({ width, height }); render(); await nextTick()
  const computed = getComputedStyle(layer())
  expect(computed.position).toBe('fixed')
  expect(computed.width).toBe('100%')
  expect(computed.height).toBe('100%')
  expect(document.querySelector('.opening-content').textContent).toContain(BRAND.tagline)
  expect(document.querySelector('.opening-skip').disabled).toBe(false)
})
it('隐藏页面立即释放覆盖层，回来不会被旧遮罩锁住', async () => {
  render(); await nextTick()
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
  document.dispatchEvent(new Event('visibilitychange')); await nextTick()
  expect(layer()).toBeNull()
  expect(document.body.style.overflow).toBe('auto')
})
it('会话标记跨加载保留，切路由不重新播放', () => {
  const values = new Map(), storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) }
  const gate = createOpeningGate()
  expect(gate(BRAND.opening, storage)).toBe(true)
  expect(gate(BRAND.opening, storage)).toBe(false)
  expect(createOpeningGate()(BRAND.opening, storage)).toBe(false)
  expect(createOpeningGate()(BRAND.opening, { getItem: () => null, setItem() {} })).toBe(true)
})
it('策略可关闭或总是播放，存储不可用也不会报错', () => {
  const gate = createOpeningGate(), denied = { getItem() { throw Error('denied') }, setItem() { throw Error('denied') } }
  expect(gate({ ...BRAND.opening, policy: 'off' }, denied)).toBe(false)
  expect(gate({ ...BRAND.opening, policy: 'always' }, denied)).toBe(true)
  expect(gate(BRAND.opening, denied)).toBe(true)
  expect(gate(BRAND.opening, denied)).toBe(false)
})
