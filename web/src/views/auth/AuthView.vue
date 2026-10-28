<script setup>
import { computed, reactive, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { authApi, publicApi } from '../../api'
import { initSyncForUser } from '../../sync/engine'
import { Smartphone, Timer, NotebookPen, Sparkles, Users, ArrowLeft, ArrowUpRight, Eye, EyeOff, ShieldCheck } from 'lucide-vue-next'

const WECHAT_PATH = 'M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.582.582 0 0 1-.023-.156.49.49 0 0 1 .201-.398C23.024 18.48 24 16.82 24 14.98c0-3.21-2.931-5.837-6.656-6.088V8.89c-.135-.01-.27-.027-.407-.03zm-2.53 3.274c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.969-.982z'
const QQ_PATH = 'M21.395 15.035a40 40 0 0 0-.803-2.264l-1.079-2.695c.001-.032.014-.562.014-.836C19.526 4.632 17.351 0 12 0S4.474 4.632 4.474 9.241c0 .274.013.804.014.836l-1.08 2.695a39 39 0 0 0-.802 2.264c-1.021 3.283-.69 4.643-.438 4.673.54.065 2.103-2.472 2.103-2.472 0 1.469.756 3.387 2.394 4.771-.612.188-1.363.479-1.845.835-.434.32-.379.646-.301.778.343.578 5.883.369 7.482.189 1.6.18 7.14.389 7.483-.189.078-.132.132-.458-.301-.778-.483-.356-1.233-.646-1.846-.836 1.637-1.384 2.393-3.302 2.393-4.771 0 0 1.563 2.537 2.103 2.472.251-.03.581-1.39-.438-4.673'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const mode = ref(route.query.mode === 'forgot' ? 'forgot' : 'login')
const loginMode = ref('code') // code | password
const loading = ref(false)
const error = ref('')
const info = ref('')
const codeSending = ref(false)
const passwordVisible = ref(false)
const registrationOpen = ref(null)
const configError = ref(false)
let alive = true
const redirectTarget = computed(() => typeof route.query.redirect === 'string'
  && route.query.redirect.startsWith('/') && !route.query.redirect.startsWith('//') ? route.query.redirect : '/')
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
  { id: 'phone', label: '手机号', color: '#4f46e5' },
]
const availableProviders = computed(() => thirdProviders.filter(provider => hasChannel(provider.id)))
const features = [
  { icon: Timer, title: '任务与专注', text: '从每日计划到番茄计时，让进步有迹可循。', tone: 'indigo' },
  { icon: NotebookPen, title: '错题与复习', text: '收录题图与解析，在该复习的时候再见一面。', tone: 'amber' },
  { icon: Sparkles, title: 'AI 学习助教', text: '连接自己的模型，结合本人学习记录答疑与复盘。', tone: 'violet' },
  { icon: Users, title: '小组与自习室', text: '与研友并肩学习，需要独处时开启隐私模式。', tone: 'green' },
]

function hasChannel(id) {
  return channels.value.includes(id)
}

async function finishOAuth(ticket) {
  try {
    await auth.exchangeOAuth(ticket)
    await initSyncForUser()
    router.replace(redirectTarget.value)
  } catch (e) {
    error.value = e.message
  }
}

async function thirdParty(id) {
  if (loading.value) return
  error.value = ''
  info.value = ''
  if (!hasChannel(id)) {
    const name = thirdProviders.find((p) => p.id === id)?.label || '该方式'
    error.value = `${name}登录暂未开放`
    return
  }
  if (id === 'phone') {
    mode.value = 'phone'
    return
  }
  if (!form.accepted) { error.value = '请先阅读并同意用户协议与隐私政策'; return }
  loading.value = true
  try {
    const data = await authApi.oauthAuthorize(id, form.accepted)
    if (data.url) window.location.href = data.url
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function sendPhoneCode() {
  error.value = ''
  info.value = ''
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
    error.value = '请输入正确的手机号'
    return
  }
  if (codeSending.value || countdown.value > 0) return
  codeSending.value = true
  try {
    await authApi.phoneSendCode(form.phone.trim())
    info.value = '验证码已发送'
    startCountdown()
  } catch (e) {
    error.value = e.message
  } finally {
    codeSending.value = false
  }
}

async function verifyPhone() {
  error.value = ''
  loading.value = true
  try {
    if (!form.accepted) { error.value = '请先阅读并同意用户协议与隐私政策'; return }
    await auth.phoneLogin(form.phone.trim(), form.code, form.accepted)
    await initSyncForUser()
    router.replace(redirectTarget.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const countdown = ref(0)
let timer = null
function startCountdown() {
  clearInterval(timer)
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) clearInterval(timer)
  }, 1000)
}
onUnmounted(() => { alive = false; clearInterval(timer) })

async function sendCode(scene) {
  error.value = ''
  info.value = ''
  if (scene === 'register' && registrationOpen.value !== true) {
    error.value = '注册暂未开放，请联系管理员创建账号'
    return
  }
  if (!/^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i.test(form.email)) {
    error.value = '请先输入正确的邮箱'
    return
  }
  if (codeSending.value || countdown.value > 0) return
  codeSending.value = true
  try {
    await authApi.sendCode(form.email.trim().toLowerCase(), scene)
    info.value = '验证码已发送，请查收邮件并检查垃圾邮件箱。'
    startCountdown()
  } catch (e) {
    error.value = e.message
  } finally {
    codeSending.value = false
  }
}

async function submit() {
  if (loading.value) return
  error.value = ''
  info.value = ''
  loading.value = true
  try {
    if (['register', 'forgot'].includes(mode.value) && form.password !== form.confirm) {
      error.value = '两次输入的密码不一致'
      return
    }
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
      if (registrationOpen.value !== true) { error.value = '注册暂未开放，请联系管理员创建账号'; return }
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
    router.replace(redirectTarget.value)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function switchMode(m) {
  if (loading.value) return
  if (m === 'register' && registrationOpen.value !== true) {
    error.value = '注册暂未开放，请联系管理员创建账号'
    return
  }
  mode.value = m
  error.value = ''
  info.value = ''
  passwordVisible.value = false
  if (m === 'login') loginMode.value = 'code'
}

const isCodeLogin = computed(() => mode.value === 'login' && loginMode.value === 'code')
const isPasswordField = computed(() => ['register', 'forgot'].includes(mode.value) || loginMode.value === 'password')
const showAgree = computed(() => mode.value === 'register' || mode.value === 'phone' || isCodeLogin.value
  || (mode.value === 'login' && availableProviders.value.some(provider => provider.id !== 'phone')))
const submitLabel = computed(() => {
  if (mode.value === 'login') return isCodeLogin.value ? '验证并登录' : '登录'
  if (mode.value === 'phone') return '验证手机号并登录'
  return mode.value === 'register' ? '创建账号' : '重置密码'
})
const heading = computed(() => ({ login: '欢迎回来', register: '开始你的研时', forgot: '找回密码', phone: '手机号登录' })[mode.value])
const description = computed(() => ({ login: '继续你的计划，积累每一点进步。', register: '创建账号，把学习计划和每次进步留下来。', forgot: '使用账号邮箱验证身份，设置新的密码。', phone: '使用已开通的手机号渠道验证身份。' })[mode.value])
const codeLoginHint = computed(() => registrationOpen.value === true
  ? '未注册邮箱验证后可创建账号。' : registrationOpen.value === false
    ? '仅限已有账号登录。' : '使用已有账号的邮箱接收验证码。')
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

async function loadPublicConfig() {
  configError.value = false
  try {
    const cfg = await publicApi.config()
    if (!alive) return
    if (Array.isArray(cfg.enabled_auth_channels)) channels.value = cfg.enabled_auth_channels
    registrationOpen.value = cfg.registration_open === true
    if (registrationOpen.value && route.query.mode === 'register' && mode.value === 'login') mode.value = 'register'
    if (!registrationOpen.value && mode.value === 'register') switchMode('login')
  } catch {
    if (alive) { configError.value = true; registrationOpen.value = null }
  }
}
onMounted(async () => {
  await loadPublicConfig()
  if (route.query.oauth_ticket) {
    await finishOAuth(String(route.query.oauth_ticket))
  }
})
</script>


<template>
  <div class="auth-page">
    <div class="auth-layout">
      <aside class="auth-intro" aria-label="关于研时">
        <div class="intro-brand" aria-label="研时">
          <span class="brand-logo" aria-hidden="true">研</span>
          <span class="brand-name">研时<small>你的学习工作台</small></span>
        </div>
        <div class="intro-copy">
          <span class="intro-kicker">计划 · 专注 · 复盘 · 同行</span>
          <h2>把每一天，<br /><span>学成自己的答案。</span></h2>
          <p>从一次专注到一道错题，让 AI 和研友陪你稳步向前。</p>
        </div>
        <div class="feature-grid">
          <div v-for="feature in features" :key="feature.title" class="auth-feature">
            <span class="feature-icon" :class="feature.tone"><component :is="feature.icon" :size="19" :stroke-width="1.8" /></span>
            <h3>{{ feature.title }}</h3>
            <p>{{ feature.text }}</p>
          </div>
        </div>
        <div class="intro-privacy"><ShieldCheck :size="17" /><p>小组学习数据可一键开启隐私保护。<br />AI 对话与密钥始终仅本人可见。</p></div>
        <p class="intro-motto">大雪深埋，静候春来。</p>
      </aside>

      <section class="auth-form-area" aria-labelledby="auth-heading">
        <div class="mobile-brand"><span class="brand-logo" aria-hidden="true">研</span><span>研时<small>计划、专注与 AI 学习助教</small></span></div>
        <div class="auth-card">
          <header class="form-heading">
            <div class="form-eyebrow">留一点时间，给更好的自己</div>
            <h1 id="auth-heading">{{ heading }}</h1>
            <p>{{ description }}</p>
          </header>
          <div v-if="registrationOpen === true" class="tabs" aria-label="账号入口">
            <button type="button" :disabled="loading" :aria-pressed="mode === 'login' || mode === 'forgot' || mode === 'phone'" :class="{ active: mode !== 'register' }" @click="switchMode('login')">登录</button>
            <button type="button" :disabled="loading" :aria-pressed="mode === 'register'" :class="{ active: mode === 'register' }" @click="switchMode('register')">注册</button>
          </div>
          <p v-if="registrationOpen === false" class="admission-note">注册暂未开放，已有账号可直接登录；新账号请联系管理员创建。</p>
          <p v-else-if="configError" class="admission-note">暂时无法确认注册状态。已有账号仍可登录。<button type="button" class="text-button" @click="loadPublicConfig">重试</button></p>

          <div v-if="mode === 'login'" class="mode-switch" aria-label="登录方式">
            <button type="button" :disabled="loading" :aria-pressed="loginMode === 'code'" :class="{ on: loginMode === 'code' }" @click="loginMode = 'code'; error = ''; info = ''">邮箱验证码</button>
            <button type="button" :disabled="loading" :aria-pressed="loginMode === 'password'" :class="{ on: loginMode === 'password' }" @click="loginMode = 'password'; error = ''; info = ''">账号密码</button>
          </div>

          <form class="form" :aria-busy="loading" @submit.prevent="submit">
            <template v-if="mode !== 'phone'">
              <label class="field" for="auth-email"><span>邮箱</span><input id="auth-email" v-model="form.email" name="email" type="email" autocomplete="username" autocapitalize="none" spellcheck="false" required :disabled="loading" placeholder="请输入账号邮箱" /></label>
              <template v-if="mode === 'register'">
                <label class="field" for="auth-nickname"><span>昵称</span><input id="auth-nickname" v-model="form.nickname" name="nickname" autocomplete="nickname" maxlength="40" required :disabled="loading" placeholder="希望研友怎么称呼你" /></label>
                <label class="field" for="auth-invite"><span>注册 / VIP 邀请码 <small>如有请填写</small></span><input id="auth-invite" v-model="form.invite_code" name="invite_code" maxlength="16" :disabled="loading" placeholder="没有可留空" /><small class="field-hint">小组邀请需要在登录后单独申请。</small></label>
              </template>
              <div v-if="isCodeLogin || mode === 'register' || mode === 'forgot'" class="field code-field">
                <label for="auth-email-code">邮箱验证码</label>
                <div class="code-row">
                  <input id="auth-email-code" v-model="form.code" name="email_code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required :disabled="loading" placeholder="输入 6 位验证码" />
                  <button type="button" class="ghost-btn" :disabled="codeSending || countdown > 0 || loading" @click="sendCode(mode === 'register' ? 'register' : mode === 'forgot' ? 'reset' : 'login')">{{ codeSending ? '发送中…' : countdown > 0 ? `${countdown} 秒后重发` : '获取验证码' }}</button>
                </div>
              </div>
              <div v-if="isPasswordField" class="field">
                <div class="field-top"><label for="auth-password">{{ mode === 'forgot' ? '新密码' : '密码' }}</label><button v-if="mode === 'login'" type="button" class="text-button" :disabled="loading" @click="switchMode('forgot')">忘记密码？</button></div>
                <div class="password-row"><input id="auth-password" v-model="form.password" name="password" :type="passwordVisible ? 'text' : 'password'" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" maxlength="64" required :disabled="loading" :placeholder="mode === 'login' ? '请输入密码' : '8–64 位，包含字母和数字'" /><button type="button" class="password-visibility" :disabled="loading" :aria-label="passwordVisible ? '隐藏密码' : '显示密码'" :aria-pressed="passwordVisible" @click="passwordVisible = !passwordVisible"><component :is="passwordVisible ? EyeOff : Eye" :size="18" /></button></div>
              </div>
              <label v-if="mode === 'register' || mode === 'forgot'" class="field" for="auth-confirm"><span>确认密码</span><input id="auth-confirm" v-model="form.confirm" name="confirm_password" type="password" autocomplete="new-password" maxlength="64" required :disabled="loading" placeholder="再输入一次密码" /></label>
            </template>
            <template v-else>
              <label class="field" for="auth-phone"><span>手机号</span><input id="auth-phone" v-model="form.phone" name="phone" type="tel" autocomplete="tel-national" inputmode="numeric" pattern="1[3-9][0-9]{9}" maxlength="11" required :disabled="loading" placeholder="请输入 11 位手机号" /></label>
              <div class="field code-field"><label for="auth-phone-code">短信验证码</label><div class="code-row"><input id="auth-phone-code" v-model="form.code" name="phone_code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" required :disabled="loading" placeholder="输入 6 位验证码" /><button type="button" class="ghost-btn" :disabled="codeSending || countdown > 0 || loading" @click="sendPhoneCode">{{ codeSending ? '发送中…' : countdown > 0 ? `${countdown} 秒后重发` : '获取验证码' }}</button></div></div>
            </template>

            <div v-if="showAgree" class="agree"><input id="auth-agree" v-model="form.accepted" type="checkbox" :disabled="loading" /><div><label for="auth-agree">{{ mode === 'login' && !isCodeLogin ? '使用第三方登录前请阅读并同意' : '我已阅读并同意' }}</label><button type="button" class="legal-link" @click="openLegal('terms')">用户协议</button>、<button type="button" class="legal-link" @click="openLegal('privacy')">隐私政策</button>及<button type="button" class="legal-link" @click="openLegal('disclaimer')">免责声明</button></div></div>
            <p v-if="error" class="error" role="alert">{{ error }}</p>
            <p v-if="info" class="info" role="status">{{ info }}</p>
            <button class="primary-btn" type="submit" :disabled="loading">{{ loading ? '请稍候…' : submitLabel }}<ArrowUpRight v-if="!loading" :size="18" /></button>
            <p v-if="isCodeLogin && registrationOpen !== false" class="login-hint">{{ codeLoginHint }}</p>
            <div v-if="mode === 'forgot' || mode === 'phone'" class="bottom-links"><button type="button" class="text-button" :disabled="loading" @click="switchMode('login')"><ArrowLeft :size="14" />返回邮箱登录</button></div>
          </form>

          <div v-if="availableProviders.length && mode !== 'forgot'" class="third-party">
            <div class="tp-divider"><span>其他登录方式</span></div>
            <div class="tp-buttons">
              <button v-for="provider in availableProviders" :key="provider.id" type="button" class="tp-btn" :disabled="loading" @click="thirdParty(provider.id)">
                <span class="tp-ic" :style="{ color: provider.color }"><svg v-if="provider.id === 'wechat'" class="brand-svg" viewBox="0 0 24 24" aria-hidden="true"><path :d="WECHAT_PATH" /></svg><svg v-else-if="provider.id === 'qq'" class="brand-svg" viewBox="0 0 24 24" aria-hidden="true"><path :d="QQ_PATH" /></svg><Smartphone v-else :size="17" /></span><span>{{ provider.label }}</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-if="showLegal" class="modal-mask" @click.self="showLegal = false">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="auth-legal-heading">
        <div class="modal-head"><h2 id="auth-legal-heading">{{ legalTab === 'terms' ? '用户协议' : legalTab === 'privacy' ? '隐私政策' : '免责声明' }}</h2><button type="button" @click="showLegal = false">关闭</button></div>
        <pre class="modal-body">{{ legalTab === 'terms' ? legal?.terms : legalTab === 'privacy' ? legal?.privacy : legal?.disclaimer }}</pre>
      </section>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  --primary: var(--brand-primary,#647D9D);
  --primary-grad: linear-gradient(135deg,#647D9D,#7890AA);
  min-height: calc(100dvh - var(--notice-h, 0px));
  padding: clamp(24px, 4vw, 64px) 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at 10% 15%, #e8eef5 0, transparent 48%), radial-gradient(ellipse at 95% 90%, #edf1f6 0, transparent 45%), var(--brand-background,#F7F8FA);
}
.auth-layout { width: 100%; max-width: 1120px; display: grid; grid-template-columns: minmax(0, 1.12fr) minmax(0, 1fr); gap: clamp(40px, 6vw, 88px); align-items: center; }
.auth-intro { display: block; min-width: 0; padding: 12px 0; }
.intro-brand { display: inline-flex; align-items: center; gap: 12px; text-decoration: none; color: var(--ink); }
.brand-logo { display: grid; place-items: center; width: 44px; height: 44px; flex-shrink: 0; border-radius: 14px; background: var(--primary-grad); box-shadow: 0 8px 20px #647d9d20; color: #fff; font-size: 25px; font-weight: 700; }
.brand-name { font-size: 24px; line-height: 1.3; font-weight: 800; letter-spacing: 2px; }
.brand-name small { display: block; margin-top: 3px; font-size: 11px; font-weight: 400; letter-spacing: 1px; color: #667085; }
.intro-copy { margin: 54px 0 32px; }
.intro-kicker { font-size: 12px; color: var(--primary); letter-spacing: 2px; font-weight: 600; }
.intro-copy h2 { margin: 14px 0 18px; font-size: clamp(34px, 3.4vw, 48px); line-height: 1.35; letter-spacing: -1px; font-weight: 750; color: #202540; }
.intro-copy h2 span { color: var(--primary); }
.intro-copy > p { margin: 0; max-width: 400px; font-size: 15px; line-height: 1.9; color: #68708a; }
.feature-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 24px 26px; }
.auth-feature { min-width: 0; }
.feature-icon { display: inline-flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 11px; margin-bottom: 8px; }
.feature-icon.indigo { background: #e9eaff; color: #4f46e5; }
.feature-icon.amber { background: #fff2dd; color: #a8690c; }
.feature-icon.violet { background: #efe8ff; color: #7c3aed; }
.feature-icon.green { background: #e2f2ef; color: #198675; }
.auth-feature h3 { margin: 0 0 5px; font-size: 14px; color: #343954; }
.auth-feature p { margin: 0; font-size: 12px; line-height: 1.8; color: #6b728b; }
.intro-privacy { display: flex; align-items: flex-start; gap: 9px; margin-top: 32px; padding-top: 24px; border-top: 1px solid #dfe3f2; color: #69728b; }
.intro-privacy svg { flex-shrink: 0; margin-top: 2px; color: #7a81a4; }
.intro-privacy p { margin: 0; font-size: 12px; line-height: 1.8; }
.intro-motto { margin: 20px 0 0; color: #8b91a6; font-size: 12px; letter-spacing: 2px; }
.auth-form-area { min-width: 0; width: 100%; max-width: 440px; justify-self: end; }
.mobile-brand { display: none; }
.auth-card { width: 100%; background: rgba(255,255,255,.96); border: 1px solid #ffffff; border-radius: 24px; padding: 32px; box-shadow: 0 16px 60px #4145850b, 0 2px 12px #31345f05; }
.form-eyebrow { color: #9298ac; font-size: 11px; letter-spacing: 1px; }
.form-heading h1 { margin: 8px 0 6px; color: #252943; font-size: 27px; line-height: 1.4; font-weight: 750; }
.form-heading p { margin: 0 0 24px; color: #7c8296; font-size: 12px; line-height: 1.7; }
.tabs { display: flex; gap: 4px; border: 1px solid #edf0f8; background: #f4f5fb; border-radius: 11px; padding: 4px; margin-bottom: 20px; }
.tabs button { flex: 1; min-height: 38px; border: 0; border-radius: 8px; background: transparent; color: #727a91; font-size: 13px; cursor: pointer; }
.tabs button.active { background: #fff; color: var(--primary); box-shadow: 0 2px 6px #27326a0a; font-weight: 600; }
.mode-switch { display: flex; gap: 22px; margin-bottom: 22px; border-bottom: 1px solid #eef0f6; }
.mode-switch button { padding: 0 0 10px; border: 0; border-bottom: 2px solid transparent; background: none; color: #8b91a5; font-size: 12px; cursor: pointer; }
.mode-switch button.on { border-bottom-color: var(--primary); color: var(--primary); font-weight: 600; }
.form { display: flex; flex-direction: column; gap: 17px; }
.field { display: flex; flex-direction: column; min-width: 0; gap: 7px; }
.field > span, .field > label, .field-top > label { color: #505a72; font-size: 12px; font-weight: 500; }
.field > span small { color: #9299ac; font-size: 11px; margin-left: 4px; font-weight: 400; }
.field input { width: 100%; min-width: 0; height: 46px; padding: 0 13px; border: 1px solid #dfe4f0; border-radius: 10px; background: #fbfcff; color: #252943; font-size: 14px; font-family: inherit; transition: border-color .18s, box-shadow .18s; }
.field input::placeholder { color: #a0a6b8; }
.field input:focus { outline: none; border-color: #8da2bd; background: #fff; box-shadow: 0 0 0 3px #647d9d14; }
.field input:disabled { opacity: .6; }
.code-row { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 8px; }
.ghost-btn { border: 1px solid #d5dfeb; border-radius: 10px; background: #f0f4f8; padding: 0 12px; color: var(--primary); font-size: 12px; cursor: pointer; white-space: nowrap; }
.ghost-btn:disabled { border-color: #e8eaf2; color: #9ca3b5; background: #f6f7fb; cursor: not-allowed; }
.field-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.text-button, .legal-link { padding: 0; border: 0; background: none; color: var(--primary); font-family: inherit; font-size: inherit; cursor: pointer; }
.field-top .text-button { font-size: 11px; }
.password-row { position: relative; }
.password-row input { padding-right: 46px; }
.password-visibility { position: absolute; top: 3px; bottom: 3px; right: 3px; width: 38px; display: grid; place-items: center; border: 0; border-radius: 8px; background: transparent; color: #8b91a5; cursor: pointer; }
.agree { display: flex; align-items: flex-start; gap: 8px; font-size: 11px; line-height: 1.8; color: #8a90a2; }
.agree > input { width: 15px; height: 15px; flex-shrink: 0; margin: 3px 0 0; accent-color: var(--primary); }
.agree label { cursor: pointer; margin-right: 3px; }
.legal-link { color: #647D9D; }
.primary-btn { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; min-height: 46px; border: 0; border-radius: 10px; padding: 12px; background: var(--primary-grad); box-shadow: 0 6px 16px #647d9d20; color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
.primary-btn:disabled { opacity: .6; cursor: not-allowed; }
.error, .info { margin: 0; padding: 10px 12px; border-radius: 8px; font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.error { color: #c33746; background: #fff0f2; border: 1px solid #fde2e7; }
.info { color: #21745f; background: #eff9f4; border: 1px solid #ddf1e5; }
.login-hint, .field-hint { margin: 0; color: #9298aa; font-size: 11px; font-weight: 400; line-height: 1.7; }
.login-hint { text-align: center; }
.bottom-links { display: flex; justify-content: center; font-size: 12px; }
.bottom-links .text-button { display: inline-flex; align-items: center; gap: 4px; }
.third-party { margin-top: 24px; }
.tp-divider { display: flex; align-items: center; gap: 12px; color: #a1a7b8; font-size: 11px; margin-bottom: 12px; }
.tp-divider::before, .tp-divider::after { content: ''; flex: 1; height: 1px; background: #edf0f6; }
.tp-buttons { display: flex; gap: 10px; }
.tp-btn { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 40px; border: 1px solid #e8ecf4; border-radius: 10px; background: #fff; color: #69748b; font-size: 12px; cursor: pointer; }
.tp-ic { display: inline-flex; align-items: center; }
.brand-svg { width: 17px; height: 17px; fill: currentColor; }
.admission-note { margin: 0 0 20px; padding: 10px 12px; border: 1px solid #e2e8ef; background: #f4f7fa; border-radius: 10px; color: #7d8793; font-size: 11px; line-height: 1.8; }
.modal-mask { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; padding: 24px; background: #1d254c66; z-index: 500; }
.modal { width: min(100%, 620px); max-height: calc(100dvh - 48px); display: flex; flex-direction: column; background: #fff; border-radius: 18px; box-shadow: 0 24px 80px #11182f30; overflow: hidden; }
.modal-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 18px 22px; border-bottom: 1px solid #edf0f6; }
.modal-head h2 { margin: 0; font-size: 16px; }
.modal-head button { flex-shrink: 0; padding: 7px 12px; border: 0; border-radius: 8px; background: #f4f5fb; color: #687089; cursor: pointer; }
.modal-body { min-height: 0; padding: 18px 22px; margin: 0; overflow-y: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; font-size: 13px; color: #5a647d; line-height: 1.9; }
@media (max-width: 959px) {
  .auth-page { padding: 30px 24px; }
  .auth-layout { grid-template-columns: minmax(0,1fr); max-width: 440px; gap: 0; }
  .auth-intro { display: none; }
  .auth-form-area { max-width: none; justify-self: stretch; }
  .mobile-brand { display: flex; gap: 10px; align-items: center; margin: 0 0 22px 4px; font-size: 21px; font-weight: 750; color: #282d49; }
  .mobile-brand .brand-logo { width: 38px; height: 38px; font-size: 22px; border-radius: 12px; }
  .mobile-brand small { display: block; margin-top: 1px; color: #9298ac; font-size: 10px; font-weight: 400; }
}
@media (max-width: 520px) {
  .auth-page { align-items: flex-start; padding: max(24px, env(safe-area-inset-top)) 20px max(28px, env(safe-area-inset-bottom)); }
  .auth-card { padding: 26px 22px; border-radius: 20px; }
  .form-heading h1 { font-size: 25px; }
  .field input { font-size: 16px; }
  .ghost-btn { padding: 0 10px; font-size: 11px; }
  .agree { font-size: 11px; }
}
@media (max-width: 359px) {
  .auth-page { padding-left: 12px; padding-right: 12px; }
  .auth-card { padding-left: 18px; padding-right: 18px; }
}
@media (prefers-reduced-motion: reduce) {
  .field input { transition: none; }
}
</style>
