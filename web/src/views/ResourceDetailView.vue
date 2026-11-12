<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  ArrowLeft,
  Heart,
  Star,
  Lock,
  Copy,
  ExternalLink,
  Pencil,
  Trash2,
  KeyRound,
} from 'lucide-vue-next';
import { resourceApi } from '../api';
import { fmtDate } from '../utils/time';
import { useToast } from '../composables/useToast';
import { useClipboard } from '../composables/useClipboard';
import CopyFallback from '../components/CopyFallback.vue';
import { useAuthStore } from '../stores/auth';
import { queueFavorite } from '../sync/community';
import { scheduleSync } from '../sync/engine';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const { toast } = useToast();
const { copy: copyToClipboard, manualCopy } = useClipboard(toast);

const row = ref(null);
const loading = ref(true);

const id = computed(() => Number(route.params.id));

async function load() {
  try {
    row.value = await resourceApi.get(id.value);
  } catch (e) {
    toast(e.message);
    router.replace('/resources');
  } finally {
    loading.value = false;
  }
}

async function copy(text, label = '链接') {
  await copyToClipboard(text, `已复制${label}`);
}

async function toggleLike() {
  try {
    const data = await resourceApi.like(id.value);
    row.value.liked = data.liked;
    row.value.like_count = data.like_count;
  } catch (e) {
    toast(e.message);
  }
}

async function toggleFav() {
  const next = !row.value.favorited;
  try {
    await queueFavorite(id.value, next, { ...row.value });
    row.value.favorited = next;
    toast(next ? '已收藏，联网后同步' : '已取消收藏，联网后同步');
    scheduleSync(0);
  } catch (e) {
    toast(e.message);
  }
}

function edit() {
  router.push(`/resources/edit/${id.value}`);
}

async function remove() {
  let reason = '';
  if (auth.isAdmin && row.value.owner?.id !== auth.user?.id) {
    reason = (prompt('删除原因（必填，会通知作者）') || '').trim();
    if (!reason) return toast('管理员删除内容必须填写原因');
  }
  if (!confirm(`删除「${row.value.title}」？删除后不可恢复。`)) return;
  try {
    await resourceApi.remove(id.value, reason);
    toast('已删除');
    router.replace('/resources');
  } catch (e) {
    toast(e.message);
  }
}

onMounted(load);
</script>

<template>
  <div>
    <CopyFallback v-model="manualCopy" />
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">资料详情</div>
      <div v-if="row?.can_edit || row?.can_delete" class="nav-actions">
        <button v-if="row.can_edit" class="mini" @click="edit"><Pencil :size="16" /></button>
        <button v-if="row.can_delete" class="mini danger" @click="remove">
          <Trash2 :size="16" />
        </button>
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

          <p v-if="row.review_status !== 'approved'">
            {{ row.review_status === 'pending' ? '当前版本待审核' : '当前版本未通过审核'
            }}{{ row.has_published_version ? '，其他人仍可查看上次批准的版本' : '，尚未公开'
            }}<span v-if="row.review_note"> · {{ row.review_note }}</span>
          </p>
          <p v-if="row.personal_note">我的个人备注：{{ row.personal_note }}</p>
          <div v-if="row.intro" class="intro">{{ row.intro }}</div>

          <div class="link-box" :class="{ masked: row.masked }">
            <template v-if="row.masked">
              <Lock :size="18" />
              <div class="mask-main">
                <div class="mask-url">{{ row.url }}</div>
                <div class="mask-tip">VIP 或经资料权限审批授权可查看完整链接与提取码</div>
              </div>
              <button class="btn btn-accent btn-sm" @click="router.push('/vip')">开通 VIP</button>
              <button
                class="btn btn-outline btn-sm"
                @click="router.push('/requests?feature=materials')"
              >
                申请查看
              </button>
            </template>
            <template v-else>
              <div class="link-main">
                <div class="link-url">{{ row.url }}</div>
                <div v-if="row.code" class="link-code">提取码：{{ row.code }}</div>
              </div>
              <button class="mini" title="复制链接" @click="copy(row.url, '链接')">
                <Copy :size="16" />
              </button>
              <a class="mini" :href="row.url" target="_blank" rel="noopener" title="打开"
                ><ExternalLink :size="16"
              /></a>
            </template>
          </div>

          <button v-if="!row.masked && row.code" class="code-btn" @click="copy(row.code, '提取码')">
            <KeyRound :size="14" />复制提取码
          </button>
        </div>

        <div class="action-row">
          <button class="act" :class="{ on: row.liked }" @click="toggleLike">
            <Heart :size="18" :class="{ fill: row.liked }" />{{ row.like_count }}
          </button>
          <button class="act" :class="{ on: row.favorited }" @click="toggleFav">
            <Star :size="18" :class="{ fill: row.favorited }" />{{
              row.favorited ? '已收藏' : '收藏'
            }}
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
.nav-actions {
  margin-left: auto;
  display: flex;
  gap: 6px;
}
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
.mini.danger {
  color: var(--red);
}
.head h1 {
  margin: 6px 0 0;
  font-size: 20px;
  font-weight: 800;
  line-height: 1.4;
}
.cat {
  font-size: 12px;
  font-weight: 700;
  color: var(--primary);
  background: #eef4fb;
  padding: 2px 8px;
  border-radius: 999px;
}
.meta {
  font-size: 12px;
  color: var(--faint);
  margin-top: 6px;
}
.intro {
  margin-top: 14px;
  font-size: 14px;
  color: var(--sub);
  line-height: 1.75;
}
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
.link-box.masked {
  background: #fff7f3;
  color: var(--tomato-deep);
}
.mask-main,
.link-main {
  flex: 1;
  min-width: 0;
}
.mask-url {
  font-size: 14px;
  word-break: break-all;
}
.mask-tip {
  font-size: 12px;
  margin-top: 3px;
  color: var(--faint);
}
.link-url {
  font-size: 14px;
  word-break: break-all;
  color: var(--ink);
}
.link-code {
  font-size: 14px;
  margin-top: 5px;
  color: var(--primary);
  font-weight: 700;
}
.code-btn {
  margin-top: 10px;
  border: none;
  background: #eef4fb;
  color: var(--primary);
  border-radius: 9px;
  padding: 9px 12px;
  font-size: 14px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}
.action-row {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
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
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.act.on {
  color: var(--accent-deep);
  border-color: #ffd88a;
  background: #fff8ea;
}
.fill {
  fill: currentColor;
}
</style>
