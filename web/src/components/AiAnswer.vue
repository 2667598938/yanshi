<script setup>
import { ref, watch } from 'vue'
import { renderMarkdown } from '../utils/markdown'
const props = defineProps({ content: { type: String, default: '' }, streaming: Boolean, reduced: Boolean })
const html = ref('')
let previousText = ''
// 只给刚到达的一小段文字做逐字淡入，避免长回答每段都生成数百个 span。
const MAX_ANIMATED = 60
// 仅为新到达的可见文字添加一次淡入。历史和已输出文字不反复播放；Markdown仍先转义。
watch(() => [props.content, props.streaming, props.reduced], ([content, streaming, reduced]) => {
  const template = document.createElement('template')
  template.innerHTML = renderMarkdown(content)
  const text = template.content.textContent || ''
  let common = 0
  while (common < text.length && common < previousText.length && text[common] === previousText[common]) common++
  if (streaming && !reduced && text.length > common) {
    const wrapFrom = Math.max(common, text.length - MAX_ANIMATED)
    const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
    const nodes = []
    while (walker.nextNode()) nodes.push(walker.currentNode)
    let offset = 0, index = 0
    for (const node of nodes) {
      const end = offset + node.textContent.length
      if (end > wrapFrom && !node.parentElement?.closest('pre,code')) {
        const split = Math.max(0, wrapFrom - offset)
        const fragment = document.createDocumentFragment()
        fragment.append(document.createTextNode(node.textContent.slice(0, split)))
        for (const char of node.textContent.slice(split)) {
          const span = document.createElement('span')
          span.className = 'stream-char'
          span.style.setProperty('--char-delay', `${Math.min(index++ * 12, 220)}ms`)
          span.textContent = char
          fragment.append(span)
        }
        node.replaceWith(fragment)
      }
      offset = end
    }
  }
  previousText = text
  html.value = template.innerHTML
}, { immediate: true })
</script>
<template>
  <div
    class="md"
    role="article"
    aria-label="AI 回答"
    aria-live="polite"
    :aria-busy="streaming ? 'true' : 'false'"
    v-html="html"
  ></div>
</template>
