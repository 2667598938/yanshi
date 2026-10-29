// Each document has its own identity. sessionStorage can be copied into a duplicated tab.
const key = Symbol.for('yanshi.documentPresenceId')
export function presenceDeviceId() {
  if (!globalThis[key]) {
    globalThis[key] = globalThis.crypto?.randomUUID?.()
      || `device-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  }
  return globalThis[key]
}
