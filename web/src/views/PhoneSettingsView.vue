<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authApi, publicApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'
const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()
const enabled = ref(false), loaded = ref(false), phone = ref(''), code = ref(''), busy = ref(false)
onMounted(async () => {
  try { enabled.value = (await publicApi.config()).enabled_auth_channels.includes('phone') }
  catch (e) { toast(e.message) }
  finally { loaded.value = true }
})
async function send() {
  busy.value = true
  try { await authApi.bindPhoneCode(phone.value.trim()); toast('验证码已发送，60秒后可再次发送') }
  catch (e) { toast(e.message) }
  finally { busy.value = false }
}
async function save() {
  busy.value = true
  try { auth.setUser(await authApi.bindPhone(phone.value.trim(), code.value)); code.value = ''; toast('手机号已绑定') }
  catch (e) { toast(e.message) }
  finally { busy.value = false }
}
</script>
<template>
  <div class="page">
    <button class="btn btn-outline" @click="router.back()">返回</button>
    <h2>绑定手机号</h2>
    <p>当前：{{ auth.user?.phone || '未绑定' }}</p>
    <p v-if="!loaded">读取中…</p>
    <p v-else-if="!enabled">手机号绑定暂未开放，当前请使用邮箱账号和密码登录。</p>
    <div v-else class="card">
      <label>新手机号<input v-model="phone" class="input mt8" inputmode="tel" maxlength="11" placeholder="11位手机号" /></label>
      <button class="btn btn-outline mt8" :disabled="busy" @click="send">发送验证码</button>
      <label class="mt16">验证码<input v-model="code" class="input mt8" inputmode="numeric" maxlength="6" /></label>
      <button class="btn btn-primary mt16" :disabled="busy" @click="save">确认绑定</button>
    </div>
  </div>
</template>
