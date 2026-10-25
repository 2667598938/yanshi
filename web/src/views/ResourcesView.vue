<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft, Plus, Search, Heart, Star, Link as LinkIcon, Lock, ChevronRight,
} from 'lucide-vue-next'
import { resourceApi } from '../api'
import { fmtDate as formatDate } from '../utils/time'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'
import { db } from '../db'
import { favoriteRows, pullCommunityMirrors } from '../sync/community'

const FAV_CACHE = 'resourceFavCache'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

const TAB = [
  { id: 'all', label: '全部资料' },
  { id: 'fav', label: '我的收藏' },
  { id: 'mine', label: '我发布的' },
]
const CATEGORIES = ['英语', '数学', '政治', '专业课', '其他']

const tab = ref(['fav', 'mine'].includes(route.query.tab) ? route.query.tab : 'all')
const query = ref('')
const category = ref('')
const rows = ref([])
const loading = ref(true)

const isVip = computed(() => auth.isVip)

async function load() {
  loading.value = true
  try {
    if (tab.value === 'fav') {
      try {
        await pullCommunityMirrors()
        rows.value = await favoriteRows()
        // 缓存收藏列表，断网时仍可查看
        await db.kv.put({ key: FAV_CACHE, value: rows.value })
      } catch (e) {
        if (e.status && e.status < 500) throw e
        const cached = await db.kv.get(FAV_CACHE)
        rows.value = await favoriteRows()
        if (!rows.value.length) rows.value = cached?.value || []
        toast('离线中，显示本机缓存的收藏')
      }
    } else if (tab.value === 'mine') rows.value = await resourceApi.mine()
    else {
      const params = {}
      if (query.value.trim()) params.q = query.value.trim()
      if (category.value) params.category = category.value
      rows.value = await resourceApi.list(params)
    }
  } catch (e) {
    toast(e.message)
  } finally {
    loading.value = false
  }
}

function publish() {
  if (!isVip.value) {
    toast('仅 VIP 可发布资料')
    router.push('/vip')
    return
  }
  router.push('/resources/edit')
}

function open(row) {
  router.push(`/resources/${row.id}`)
}

function fmtDate(v) {
  return formatDate(v)
}

watch([tab, category], load)
onMounted(load)
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">资料库</div>
      <button class="publish" :class="{ locked: !isVip }" @click="publish">
        <Lock v-if="!isVip" :size="15" />
        <Plus v-else :size="16" />发布资料
      </button>
    </div>

    <div class="page">
      <div class="tabs">
        <button
          v-for="t in TAB"
          :key="t.id"
          :class="{ on: tab === t.id }"
          @click="tab = t.id"
        >{{ t.label }}</button>
      </div>

      <template v-if="tab === 'all'">
        <form class="search-row" @submit.prevent="load">
          <div class="search-box">
            <Search :size="16" />
            <input v-model="query" placeholder="搜索标题或简介" maxlength="40" />
          </div>
          <button class="btn btn-outline btn-sm" type="submit">搜索</button>
        </form>
        <div class="cat-row">
          <button class="cat-chip" :class="{ on: !category }" @click="category = ''">全部</button>
          <button
            v-for="c in CATEGORIES"
            :key="c"
            class="cat-chip"
            :class="{ on: category === c }"
            @click="category = c"
          >{{ c }}</button>
        </div>
      </template>

      <div v-if="loading" class="empty">读取中…</div>
      <div v-else-if="!rows.length" class="empty">
        {{ tab === 'fav' ? '还没有收藏资料' : tab === 'mine' ? '还没有发布过资料' : '还没有资料，等第一位分享者' }}
      </div>
      <div v-else class="res-list">
        <button v-for="r in rows" :key="r.id" class="res-card" @click="open(r)">
          <div class="res-top">
            <span class="res-title">{{ r.title }}</span>
            <span v-if="r.category" class="res-cat">{{ r.category }}</span>
          </div>
          <div v-if="r.intro" class="res-intro">{{ r.intro }}</div>
          <div class="res-link">
            <LinkIcon :size="13" />
            <span class="res-url">{{ r.url }}</span>
            <span v-if="r.masked" class="res-mask">仅 VIP 可见完整链接</span>
          </div>
          <div class="res-foot">
            <span class="res-owner">{{ r.owner?.nickname || '研友' }} · {{ fmtDate(r.created_at) }}</span>
            <span class="res-stat"><Heart :size="13" />{{ r.like_count }}</span>
            <Star :size="13" :class="{ on: r.favorited }" />
            <ChevronRight :size="15" class="res-arrow" />
          </div>
        </button>
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
.publish {
  margin-left: auto;
  border: none;
  border-radius: 10px;
  background: var(--primary);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  padding: 9px 13px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.publish.locked { background: #eef1f6; color: var(--faint); }
.tabs { display: flex; gap: 6px; background: #fff; border-radius: 12px; padding: 4px; margin-bottom: 12px; box-shadow: var(--shadow-soft); }
.tabs button { flex: 1; border: none; background: transparent; padding: 9px 0; border-radius: 9px; font-size: 13px; color: var(--sub); cursor: pointer; }
.tabs button.on { background: var(--primary); color: #fff; font-weight: 600; }
.search-row { display: flex; gap: 8px; margin-bottom: 10px; }
.search-box {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 7px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 11px;
  padding: 0 12px;
  color: var(--faint);
}
.search-box input { flex: 1; height: 40px; border: none; background: none; outline: none; font-size: 13.5px; }
.cat-row { display: flex; gap: 7px; overflow-x: auto; padding-bottom: 4px; margin-bottom: 12px; }
.cat-chip {
  border: 1.5px solid var(--line);
  background: #fff;
  color: var(--sub);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.cat-chip.on { border-color: transparent; background: var(--primary); color: #fff; }
.res-list { display: flex; flex-direction: column; gap: 10px; }
.res-card {
  text-align: left;
  background: #fff;
  border: none;
  border-radius: var(--radius);
  padding: 15px 16px 13px;
  box-shadow: var(--shadow-soft);
  cursor: pointer;
  color: var(--ink);
}
.res-top { display: flex; align-items: center; gap: 8px; }
.res-title { flex: 1; font-size: 15px; font-weight: 700; }
.res-cat { font-size: 10.5px; font-weight: 700; color: var(--primary); background: #eef4fb; padding: 2px 8px; border-radius: 999px; }
.res-intro { margin-top: 5px; font-size: 12.5px; color: var(--sub); line-height: 1.6; }
.res-link {
  margin-top: 9px;
  display: flex;
  align-items: center;
  gap: 6px;
  background: #f7f9fc;
  border-radius: 9px;
  padding: 8px 10px;
  color: var(--faint);
  font-size: 11.5px;
}
.res-url { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.res-mask { color: var(--tomato-deep); font-weight: 600; flex-shrink: 0; }
.res-foot { display: flex; align-items: center; gap: 10px; margin-top: 10px; font-size: 11px; color: var(--faint); }
.res-owner { flex: 1; }
.res-stat { display: inline-flex; align-items: center; gap: 3px; }
.res-foot svg.on { color: var(--accent-deep); fill: currentColor; }
.res-arrow { color: #cad2de; }
</style>
