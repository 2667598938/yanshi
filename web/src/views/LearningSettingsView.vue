<script setup>
import { reactive, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useLearningSettingsStore } from '../stores/learningSettings'
import { useToast } from '../composables/useToast'
const store = useLearningSettingsStore()
const router = useRouter()
const { toast } = useToast()
const form = reactive({ ...store.value })
const saving = ref(false)
onMounted(async () => { await store.load(); Object.assign(form, store.value) })
async function save() {
  if (saving.value) return
  saving.value = true
  try { await store.save(form); toast('设置已保存，联网后同步'); router.back() }
  catch (error) { toast(error.message || '保存失败，请重试') }
  finally { saving.value = false }
}
</script>
<template>
  <div>
    <div class="nav"><button class="btn btn-ghost" @click="router.back()">返回</button><div class="nav-title">专注与休息设置</div></div>
    <div class="page">
      <form class="card settings-form" @submit.prevent="save">
        <label>默认专注时长（5–180分钟）<input v-model.number="form.focusMin" class="input" type="number" min="5" max="180" required /></label>
        <label>短休息（1–60分钟）<input v-model.number="form.shortBreakMin" class="input" type="number" min="1" max="60" required /></label>
        <label>长休息（1–180分钟）<input v-model.number="form.longBreakMin" class="input" type="number" min="1" max="180" required /></label>
        <label>每完成几次后长休息（1–8次）<input v-model.number="form.longBreakEvery" class="input" type="number" min="1" max="8" required /></label>
        <p>休息不计入专注时长；休息结束后等待你手动开始下一次专注。</p>
        <button class="btn btn-primary btn-block" :disabled="saving">{{ saving ? '保存中…' : '保存设置' }}</button>
      </form>
    </div>
  </div>
</template>
<style scoped>.settings-form { display: grid; gap: 18px; padding: 20px; }.settings-form label { display: grid; gap: 8px; font-size: 14px; }.settings-form p { font-size: 13px; color: var(--sub); line-height: 1.6; }</style>
