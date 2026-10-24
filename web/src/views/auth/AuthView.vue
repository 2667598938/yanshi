<script setup>
import { computed, reactive, ref, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { authApi, publicApi } from '../../api'
import { initSyncForUser } from '../../sync/engine'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const mode = ref(route.query.mode === 'register' ? 'register' : route.query.mode === 'forgot' ? 'forgot' : 'login')
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
  accepted: false,
})

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
    if (mode.value === 'login') {
      await auth.login(form.email.trim().toLowerCase(), form.password)
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
}

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
      legal.value = { terms: '协议加载失败', privacy: '隐私政策加载失败' }
    }
  }
  showLegal.value = true
}

const title = computed(() =>
  mode.value === 'login' ? '登录' : mode.value === 'register' ? '注册' : '找回密码'
)
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
      </div>

      <form class="form" @submit.prevent="submit">
        <label class="field">
          <span>邮箱</span>
          <input v-model="form.email" type="email" autocomplete="username" placeholder="you@example.com" />
        </label>

        <template v-if="mode === 'register'">
          <label class="field">
            <span>昵称</span>
            <input v-model="form.nickname" maxlength="40" placeholder="小组里怎么称呼你" />
          </label>
          <label class="field code-field">
            <span>邀请码</span>
            <input v-model="form.invite_code" maxlength="16" placeholder="向管理员索取" />
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

        <label class="field">
          <span>{{ mode === 'forgot' ? '新密码' : '密码' }}</span>
          <input v-model="form.password" :type="'password'" autocomplete="current-password"
                 placeholder="8-64 位，含字母和数字" />
        </label>
        <label v-if="mode !== 'login'" class="field">
          <span>确认密码</span>
          <input v-model="form.confirm" type="password" autocomplete="new-password" placeholder="再输入一次" />
        </label>

        <label v-if="mode === 'register'" class="agree">
          <input v-model="form.accepted" type="checkbox" />
          <span>
            我已阅读并同意
            <a @click.prevent="openLegal('terms')">用户协议</a>与
            <a @click.prevent="openLegal('privacy')">隐私政策</a>
          </span>
        </label>

        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="info" class="info">{{ info }}</p>

        <button class="primary-btn" type="submit" :disabled="loading">
          {{ loading ? '请稍候…' : title }}
        </button>

        <div class="bottom-links">
          <a v-if="mode === 'login'" @click.prevent="switchMode('register')">没有账号？去注册</a>
          <a v-if="mode === 'login'" @click.prevent="switchMode('forgot')">忘记密码</a>
          <a v-if="mode !== 'login'" @click.prevent="switchMode('login')">返回登录</a>
        </div>
      </form>
    </div>

    <div v-if="showLegal" class="modal-mask" @click.self="showLegal = false">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ legalTab === 'terms' ? '用户协议' : '隐私政策' }}</h3>
          <button @click="showLegal = false">关闭</button>
        </div>
        <pre class="modal-body">{{ legalTab === 'terms' ? legal?.terms : legal?.privacy }}</pre>
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
