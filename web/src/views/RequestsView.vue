<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import {
  ArrowLeft,
  Send,
  Sparkles,
  BookOpen,
  Users,
  Ellipsis,
  Crown,
  ChevronRight,
} from 'lucide-vue-next';
import { useAuthStore } from '../stores/auth';
import { requestApi } from '../api';
import { fmtDateTime } from '../utils/time';
import { useToast } from '../composables/useToast';

const router = useRouter();
const route = useRoute();
const auth = useAuthStore();
const { toast } = useToast();

const FEATURES = [
  { id: 'ai', label: 'AI 问答权限', icon: Sparkles },
  { id: 'materials', label: '资料区完整链接', icon: BookOpen },
  { id: 'room', label: '房间类型权限（未开放）', icon: Users },
  { id: 'other', label: '其他功能', icon: Ellipsis },
];
const STATUS = {
  pending: { label: '审核中', cls: 'tag-pending' },
  approved: { label: '已通过', cls: 'tag-approved' },
  rejected: { label: '已驳回', cls: 'tag-rejected' },
  withdrawn: { label: '已撤回', cls: 'tag-withdrawn' },
  revoked: { label: '已撤销', cls: 'tag-rejected' },
};

const feature = ref(
  FEATURES.some((f) => f.id === route.query.feature) ? route.query.feature : 'ai',
);
const reason = ref('');
const submitting = ref(false);
const rows = ref([]);
const loading = ref(true);

const isVip = computed(() => auth.isVip);

function fmtDate(v) {
  return fmtDateTime(v);
}

async function load() {
  try {
    rows.value = await requestApi.mine();
  } catch (e) {
    toast(e.message);
  } finally {
    loading.value = false;
  }
}

async function submit() {
  const text = reason.value.trim();
  if (text.length < 5) return toast('请至少写 5 个字的申请理由');
  submitting.value = true;
  try {
    const row = await requestApi.create({ feature: feature.value, reason: text });
    rows.value.unshift(row);
    reason.value = '';
    toast(
      row.status === 'approved' ? '权限已通过，功能以站点开放状态为准' : '已提交，等待管理员审批',
    );
  } catch (e) {
    toast(e.message);
  } finally {
    submitting.value = false;
  }
}

async function withdraw(row) {
  try {
    const next = await requestApi.withdraw(row.id);
    Object.assign(row, next);
    toast('已撤回');
  } catch (e) {
    toast(e.message);
  }
}

onMounted(load);
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">功能申请</div>
    </div>

    <div class="page">
      <!-- VIP 提示 -->
      <button v-if="isVip" class="vip-banner on" @click="router.push('/vip')">
        <Crown :size="17" />
        <span class="vb-txt">VIP 免人工审批，功能以站点开放状态为准</span>
        <ChevronRight :size="16" />
      </button>
      <button v-else class="vip-banner" @click="router.push('/vip')">
        <Crown :size="17" />
        <span class="vb-txt">开通 VIP 可免审核，提交即通过</span>
        <ChevronRight :size="16" />
      </button>

      <!-- 申请表单 -->
      <div class="card">
        <div class="form-title">申请开通</div>
        <div class="feature-grid">
          <button
            v-for="f in FEATURES.filter((item) => item.id !== 'room')"
            :key="f.id"
            class="feature-pill"
            :class="{ on: feature === f.id }"
            @click="feature = f.id"
          >
            <component :is="f.icon" :size="15" />{{ f.label }}
          </button>
        </div>
        <textarea
          v-model="reason"
          class="ta"
          rows="4"
          maxlength="500"
          placeholder="说明用途，例如：需要下载数学讲义，用于强化阶段"
        ></textarea>
        <div class="form-foot">
          <span class="count">{{ reason.trim().length }}/500</span>
          <button class="btn btn-primary btn-sm" :disabled="submitting" @click="submit">
            <Send :size="15" />{{ submitting ? '提交中…' : '提交申请' }}
          </button>
        </div>
      </div>

      <!-- 我的申请 -->
      <div class="section-title">我的申请</div>
      <div v-if="loading" class="empty">读取中…</div>
      <div v-else-if="!rows.length" class="empty">还没有申请记录</div>
      <div v-else class="card list-card">
        <div v-for="r in rows" :key="r.id" class="req-row">
          <div class="req-head">
            <div class="req-name">{{ r.feature_label }}</div>
            <span class="tag" :class="STATUS[r.status]?.cls">{{ STATUS[r.status]?.label }}</span>
          </div>
          <div class="req-reason">{{ r.reason }}</div>
          <div v-if="r.review_note" class="req-note">审批备注：{{ r.review_note }}</div>
          <div class="req-foot">
            <span>{{ fmtDate(r.created_at) }}</span>
            <span v-if="r.status === 'pending'" class="req-withdraw" @click="withdraw(r)"
              >撤回</span
            >
          </div>
        </div>
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
.vip-banner {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 12px 15px;
  border: none;
  border-radius: 14px;
  background: #fff3df;
  color: var(--accent-deep);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
  cursor: pointer;
}
.vip-banner.on {
  background: linear-gradient(135deg, #ffe9b8, #ffd88a);
  color: #5b3b00;
}
.vb-txt {
  flex: 1;
  text-align: left;
}
.form-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
}
.feature-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.feature-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 9px 13px;
  border-radius: 999px;
  border: 1.5px solid var(--line);
  background: #fff;
  color: var(--sub);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}
.feature-pill.on {
  border-color: transparent;
  background: var(--primary);
  color: #fff;
}
.ta {
  width: 100%;
  box-sizing: border-box;
  margin-top: 13px;
  border: 1.5px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 14px;
  font-family: inherit;
  color: var(--ink);
  background: #fafbfe;
  resize: vertical;
  outline: none;
}
.ta:focus {
  border-color: var(--primary);
}
.form-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 10px;
}
.count {
  font-size: 12px;
  color: var(--faint);
}
.list-card {
  padding: 2px 16px;
}
.req-row {
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
}
.req-row:last-child {
  border-bottom: none;
}
.req-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.req-name {
  flex: 1;
  font-size: 14px;
  font-weight: 700;
}
.req-reason {
  margin-top: 6px;
  font-size: 14px;
  color: var(--sub);
  line-height: 1.65;
  background: #f6f9fd;
  border-radius: 9px;
  padding: 8px 10px;
}
.req-note {
  margin-top: 7px;
  font-size: 14px;
  color: var(--primary-deep);
}
.req-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: var(--faint);
}
.req-withdraw {
  color: var(--red);
  cursor: pointer;
  font-weight: 600;
}
.tag {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
}
.tag-pending {
  background: #fff3df;
  color: var(--accent-deep);
}
.tag-approved {
  background: #e7f6f0;
  color: var(--green);
}
.tag-rejected {
  background: #fdecec;
  color: var(--red);
}
.tag-withdrawn {
  background: #eef1f6;
  color: var(--faint);
}
</style>
