<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, Bell, Crown, ClipboardCheck, FileWarning, CheckCheck, ChevronRight,
} from 'lucide-vue-next'
import { messageApi } from '../api'
import { fmtShort, fmtDateTime } from '../utils/time'
import { useToast } from '../composables/useToast'
import { useNotificationsStore } from '../stores/notifications'

const router = useRouter()
const notifications = useNotificationsStore()
const { toast } = useToast()

const rows = ref([])
const loading = ref(true)
const detail = ref(null)

const KIND = {
  apply: { icon: ClipboardCheck, cls: 'k-apply' },
  vip: { icon: Crown, cls: 'k-vip' },
  content: { icon: FileWarning, cls: 'k-content' },
  system: { icon: Bell, cls: 'k-system' },
}

function fmtTime(v) {
  return fmtDateTime(v)
}

async function load() {
  try {
    rows.value = await messageApi.list()
  } catch (e) {
    toast(e.message)
  } finally {
    loading.value = false
  }
}

async function open(row) {
  detail.value = row
  if (!row.is_read) {
    try {
      const next = await messageApi.read(row.id)
      Object.assign(row, next)
      await notifications.refresh()
    } catch {
      /* 已读失败不阻断查看 */
    }
  }
}

async function readAll() {
  try {
    await messageApi.readAll()
    rows.value.forEach((r) => { r.is_read = true })
    await notifications.refresh()
    toast('已全部标为已读')
  } catch (e) {
    toast(e.message)
  }
}

function goLink() {
  const link = detail.value?.link
  if (!link) return
  detail.value = null
  router.push(link)
}

onMounted(load)
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">消息中心</div>
      <button class="read-all" @click="readAll"><CheckCheck :size="15" />全部已读</button>
    </div>

    <div class="page">
      <div v-if="loading" class="empty">读取中…</div>
      <div v-else-if="!rows.length" class="empty">还没有消息</div>
      <div v-else class="card list">
        <div v-for="m in rows" :key="m.id" class="msg-row" @click="open(m)">
          <span class="msg-ic" :class="KIND[m.kind]?.cls">
            <component :is="KIND[m.kind]?.icon || Bell" :size="17" />
          </span>
          <div class="msg-main">
            <div class="msg-head">
              <span class="msg-title">{{ m.title }}</span>
              <span class="msg-time">{{ fmtShort(m.created_at) }}</span>
            </div>
            <div class="msg-preview">{{ m.content }}</div>
          </div>
          <span v-if="!m.is_read" class="unread-dot"></span>
        </div>
      </div>
    </div>

    <div v-if="detail" class="mask" @click.self="detail = null">
      <div class="sheet">
        <div class="detail-kind">{{ detail.kind === 'apply' ? '功能申请' : detail.kind === 'vip' ? '会员通知' : detail.kind === 'content' ? '内容通知' : '系统消息' }}</div>
        <div class="detail-title">{{ detail.title }}</div>
        <div class="detail-time">{{ fmtTime(detail.created_at) }}</div>
        <div class="detail-content">{{ detail.content }}</div>
        <button v-if="detail.link" class="btn btn-primary btn-block" @click="goLink">
          去看看<ChevronRight :size="16" />
        </button>
        <button class="btn btn-ghost btn-block mt8" @click="detail = null">关闭</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back {
  border: none;
  background: #fff;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sub);
  cursor: pointer;
  box-shadow: var(--shadow-soft);
}
.read-all {
  margin-left: auto;
  border: none;
  background: none;
  color: var(--primary);
  font-size: 12.5px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
}
.list { padding: 2px 16px; }
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 13px 0;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
}
.msg-row:last-child { border-bottom: none; }
.msg-ic {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.k-apply { background: #eef0fe; color: var(--purple); }
.k-vip { background: #fff3df; color: var(--accent-deep); }
.k-content { background: #fdecec; color: var(--red); }
.k-system { background: #e6f0fb; color: var(--primary); }
.msg-main { flex: 1; min-width: 0; }
.msg-head { display: flex; align-items: baseline; gap: 8px; }
.msg-title { font-size: 14px; font-weight: 700; flex: 1; }
.msg-time { font-size: 10.5px; color: var(--faint); flex-shrink: 0; }
.msg-preview {
  margin-top: 3px;
  font-size: 12px;
  color: var(--faint);
  line-height: 1.55;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.unread-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--tomato);
  margin-top: 6px;
  flex-shrink: 0;
}
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet {
  width: 100%;
  max-width: 520px;
  background: #fff;
  border-radius: 22px 22px 0 0;
  padding: 22px 18px calc(22px + env(safe-area-inset-bottom));
}
.detail-kind { font-size: 11.5px; color: var(--faint); }
.detail-title { font-size: 18px; font-weight: 800; margin-top: 4px; }
.detail-time { font-size: 11.5px; color: var(--faint); margin-top: 4px; }
.detail-content {
  margin: 14px 0 18px;
  font-size: 13.5px;
  color: var(--sub);
  line-height: 1.8;
  white-space: pre-wrap;
}
</style>
