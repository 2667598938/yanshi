<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, Ticket, Check, ShieldCheck, Sparkles, Crown } from 'lucide-vue-next';
import { useAuthStore } from '../stores/auth';
import { vipApi } from '../api';
import { useToast } from '../composables/useToast';

const router = useRouter();
const auth = useAuthStore();
const { toast } = useToast();

const code = ref('');
const submitting = ref(false);

const benefits = [
  'AI 问答权限，按每日预算与服务商额度使用',
  '功能申请免人工审批，以站点开放状态为准',
  '个人中心 VIP 专属标识',
  '发布网盘资料、查看资料完整链接',
];

async function activate() {
  const value = code.value.trim().toUpperCase();
  if (!value) return toast('请输入邀请码');
  submitting.value = true;
  try {
    const data = await vipApi.redeem(value);
    if (auth.user) {
      auth.setUser({
        ...auth.user,
        is_vip: data.is_vip,
        vip_until: data.vip_until,
        vip_permanent: !!data.vip_permanent,
      });
    }
    toast(`已开通 ${data.granted_days} 天 VIP`);
    router.replace('/vip');
  } catch (e) {
    toast(e.message);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">开通 VIP</div>
    </div>

    <div class="page">
      <div class="hero">
        <h1>输入邀请码<br />立即解锁全部功能</h1>
        <p>邀请码由管理员发放，一次性核销</p>
      </div>

      <div class="card form-card">
        <input
          v-model="code"
          class="code-input tnum"
          maxlength="32"
          placeholder="XXXX-XXXX"
          @keyup.enter="activate"
        />
        <p class="hint">不区分大小写，已使用的邀请码不能再次核销</p>
        <button class="btn btn-primary btn-block" :disabled="submitting" @click="activate">
          <Ticket :size="18" />{{ submitting ? '激活中…' : '立即激活' }}
        </button>
      </div>

      <div class="card rights">
        <div class="rights-title">VIP 权益</div>
        <div v-for="(b, i) in benefits" :key="b" class="right-row">
          <span class="right-ic">
            <component :is="[Sparkles, ShieldCheck, Crown, Ticket][i]" :size="16" />
          </span>
          <span>{{ b }}</span>
          <Check :size="15" class="right-check" />
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
.hero {
  padding: 14px 4px 6px;
}
.hero h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.4;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: var(--ink);
}
.hero p {
  margin: 9px 0 0;
  font-size: 14px;
  color: var(--sub);
}
.form-card {
  margin-top: 22px;
}
.code-input {
  width: 100%;
  height: 54px;
  border: 1.5px solid var(--line);
  border-radius: 14px;
  padding: 0 16px;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 4px;
  text-align: center;
  color: var(--ink);
  background: #fff;
  outline: none;
  text-transform: uppercase;
}
.code-input:focus {
  border-color: var(--accent-deep);
}
.code-input::placeholder {
  color: #c4cdd9;
  letter-spacing: 4px;
}
.hint {
  margin: 9px 2px 16px;
  font-size: 12px;
  color: var(--faint);
}
.rights {
  margin-top: 14px;
  padding: 16px 16px 6px;
}
.rights-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 6px;
}
.right-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 11px 0;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
  color: var(--ink);
}
.right-row:last-child {
  border-bottom: none;
}
.right-ic {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: #fff3df;
  color: var(--accent-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.right-check {
  margin-left: auto;
  color: var(--green);
  flex-shrink: 0;
}
</style>
