import { ref } from 'vue'
import { copyText } from '../utils/clipboard'

export function useClipboard(toast) {
  const manualCopy = ref(null)
  async function copy(value, successMessage = '已复制') {
    const text = String(value ?? '')
    if (!text) {
      toast('暂无可复制的内容')
      return false
    }
    if (await copyText(text)) {
      toast(successMessage)
      return true
    }
    manualCopy.value = text
    return false
  }
  return { copy, manualCopy }
}
