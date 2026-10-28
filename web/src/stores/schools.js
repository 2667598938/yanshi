import { defineStore } from 'pinia'
import { schoolApi } from '../api'
import { activeAccountId, localAccountScope } from '../db'
import { toPlain } from '../utils/plain'
import { SCHOOL_MAP, SCHOOLS } from '../data/schools'
const pendingLoads = new WeakMap()

function mergeRows(rows) {
  const map = new Map(SCHOOLS.map((row) => [row.key, { ...row }]))
  for (const row of rows || []) {
    if (!row?.key) continue
    const base = map.get(row.key) || {}
    map.set(row.key, {
      ...base,
      key: row.key,
      name: row.name || base.name || row.key,
      short: row.short || row.name || base.short || row.key,
      logo: row.logo_key || base.logo || '',
      color: row.info?.color || base.color || '#526484',
    })
  }
  return [...map.values()]
}

// 本人梦校目录：只读取自己的院校展示信息（名称/简称/校徽），不把相册或资料库带进房间。
export const useSchoolsStore = defineStore('schools', {
  state: () => ({ rows: [], loaded: false, loading: false, ownerId: null, generation: 0 }),
  getters: {
    choices: (state) => mergeRows(state.rows),
    nameFor() {
      return (value) => {
        const text = String(value || '').trim()
        if (!text) return ''
        const byKey = this.choices.find((row) => row.key === text)
        if (byKey) return byKey.name
        const byName = this.choices.find((row) => row.name === text)
        if (byName) return byName.name
        return text
      }
    },
    shortFor() {
      return (value) => {
        const name = this.nameFor(value)
        const row = this.choices.find((item) => item.name === name)
        return row?.short || name
      }
    },
    logoFor() {
      return (value) => {
        const name = this.nameFor(value)
        return this.choices.find((item) => item.name === name)?.logo || SCHOOL_MAP[value]?.logo || ''
      }
    },
  },
  actions: {
    resetForAccount() {
      this.generation++
      this.rows = []
      this.loaded = false
      this.loading = false
      this.ownerId = activeAccountId()
      pendingLoads.delete(this)
    },
    setRows(rows) {
      this.rows = Array.isArray(rows) ? rows : []
    },
    async updateCatalog(rows, scope = localAccountScope()) {
      scope.assertCurrent()
      this.generation++ // 不允许更新前发出的旧请求覆盖刚保存的目录。
      this.ownerId = activeAccountId()
      this.setRows(rows)
      this.loaded = true
      this.loading = false
      await scope.db.kv.put({ key: 'schools:catalog', value: toPlain(rows) })
    },
    async load(force = false) {
      if (this.ownerId !== activeAccountId()) this.resetForAccount()
      if (this.loaded && !force) return
      if (this.loading) return pendingLoads.get(this)
      const scope = localAccountScope()
      const generation = ++this.generation
      const current = () => scope.isCurrent() && generation === this.generation
      this.loading = true
      const pending = (async () => {
        try {
          const cached = await scope.db.kv.get('schools:catalog')
          if (!current()) return
          if (cached?.value) this.setRows(cached.value)
          const rows = await schoolApi.list()
          if (!current()) return
          this.setRows(rows)
          await scope.db.kv.put({ key: 'schools:catalog', value: toPlain(rows) })
          if (current()) this.loaded = true
        } catch {
          // 断网保留本账号缓存，下次进入页面仍可重试。
        } finally {
          if (current()) {
            this.loading = false
            pendingLoads.delete(this)
          }
        }
      })()
      pendingLoads.set(this, pending)
      return pending
    },
  },
})
