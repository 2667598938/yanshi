<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { adminApi } from '../api'
import { useToast } from '../composables/useToast'
const router = useRouter()
const { toast } = useToast()
const rows = ref([])
const status = ref('all')
const busy = ref(null)
const labels = { pending: '等待发送', sending: '发送中', sent: '已发送', retry: '等待重试', failed: '发送失败', cancelled: '已取消' }
async function load() { try { rows.value = await adminApi.emailJobs(status.value) } catch (error) { toast(error.message) } }
async function retry(row) {
  if (busy.value) return
  busy.value = row.id
  try { await adminApi.retryEmail(row.id); toast('已重新入队'); await load() }
  catch (error) { toast(error.message) }
  finally { busy.value = null }
}
onMounted(load)
</script>
<template>
  <div>
    <div class="nav"><button class="btn btn-ghost" @click="router.back()">返回</button><div class="nav-title">通知邮件任务</div></div>
    <div class="page">
      <select v-model="status" class="select" aria-label="邮件状态" @change="load"><option value="all">全部状态</option><option v-for="(label, key) in labels" :key="key" :value="key">{{ label }}</option></select>
      <button class="btn btn-ghost" @click="load">刷新</button>
      <p v-if="!rows.length" class="empty">暂无邮件任务</p>
      <div v-for="row in rows" :key="row.id" class="card email-row">
        <strong>{{ row.subject }}</strong><p>{{ row.recipient }} · {{ labels[row.status] }} · 已尝试{{ row.attempts }}次</p>
        <p v-if="row.last_error">{{ row.last_error }}</p>
        <button v-if="['failed', 'retry'].includes(row.status)" class="btn btn-primary btn-sm" :disabled="!!busy" @click="retry(row)">重新发送</button>
      </div>
    </div>
  </div>
</template>
<style scoped>.email-row { margin-top: 14px; padding: 18px; overflow-wrap: anywhere; }.email-row p { font-size: 14px; color: var(--sub); line-height: 1.5; }</style>
