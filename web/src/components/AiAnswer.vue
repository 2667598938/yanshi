<script setup>
import { ref, watch } from 'vue'
import { renderMarkdown } from '../utils/markdown'
const props = defineProps({ content: { type: String, default: '' }, streaming: Boolean, reduced: Boolean })
const html = ref('')
let previousText = ''
// 仅为新到达的可见文字添加一次淡入。历史和已输出文字不反复播放；Markdown仍先转义。
watch(() => [props.content, props.streaming, props.reduced], ([content, streaming, reduced]) => {
  const template = document.createElement('template')
  template.innerHTML = renderMarkdown(content)
  const text = template.content.textContent || ''
  let common = 0
  while (common < text.length && common < previousText.length && text[common] === previousText[common]) common++
  if (streaming && !reduced && text.length > common) {
    const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
    const nodes = []
    while (walker.nextNode()) nodes.push(walker.currentNode)
    let offset = 0, index = 0
    for (const node of nodes) {
      const end = offset + node.textContent.length
      if (end > common && !node.parentElement?.closest('pre,code')) {
        const split = Math.max(0, common - offset)
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
<template><div class="md" v-html="html"></div></template>
