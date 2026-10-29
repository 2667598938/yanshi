// @vitest-environment happy-dom
// 回归：手机端场景条必须换行，不能靠无提示横向滚动把最后一个场景裁掉。
import { readFileSync } from 'node:fs'
import { afterEach, expect, it } from 'vitest'

const aiCSS = readFileSync('src/assets/styles/ai-neural.css', 'utf8')
let style
let host

afterEach(() => {
  host?.remove()
  style?.remove()
  host = null
  style = null
  window.happyDOM.setViewport({ width: 1024, height: 768 })
})

function renderSceneBar(width) {
  window.happyDOM.settings.disableComputedStyleRendering = false
  window.happyDOM.setViewport({ width, height: 844 })
  style = document.createElement('style')
  style.textContent = aiCSS
  document.head.append(style)
  host = document.createElement('div')
  host.className = 'ai-wrap neural state-idle'
  host.innerHTML = '<div class="scene-bar">' +
    '<button class="scene-chip on">考研答疑</button><button class="scene-chip">通用问答</button>' +
    '<button class="scene-chip">作文批改</button><button class="scene-chip">计划生成</button>' +
    '<button class="scene-chip">学习复盘</button></div>'
  document.body.append(host)
  return getComputedStyle(host.querySelector('.scene-bar'))
}

it.each([390, 430])('%ipx 手机宽度下场景条换行而不是隐藏最后一项', (width) => {
  const bar = renderSceneBar(width)
  expect(bar.flexWrap).toBe('wrap')
  expect(bar.overflowX).not.toBe('auto')
})
