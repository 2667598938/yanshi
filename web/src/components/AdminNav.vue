<script setup>
import { useRouter } from 'vue-router'
import { ref } from 'vue'
import { authApi } from '../api'
import { useAuthStore } from '../stores/auth'
const router = useRouter(), auth = useAuthStore()
const changing=ref(false),oldPassword=ref(''),newPassword=ref(''),confirmPassword=ref(''),error=ref(''),busy=ref(false)
const links = [
  ['/admin', '管理概览'], ['/admin/resources', '资料审核'],
  ['/admin/schools', '院校管理'], ['/admin/email-jobs', '邮件任务'], ['/admin/operations', '设置与日志'],
]
async function logout() { await auth.logout(); await router.replace('/login') }
async function changePassword(){
 if(busy.value)return
 if(newPassword.value!==confirmPassword.value){error.value='两次新密码不一致';return}
 busy.value=true;error.value=''
 try{const result=await authApi.changePassword(oldPassword.value,newPassword.value);await auth.acceptSession(result);oldPassword.value='';newPassword.value='';confirmPassword.value='';changing.value=false}
 catch(e){error.value=e.message||'密码修改失败'}finally{busy.value=false}
}
</script>
<template>
  <header class="admin-navigation">
    <router-link to="/admin" class="admin-brand">研时 · 管理后台</router-link>
    <nav aria-label="主管理员后台导航">
      <router-link v-for="[to,label] in links" :key="to" :to="to">{{ label }}</router-link>
    </nav>
    <button class="btn btn-outline btn-sm" @click="changing=true">修改密码</button>
    <button class="btn btn-danger btn-sm" @click="logout">退出登录</button>
    <div v-if="changing" class="admin-password-mask"><form class="card" @submit.prevent="changePassword"><h2>修改主管理员密码</h2><label>原密码<input v-model="oldPassword" type="password" autocomplete="current-password" required/></label><label>新密码<input v-model="newPassword" type="password" autocomplete="new-password" minlength="8" maxlength="64" required/></label><label>确认新密码<input v-model="confirmPassword" type="password" autocomplete="new-password" minlength="8" maxlength="64" required/></label><p v-if="error" role="alert">{{error}}</p><button class="btn btn-primary" :disabled="busy">保存</button><button type="button" class="btn btn-outline" @click="changing=false;oldPassword='';newPassword='';confirmPassword=''">取消</button></form></div>
  </header>
</template>
<style scoped>
.admin-navigation{padding:16px;background:var(--card);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.admin-password-mask{position:fixed;inset:0;background:#0007;z-index:500;display:grid;place-items:center;padding:16px}.admin-password-mask form{width:min(100%,440px)}.admin-password-mask h2{font-size:20px}.admin-password-mask label{display:grid;margin:12px 0;font-size:14px}.admin-password-mask input{padding:12px;border:1px solid var(--line);border-radius:8px;font-size:14px}.admin-password-mask button{margin-right:8px}
.admin-brand{font-weight:800;color:var(--primary);font-size: 20px;text-decoration:none}
nav{display:flex;gap:8px;flex:1;flex-wrap:wrap}nav a{padding:8px;color:var(--sub);text-decoration:none;border-radius:8px;font-size: 14px}nav a.router-link-exact-active{background:var(--primary);color:white}
@media(max-width:640px){nav{order:3;flex-basis:100%}.admin-navigation>.btn{margin-left:auto}}
</style>
