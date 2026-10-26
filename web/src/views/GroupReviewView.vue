<script setup>
import {ref,onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {groupAdmissionApi} from '../api'
const router=useRouter(),rows=ref([]),invites=ref([]),fresh=ref(null),hours=ref(24),target=ref(''),busy=ref(false),error=ref('')
async function load(){try{const [r,i]=await Promise.all([groupAdmissionApi.queue(),groupAdmissionApi.invites()]);rows.value=r;invites.value=i}catch(e){error.value=e.message}}
async function create(){busy.value=true;error.value='';try{fresh.value=await groupAdmissionApi.createInvite({expires_hours:Number(hours.value),...(target.value?{target_user_id:Number(target.value)}:{})});await load()}catch(e){error.value=e.message}finally{busy.value=false}}
async function review(row,approve){
 const remark=approve?'':(prompt('驳回原因（必填）')||'').trim();if(!approve&&!remark)return
 if(!confirm(approve?'批准加入学习小组？将开启默认学习共享，不授予VIP或房间权限。':'确认驳回申请？'))return
 busy.value=true;error.value='';try{await groupAdmissionApi.review(row.id,{approve,remark,expected_revision:row.revision});await load()}catch(e){error.value=e.message;await load()}finally{busy.value=false}
}
async function revoke(row){if(!confirm('撤销这个邀请？相关待审申请也将驳回，已有成员关系不受影响。'))return;busy.value=true;try{await groupAdmissionApi.revoke(row.id);await load()}catch(e){error.value=e.message}finally{busy.value=false}}
onMounted(load)
</script>
<template><div class="page"><button class="btn btn-outline" @click="router.back()">返回后台</button><h2>小组邀请与审批</h2><p>仅本组管理员可操作。申请必须审核；审批只控制学习小组关系，不附带VIP和房间权限。</p><p v-if="error">{{error}}</p>
<div class="card"><label>有效小时（1–168）<input v-model.number="hours" type="number" class="input" min="1" max="168" /></label><label>指定接收账号ID（可选）<input v-model="target" type="number" class="input" /></label><button class="btn btn-primary" :disabled="busy" @click="create">生成独立小组邀请</button><template v-if="fresh"><p>邀请码仅本次显示，请自行复制；一份邀请绑定一个申请账号。</p><textarea readonly class="input" :value="fresh.code" @focus="$event.target.select()"></textarea><p>到期：{{fresh.expires_at}}</p></template></div>
<h3>待审核</h3><p v-if="!rows.length">暂无待审申请</p><div v-for="row in rows" :key="row.id" class="card mt16"><strong>{{row.user.nickname}} · {{row.user.email}}</strong><p>{{row.reason}}</p><button class="btn btn-primary" :disabled="busy" @click="review(row,true)">批准入组</button><button class="btn btn-outline" :disabled="busy" @click="review(row,false)">驳回</button></div>
<h3>最近邀请</h3><div v-for="row in invites" :key="row.id" class="card mt16"><p>#{{row.id}} · 到期{{row.expires_at}} · {{row.revoked_at?'已撤销':new Date(row.expires_at).getTime()<=Date.now()?'已过期':row.reserved_by?'已绑定申请账号':'尚未使用'}}</p><button v-if="!row.revoked_at" class="btn btn-outline" :disabled="busy" @click="revoke(row)">撤销邀请</button></div></div></template>
<style scoped>p{font-size:13px;line-height:1.7}label{display:block;margin:12px 0}button{margin:4px}</style>
