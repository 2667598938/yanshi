<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Send, Trash2, MessageCircle } from 'lucide-vue-next'
import { postApi } from '../api'
import { fmtShort } from '../utils/time'
import BlobImage from '../components/BlobImage.vue'
import { useToast } from '../composables/useToast'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

const post = ref(null)
const comments = ref([])
const loading = ref(true)
const input = ref('')
const replyTo = ref(null)
const sending = ref(false)

const id = computed(() => Number(route.params.id))
const roots = computed(() => comments.value.filter((c) => !c.parent_id))
const childrenOf = (cid) => comments.value.filter((c) => c.parent_id === cid)

function fmtTime(v) {
  return fmtShort(v)
}

async function load() {
  try {
    const [p, cs] = await Promise.all([postApi.get(id.value), postApi.comments(id.value)])
    post.value = p
    comments.value = cs
  } catch (e) {
    toast(e.message)
    router.replace('/posts')
  } finally {
    loading.value = false
  }
}

function reply(c) {
  replyTo.value = c
  input.value = ''
}

async function send() {
  const text = input.value.trim()
  if (!text) return
  sending.value = true
  try {
    const row = await postApi.comment(id.value, {
      content: text,
      parent_id: replyTo.value?.id || undefined,
    })
    comments.value.push(row)
    input.value = ''
    replyTo.value = null
    post.value.comment_count = (post.value.comment_count || 0) + 1
  } catch (e) {
    toast(e.message)
  } finally {
    sending.value = false
  }
}

async function removeComment(c) {
  let reason = ''
  if (auth.isAdmin && !c.mine) {
    reason = (prompt('删除原因（必填，会通知作者）') || '').trim()
    if (!reason) return toast('管理员删除内容必须填写原因')
  }
  if (!confirm('删除这条评论？')) return
  try {
    await postApi.deleteComment(c.id, reason)
    const ids = new Set([c.id, ...childrenOf(c.id).map((x) => x.id)])
    comments.value = comments.value.filter((x) => !ids.has(x.id))
  } catch (e) {
    toast(e.message)
  }
}

async function removePost() {
  let reason = ''
  if (auth.isAdmin && !post.value?.mine) {
    reason = (prompt('删除原因（必填，会通知作者）') || '').trim()
    if (!reason) return toast('管理员删除内容必须填写原因')
  }
  if (!confirm('删除这条动态？')) return
  try {
    await postApi.remove(id.value, reason)
    toast('已删除')
    router.replace('/posts')
  } catch (e) {
    toast(e.message)
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">动态详情</div>
      <button v-if="post?.can_delete" class="del-btn" @click="removePost"><Trash2 :size="17" /></button>
    </div>

    <div class="page">
      <div v-if="loading" class="empty">读取中…</div>
      <template v-else-if="post">
        <div class="card post">
          <div class="post-head">
            <BlobImage class="p-avatar" :src="post.author?.avatar_key" :fallback="''" />
            <div class="p-meta">
              <div class="p-name">{{ post.author?.nickname || '研友' }}</div>
              <div class="p-time">{{ fmtTime(post.created_at) }}</div>
            </div>
          </div>
          <div class="p-content">{{ post.content }}</div>
        </div>

        <div class="section-title">评论 {{ comments.length }}</div>
        <div v-if="!comments.length" class="empty">还没有评论，说点什么</div>
        <div v-else class="card comments">
          <template v-for="c in roots" :key="c.id">
            <div class="cmt">
              <div class="cmt-head">
                <span class="cmt-name">{{ c.author?.nickname }}</span>
                <span class="cmt-time">{{ fmtTime(c.created_at) }}</span>
                <button v-if="c.can_delete" class="cmt-del" @click="removeComment(c)"><Trash2 :size="13" /></button>
              </div>
              <div class="cmt-text">{{ c.content }}</div>
              <button class="reply-btn" @click="reply(c)">回复</button>
            </div>
            <div v-for="r in childrenOf(c.id)" :key="r.id" class="cmt child">
              <div class="cmt-head">
                <span class="cmt-name">{{ r.author?.nickname }}</span>
                <span v-if="r.reply_to" class="cmt-reply-to">回复 @{{ r.reply_to }}</span>
                <span class="cmt-time">{{ fmtTime(r.created_at) }}</span>
                <button v-if="r.can_delete" class="cmt-del" @click="removeComment(r)"><Trash2 :size="13" /></button>
              </div>
              <div class="cmt-text">{{ r.content }}</div>
              <button class="reply-btn" @click="reply(r)">回复</button>
            </div>
          </template>
        </div>

        <div class="composer">
          <div v-if="replyTo" class="reply-hint">
            回复 @{{ replyTo.author?.nickname }}
            <button @click="replyTo = null">取消</button>
          </div>
          <div class="composer-row">
            <input v-model="input" maxlength="500" placeholder="写评论…" @keyup.enter="send" />
            <button :disabled="sending || !input.trim()" @click="send"><Send :size="17" /></button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.back { border: none; background: #fff; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.del-btn { margin-left: auto; border: none; background: #fdecec; color: var(--red); width: 34px; height: 34px; border-radius: 9px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.post-head { display: flex; align-items: center; gap: 9px; }
.p-avatar { width: 34px; height: 34px; border-radius: 50%; object-fit: cover; background: #eef3f9; }
.p-name { font-size: 13.5px; font-weight: 700; }
.p-time { font-size: 10.5px; color: var(--faint); margin-top: 1px; }
.p-content { margin-top: 12px; font-size: 14.5px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; }
.comments { padding: 4px 16px; }
.cmt { padding: 12px 0; border-bottom: 1px solid var(--line); }
.cmt:last-child { border-bottom: none; }
.cmt.child { margin-left: 14px; padding-left: 12px; border-left: 2px solid var(--line); border-bottom: 1px solid var(--line); }
.cmt-head { display: flex; align-items: baseline; gap: 7px; }
.cmt-name { font-size: 12.5px; font-weight: 700; }
.cmt-reply-to { font-size: 11px; color: var(--primary); }
.cmt-time { margin-left: auto; font-size: 10.5px; color: var(--faint); }
.cmt-del { border: none; background: none; color: var(--faint); cursor: pointer; padding: 0; display: inline-flex; }
.cmt-text { margin-top: 4px; font-size: 13.5px; line-height: 1.7; color: var(--ink); word-break: break-word; }
.reply-btn { border: none; background: none; color: var(--faint); font-size: 11px; cursor: pointer; padding: 3px 0 0; }
.composer { margin-top: 14px; }
.reply-hint { display: flex; align-items: center; justify-content: space-between; font-size: 11.5px; color: var(--primary); background: #eef4fb; border-radius: 9px; padding: 7px 10px; margin-bottom: 8px; }
.reply-hint button { border: none; background: none; color: var(--faint); cursor: pointer; font-size: 11px; }
.composer-row { display: flex; gap: 8px; }
.composer-row input { flex: 1; height: 44px; border: 1px solid var(--line); border-radius: 999px; padding: 0 16px; font-size: 14px; background: #fff; outline: none; }
.composer-row button { width: 44px; height: 44px; border-radius: 50%; border: none; background: var(--primary); color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.composer-row button:disabled { opacity: .5; }
</style>
