// @vitest-environment node
import { readFileSync } from 'node:fs'
import { Window } from 'happy-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
let browser
beforeEach(() => vi.useFakeTimers())
afterEach(async () => { await browser?.happyDOM.close(); vi.useRealTimers() })
function load(reduced = false) {
  browser = new Window({ url: 'file:///preview/ai-neural.html', settings: { enableJavaScriptEvaluation: true } })
  const source = readFileSync('public/previews/ai-neural.html', 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  browser.document.write(source.replace(/<script>[\s\S]*?<\/script>/, ''))
  browser.setTimeout = setTimeout; browser.clearTimeout = clearTimeout
  browser.fetch = vi.fn(() => { throw Error('视觉演示不应请求任何接口') })
  browser.matchMedia = query => ({ matches: query.includes('reduced-motion') && reduced, addEventListener() {} })
  browser.eval(script)
  return browser.document
}
it('单文件可从file地址运行，模拟生成完整经过thinking与delivering，且不请求接口', async () => {
  const doc = load()
  doc.getElementById('prompt').value = '<img src=x onerror=alert(1)>'
  doc.getElementById('form').dispatchEvent(new browser.Event('submit', { cancelable: true }))
  expect(doc.getElementById('demo').classList.contains('state-thinking')).toBe(true)
  expect(doc.querySelector('.chat-msg.user img')).toBeNull()
  await vi.advanceTimersByTimeAsync(1400)
  expect(doc.getElementById('demo').classList.contains('state-delivering')).toBe(true)
  await vi.advanceTimersByTimeAsync(4000)
  expect(doc.getElementById('demo').classList.contains('state-idle')).toBe(true)
  expect(doc.getElementById('answer-text').textContent).toContain('先完成两项最重要的任务')
  expect(doc.getElementById('details').hidden).toBe(false)
  expect(browser.fetch).not.toHaveBeenCalled()
})
it('减少动态效果快速完成；主题切换与重置恢复空态', async () => {
  const doc = load(true)
  doc.getElementById('form').dispatchEvent(new browser.Event('submit', { cancelable: true }))
  await vi.advanceTimersByTimeAsync(80)
  expect(doc.getElementById('answer-text').textContent).toContain('就很好')
  expect(doc.querySelectorAll('.stream-char').length).toBe(0)
  doc.getElementById('theme').click()
  expect(doc.getElementById('demo').classList.contains('theme-light')).toBe(true)
  doc.getElementById('reset').click()
  expect(doc.getElementById('result').hidden).toBe(true)
  expect(doc.getElementById('welcome').hidden).toBe(false)
  expect(doc.getElementById('demo').classList.contains('is-empty')).toBe(true)
})
it('停止演示后旧计时器不能回填或继续输出', async () => {
  const doc = load()
  doc.getElementById('form').dispatchEvent(new browser.Event('submit', { cancelable: true }))
  doc.getElementById('form').dispatchEvent(new browser.Event('submit', { cancelable: true }))
  await vi.advanceTimersByTimeAsync(5000)
  expect(doc.getElementById('answer-text')).toBeNull()
  expect(doc.getElementById('demo').classList.contains('state-idle')).toBe(true)
})
