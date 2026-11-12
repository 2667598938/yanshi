import { defineStore } from 'pinia';
import { localAccountScope, uid } from '../db';
import { writeRecord, patchRecord } from '../sync/engine';

// 科目：统一软删除（归档），不物理删除，保证历史番茄记录的统计仍能找到科目
export const useSubjectsStore = defineStore('subjects', {
  state: () => ({ list: [], loaded: false }),
  getters: {
    active: (s) => s.list.filter((x) => !x.archived).sort((a, b) => a.order - b.order),
    byId: (s) => Object.fromEntries(s.list.map((x) => [x.id, x])),
  },
  actions: {
    async load() {
      const scope = localAccountScope();
      if (this.loaded) return;
      const rows = await scope.db.subjects.toArray();
      if (!scope.isCurrent()) return;
      this.list = rows;
      this.loaded = true;
    },
    async add({ name, color, icon }) {
      const scope = localAccountScope();
      const orders = this.list.map((x) => x.order);
      const order = orders.length ? Math.max(...orders) + 1 : 0;
      const item = {
        id: uid('sub_'),
        name: (name || '').trim() || '新科目',
        color,
        icon,
        tags: [],
        order,
        archived: 0,
        builtin: 0,
        createdAt: Date.now(),
      };
      await writeRecord('subjects', item, { create: true });
      scope.assertCurrent();
      this.list.push(item);
      return item;
    },
    async update(id, patch) {
      const scope = localAccountScope();
      const row = await patchRecord('subjects', id, patch);
      scope.assertCurrent();
      const i = this.list.findIndex((x) => x.id === id);
      if (i >= 0) {
        if (row) this.list[i] = row;
      }
    },
    // 归档（隐藏但保留历史统计）；已归档的可恢复
    async setArchived(id, archived) {
      await this.update(id, { archived: archived ? 1 : 0 });
    },
    nameOf(id) {
      return this.byId[id]?.name || '未分类';
    },
    colorOf(id) {
      return this.byId[id]?.color || '#97a4b6';
    },
  },
});
