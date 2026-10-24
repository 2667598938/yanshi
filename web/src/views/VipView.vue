<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, Crown, ShieldCheck, Sparkles, Ticket, ChevronRight, Check,
} from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { vipApi } from '../api'
import { useToast } from '../composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

const status = ref(null)
const loading = ref(true)

const isVip = computed(() => status.value?.is_vip || false)
const untilText = computed(() =>
  status.value?.vip_until ? status.value.vip_until.slice(0, 10) : ''
)

const benefits = [
  { icon: Sparkles, title: 'AI 问答权限', sub: '随时向助教提问，不受次数限制' },
  { icon: ShieldCheck, title: '功能申请免审核', sub: '提交即开通，无需等待审批' },
  { icon: Crown, title: 'VIP 专属标识', sub: '个人中心展示会员身份' },
  { icon: Ticket, title: '邀请码优先发放', sub: '可向管理员申请邀请码赠送给研友' },
]

async function load() {
  try {
    status.value = await vipApi.status()
    if (auth.user && status.value) {
      auth.setUser({
        ...auth.user,
        is_vip: status.value.is_vip,
        vip_until: status.value.vip_until,
      })
    }
  } catch (e) {
    toast(e.message)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">会员中心</div>
    </div>

    <div class="page">
      <!-- 会员卡 -->
      <div class="vip-hero">
        <div class="vh-top">
          <span>你好，{{ auth.user?.nickname || '研友' }}</span>
          <span class="vh-badge"><Crown :size="13" />研时 VIP</span>
        </div>
        <div class="vh-state">
          <template v-if="loading">读取中…</template>
          <template v-else-if="isVip">VIP 有效期至 {{ untilText }} · 剩余 {{ status.days_left }} 天</template>
          <template v-else>尚未开通 VIP</template>
        </div>
        <div class="vh-actions">
          <button class="btn btn-accent" @click="router.push('/vip/redeem')">
            <Ticket :size="17" />{{ isVip ? '邀请码续期' : '邀请码开通' }}
          </button>
          <button class="btn btn-ghost btn-sm" @click="router.push('/requests')">
            功能申请<ChevronRight :size="15" />
          </button>
        </div>
      </div>

      <!-- 权益 -->
      <div class="section-title">专属权益</div>
      <div class="card benefit-card">
        <div v-for="b in benefits" :key="b.title" class="benefit-row">
          <span class="benefit-ic"><component :is="b.icon" :size="18" /></span>
          <div class="benefit-main">
            <div class="benefit-title">{{ b.title }}</div>
            <div class="benefit-sub">{{ b.sub }}</div>
          </div>
          <Check :size="16" class="benefit-check" />
        </div>
      </div>

      <div class="tip-card">
        <Ticket :size="17" />
        <span>邀请码由管理员发放，一次性核销；每枚邀请码包含的会员天数以管理员设置为准。</span>
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
.vip-hero {
  position: relative;
  border-radius: 22px;
  padding: 20px 18px 18px;
  color: #fff;
  background: linear-gradient(150deg, #2d4f80, #16294d 70%);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.vip-hero::after {
  content: 'VIP';
  position: absolute;
  right: -6px;
  bottom: -22px;
  font-size: 92px;
  font-weight: 900;
  letter-spacing: -4px;
  color: rgba(240, 168, 48, 0.14);
  pointer-events: none;
}
.vh-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.78);
}
.vh-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 700;
  color: #3a2700;
  background: linear-gradient(120deg, #ffd88a, #f0a830);
  padding: 4px 10px;
  border-radius: 999px;
}
.vh-state {
  position: relative;
  margin-top: 10px;
  font-size: 19px;
  font-weight: 800;
  letter-spacing: 0.3px;
  line-height: 1.45;
}
.vh-actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 18px;
  flex-wrap: wrap;
}
.vh-actions .btn-ghost {
  background: rgba(255, 255, 255, 0.14);
  color: rgba(255, 255, 255, 0.86);
}
.vh-actions .btn-sm {
  padding: 10px 14px;
}
.benefit-card {
  padding: 4px 16px;
}
.benefit-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
}
.benefit-row:last-child {
  border-bottom: none;
}
.benefit-ic {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: #fff3df;
  color: var(--accent-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.benefit-main {
  flex: 1;
  min-width: 0;
}
.benefit-title {
  font-size: 14px;
  font-weight: 700;
}
.benefit-sub {
  font-size: 11.5px;
  color: var(--faint);
  margin-top: 2px;
}
.benefit-check {
  color: var(--green);
  flex-shrink: 0;
}
.tip-card {
  margin-top: 14px;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 13px 15px;
  border-radius: 14px;
  background: #eef3f9;
  color: var(--sub);
  font-size: 12px;
  line-height: 1.7;
}
</style>
