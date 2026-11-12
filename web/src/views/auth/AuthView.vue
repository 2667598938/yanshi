<script setup>
import { computed, reactive, ref, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../../stores/auth';
import { authApi, publicApi } from '../../api';
import { initSyncForUser } from '../../sync/engine';
import PixelBookMark from '../../components/PixelBookMark.vue';
import {
  Github,
  Smartphone,
  Timer,
  NotebookPen,
  Sparkles,
  Users,
  ArrowLeft,
  ArrowUpRight,
  Eye,
  EyeOff,
  ShieldCheck,
} from 'lucide-vue-next';

const WECHAT_PATH =
  'M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.047c.134 0 .24-.111.24-.247 0-.06-.023-.12-.038-.177l-.327-1.233a.582.582 0 0 1-.023-.156.49.49 0 0 1 .201-.398C23.024 18.48 24 16.82 24 14.98c0-3.21-2.931-5.837-6.656-6.088V8.89c-.135-.01-.27-.027-.407-.03zm-2.53 3.274c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.969-.982z';
const QQ_PATH =
  'M21.395 15.035a40 40 0 0 0-.803-2.264l-1.079-2.695c.001-.032.014-.562.014-.836C19.526 4.632 17.351 0 12 0S4.474 4.632 4.474 9.241c0 .274.013.804.014.836l-1.08 2.695a39 39 0 0 0-.802 2.264c-1.021 3.283-.69 4.643-.438 4.673.54.065 2.103-2.472 2.103-2.472 0 1.469.756 3.387 2.394 4.771-.612.188-1.363.479-1.845.835-.434.32-.379.646-.301.778.343.578 5.883.369 7.482.189 1.6.18 7.14.389 7.483-.189.078-.132.132-.458-.301-.778-.483-.356-1.233-.646-1.846-.836 1.637-1.384 2.393-3.302 2.393-4.771 0 0 1.563 2.537 2.103 2.472.251-.03.581-1.39-.438-4.673';

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const pixelArt = '/art/pixel-study-room.webp';
const desktopArtUnavailable = ref(false);
const mobileArtUnavailable = ref(false);

const mode = ref(route.query.mode === 'forgot' ? 'forgot' : 'login');
const passwordOnly = ref(true); // 配置未到达或读取失败时，默认只开放密码登录。
const emailCodeAvailable = ref(false);
const configLoading = ref(true);
const loginMode = ref('password'); // code | password
const loading = ref(false);
const error = ref('');
const info = ref('');
const codeSending = ref(false);
const passwordVisible = ref(false);
const registrationOpen = ref(null);
const registrationSlots = ref(null);
const configError = ref(false);
let alive = true;
const redirectTarget = computed(() =>
  typeof route.query.redirect === 'string' &&
  route.query.redirect.startsWith('/') &&
  !route.query.redirect.startsWith('//')
    ? route.query.redirect
    : '/',
);
const form = reactive({
  email: '',
  password: '',
  confirm: '',
  nickname: '',
  invite_code: '',
  code: '',
  phone: '',
  accepted: false,
});

const channels = ref(['email']);
const thirdProviders = [
  { id: 'github', label: 'GitHub', color: '#181717' },
  { id: 'wechat', label: '微信', color: '#07C160' },
  { id: 'qq', label: 'QQ', color: '#12B7F5' },
  { id: 'phone', label: '手机号', color: '#4f46e5' },
];
const availableProviders = computed(() =>
  passwordOnly.value ? [] : thirdProviders.filter((provider) => hasChannel(provider.id)),
);
const features = [
  { icon: Timer, title: '任务与专注' },
  { icon: NotebookPen, title: '错题与复习' },
  { icon: Sparkles, title: 'AI 学习助教' },
  { icon: Users, title: '小组与自习室' },
];

function hasChannel(id) {
  return channels.value.includes(id);
}

async function finishOAuth(ticket) {
  if (passwordOnly.value) {
    error.value = '内测期间仅支持账号密码登录';
    return;
  }
  try {
    await auth.exchangeOAuth(ticket);
    await initSyncForUser();
    router.replace(redirectTarget.value);
  } catch (e) {
    error.value = e.message;
  }
}

async function thirdParty(id) {
  if (loading.value) return;
  error.value = '';
  info.value = '';
  if (passwordOnly.value || !hasChannel(id)) {
    const name = thirdProviders.find((p) => p.id === id)?.label || '该方式';
    error.value = `${name}登录暂未开放`;
    return;
  }
  if (id === 'phone') {
    mode.value = 'phone';
    return;
  }
  if (!form.accepted) {
    error.value = '请先阅读并同意用户协议与隐私政策';
    return;
  }
  loading.value = true;
  try {
    const data = await authApi.oauthAuthorize(id, form.accepted);
    if (data.url) window.location.href = data.url;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function sendPhoneCode() {
  error.value = '';
  info.value = '';
  if (!/^1[3-9]\d{9}$/.test(form.phone.trim())) {
    error.value = '请输入正确的手机号';
    return;
  }
  if (codeSending.value || countdown.value > 0) return;
  codeSending.value = true;
  try {
    await authApi.phoneSendCode(form.phone.trim());
    info.value = '验证码已发送';
    startCountdown();
  } catch (e) {
    error.value = e.message;
  } finally {
    codeSending.value = false;
  }
}

async function verifyPhone() {
  error.value = '';
  loading.value = true;
  try {
    if (!form.accepted) {
      error.value = '请先阅读并同意用户协议与隐私政策';
      return;
    }
    await auth.phoneLogin(form.phone.trim(), form.code, form.accepted);
    await initSyncForUser();
    router.replace(redirectTarget.value);
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

const countdown = ref(0);
let timer = null;
function startCountdown() {
  clearInterval(timer);
  countdown.value = 60;
  timer = setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0) clearInterval(timer);
  }, 1000);
}
onUnmounted(() => {
  alive = false;
  clearInterval(timer);
});

async function sendCode(scene) {
  error.value = '';
  info.value = '';
  if (scene === 'register' && registrationOpen.value !== true) {
    error.value = '注册暂未开放，请联系管理员创建账号';
    return;
  }
  if (scene === 'register' && registrationSlots.value === 0) {
    error.value = '本站注册名额已满';
    return;
  }
  if (!/^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i.test(form.email)) {
    error.value = '请先输入正确的邮箱';
    return;
  }
  if (codeSending.value || countdown.value > 0) return;
  codeSending.value = true;
  try {
    await authApi.sendCode(form.email.trim().toLowerCase(), scene);
    info.value = '验证码已发送，请查收邮件并检查垃圾邮件箱。';
    startCountdown();
  } catch (e) {
    error.value = e.message;
  } finally {
    codeSending.value = false;
  }
}

async function submit() {
  if (loading.value) return;
  error.value = '';
  info.value = '';
  loading.value = true;
  try {
    if (['register', 'forgot'].includes(mode.value) && form.password !== form.confirm) {
      error.value = '两次输入的密码不一致';
      return;
    }
    if (mode.value === 'phone') {
      loading.value = false;
      await verifyPhone();
      return;
    }
    if (mode.value === 'login') {
      if (loginMode.value === 'code') {
        if (!form.accepted) {
          error.value = '请先阅读并同意用户协议与隐私政策';
          loading.value = false;
          return;
        }
        await auth.emailLogin({
          email: form.email.trim().toLowerCase(),
          code: form.code,
          accepted_terms: true,
        });
      } else {
        await auth.login(form.email.trim().toLowerCase(), form.password);
      }
    } else if (mode.value === 'register') {
      if (registrationOpen.value !== true) {
        error.value = '注册暂未开放，请联系管理员创建账号';
        return;
      }
      if (registrationSlots.value === 0) {
        error.value = '本站注册名额已满';
        return;
      }
      if (!form.accepted) {
        error.value = '请先阅读并同意用户协议与隐私政策';
        loading.value = false;
        return;
      }
      await auth.register({
        email: form.email.trim().toLowerCase(),
        code: form.code,
        password: form.password,
        nickname: form.nickname.trim(),
        invite_code: form.invite_code.trim().toUpperCase(),
        accepted_terms: true,
      });
    } else {
      await authApi.resetPassword({
        email: form.email.trim().toLowerCase(),
        code: form.code,
        password: form.password,
      });
      mode.value = 'login';
      info.value = '密码已重置，请用新密码登录';
      loading.value = false;
      return;
    }
    await initSyncForUser();
    router.replace(redirectTarget.value);
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

function switchMode(m) {
  if (loading.value) return;
  if (m === 'register' && registrationOpen.value !== true) {
    error.value = '注册暂未开放，请联系管理员创建账号';
    return;
  }
  mode.value = m;
  error.value = '';
  info.value = '';
  passwordVisible.value = false;
  if (m === 'login')
    loginMode.value = passwordOnly.value || !emailCodeAvailable.value ? 'password' : 'code';
}

const isCodeLogin = computed(() => mode.value === 'login' && loginMode.value === 'code');
const isPasswordField = computed(
  () => ['register', 'forgot'].includes(mode.value) || loginMode.value === 'password',
);
const showAgree = computed(
  () =>
    mode.value === 'register' ||
    mode.value === 'phone' ||
    isCodeLogin.value ||
    (mode.value === 'login' &&
      availableProviders.value.some((provider) => provider.id !== 'phone')),
);
const submitLabel = computed(() => {
  if (mode.value === 'login') return isCodeLogin.value ? '验证并登录' : '登录';
  if (mode.value === 'phone') return '验证手机号并登录';
  return mode.value === 'register' ? '创建账号' : '重置密码';
});
const heading = computed(
  () =>
    ({ login: '欢迎回来', register: '开始你的研时', forgot: '找回密码', phone: '手机号登录' })[
      mode.value
    ],
);
const description = computed(
  () =>
    ({
      login: '登录你的小天地，接着积累今天的进步。',
      register: '创建账号，把学习计划和每次进步留下来。',
      forgot: '使用账号邮箱验证身份，设置新的密码。',
      phone: '使用已开通的手机号渠道验证身份。',
    })[mode.value],
);
const codeLoginHint = computed(() =>
  registrationOpen.value === true
    ? '未注册邮箱验证后可创建账号。'
    : registrationOpen.value === false
      ? '仅限已有账号登录。'
      : '使用已有账号的邮箱接收验证码。',
);
// 协议弹层
const showLegal = ref(false);
const legal = ref(null);
const legalTab = ref('terms');
async function openLegal(tab) {
  legalTab.value = tab;
  if (!legal.value) {
    try {
      legal.value = await publicApi.legal();
    } catch {
      legal.value = {
        terms: '协议加载失败',
        privacy: '隐私政策加载失败',
        disclaimer: '免责声明加载失败',
      };
    }
  }
  showLegal.value = true;
}

async function loadPublicConfig() {
  configLoading.value = true;
  configError.value = false;
  try {
    const cfg = await publicApi.config();
    if (!alive) return;
    passwordOnly.value = cfg.auth_password_only !== false;
    emailCodeAvailable.value = !passwordOnly.value && cfg.email_code_available !== false;
    loginMode.value = emailCodeAvailable.value ? 'code' : 'password';
    if (Array.isArray(cfg.enabled_auth_channels)) channels.value = cfg.enabled_auth_channels;
    registrationOpen.value = !passwordOnly.value && cfg.registration_open === true;
    registrationSlots.value = Number.isInteger(cfg.registration_slots)
      ? cfg.registration_slots
      : null;
    if (registrationOpen.value && route.query.mode === 'register' && mode.value === 'login')
      mode.value = 'register';
    if (!registrationOpen.value && mode.value === 'register') switchMode('login');
  } catch {
    if (alive) {
      configError.value = true;
      registrationOpen.value = null;
      passwordOnly.value = true;
      loginMode.value = 'password';
    }
  } finally {
    if (alive) configLoading.value = false;
  }
}
onMounted(async () => {
  await loadPublicConfig();
  if (route.query.oauth_ticket) {
    await finishOAuth(String(route.query.oauth_ticket));
  }
});
</script>

<template>
  <div class="auth-page pixel-auth">
    <div class="auth-window">
      <div class="pixel-windowbar">
        <span><i aria-hidden="true"></i>研时 · 学习小屋</span
        ><span class="window-pixels" aria-hidden="true"><i></i><i></i><i></i></span>
      </div>
      <div class="auth-layout">
        <aside class="auth-intro" aria-label="关于研时">
          <div class="intro-brand" aria-label="研时">
            <span class="brand-logo"><PixelBookMark /></span>
            <span class="brand-name">研时<small>YOUR LITTLE STUDY CORNER</small></span>
          </div>
          <div class="intro-copy">
            <h2>小小的进步，<br /><span>也会闪闪发光。</span></h2>
            <p>收拾好书桌，和 AI、研友一起，<br />向理想再靠近一点点。</p>
          </div>
          <figure class="pixel-scene">
            <img
              v-if="!desktopArtUnavailable"
              :src="pixelArt"
              width="1448"
              height="1086"
              alt=""
              fetchpriority="high"
              @error="desktopArtUnavailable = true"
            />
            <div v-else class="pixel-scene-fallback" aria-hidden="true">
              <PixelBookMark /><span>今天，也一起慢慢进步。</span>
            </div>
            <figcaption><span aria-hidden="true">✦</span> 一页一题，慢慢靠近理想。</figcaption>
          </figure>
          <div class="feature-trail" aria-label="学习功能">
            <span v-for="feature in features" :key="feature.title"
              ><component :is="feature.icon" :size="13" />{{ feature.title }}</span
            >
          </div>
        </aside>

        <section class="auth-form-area" aria-labelledby="auth-heading">
          <div class="mobile-brand">
            <span class="brand-logo"><PixelBookMark /></span
            ><span>研时<small>你的像素学习小屋</small></span>
          </div>
          <div class="pixel-mobile-scene" aria-hidden="true">
            <img
              v-if="!mobileArtUnavailable"
              :src="pixelArt"
              width="1448"
              height="1086"
              alt=""
              @error="mobileArtUnavailable = true"
            /><span v-else>今天，也一起慢慢进步。</span>
          </div>
          <div class="auth-card">
            <header class="form-heading">
              <div class="form-eyebrow"><span aria-hidden="true">✦</span> 一起开启今天的学习</div>
              <h1 id="auth-heading">{{ heading }}</h1>
              <p>{{ description }}</p>
            </header>
            <p v-if="configLoading" class="admission-note" role="status">正在确认登录方式…</p>
            <div v-if="registrationOpen === true" class="tabs" aria-label="账号入口">
              <button
                type="button"
                :disabled="loading"
                :aria-pressed="mode === 'login' || mode === 'forgot' || mode === 'phone'"
                :class="{ active: mode !== 'register' }"
                @click="switchMode('login')"
              >
                登录
              </button>
              <button
                type="button"
                :disabled="loading"
                :aria-pressed="mode === 'register'"
                :class="{ active: mode === 'register' }"
                @click="switchMode('register')"
              >
                注册
              </button>
            </div>

            <div
              v-if="mode === 'login' && emailCodeAvailable"
              class="mode-switch"
              aria-label="登录方式"
            >
              <button
                type="button"
                :disabled="loading"
                :aria-pressed="loginMode === 'code'"
                :class="{ on: loginMode === 'code' }"
                @click="
                  loginMode = 'code';
                  error = '';
                  info = '';
                "
              >
                邮箱验证码
              </button>
              <button
                type="button"
                :disabled="loading"
                :aria-pressed="loginMode === 'password'"
                :class="{ on: loginMode === 'password' }"
                @click="
                  loginMode = 'password';
                  error = '';
                  info = '';
                "
              >
                账号密码
              </button>
            </div>

            <form class="form" :aria-busy="loading" @submit.prevent="submit">
              <template v-if="mode !== 'phone'">
                <label class="field" for="auth-email"
                  ><span>邮箱</span
                  ><input
                    id="auth-email"
                    v-model="form.email"
                    name="email"
                    type="email"
                    autocomplete="username"
                    autocapitalize="none"
                    spellcheck="false"
                    required
                    :disabled="loading"
                    placeholder="请输入账号邮箱"
                /></label>
                <template v-if="mode === 'register'">
                  <label class="field" for="auth-nickname"
                    ><span>昵称</span
                    ><input
                      id="auth-nickname"
                      v-model="form.nickname"
                      name="nickname"
                      autocomplete="nickname"
                      maxlength="40"
                      required
                      :disabled="loading"
                      placeholder="希望研友怎么称呼你"
                  /></label>
                  <label class="field" for="auth-invite"
                    ><span>注册 / VIP 邀请码 <small>如有请填写</small></span
                    ><input
                      id="auth-invite"
                      v-model="form.invite_code"
                      name="invite_code"
                      maxlength="16"
                      :disabled="loading"
                      placeholder="没有可留空"
                    /><small class="field-hint">小组邀请需要在登录后单独申请。</small></label
                  >
                </template>
                <div
                  v-if="isCodeLogin || mode === 'register' || mode === 'forgot'"
                  class="field code-field"
                >
                  <label for="auth-email-code">邮箱验证码</label>
                  <div class="code-row">
                    <input
                      id="auth-email-code"
                      v-model="form.code"
                      name="email_code"
                      inputmode="numeric"
                      autocomplete="one-time-code"
                      pattern="[0-9]{6}"
                      maxlength="6"
                      required
                      :disabled="loading"
                      placeholder="输入 6 位验证码"
                    />
                    <button
                      type="button"
                      class="ghost-btn"
                      :disabled="codeSending || countdown > 0 || loading"
                      @click="
                        sendCode(
                          mode === 'register' ? 'register' : mode === 'forgot' ? 'reset' : 'login',
                        )
                      "
                    >
                      {{
                        codeSending
                          ? '发送中…'
                          : countdown > 0
                            ? `${countdown} 秒后重发`
                            : '获取验证码'
                      }}
                    </button>
                  </div>
                </div>
                <div v-if="isPasswordField" class="field">
                  <div class="field-top">
                    <label for="auth-password">{{
                      mode === 'forgot' ? '新密码' : '密码'
                    }}</label><button
                      v-if="mode === 'login'"
                      type="button"
                      class="text-button"
                      :disabled="loading"
                      @click="switchMode('forgot')"
                    >
                      忘记密码？
                    </button>
                  </div>
                  <div class="password-row">
                    <input
                      id="auth-password"
                      v-model="form.password"
                      name="password"
                      :type="passwordVisible ? 'text' : 'password'"
                      :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
                      maxlength="64"
                      required
                      :disabled="loading"
                      :placeholder="mode === 'login' ? '请输入密码' : '8–64 位，包含字母和数字'"
                    /><button
                      type="button"
                      class="password-visibility"
                      :disabled="loading"
                      :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
                      :aria-pressed="passwordVisible"
                      @click="passwordVisible = !passwordVisible"
                    >
                      <component :is="passwordVisible ? EyeOff : Eye" :size="18" />
                    </button>
                  </div>
                </div>
                <label
                  v-if="mode === 'register' || mode === 'forgot'"
                  class="field"
                  for="auth-confirm"
                  ><span>确认密码</span
                  ><input
                    id="auth-confirm"
                    v-model="form.confirm"
                    name="confirm_password"
                    type="password"
                    autocomplete="new-password"
                    maxlength="64"
                    required
                    :disabled="loading"
                    placeholder="再输入一次密码"
                /></label>
              </template>
              <template v-else>
                <label class="field" for="auth-phone"
                  ><span>手机号</span
                  ><input
                    id="auth-phone"
                    v-model="form.phone"
                    name="phone"
                    type="tel"
                    autocomplete="tel-national"
                    inputmode="numeric"
                    pattern="1[3-9][0-9]{9}"
                    maxlength="11"
                    required
                    :disabled="loading"
                    placeholder="请输入 11 位手机号"
                /></label>
                <div class="field code-field">
                  <label for="auth-phone-code">短信验证码</label>
                  <div class="code-row">
                    <input
                      id="auth-phone-code"
                      v-model="form.code"
                      name="phone_code"
                      inputmode="numeric"
                      autocomplete="one-time-code"
                      pattern="[0-9]{6}"
                      maxlength="6"
                      required
                      :disabled="loading"
                      placeholder="输入 6 位验证码"
                    /><button
                      type="button"
                      class="ghost-btn"
                      :disabled="codeSending || countdown > 0 || loading"
                      @click="sendPhoneCode"
                    >
                      {{
                        codeSending
                          ? '发送中…'
                          : countdown > 0
                            ? `${countdown} 秒后重发`
                            : '获取验证码'
                      }}
                    </button>
                  </div>
                </div>
              </template>

              <div v-if="showAgree" class="agree">
                <input
                  id="auth-agree"
                  v-model="form.accepted"
                  type="checkbox"
                  :disabled="loading"
                />
                <div>
                  <label for="auth-agree">{{
                    mode === 'login' && !isCodeLogin
                      ? '使用第三方登录前请阅读并同意'
                      : '我已阅读并同意'
                  }}</label><button type="button" class="legal-link" @click="openLegal('terms')">
                    用户协议</button
                  >、<button type="button" class="legal-link" @click="openLegal('privacy')">
                    隐私政策</button
                  >及<button type="button" class="legal-link" @click="openLegal('disclaimer')">
                    免责声明
                  </button>
                </div>
              </div>
              <p v-if="error" class="error" role="alert">{{ error }}</p>
              <p v-if="info" class="info" role="status">{{ info }}</p>
              <button class="primary-btn" type="submit" :disabled="loading">
                {{ loading ? '请稍候…' : submitLabel }}<ArrowUpRight v-if="!loading" :size="18" />
              </button>
              <p v-if="isCodeLogin && registrationOpen !== false" class="login-hint">
                {{ codeLoginHint }}
              </p>
              <div v-if="mode === 'forgot' || mode === 'phone'" class="bottom-links">
                <button
                  type="button"
                  class="text-button"
                  :disabled="loading"
                  @click="switchMode('login')"
                >
                  <ArrowLeft :size="14" />返回邮箱登录
                </button>
              </div>
            </form>

            <p v-if="registrationOpen === false" class="admission-note">
              注册暂未开放，新账号请联系管理员创建。
            </p>
            <p v-else-if="mode === 'register' && registrationSlots !== null" class="admission-note">
              {{
                registrationSlots ? `剩余 ${registrationSlots} 个注册名额` : '本站注册名额已满。'
              }}
            </p>
            <p v-else-if="configError" class="admission-note">
              暂时无法确认注册状态。已有账号仍可登录。<button
                type="button"
                class="text-button"
                @click="loadPublicConfig"
              >
                重试
              </button>
            </p>
            <p v-if="passwordOnly" class="admission-note">内测期间仅支持账号密码登录。</p>
            <div v-if="passwordOnly" class="agree">
              <button type="button" class="legal-link" @click="openLegal('terms')">用户协议</button
              ><button type="button" class="legal-link" @click="openLegal('privacy')">
                隐私政策
              </button>
            </div>

            <div v-if="availableProviders.length && mode !== 'forgot'" class="third-party">
              <div class="tp-divider"><span>其他登录方式</span></div>
              <div class="tp-buttons">
                <button
                  v-for="provider in availableProviders"
                  :key="provider.id"
                  type="button"
                  class="tp-btn"
                  :disabled="loading"
                  @click="thirdParty(provider.id)"
                >
                  <span class="tp-ic" :style="{ color: provider.color }"
                    ><Github v-if="provider.id === 'github'" :size="17" /><svg
                      v-else-if="provider.id === 'wechat'"
                      class="brand-svg"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path :d="WECHAT_PATH" /></svg
                    ><svg
                      v-else-if="provider.id === 'qq'"
                      class="brand-svg"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path :d="QQ_PATH" /></svg
                    ><Smartphone v-else :size="17" /></span
                  ><span>{{ provider.label }}</span>
                </button>
              </div>
            </div>
          </div>
          <p class="pixel-private-note"><ShieldCheck :size="13" />AI 对话与密钥，仅本人可见</p>
        </section>
      </div>
    </div>
    <p class="pixel-page-note">不必一下子很厉害，每天前进一点就很好。</p>

    <div v-if="showLegal" class="modal-mask" @click.self="showLegal = false">
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="auth-legal-heading">
        <div class="modal-head">
          <h2 id="auth-legal-heading">
            {{
              legalTab === 'terms' ? '用户协议' : legalTab === 'privacy' ? '隐私政策' : '免责声明'
            }}
          </h2>
          <button type="button" @click="showLegal = false">关闭</button>
        </div>
        <pre class="modal-body">{{
          legalTab === 'terms'
            ? legal?.terms
            : legalTab === 'privacy'
              ? legal?.privacy
              : legal?.disclaimer
        }}</pre>
      </section>
    </div>
  </div>
</template>

<style src="../../assets/styles/pixel-auth.css" scoped></style>
