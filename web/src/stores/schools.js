import { defineStore } from 'pinia'
import { schoolApi } from '../api'
import { db } from '../db'
import { SCHOOL_MAP, SCHOOLS } from '../data/schools'

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
  state: () => ({ rows: [], loaded: false, loading: false }),
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
    setRows(rows) {
      this.rows = Array.isArray(rows) ? rows : []
    },
    async load(force = false) {
      if (this.loaded && !force) return
      if (this.loading) return
      this.loading = true
      try {
        const cached = await db.kv.get('schools:catalog')
        if (cached?.value) this.setRows(cached.value)
        const rows = await schoolApi.list()
        this.setRows(rows)
        await db.kv.put({ key: 'schools:catalog', value: rows })
      } catch {
        // 断网时使用本机缓存与内置院校
      } finally {
        this.loaded = true
        this.loading = false
      }
    },
  },
})
