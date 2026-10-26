<script setup>
import {ref,onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {groupAdmissionApi} from '../api'
const router=useRouter(),state=ref(null),code=ref(''),reason=ref(''),busy=ref(false),error=ref('')
async function load(){try{state.value=await groupAdmissionApi.mine()}catch(e){error.value=e.message}}
async function apply(){
 if(busy.value||!code.value.trim())return
 if(!confirm('审批通过后，小组成员将默认只读互看学习数据；你可随时开启隐私模式。申请不授予VIP或房间准入。确认申请？'))return
 busy.value=true;error.value=''
 try{await groupAdmissionApi.apply({code:code.value.trim(),reason:reason.value.trim()});code.value='';await load()}catch(e){error.value=e.message}finally{busy.value=false}
}
async function withdraw(row){if(!confirm('撤回这条待审申请？'))return;busy.value=true;try{await groupAdmissionApi.withdraw(row.id,row.revision);await load()}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load)
const labels={pending:'待审核',approved:'已通过',rejected:'未通过',cancelled:'已撤回'}
</script>
<template><div class="page"><button class="btn btn-outline" @click="router.back()">返回</button><h2>学习小组邀请与申请</h2>
<p>注册、VIP和房间准入相互独立。有效小组邀请仍需管理员审批，批准后默认共享学习数据，隐私模式可停止共享。</p>
<p v-if="error">{{error}}</p><template v-if="state"><div v-if="state.is_member" class="card">你已加入学习小组。<router-link to="/group">查看小组学习数据</router-link></div>
<div v-else class="card"><label>小组邀请码<input v-model="code" class="input" maxlength="128" autocomplete="off" /></label><label>申请说明<textarea v-model="reason" class="input" maxlength="300"></textarea></label><button class="btn btn-primary" :disabled="busy||!code.trim()||state.applications.some(a=>a.status==='pending')" @click="apply">提交入组申请</button></div>
<div v-for="row in state.applications" :key="row.id" class="card mt16"><strong>{{labels[row.status]||row.status}}</strong><p>{{row.reason}}</p><p v-if="row.remark">处理说明：{{row.remark}}</p><button v-if="row.status==='pending'" class="btn btn-outline" :disabled="busy" @click="withdraw(row)">撤回申请</button></div></template></div></template>
<style scoped>p{font-size:13px;line-height:1.7}label{display:block;margin:12px 0}</style>
