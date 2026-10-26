<script setup>
import {ref,onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {adminApi} from '../api'
import {useToast} from '../composables/useToast'
const router=useRouter(),{toast}=useToast(),config=ref(null),logs=ref([]),diagnostics=ref(null),busy=ref(false),revision=ref(0)
const logAction=ref(''),logActor=ref(''),moreLogs=ref(true)
async function loadLogs(append=false){try{const rows=await adminApi.auditLogs(100,{action:logAction.value,...(logActor.value?{actor_id:Number(logActor.value)}:{}),...(append&&logs.value.length?{before_id:logs.value.at(-1).id}:{})});logs.value=append?[...logs.value,...rows]:rows;moreLogs.value=rows.length===100}catch(e){toast(e.message)}}
const batch=ref({count:5,remark:'',expires_days:7,vip_days:30}),codes=ref([])
async function load(){try{const [c,l,d]=await Promise.all([adminApi.config(),adminApi.auditLogs(100),adminApi.diagnostics()]);config.value=c.values;revision.value=c.revision;logs.value=l;diagnostics.value=d}catch(e){toast(e.message)}}
async function save(){busy.value=true;try{const result=await adminApi.updateConfig({...config.value,expected_revision:revision.value});revision.value=result.revision;toast('配置已保存')}catch(e){toast(e.message);if(e.status===409)toast('你的输入仍保留，请复制后重新载入比较')}finally{busy.value=false}}
async function generate(){busy.value=true;try{codes.value=await adminApi.batchInvites(batch.value);toast(`已生成${codes.value.length}个，可导出CSV`)}catch(e){toast(e.message)}finally{busy.value=false}}
function exportCodes(){
 const cell=v=>'"'+String(v??'').replace(/^[=+@-]/,"'"+'$&').replaceAll('"','""')+'"'
 const text=['邀请码,备注,VIP天数,到期日',...codes.value.map(row=>[row.code,row.remark,row.vip_days,row.expires_at].map(cell).join(','))].join('\r\n')
 const url=URL.createObjectURL(new Blob(['\uFEFF'+text],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='yanshi-invites.csv';a.click();URL.revokeObjectURL(url)
}
onMounted(load)
</script>
<template><div class="page"><button class="btn btn-outline" @click="router.back()">返回后台</button><h2>设置、日志与运行状态</h2>
<div v-if="config" class="card"><h3>站点配置 · 版本{{revision}}</h3><label>站名<input v-model="config.site_name" class="input" maxlength="60" /></label><label><input v-model="config.registration_open" type="checkbox" />开放注册（仍受部署账号上限约束）</label>
<label>新账号默认年份<input v-model.number="config.exam_year" type="number" class="input" /></label><label>默认日期<input v-model="config.exam_date" type="date" class="input" /></label><p>个人时间节点由成员自己维护，这里不会覆盖个人倒计时。</p><button class="btn btn-primary" :disabled="busy" @click="save">保存配置</button><button class="btn btn-outline" :disabled="busy" @click="load">重新载入</button></div>
<div class="card mt16"><h3>批量邀请码</h3><label>数量（1–100）<input v-model.number="batch.count" class="input" type="number" min="1" max="100" /></label><label>备注<input v-model="batch.remark" class="input" maxlength="200" /></label><label>邀请码有效天数<input v-model.number="batch.expires_days" class="input" type="number" min="1" max="365" /></label><label>兑换VIP天数（0为永久）<input v-model.number="batch.vip_days" class="input" type="number" min="0" max="3650" /></label><button class="btn btn-primary" :disabled="busy" @click="generate">生成</button><button class="btn btn-outline" :disabled="!codes.length" @click="exportCodes">导出本批CSV</button><p v-for="code in codes" :key="code.id">{{code.code}} · {{code.vip_days||'永久'}}天</p></div>
<div v-if="diagnostics" class="card mt16"><h3>运行诊断</h3><p>数据库：{{diagnostics.database_ready?'就绪':'未就绪'}} · 存储：{{diagnostics.image_storage}}</p><p>SMTP {{diagnostics.smtp_configured?'已配置':'未配置'}} · 七牛 {{diagnostics.qiniu_configured?'已配置':'未配置'}} · 账号上限 {{diagnostics.account_max_users}}</p><p>登录渠道 {{diagnostics.auth_channels?.join('、')}}。配置就绪不等于真实联调通过。</p></div>
<div class="card mt16"><h3>操作日志</h3><input v-model="logAction" class="input" placeholder="操作名称筛选" /><input v-model="logActor" class="input" type="number" placeholder="操作人ID（可选）" /><button class="btn btn-outline" @click="loadLogs(false)">查询</button><p v-for="row in logs" :key="row.id">{{row.created_at}} · 操作人{{row.actor_id??'历史未记录'}} · 目标{{row.user_id??'平台'}} · {{row.action}}<br><span class="detail">{{row.detail}}</span></p><button v-if="moreLogs && logs.length" class="btn btn-outline" @click="loadLogs(true)">加载更早日志</button></div></div></template>
<style scoped>label{display:block;margin:10px 0}p{font-size:13px;line-height:1.6}.detail{white-space:pre-wrap;overflow-wrap:anywhere}button{margin:4px}</style>
