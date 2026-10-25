<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, Plus, MessageCircle, ChevronRight, Sparkles, Check,
} from 'lucide-vue-next'
import { postApi } from '../api'
import { fmtShort } from '../utils/time'
import BlobImage from '../components/BlobImage.vue'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'
import { pendingPosts, queuePost, SYNCED_EVENT } from '../sync/community'
import { scheduleSync } from '../sync/engine'

const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

const tab = ref('all')
const rows = ref([])
const pending = ref([])
const loading = ref(true)
const showCompose = ref(false)
const draft = ref('')
const posting = ref(false)

function fmtTime(v) {
  return fmtShort(v)
}

function fmtLocal(ms) {
  return fmtShort(new Date(ms).toISOString())
}

async function loadPending() {
  pending.value = await pendingPosts()
}

async function load() {
  loading.value = true
  await loadPending()
  try {
    rows.value = tab.value === 'mine' ? await postApi.mine() : await postApi.list()
  } catch (e) {
    toast(e.message)
  } finally {
    loading.value = false
  }
}

function switchTab(t) {
  tab.value = t
  load()
}

async function saveLocal(text) {
  const row = await queuePost(text)
  pending.value.unshift(row)
  draft.value = ''
  showCompose.value = false
  toast('已保存到本机，联网后自动上传')
  scheduleSync(0)
}

async function publish() {
  const text = draft.value.trim()
  if (!text) return toast('写点什么再发布')
  posting.value = true
  try {
    if (!navigator.onLine) {
      await saveLocal(text)
      return
    }
    try {
      const row = await postApi.create(text)
      rows.value.unshift(row)
      draft.value = ''
      showCompose.value = false
      toast('已发布')
    } catch (e) {
      // 鉴权/内容校验错误直接提示；断网或服务不可用（含网关 502）转为本地草稿
      if (e.status && e.status < 500) return toast(e.message)
      await saveLocal(text)
    }
  } finally {
    posting.value = false
  }
}

async function onSynced() {
  await load()
}

onMounted(() => {
  load()
  window.addEventListener(SYNCED_EVENT, onSynced)
})
onUnmounted(() => window.removeEventListener(SYNCED_EVENT, onSynced))
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">动态</div>
      <button class="compose-btn" @click="showCompose = true"><Plus :size="16" />发动态</button>
    </div>

    <div class="page">
      <button class="insp-banner" @click="router.push('/inspirations')">
        <Sparkles :size="18" />
        <div class="ib-main">
          <div class="ib-title">励志区 · 大雪深埋</div>
          <div class="ib-sub">投稿一句文案或一张图，审核后轮播</div>
        </div>
        <ChevronRight :size="17" />
      </button>

      <div class="tabs">
        <button :class="{ on: tab === 'all' }" @click="switchTab('all')">全部动态</button>
        <button :class="{ on: tab === 'mine' }" @click="switchTab('mine')">我的帖子</button>
      </div>

      <div v-if="loading" class="empty">读取中…</div>
      <div v-else-if="!rows.length && !pending.length" class="empty">
        {{ tab === 'mine' ? '还没有发过动态' : '还没有动态，来第一条' }}
      </div>
      <div v-else class="post-list">
        <div v-for="p in pending" :key="p.id" class="post-card is-pending">
          <div class="post-head">
            <BlobImage class="p-avatar" :src="auth.user?.avatar_key" :fallback="''" />
            <span class="p-name">{{ auth.user?.nickname || '我' }}</span>
            <span class="p-time">{{ fmtLocal(p.createdAt) }}</span>
          </div>
          <div class="p-content">{{ p.content }}</div>
          <div class="p-foot">
            <span class="p-pending">待上传 · 仅本机可见</span>
          </div>
        </div>
        <button v-for="p in rows" :key="p.id" class="post-card" @click="router.push(`/posts/${p.id}`)">
          <div class="post-head">
            <BlobImage class="p-avatar" :src="p.author?.avatar_key" :fallback="''" />
            <span class="p-name">{{ p.author?.nickname || '研友' }}</span>
            <span class="p-time">{{ fmtTime(p.created_at) }}</span>
          </div>
          <div class="p-content">{{ p.content }}</div>
          <div class="p-foot">
            <span><MessageCircle :size="13" />{{ p.comment_count }} 条评论</span>
            <span v-if="p.mine" class="p-mine">我发布的</span>
          </div>
        </button>
      </div>
    </div>

    <div v-if="showCompose" class="mask" @click.self="showCompose = false">
      <div class="sheet">
        <div class="sheet-title">发动态</div>
        <textarea
          v-model="draft"
          class="ta"
          rows="5"
          maxlength="2000"
          placeholder="记录今天的学习、困惑或一点小进展…"
        ></textarea>
        <div class="compose-foot">
          <span>{{ draft.trim().length }}/2000</span>
          <button class="btn btn-primary btn-sm" :disabled="posting" @click="publish">
            <Check :size="15" />{{ posting ? '发布中…' : '发布' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back { border: none; background: #fff; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.compose-btn { margin-left: auto; border: none; border-radius: 10px; background: var(--primary); color: #fff; font-size: 12.5px; font-weight: 600; padding: 9px 13px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.insp-banner { width: 100%; display: flex; align-items: center; gap: 11px; border: none; border-radius: 14px; padding: 13px 15px; margin-bottom: 12px; background: linear-gradient(135deg, #16294d, #2d4f80); color: #eaf1ff; cursor: pointer; text-align: left; }
.ib-main { flex: 1; }
.ib-title { font-size: 13.5px; font-weight: 700; }
.ib-sub { font-size: 11px; color: rgba(234, 241, 255, 0.66); margin-top: 2px; }
.tabs { display: flex; gap: 6px; background: #fff; border-radius: 12px; padding: 4px; margin-bottom: 12px; box-shadow: var(--shadow-soft); }
.tabs button { flex: 1; border: none; background: transparent; padding: 9px 0; border-radius: 9px; font-size: 13px; color: var(--sub); cursor: pointer; }
.tabs button.on { background: var(--primary); color: #fff; font-weight: 600; }
.post-list { display: flex; flex-direction: column; gap: 10px; }
.post-card { text-align: left; background: #fff; border: none; border-radius: var(--radius); padding: 14px 16px; box-shadow: var(--shadow-soft); color: var(--ink); cursor: pointer; }
.post-card.is-pending { border: 1px dashed #e6c98a; background: #fffdf7; cursor: default; }
.p-pending { color: #a5781f; font-weight: 600; }
.post-head { display: flex; align-items: center; gap: 8px; }
.p-avatar { width: 28px; height: 28px; border-radius: 50%; object-fit: cover; background: #eef3f9; flex-shrink: 0; }
.p-name { font-size: 12.5px; font-weight: 700; }
.p-time { margin-left: auto; font-size: 10.5px; color: var(--faint); }
.p-content { margin-top: 9px; font-size: 14px; line-height: 1.72; white-space: pre-wrap; word-break: break-word; }
.p-foot { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 11px; color: var(--faint); }
.p-foot span { display: inline-flex; align-items: center; gap: 3px; }
.p-mine { color: var(--primary); }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; margin-bottom: 12px; }
.ta { width: 100%; box-sizing: border-box; border: 1.5px solid var(--line); border-radius: 12px; padding: 12px 14px; font-size: 14px; font-family: inherit; background: #fafbfe; resize: vertical; outline: none; }
.ta:focus { border-color: var(--primary); }
.compose-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; font-size: 11.5px; color: var(--faint); }
</style>
