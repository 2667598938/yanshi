<script setup>
import { computed, reactive, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { authApi, publicApi } from '../../api'
import { initSyncForUser } from '../../sync/engine'
import { Smartphone } from 'lucide-vue-next'

const WECHAT_PATH = 'M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.582.582 0 0 1-.023-.156.49.49 0 0 1 .201-.398C23.024 18.48 24 16.82 24 14.98c0-3.21-2.931-5.837-6.656-6.088V8.89c-.135-.01-.27-.027-.407-.03zm-2.53 3.274c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.969-.982z'
const QQ_PATH = 'M21.395 15.035a40 40 0 0 0-.803-2.264l-1.079-2.695c.001-.032.014-.562.014-.836C19.526 4.632 17.351 0 12 0S4.474 4.632 4.474 9.241c0 .274.013.804.014.836l-1.08 2.695a39 39 0 0 0-.802 2.264c-1.021 3.283-.69 4.643-.438 4.673.54.065 2.103-2.472 2.103-2.472 0 1.469.756 3.387 2.394 4.771-.612.188-1.363.479-1.845.835-.434.32-.379.646-.301.778.343.578 5.883.369 7.482.189 1.6.18 7.14.389 7.483-.189.078-.132.132-.458-.301-.778-.483-.356-1.233-.646-1.846-.836 1.637-1.384 2.393-3.302 2.393-4.771 0 0 1.563 2.537 2.103 2.472.251-.03.581-1.39-.438-4.673'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const mode = ref(route.query.mode === 'register' ? 'register' : route.query.mode === 'forgot' ? 'forgot' : 'login')
const loginMode = ref('code') // code | password
const loading = ref(false)
const error = ref('')
const info = ref('')
const form = reactive({
  email: '',
  password: '',
  confirm: '',
  nickname: '',
  invite_code: '',
  code: '',
  phone: '',
  accepted: false,
})

const channels = ref(['email'])
const thirdProviders = [
  { id: 'wechat', label: '微信', color: '#07C160' },
  { id: 'qq', label: 'QQ', color: '#12B7F5' },
  { id: 'phone', label: '手机号', color: '#2f6fb0' },
]

function hasChannel(id) {
  return channels.value.includes(id)
}

async function finishOAuth(ticket) {
  try {
    await auth.exchangeOAuth(ticket)
    await initSyncForUser()
    router.replace('/')
  } catch (e) {
    error.value = e.message
  }
}

async function thirdParty(id) {
  error.value = ''
  if (!hasChannel(id)) {
    const name = thirdProviders.find((p) => p.id === id)?.label || '该方式'
    error.value = `${name}登录暂未开放`
    return
  }
  if (id === 'phone') {
    mode.value = 'phone'
    return
  }
  try {
    const data = await authApi.oauthAuthorize(id)
    if (data.url) window.location.href = data.url
  } catch (e) {
    error.value = e.message
  }
}

async function sendPhoneCode() {
  error.value = ''
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
    error.value = '请输入正确的手机号'
    return
  }
  if (countdown.value > 0) return
  try {
    await authApi.phoneSendCode(form.phone.trim())
    info.value = '验证码已发送'
    startCountdown()
  } catch (e) {
    error.value = e.message
  }
}

async function verifyPhone() {
  error.value = ''
  loading.value = true
  try {
    await auth.phoneLogin(form.phone.trim(), form.code)
    await initSyncForUser()
    router.replace(route.query.redirect || '/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const countdown = ref(0)
let timer = null
function startCountdown() {
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) clearInterval(timer)
  }, 1000)
}
onUnmounted(() => clearInterval(timer))

async function sendCode(scene) {
  error.value = ''
  if (!/^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i.test(form.email)) {
    error.value = '请先输入正确的邮箱'
    return
  }
  if (countdown.value > 0) return
  try {
    await authApi.sendCode(form.email.trim().toLowerCase(), scene)
    info.value = '验证码已发送（开发模式下可在后端控制台查看）'
    startCountdown()
  } catch (e) {
    error.value = e.message
  }
}

async function submit() {
  error.value = ''
  info.value = ''
  loading.value = true
  try {
    if (mode.value === 'phone') {
      loading.value = false
      await verifyPhone()
      return
    }
    if (mode.value === 'login') {
      if (loginMode.value === 'code') {
        if (!form.accepted) {
          error.value = '请先阅读并同意用户协议与隐私政策'
          loading.value = false
          return
        }
        await auth.emailLogin({
          email: form.email.trim().toLowerCase(),
          code: form.code,
          accepted_terms: true,
        })
      } else {
        await auth.login(form.email.trim().toLowerCase(), form.password)
      }
    } else if (mode.value === 'register') {
      if (form.password !== form.confirm) {
        error.value = '两次输入的密码不一致'
        loading.value = false
        return
      }
      if (!form.accepted) {
        error.value = '请先阅读并同意用户协议与隐私政策'
        loading.value = false
        return
      }
      await auth.register({
        email: form.email.trim().toLowerCase(),
        code: form.code,
        password: form.password,
        nickname: form.nickname.trim(),
        invite_code: form.invite_code.trim().toUpperCase(),
        accepted_terms: true,
      })
    } else {
      await authApi.resetPassword({
        email: form.email.trim().toLowerCase(),
        code: form.code,
        password: form.password,
      })
      mode.value = 'login'
      info.value = '密码已重置，请用新密码登录'
      loading.value = false
      return
    }
    await initSyncForUser()
    router.replace(route.query.redirect || '/')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function switchMode(m) {
  mode.value = m
  error.value = ''
  info.value = ''
  if (m === 'login') loginMode.value = 'code'
}

const isCodeLogin = computed(() => mode.value === 'login' && loginMode.value === 'code')
const isPasswordField = computed(() => mode.value !== 'login' || loginMode.value === 'password')
const showAgree = computed(() => mode.value === 'register' || isCodeLogin.value)
const submitLabel = computed(() => {
  if (mode.value === 'login') return isCodeLogin.value ? '登录 / 自动注册' : '登录'
  return mode.value === 'register' ? '注册' : '重置密码'
})
// 协议弹层
const showLegal = ref(false)
const legal = ref(null)
const legalTab = ref('terms')
async function openLegal(tab) {
  legalTab.value = tab
  if (!legal.value) {
    try {
      legal.value = await publicApi.legal()
    } catch {
      legal.value = { terms: '协议加载失败', privacy: '隐私政策加载失败', disclaimer: '免责声明加载失败' }
    }
  }
  showLegal.value = true
}

onMounted(async () => {
  try {
    const cfg = await publicApi.config()
    if (Array.isArray(cfg.enabled_auth_channels)) channels.value = cfg.enabled_auth_channels
  } catch {
    /* 配置拉取失败时保持仅邮箱登录 */
  }
  if (route.query.oauth_ticket) {
    await finishOAuth(String(route.query.oauth_ticket))
  }
})
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="brand">
        <div class="brand-logo">研</div>
        <h1>研时</h1>
        <p class="slogan">大雪深埋 · 静候春来</p>
      </div>

      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="switchMode('login')">登录</button>
        <button :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
        <button v-if="mode === 'forgot'" :class="{ active: true }">找回密码</button>
        <button v-if="mode === 'phone'" :class="{ active: true }">手机号</button>
      </div>

      <div v-if="mode === 'login'" class="mode-switch">
        <button :class="{ on: loginMode === 'code' }" @click="loginMode = 'code'">验证码登录</button>
        <button :class="{ on: loginMode === 'password' }" @click="loginMode = 'password'">密码登录</button>
      </div>

      <form class="form" @submit.prevent="submit">
        <template v-if="mode !== 'phone'">
        <label class="field">
          <span>邮箱</span>
          <input v-model="form.email" type="email" autocomplete="username" placeholder="you@example.com" />
        </label>

        <label v-if="isCodeLogin" class="field code-field">
          <span>邮箱验证码</span>
          <div class="code-row">
            <input v-model="form.code" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
            <button type="button" class="ghost-btn" :disabled="countdown > 0" @click="sendCode('login')">
              {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
            </button>
          </div>
        </label>

        <template v-if="mode === 'register'">
          <label class="field">
            <span>昵称</span>
            <input v-model="form.nickname" maxlength="40" placeholder="小组里怎么称呼你" />
          </label>
          <label class="field code-field">
            <span>邀请码（可选，用于开通 VIP）</span>
            <input v-model="form.invite_code" maxlength="16" placeholder="没有可留空" />
          </label>
          <label class="field code-field">
            <span>邮箱验证码</span>
            <div class="code-row">
              <input v-model="form.code" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
              <button type="button" class="ghost-btn" :disabled="countdown > 0" @click="sendCode('register')">
                {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
              </button>
            </div>
          </label>
        </template>

        <template v-if="mode === 'forgot'">
          <label class="field code-field">
            <span>邮箱验证码</span>
            <div class="code-row">
              <input v-model="form.code" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
              <button type="button" class="ghost-btn" :disabled="countdown > 0" @click="sendCode('reset')">
                {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
              </button>
            </div>
          </label>
        </template>

        <label v-if="isPasswordField" class="field">
          <span>{{ mode === 'forgot' ? '新密码' : '密码' }}</span>
          <input v-model="form.password" :type="'password'" autocomplete="current-password"
                 placeholder="8-64 位，含字母和数字" />
        </label>
        <label v-if="mode !== 'login'" class="field">
          <span>确认密码</span>
          <input v-model="form.confirm" type="password" autocomplete="new-password" placeholder="再输入一次" />
        </label>

        <label v-if="showAgree" class="agree">
          <input v-model="form.accepted" type="checkbox" />
          <span>
            我已阅读并同意
            <a @click.prevent="openLegal('terms')">用户协议</a>、
            <a @click.prevent="openLegal('privacy')">隐私政策</a>与
            <a @click.prevent="openLegal('disclaimer')">免责声明</a>
          </span>
        </label>

        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="info" class="info">{{ info }}</p>

        <button class="primary-btn" type="submit" :disabled="loading">
          {{ loading ? '请稍候…' : submitLabel }}
        </button>

        <div class="bottom-links">
          <a v-if="mode === 'login'" @click.prevent="switchMode('register')">没有账号？去注册</a>
          <a v-if="mode === 'login' && loginMode === 'password'" @click.prevent="switchMode('forgot')">忘记密码</a>
          <a v-if="mode !== 'login'" @click.prevent="switchMode('login')">返回登录</a>
        </div>
        </template>
        <template v-else>
          <label class="field">
            <span>手机号</span>
            <input v-model="form.phone" inputmode="numeric" maxlength="11" placeholder="11 位手机号" />
          </label>
          <label class="field code-field">
            <span>短信验证码</span>
            <div class="code-row">
              <input v-model="form.code" inputmode="numeric" maxlength="6" placeholder="6 位验证码" />
              <button type="button" class="ghost-btn" :disabled="countdown > 0" @click="sendPhoneCode">
                {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
              </button>
            </div>
          </label>
          <p class="field-hint">未注册手机号验证成功后自动创建账号；该渠道当前默认关闭。</p>
          <button class="primary-btn" type="submit" :disabled="loading">
            {{ loading ? '请稍候…' : '手机号登录 / 自动注册' }}
          </button>
          <div class="bottom-links">
            <a @click.prevent="switchMode('login')">返回登录</a>
          </div>
        </template>
      </form>

      <div class="third-party">
        <div class="tp-divider"><span>其他登录方式</span></div>
        <div class="tp-buttons">
          <button
            v-for="p in thirdProviders"
            :key="p.id"
            class="tp-btn"
            :class="{ off: !hasChannel(p.id) }"
            @click="thirdParty(p.id)"
          >
            <span class="tp-ic" :style="{ color: hasChannel(p.id) ? p.color : '#aab4c3' }">
              <svg v-if="p.id === 'wechat'" class="brand-svg" viewBox="0 0 24 24" aria-hidden="true">
                <path :d="WECHAT_PATH" />
              </svg>
              <svg v-else-if="p.id === 'qq'" class="brand-svg" viewBox="0 0 24 24" aria-hidden="true">
                <path :d="QQ_PATH" />
              </svg>
              <Smartphone v-else :size="17" :stroke-width="1.9" />
            </span>
            <span class="tp-name">{{ p.label }}</span>
            <span v-if="!hasChannel(p.id)" class="tp-off">暂不开放</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="showLegal" class="modal-mask" @click.self="showLegal = false">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ legalTab === 'terms' ? '用户协议' : legalTab === 'privacy' ? '隐私政策' : '免责声明' }}</h3>
          <button @click="showLegal = false">关闭</button>
        </div>
        <pre class="modal-body">{{ legalTab === 'terms' ? legal?.terms : legalTab === 'privacy' ? legal?.privacy : legal?.disclaimer }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
  background: linear-gradient(180deg, #f6f8fc 0%, #eef2f9 100%);
}
.auth-card {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 18px;
  padding: 28px 24px 24px;
  box-shadow: 0 12px 40px rgba(30, 50, 90, 0.1);
}
.brand {
  text-align: center;
  margin-bottom: 18px;
}
.brand-logo {
  width: 56px;
  height: 56px;
  margin: 0 auto 10px;
  border-radius: 16px;
  background: #2f6bff;
  color: #fff;
  font-size: 28px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.brand h1 {
  font-size: 24px;
  margin: 0;
  color: #1f2a44;
  letter-spacing: 4px;
}
.slogan {
  margin: 6px 0 0;
  color: #8a93a8;
  font-size: 13px;
  letter-spacing: 2px;
}
.tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 18px;
  background: #f1f4fa;
  border-radius: 10px;
  padding: 4px;
}
.tabs button {
  flex: 1;
  border: none;
  background: transparent;
  padding: 9px 0;
  border-radius: 8px;
  font-size: 14px;
  color: #6b7488;
  cursor: pointer;
}
.tabs button.active {
  background: #fff;
  color: #2f6bff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(47, 107, 255, 0.12);
}
.mode-switch {
  display: flex;
  justify-content: center;
  gap: 18px;
  margin: -6px 0 14px;
}
.mode-switch button {
  border: none;
  background: none;
  padding: 0 2px 2px;
  font-size: 12.5px;
  color: #8a93a8;
  cursor: pointer;
  border-bottom: 2px solid transparent;
}
.mode-switch button.on {
  color: #2f6bff;
  font-weight: 600;
  border-bottom-color: #2f6bff;
}
.field-hint {
  font-size: 11.5px;
  color: #9aa3b5;
  margin: 2px 2px 6px;
  line-height: 1.6;
}
.third-party {
  margin-top: 20px;
}
.tp-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #a2aab8;
  font-size: 11px;
  margin-bottom: 12px;
}
.tp-divider::before,
.tp-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #e8edf5;
}
.tp-buttons {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.tp-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  padding: 10px 4px;
  border: 1px solid #e6ebf3;
  border-radius: 12px;
  background: #fff;
  color: #4a5568;
  cursor: pointer;
  position: relative;
}
.tp-btn.off {
  opacity: 0.55;
  background: #fafbfe;
}
.tp-ic {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: #f4f7fb;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #4a5568;
}
.brand-svg {
  width: 19px;
  height: 19px;
  fill: currentColor;
}
.tp-name {
  font-size: 12px;
  font-weight: 600;
}
.tp-off {
  position: absolute;
  top: 4px;
  right: 4px;
  font-size: 9px;
  color: #9aa3b5;
  background: #f1f4fa;
  border-radius: 999px;
  padding: 1px 5px;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field > span {
  font-size: 13px;
  color: #5a6478;
}
.field input[type='email'],
.field input[type='password'],
.field input:not([type]) {
  width: 100%;
  box-sizing: border-box;
}
.field input {
  height: 44px;
  border: 1px solid #dfe4ee;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 15px;
  background: #fafbfe;
}
.field input:focus {
  outline: none;
  border-color: #2f6bff;
  background: #fff;
}
.code-row {
  display: flex;
  gap: 8px;
}
.code-row input {
  flex: 1;
  height: 44px;
  border: 1px solid #dfe4ee;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 15px;
  background: #fafbfe;
}
.ghost-btn {
  white-space: nowrap;
  border: 1px solid #2f6bff;
  color: #2f6bff;
  background: #fff;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 13px;
  cursor: pointer;
  min-width: 96px;
}
.ghost-btn:disabled {
  border-color: #c6ccda;
  color: #9aa3b5;
  cursor: not-allowed;
}
.agree {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #6b7488;
}
.agree a {
  color: #2f6bff;
  cursor: pointer;
}
.primary-btn {
  height: 48px;
  border: none;
  border-radius: 12px;
  background: #2f6bff;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
}
.primary-btn:disabled {
  opacity: 0.6;
}
.error {
  color: #e5484d;
  font-size: 13px;
  margin: 0;
}
.info {
  color: #1f9d63;
  font-size: 13px;
  margin: 0;
}
.bottom-links {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}
.bottom-links a {
  color: #2f6bff;
  font-size: 13px;
  cursor: pointer;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 30, 50, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 100;
}
.modal {
  background: #fff;
  border-radius: 14px;
  max-width: 560px;
  width: 100%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px;
  border-bottom: 1px solid #eef1f6;
}
.modal-head h3 {
  margin: 0;
  font-size: 16px;
}
.modal-head button {
  border: none;
  background: #f1f4fa;
  border-radius: 8px;
  padding: 6px 12px;
  cursor: pointer;
}
.modal-body {
  padding: 16px 18px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.8;
  color: #3a4256;
  margin: 0;
}
</style>
