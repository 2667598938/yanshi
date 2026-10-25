import { defineStore } from 'pinia'
import { db, uid, activeAccountId } from '../db'
import { writeRecord, enqueueDelete } from '../sync/engine'
import { timeNodeApi } from '../api'
import { useAuthStore } from './auth'

export const useTimeNodesStore = defineStore('timeNodes', {
  state: () => ({ list: [], loaded: false }),
  actions: {
    async load(force = false) {
      if (this.loaded && !force) return
      const account = activeAccountId()
      this.list = await db.timeNodes.toArray()
      if (useAuthStore().isLoggedIn) {
        try {
          const rows = await timeNodeApi.list()
          if (account !== activeAccountId()) return
          await db.transaction('rw', db.timeNodes, db.outbox, async () => {
            const pending = new Set((await db.outbox.toArray()).map(row => row.recordId))
            const ids=new Set(rows.map(row=>row.id))
            for(const local of await db.timeNodes.toArray())if(!ids.has(local.id)&&!pending.has(local.id))await db.timeNodes.delete(local.id)
            for (const row of rows) if (!pending.has(row.id)) {
              const { id, _rev, ...value } = row
              await db.timeNodes.put({ id, _rev, value })
            }
          })
          this.list = await db.timeNodes.toArray()
        } catch { /* 离线保留本人缓存 */ }
      }
      this.loaded = true
    },
    async save(id, value) {
      const row = id ? await db.timeNodes.get(id) : null
      await writeRecord('timeNodes', { id: id || uid('node-'), value, _rev: row?._rev || 0 })
      this.list = await db.timeNodes.toArray()
    },
    async remove(id) {
      await enqueueDelete('timeNodes', id)
      this.list = await db.timeNodes.toArray()
    },
  },
})
