<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({ modelValue: { type: String, default: null } })
const emit = defineEmits(['update:modelValue'])
const field = ref(null)
let previousFocus = null
function selectAll() {
  field.value?.focus({ preventScroll: true })
  field.value?.select()
  field.value?.setSelectionRange(0, props.modelValue?.length || 0)
}
function close() {
  emit('update:modelValue', null)
  previousFocus?.focus?.({ preventScroll: true })
}
watch(() => props.modelValue, async (value) => {
  if (value === null) return
  previousFocus = document.activeElement
  await nextTick()
  selectAll()
}, { immediate: true })
</script>

<template>
  <div v-if="modelValue !== null" class="copy-mask" @click.self="close" @keydown.esc="close">
    <section role="dialog" aria-modal="true" aria-label="手动复制" class="copy-dialog">
      <h2>手动复制</h2>
      <p>请长按下面的内容选择“复制”，电脑可按 Ctrl+C 或 ⌘C。</p>
      <textarea ref="field" :value="modelValue" readonly rows="3" aria-label="待复制内容" />
      <div class="copy-actions">
        <button type="button" class="btn btn-outline" @click="selectAll">全选</button>
        <button type="button" class="btn btn-primary" @click="close">关闭</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.copy-mask { position: fixed; inset: 0; z-index: 2000; background: rgba(15, 23, 42, .5); display: flex; align-items: center; justify-content: center; padding: 20px; }
.copy-dialog { width: 100%; max-width: 420px; padding: 22px; border-radius: 18px; background: #fff; color: var(--ink); }
.copy-dialog h2 { margin: 0 0 10px; font-size: 18px; }
.copy-dialog p { margin: 0 0 14px; font-size: 13px; line-height: 1.6; color: var(--sub); }
.copy-dialog textarea { width: 100%; box-sizing: border-box; padding: 12px; border: 1px solid var(--line); border-radius: 10px; resize: vertical; font: inherit; font-size: 16px; user-select: text; -webkit-user-select: text; }
.copy-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
</style>
