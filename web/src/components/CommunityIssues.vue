<script setup>
import { computed, ref } from 'vue'
import { communityState, resolveCommunityIssue } from '../sync/community'
import { scheduleSync } from '../sync/engine'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'
const auth = useAuthStore()
const { toast } = useToast()
const drafts = ref({})
const issues = computed(() => Number(auth.user?.id) === communityState.accountId ? communityState.issues : [])
async function choose(item, choice) {
  if (choice === 'cloud' && !item.cloud && !confirm('确认移除这条待同步修改？请先复制需要保留的文字。')) return
  try {
    await resolveCommunityIssue(item.id, choice, drafts.value[item.id] ?? item.record.content)
    scheduleSync(0)
  } catch (e) { toast(e.message) }
}
</script>
<template>
  <aside v-if="issues.length" class="community-issues" aria-label="待处理的社区同步">
    <details v-for="item in issues" :key="item.id" open>
      <summary>{{ item.type === 'favorite' ? '收藏' : '帖子' }}同步需要处理</summary>
      <p>{{ item.error }}</p>
      <p v-if="item.type === 'postDelete'">本机准备删除；云端内容：{{ item.cloud?.content || item.record.content }}</p>
      <template v-else-if="item.type !== 'favorite'">
        <label>本机内容，可修改后重试</label>
        <textarea :value="drafts[item.id] ?? item.record.content" maxlength="2000" @input="drafts[item.id] = $event.target.value"></textarea>
        <p v-if="item.cloud">云端：{{ item.cloud.content }}</p>
      </template>
      <p v-else>本机：{{ item.record.favorited ? '收藏' : '取消收藏' }}；云端：{{ item.cloud?.favorited ? '收藏' : '取消收藏' }}</p>
      <button class="btn btn-outline btn-sm" @click="choose(item, 'cloud')">{{ item.cloud ? '采用云端' : '移除待同步修改' }}</button>
      <button v-if="item.type !== 'favorite' || item.errorStatus !== 404" class="btn btn-primary btn-sm" @click="choose(item, 'local')">{{ item.type === 'postEdit' && item.errorStatus === 404 ? '保存为新帖' : '保留本机并重试' }}</button>
    </details>
  </aside>
</template>
<style scoped>
.community-issues { position: fixed; z-index: 110; right: 12px; bottom: 76px; width: min(360px, calc(100vw - 24px)); max-height: 65vh; overflow: auto; box-shadow: var(--shadow); border-radius: 12px; background: #fff8e9; padding: 12px; }
p, label { font-size: 12px; margin: 8px 0; white-space: pre-wrap; }
textarea { width: 100%; min-height: 80px; margin: 6px 0; }
button { margin: 4px 4px 0 0; }
</style>
