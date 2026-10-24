import { reactive } from 'vue'

export const toastState = reactive({ list: [] })
let seq = 0

// 全局轻提示
export function toast(msg, duration = 2000) {
  const item = { id: ++seq, msg }
  toastState.list.push(item)
  setTimeout(() => {
    const i = toastState.list.findIndex((x) => x.id === item.id)
    if (i >= 0) toastState.list.splice(i, 1)
  }, duration)
}

export function useToast() {
  return { toast }
}
