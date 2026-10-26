<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { groupApi } from '../api'
import { useAuthStore } from '../stores/auth'
import BlobImage from '../components/BlobImage.vue'
const router=useRouter(), auth=useAuthStore()
const members=ref([]), selected=ref(null), records=ref([]), error=ref(''), tab=ref('task')
let interval, generation=0,alive=true
async function load(){
  const seq=++generation, account=auth.user?.id
  if(document.visibilityState==='hidden'){records.value=[];return}
  try{
    const rows=await groupApi.members()
    if(!alive||seq!==generation||account!==auth.user?.id)return
    members.value=rows
    const member=rows.find(row=>row.id===selected.value)
    if(!member || (member.is_private_mode&&member.id!==account)){records.value=[];return}
    const all=[];let after=''
    for(;;){
      const data=await groupApi.learning(member.id,after);all.push(...data.items)
      if(!data.next)break
      after=data.next
    }
    if(alive&&seq===generation&&account===auth.user?.id){records.value=all;error.value=''}
  }catch(e){if(alive&&seq===generation){records.value=[];error.value=e.status===404?'该成员已开启隐私或共享权限已变化':e.message}}
}
watch(()=>auth.user?.id,()=>{generation++;records.value=[];members.value=[];selected.value=null})
function select(member){records.value=[];selected.value=member.id;load()}
const chosen=computed(()=>members.value.find(row=>row.id===selected.value))
const visible=computed(()=>records.value.filter(row=>row.type===tab.value))
const heat=computed(()=>{
 const result={};for(const row of records.value.filter(row=>row.type==='session'&&!row.conflict_flag&&!row.validation_issue))result[row.date]=(result[row.date]||0)+(row.actualSec||0)
 return Object.entries(result).sort(([a],[b])=>a.localeCompare(b))
})
onMounted(()=>{load();interval=setInterval(load,5000);document.addEventListener('visibilitychange',load)})
onBeforeUnmount(()=>{alive=false;generation++;records.value=[];clearInterval(interval);document.removeEventListener('visibilitychange',load)})
</script>
<template>
 <div class="page"><button class="btn btn-outline" @click="router.back()">返回</button><h2>受邀小组 · 学习互助</h2><router-link to="/group/admission">入组邀请与申请记录</router-link>
 <p>小组默认共享学习记录；隐私模式一键停止共享。这里只读查看，不会导入或修改对方的数据。</p>
 <button v-for="member in members" :key="member.id" class="btn btn-outline" @click="select(member)">{{member.nickname}} · {{member.statusText || '状态更新中'}}<small style="display:block">{{member.status==='private'?'位置已隐藏':member.roomName ? '房间：'+member.roomName : member.isOnline?'未在自习室':'未在线'}} </small></button>
 <p v-if="error">{{error}}</p>
 <template v-if="chosen">
 <h3>{{chosen.nickname}}</h3><p v-if="chosen.is_private_mode&&chosen.id!==auth.user.id">隐私中，学习数据不可见。</p>
 <template v-else>
 <div><button v-for="[key,label] in [['task','任务清单'],['mistake','错题集'],['session','番茄记录'],['stats','热力与时长']]" :key="key" class="btn btn-outline btn-sm" @click="tab=key">{{label}}</button></div>
 <div v-if="tab==='stats'" class="card mt16"><p>累计已同步时长：{{Math.round(heat.reduce((sum,entry)=>sum+entry[1],0)/60)}} 分钟</p><div class="heat"><span v-for="[day,sec] in heat" :key="day" :title="`${day} ${Math.round(sec/60)}分钟`" :style="{background:sec>3600?'#56836a':'#cce3d3'}">{{day.slice(5)}}<br>{{Math.round(sec/60)}}m</span></div></div>
 <div v-for="row in visible" :key="row.id" class="card mt16">
 <strong>{{row.title||row.content||row.learningContent||row.date||'学习记录'}}</strong>
 <p v-if="row.type==='task'">{{row.done?'已完成':'待完成'}} · {{row.dueDate}} · 预计{{row.estimatedMin||0}}分钟 · {{row.acceptCriteria}}</p>
 <template v-if="row.type==='mistake'"><p>{{row.chapter}} · 错因：{{row.reason}} · {{(row.tags||[]).join('、')}}</p><p>思路：{{row.idea}}</p><p>解析：{{row.analysis}}</p><BlobImage v-for="key in [...(row.images||[]),...(row.answerImages||[])]" :key="key" :src="key" class="picture" /></template>
 <p v-if="row.type==='session'">{{row.conflict_flag||row.validation_issue?'待本人处理，暂不计入统计':Math.round((row.actualSec||0)/60)+'分钟 · '+row.status}}</p>
 </div><p v-if="!visible.length&&tab!=='stats'">暂无已同步记录</p>
 </template></template></div>
</template>
<style scoped>p{font-size:13px;line-height:1.7}button{margin:4px}.picture{width:100%;max-height:360px;object-fit:contain}.heat{display:flex;flex-wrap:wrap;gap:4px}.heat span{padding:7px;border-radius:4px;font-size:10px}</style>
