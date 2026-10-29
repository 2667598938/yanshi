import { defineStore } from 'pinia'
import { db, localAccountScope, uid, activeAccountId } from '../db'
import { writeRecord, enqueueDelete } from '../sync/engine'
import { timeNodeApi } from '../api'
import { useAuthStore } from './auth'

export const useTimeNodesStore = defineStore('timeNodes', {
  state: () => ({ list: [], loaded: false }),
  actions: {
    async load(force = false) {
      const scope = localAccountScope()
      if (this.loaded && !force) return
      const account = activeAccountId()
      const local = await scope.db.timeNodes.toArray()
      if (!scope.isCurrent()) return
      this.list = local
      if (useAuthStore().isLoggedIn) {
        try {
          const rows = await timeNodeApi.list()
          if (!scope.isCurrent() || account !== activeAccountId()) return
          await db.transaction('rw', db.timeNodes, db.outbox, db.syncMeta, async () => {
            const pending = new Set((await db.outbox.toArray()).map(row => row.recordId))
            for (const row of await db.syncMeta.toArray()) if (row.key.startsWith('conflict:')) pending.add(row.key.slice(9))
            const ids=new Set(rows.map(row=>row.id))
            for(const local of await db.timeNodes.toArray())if(!ids.has(local.id)&&!pending.has(local.id))await db.timeNodes.delete(local.id)
            for (const row of rows) if (!pending.has(row.id)) {
              const { id, _rev, ...value } = row
              await db.timeNodes.put({ id, _rev, value })
            }
          })
          const latest = await scope.db.timeNodes.toArray()
          if (!scope.isCurrent()) return
          this.list = latest
        } catch { /* 离线保留本人缓存 */ }
      }
      if (!scope.isCurrent()) return
      this.loaded = true
    },
    async save(id, value) {
      const scope = localAccountScope()
      const row = id ? await scope.db.timeNodes.get(id) : null
      scope.assertCurrent()
      await writeRecord('timeNodes', { id: id || uid('node-'), value, _rev: row?._rev || 0 })
      const latest = await scope.db.timeNodes.toArray()
      if (scope.isCurrent()) this.list = latest
    },
    async remove(id) {
      const scope = localAccountScope()
      await enqueueDelete('timeNodes', id)
      const latest = await scope.db.timeNodes.toArray()
      if (scope.isCurrent()) this.list = latest
    },
  },
})
