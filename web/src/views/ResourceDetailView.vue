<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Heart, Star, Lock, Copy, ExternalLink, Pencil, Trash2, KeyRound,
} from 'lucide-vue-next'
import { resourceApi } from '../api'
import { fmtDate } from '../utils/time'
import { useToast } from '../composables/useToast'
import { queueFavorite } from '../sync/community'
import { scheduleSync } from '../sync/engine'

const route = useRoute()
const router = useRouter()
const { toast } = useToast()

const row = ref(null)
const loading = ref(true)

const id = computed(() => Number(route.params.id))

async function load() {
  try {
    row.value = await resourceApi.get(id.value)
  } catch (e) {
    toast(e.message)
    router.replace('/resources')
  } finally {
    loading.value = false
  }
}

async function copy(text, label = '链接') {
  try {
    await navigator.clipboard.writeText(text)
    toast(`已复制${label}`)
  } catch {
    toast('复制失败，请手动选择')
  }
}

async function toggleLike() {
  try {
    const data = await resourceApi.like(id.value)
    row.value.liked = data.liked
    row.value.like_count = data.like_count
  } catch (e) {
    toast(e.message)
  }
}

async function toggleFav() {
  const next = !row.value.favorited
  row.value.favorited = next
  if (!navigator.onLine) {
    await queueFavorite(id.value, next)
    toast(next ? '已收藏，联网后同步' : '已取消收藏，联网后同步')
    scheduleSync(0)
    return
  }
  try {
    await resourceApi.setFavorite(id.value, next)
    toast(next ? '已收藏' : '已取消收藏')
  } catch (e) {
    if (!e.status || e.status >= 500) {
      // 断网/服务不可用：写入离线队列，联网后自动同步
      await queueFavorite(id.value, next)
      toast(next ? '已收藏，联网后同步' : '已取消收藏，联网后同步')
      scheduleSync(0)
      return
    }
    row.value.favorited = !next
    toast(e.message)
  }
}

function edit() {
  router.push(`/resources/edit/${id.value}`)
}

async function remove() {
  if (!confirm(`删除「${row.value.title}」？删除后不可恢复。`)) return
  try {
    await resourceApi.remove(id.value)
    toast('已删除')
    router.replace('/resources')
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
      <div class="nav-title">资料详情</div>
      <div v-if="row?.can_edit" class="nav-actions">
        <button class="mini" @click="edit"><Pencil :size="16" /></button>
        <button class="mini danger" @click="remove"><Trash2 :size="16" /></button>
      </div>
    </div>

    <div class="page">
      <div v-if="loading" class="empty">读取中…</div>
      <template v-else-if="row">
        <div class="card">
          <div class="head">
            <span v-if="row.category" class="cat">{{ row.category }}</span>
            <h1>{{ row.title }}</h1>
            <div class="meta">
              {{ row.owner?.nickname || '研友' }} · {{ fmtDate(row.created_at) }}
            </div>
          </div>

          <div v-if="row.intro" class="intro">{{ row.intro }}</div>

          <div class="link-box" :class="{ masked: row.masked }">
            <template v-if="row.masked">
              <Lock :size="18" />
              <div class="mask-main">
                <div class="mask-url">{{ row.url }}</div>
                <div class="mask-tip">完整链接与提取码仅 VIP 可见</div>
              </div>
              <button class="btn btn-accent btn-sm" @click="router.push('/vip')">开通 VIP</button>
            </template>
            <template v-else>
              <div class="link-main">
                <div class="link-url">{{ row.url }}</div>
                <div v-if="row.code" class="link-code">提取码：{{ row.code }}</div>
              </div>
              <button class="mini" title="复制链接" @click="copy(row.url, '链接')"><Copy :size="16" /></button>
              <a class="mini" :href="row.url" target="_blank" rel="noopener" title="打开"><ExternalLink :size="16" /></a>
            </template>
          </div>

          <button
            v-if="!row.masked && row.code"
            class="code-btn"
            @click="copy(row.code, '提取码')"
          >
            <KeyRound :size="14" />复制提取码
          </button>
        </div>

        <div class="action-row">
          <button class="act" :class="{ on: row.liked }" @click="toggleLike">
            <Heart :size="18" :class="{ fill: row.liked }" />{{ row.like_count }}
          </button>
          <button class="act" :class="{ on: row.favorited }" @click="toggleFav">
            <Star :size="18" :class="{ fill: row.favorited }" />{{ row.favorited ? '已收藏' : '收藏' }}
          </button>
        </div>
      </template>
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
.nav-actions { margin-left: auto; display: flex; gap: 6px; }
.mini {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--sub);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.mini.danger { color: var(--red); }
.head h1 { margin: 6px 0 0; font-size: 21px; font-weight: 800; line-height: 1.4; }
.cat { font-size: 10.5px; font-weight: 700; color: var(--primary); background: #eef4fb; padding: 2px 8px; border-radius: 999px; }
.meta { font-size: 11.5px; color: var(--faint); margin-top: 6px; }
.intro { margin-top: 14px; font-size: 13.5px; color: var(--sub); line-height: 1.75; }
.link-box {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 12px;
  background: #f7f9fc;
  padding: 13px;
  color: var(--sub);
}
.link-box.masked { background: #fff7f3; color: var(--tomato-deep); }
.mask-main, .link-main { flex: 1; min-width: 0; }
.mask-url { font-size: 12.5px; word-break: break-all; }
.mask-tip { font-size: 11px; margin-top: 3px; color: var(--faint); }
.link-url { font-size: 12.5px; word-break: break-all; color: var(--ink); }
.link-code { font-size: 12px; margin-top: 5px; color: var(--primary); font-weight: 700; }
.code-btn {
  margin-top: 10px;
  border: none;
  background: #eef4fb;
  color: var(--primary);
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 12.5px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}
.action-row { display: flex; gap: 10px; margin-top: 14px; }
.act {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--sub);
  border-radius: 13px;
  padding: 13px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
}
.act.on { color: var(--accent-deep); border-color: #ffd88a; background: #fff8ea; }
.fill { fill: currentColor; }
</style>
