<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTimeNodesStore } from '../stores/timeNodes'
import { useProfileStore } from '../stores/profile'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'
const router=useRouter(), nodes=useTimeNodesStore(), profile=useProfileStore(), auth=useAuthStore()
const {toast}=useToast()
const editing=ref(null), form=ref(null), motto=ref(auth.user?.custom_motto || '')
onMounted(()=>nodes.load(true))
function edit(row) {
  editing.value=row?.id || null
  form.value=row ? {...row.value} : {node_name:'',target_date:'',show_on_home:true,custom_msg:''}
}
async function save() {
  if (!form.value.node_name.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(form.value.target_date)) return toast('请填写名称和有效日期')
  try { await nodes.save(editing.value,{...form.value,node_name:form.value.node_name.trim()});form.value=null;toast('已保存，联网后同步至本人其他设备') }
  catch(e){toast(e.message)}
}
async function remove(row) {
  if (!confirm('删除这个时间节点？')) return
  try {await nodes.remove(row.id)} catch(e){toast(e.message)}
}
async function saveMotto(){try{await profile.save({custom_motto:motto.value});toast('个人寄语已保存')}catch(e){toast(e.message)}}
</script>
<template>
  <div class="page"><button class="btn btn-outline" @click="router.back()">返回</button><h2>我的时间节点</h2>
    <p>仅本人可见，不参与小组共享。预置日期是可修改、可删除的示例。</p>
    <button class="btn btn-primary" @click="edit(null)">新增节点</button>
    <div v-for="row in nodes.list" :key="row.id" class="card mt16">
      <strong>{{row.value.node_name}}</strong> · {{row.value.target_date}} · {{row.value.show_on_home?'首页显示':'仅此处保留'}}
      <p>{{row.value.custom_msg}}</p><button class="btn btn-outline btn-sm" @click="edit(row)">编辑</button><button class="btn btn-outline btn-sm" @click="remove(row)">删除</button>
    </div>
    <div v-if="form" class="card mt16">
      <label>名称<input v-model="form.node_name" class="input" maxlength="80" /></label>
      <label>日期<input v-model="form.target_date" type="date" class="input" /></label>
      <label><input v-model="form.show_on_home" type="checkbox" />在首页展示</label>
      <label>节点寄语<textarea v-model="form.custom_msg" class="input" maxlength="500"></textarea></label>
      <button class="btn btn-primary" @click="save">保存节点</button><button class="btn btn-outline" @click="form=null">取消</button>
    </div>
    <div class="card mt16"><label>我的专属长寄语<textarea v-model="motto" class="input" maxlength="500" placeholder="留空只显示随机文案或节点寄语"></textarea></label><button class="btn btn-primary" @click="saveMotto">保存寄语</button></div>
  </div>
</template>
<style scoped>label{display:block;margin:12px 0} p{font-size:13px;line-height:1.7}button{margin:4px}</style>
