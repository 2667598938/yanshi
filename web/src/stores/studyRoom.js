import { defineStore } from 'pinia'

// A co-study visit belongs to this tab and account, independently of routing.
const key = owner => `yanshi:co-study:${owner}`
export const useStudyRoomStore = defineStore('studyRoom', {
  state: () => ({ owner: null, room: null, revision: 0 }),
  actions: {
    load(owner) {
      if (owner === this.owner) return
      if (this.owner) { try { sessionStorage.removeItem(key(this.owner)) } catch { /* End the previous account's visit. */ } }
      this.owner = owner || null
      this.revision += 1
      this.room = null
      if (!owner) return
      try {
        const saved = JSON.parse(sessionStorage.getItem(key(owner)) || 'null')
        if (Number.isSafeInteger(saved?.id) && saved.id > 0) this.room = saved
      } catch { /* No persisted co-study visit. */ }
    },
    enter(room, owner) {
      this.load(owner)
      if (!owner || !Number.isSafeInteger(room?.id) || room.id <= 0) return
      this.room = { id: room.id, name: room.name || '自习室' }
      this.revision += 1
      try { sessionStorage.setItem(key(owner), JSON.stringify(this.room)) } catch { /* Optional persistence. */ }
    },
    leave() {
      if (this.owner) { try { sessionStorage.removeItem(key(this.owner)) } catch { /* Optional persistence. */ } }
      this.room = null
      this.revision += 1
    },
  },
})
