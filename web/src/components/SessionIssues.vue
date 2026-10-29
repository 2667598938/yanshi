<script setup>
import {ref,computed,watch,onBeforeUnmount} from 'vue'
import {useAuthStore} from '../stores/auth'
import {timerApi,syncApi} from '../api'
import {syncNow,waitForSync} from '../sync/engine'
import {uid} from '../db'
const auth=useAuthStore(),groups=ref([]),invalid=ref([]),abandoned=ref([]),busy=ref(false),error=ref(''),hidden=ref(false)
let alive=true,generation=0
const group=computed(()=>groups.value[0]||null)
const kept=computed(()=>group.value?group.value.items.filter(row=>!abandoned.value.includes(row.id)):[])
const keptIds=computed(()=>kept.value.map(row=>row.id))
const abandonedCount=computed(()=>group.value?group.value.items.length-kept.value.length:0)
const selectionValid=computed(()=>{
 if(!group.value||!kept.value.length)return false
 const sorted=[...kept.value].sort((a,b)=>a.started_at-b.started_at)
 return sorted.every((row,i)=>i===0||sorted[i-1].ended_at<=row.started_at)
})
const selectionHint=computed(()=>{
 if(!group.value)return ''
 if(!kept.value.length)return '至少保留一条记录。'
 if(!selectionValid.value)return '所选保留记录仍互相重叠，请再放弃其中一条。'
 return '可保留多条互不重叠的记录；只会删除你勾选放弃的记录。'
})
async function load(){
 if(!auth.isLoggedIn||busy.value)return
 const who=auth.user?.id,seq=generation
 try{const data=await timerApi.conflicts();if(alive&&seq===generation&&who===auth.user?.id){groups.value=data.groups;invalid.value=data.invalid;abandoned.value=[]}}
 catch{}
}
watch(()=>auth.user?.id,()=>{generation++;groups.value=[];invalid.value=[];abandoned.value=[];hidden.value=false;load()},{immediate:true})
const interval=setInterval(load,15000)
onBeforeUnmount(()=>{alive=false;generation++;clearInterval(interval)})
function fmt(ms){return new Date(ms).toLocaleString()}
async function resolve(){
 if(!group.value||busy.value||!selectionValid.value||!abandonedCount.value)return
 if(!confirm(`将删除勾选放弃的 ${abandonedCount.value} 条记录，保留 ${kept.value.length} 条互不重叠记录，并同步到所有设备。确认处理？`))return
 busy.value=true;error.value='';const owner=auth.user?.id
 try{await waitForSync();if(owner!==auth.user?.id)return;await timerApi.resolve({group_id:group.value.id,keep_ids:keptIds.value,versions:Object.fromEntries(group.value.items.map(i=>[i.id,i.revision])),confirmed:true});abandoned.value=[];await syncNow()}
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
 <template v-if="group"><h4>重叠时段 · {{groups.length}}组</h4>
 <p class="keep-hint">{{selectionHint}}</p>
 <label v-for="row in group.items" :key="row.id"><input v-model="abandoned" type="checkbox" :value="row.id" :disabled="busy" />放弃 {{fmt(row.started_at)}} — {{fmt(row.ended_at)}} · {{Math.round(row.seconds/60)}}分钟</label>
 <div class="actions"><button class="btn btn-primary" :disabled="busy||!selectionValid||!abandonedCount" @click="resolve">确认放弃 {{abandonedCount}} 条，保留 {{kept.length}} 条</button></div></template>
 <div v-for="row in invalid" :key="row.id"><p>{{row.id}}：{{row.reason}}</p><button class="btn btn-outline" :disabled="busy" @click="discard(row)">确认后删除此记录</button></div>
 <p v-if="error">{{error}}</p><button class="btn btn-outline" :disabled="busy" @click="hidden=true">稍后处理</button>
 </section></div>
</template>
<style scoped>.session-mask{position:fixed;inset:0;z-index:240;background:#0006;display:flex;align-items:flex-end;justify-content:center}.session-sheet{background:white;padding:20px;border-radius:18px 18px 0 0;max-width:720px;width:100%;max-height:80vh;overflow:auto}label{display:block;padding:12px 0;font-size: 14px}p{font-size: 14px;line-height:1.7}.keep-hint{color:#607488}.actions{position:sticky;bottom:0;background:white;padding:12px 0}.issues-tip{position:fixed;bottom:100px;right:12px;z-index:100;padding:10px;border-radius:8px}</style>
