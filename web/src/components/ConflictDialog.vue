<script setup>
// 多设备同步冲突裁决：40902 时由 sync/engine 把冲突记录挂起到 syncState.pendingConflicts，
// 本组件弹层让用户选择「保留本机（覆盖云端）」或「采用云端（丢弃本机改动）」，
// 保证冲突可收敛、不再无限重试。
import { syncState, resolveConflict } from '../sync/engine'

function choose(entry, choice) {
  if(entry.invalidSession && !confirm('确认放弃这条本机无效修改？云端有效版本会保留，若云端没有则删除本机记录。'))return
  resolveConflict(entry.id, choice)
}
</script>

<template>
  <div v-if="syncState.pendingConflicts.length" class="cf-mask">
    <div
      v-for="c in syncState.pendingConflicts"
      :key="c.id"
      class="cf-card"
      role="dialog"
      aria-modal="true"
    >
      <div class="cf-title">{{c.invalidSession?'计时校验未通过':'同步冲突'}} · {{ c.label }}</div>
      <p class="cf-desc">
        <template v-if="c.invalidSession">{{c.message}}。本机记录已挂起且不计入统计，其他记录仍可同步。</template><template v-else>这条{{ c.label }}在另一台设备上被改动过，与本机待同步内容不一致。请选择保留哪一份。</template>
      </p>
      <div class="cf-hint">
        <span class="chip" :class="{ del: !c.localRecord }">
          本机：{{ c.localRecord ? '已修改' : '已删除' }}
        </span>
        <span class="chip" :class="{ del: !c.serverRecord }">
          云端：{{ c.serverRecord ? '已修改' : '已删除' }}
        </span>
      </div>
      <div class="cf-actions">
        <button class="cf-btn cloud" @click="choose(c, 'cloud')">
          {{c.invalidSession?'确认后放弃本机无效修改':'用云端'}}
          <small>{{c.invalidSession?'云端有效版本保留；云端无此项则删除本机记录':'丢弃本机改动'}}</small>
        </button>
        <button v-if="!c.invalidSession" class="cf-btn local" @click="choose(c, 'local')">
          保留本机
          <small>覆盖云端</small>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cf-mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(21, 36, 60, 0.42);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 20px;
  backdrop-filter: blur(2px);
}
.cf-card {
  width: 100%;
  max-width: 420px;
  background: var(--card);
  border-radius: var(--radius);
  box-shadow: 0 12px 36px rgba(22, 41, 77, 0.22);
  padding: 20px 18px 18px;
}
.cf-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--night);
  margin-bottom: 8px;
}
.cf-desc {
  margin: 0 0 14px;
  font-size: 14px;
  color: var(--sub);
  line-height: 1.6;
}
.cf-hint {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.chip {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef4fb;
  color: var(--primary-deep);
  border: 1px solid var(--line);
}
.chip.del {
  background: #fdeeed;
  color: var(--tomato-deep);
}
.cf-actions {
  display: flex;
  gap: 10px;
}
.cf-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  padding: 11px 8px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  line-height: 1.3;
}
.cf-btn small {
  font-size: 11px;
  font-weight: 400;
  opacity: 0.82;
}
.cf-btn.cloud {
  background: #eef2f7;
  color: var(--sub);
}
.cf-btn.local {
  background: var(--primary);
  color: #fff;
}
.cf-btn.local:active {
  background: var(--primary-deep);
}
.cf-btn.cloud:active {
  background: #e2e9f1;
}
</style>
