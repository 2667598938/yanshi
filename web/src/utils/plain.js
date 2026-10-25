import { toRaw } from 'vue'

// IndexedDB 不能克隆 Vue Proxy。递归还原数组/普通对象，同时保留图片等原生数据。
export function toPlain(value) {
  const raw = toRaw(value)
  if (Array.isArray(raw)) return raw.map(toPlain)
  if (raw && typeof raw === 'object') {
    if (raw instanceof Date || raw instanceof Blob || raw instanceof ArrayBuffer || ArrayBuffer.isView(raw)) return raw
    return Object.fromEntries(Object.entries(raw).map(([key, item]) => [key, toPlain(item)]))
  }
  return raw
}
