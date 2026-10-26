<script setup>
import {ref,watch,onBeforeUnmount} from 'vue'
import {useAuthStore} from '../stores/auth'
import {timerApi,syncApi} from '../api'
import {syncNow,waitForSync} from '../sync/engine'
import {uid} from '../db'
const auth=useAuthStore(),groups=ref([]),invalid=ref([]),choice=ref(''),busy=ref(false),error=ref(''),hidden=ref(false)
let alive=true,generation=0
async function load(){
 if(!auth.isLoggedIn||busy.value)return
 const who=auth.user?.id,seq=generation
 try{const data=await timerApi.conflicts();if(alive&&seq===generation&&who===auth.user?.id){groups.value=data.groups;invalid.value=data.invalid}}
 catch{}
}
watch(()=>auth.user?.id,()=>{generation++;groups.value=[];invalid.value=[];choice.value='';hidden.value=false;load()},{immediate:true})
const interval=setInterval(load,15000)
onBeforeUnmount(()=>{alive=false;generation++;clearInterval(interval)})
function fmt(ms){return new Date(ms).toLocaleString()}
async function resolve(group){
 if(!choice.value||busy.value)return
 if(!confirm('仅保留所选记录，其余冲突记录将删除并同步到所有设备。确认处理？'))return
 busy.value=true;error.value='';const owner=auth.user?.id
 try{await waitForSync();if(owner!==auth.user?.id)return;await timerApi.resolve({group_id:group.id,keep_id:choice.value,versions:Object.fromEntries(group.items.map(i=>[i.id,i.revision])),confirmed:true});choice.value='';await syncNow()}
 catch(e){error.value=e.message}
 finally{busy.value=false;await load()}
}
async function discard(row){
 if(busy.value||!confirm('删除这条不符合校验的历史计时？将同步到所有设备。'))return
 busy.value=true;error.value='';const owner=auth.user?.id
 try{await waitForSync();if(owner!==auth.user?.id)return;await syncApi.commands(uid('discard-'),[{id:row.id,expectedRevision:row.revision,record:null}]);await syncNow()}
 catch(e){error.value=e.message}
 finally{busy.value=false;await load()}
}
</script>
<template>
 <button v-if="hidden&&(groups.length||invalid.length)" class="issues-tip" @click="hidden=false">有计时冲突待处理，不计入统计</button>
 <div v-if="!hidden&&(groups.length||invalid.length)" class="session-mask"><section class="session-sheet" role="dialog" aria-modal="true" aria-label="计时记录冲突处理">
 <h3>计时记录需要处理</h3><p>原记录已保留，冲突与无效记录不计入时长或番茄数。不会自动合并、删除或重复累加。</p>
 <template v-if="groups.length"><h4>重叠时段 · {{groups.length}}组</h4>
 <label v-for="row in groups[0].items" :key="row.id"><input v-model="choice" type="radio" :value="row.id" :disabled="busy" />保留 {{fmt(row.started_at)}} — {{fmt(row.ended_at)}} · {{Math.round(row.seconds/60)}}分钟</label>
 <div class="actions"><button class="btn btn-primary" :disabled="busy||!choice" @click="resolve(groups[0])">确认仅保留所选，删除其余</button></div></template>
 <div v-for="row in invalid" :key="row.id"><p>{{row.id}}：{{row.reason}}</p><button class="btn btn-outline" :disabled="busy" @click="discard(row)">确认后删除此记录</button></div>
 <p v-if="error">{{error}}</p><button class="btn btn-outline" :disabled="busy" @click="hidden=true">稍后处理</button>
 </section></div>
</template>
<style scoped>.session-mask{position:fixed;inset:0;z-index:240;background:#0006;display:flex;align-items:flex-end;justify-content:center}.session-sheet{background:white;padding:20px;border-radius:18px 18px 0 0;max-width:720px;width:100%;max-height:80vh;overflow:auto}label{display:block;padding:12px 0;font-size:13px}p{font-size:13px;line-height:1.7}.actions{position:sticky;bottom:0;background:white;padding:12px 0}.issues-tip{position:fixed;bottom:100px;right:12px;z-index:100;padding:10px;border-radius:8px}</style>
