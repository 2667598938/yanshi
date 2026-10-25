<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { schoolApi, attachmentApi, aiApi } from '../api'
import { useToast } from '../composables/useToast'
import BlobImage from '../components/BlobImage.vue'
import { db, uid } from '../db'
const router = useRouter()
const { toast } = useToast()
const rows = ref([]), selected = ref(''), busy = ref(false)
const form = ref({ key: '', name: '', short: '', logo_key: '', album_keys: [], info: {} })
function choose(key) {
  selected.value = key
  const row = rows.value.find(row => row.key === key)
  form.value = row ? JSON.parse(JSON.stringify(row)) : { key: '', name: '', short: '', logo_key: '', album_keys: [], info: {} }
  form.value.info = { city: '', motto: '', color: '#526484', ...form.value.info }
}
onMounted(async () => { try { rows.value = await schoolApi.list(); choose(rows.value[0]?.key || '') } catch (e) { toast(e.message) } })
async function upload(event, logo = false) {
  const files = Array.from(event.target.files || []); event.target.value = ''; busy.value = true
  try {
    for (const file of (logo ? files.slice(0, 1) : files)) {

      const result = await attachmentApi.uploadImage(file, 'school')
      if (logo) form.value.logo_key = result.key
      else form.value.album_keys.push(result.key)
    }
  } catch (e) { toast(e.message) }
  finally { busy.value = false }
}
async function save() {
  if (!form.value.name.trim()) return toast('请填写院校名')
  busy.value = true
  try {
    const body = { name: form.value.name.trim(), short: form.value.short, logo_key: form.value.logo_key,
      album_keys: form.value.album_keys, info: form.value.info, sort_order: Number(form.value.sort_order || 0) }
    const row = selected.value ? await schoolApi.update(selected.value, body)
      : await schoolApi.create({ ...body, key: form.value.key.trim() || uid('school-') })
    rows.value = [...rows.value.filter(r => r.key !== row.key), row]
    choose(row.key); toast('已保存，梦校墙重新进入后更新')
  } catch (e) { toast(e.message) }
  finally { busy.value = false }
}
async function removeSchool(){
 if(!selected.value||!confirm('删除自己的这所梦校？其他成员的梦校不受影响。'))return
 try{await schoolApi.remove(selected.value);rows.value=await schoolApi.list();choose(rows.value[0]?.key||'')}catch(e){toast(e.message)}
}
async function research(){
 if(!form.value.name.trim())return toast('请先填写学校名称')
 await db.kv.put({key:'ai:draft',value:{content:`请辅助整理${form.value.name}的学校简介和可供核实的官方公开信息。只提供文本建议，不自动修改院校；无法联网核实时请明确说明。`,images:[]}})
 router.push('/ai')
}
</script>
<template>
  <div class="page">
    <button class="btn btn-outline" @click="router.back()">返回</button><h2>我的梦校与校园相册</h2>
    <select class="input" :value="selected" :disabled="busy" @change="choose($event.target.value)">
      <option v-for="row in rows" :key="row.key" :value="row.key">{{ row.name }}</option><option value="">新增院校</option>
    </select>
    <div class="card mt16">
      <label>院校标识<input v-model="form.key" class="input" :disabled="!!selected || busy" maxlength="32" placeholder="英文字母、数字、下划线或连字符" /></label>
      <label>院校名<input v-model="form.name" class="input" maxlength="80" /></label>
      <button class="btn btn-outline" @click="research">AI辅助整理信息（手动核实录入）</button>
      <button v-if="selected" class="btn btn-outline" :disabled="busy" @click="removeSchool">删除本校</button>
      <label>简称<input v-model="form.short" class="input" maxlength="40" /></label>
      <label>简介<textarea v-model="form.info.description" class="input" maxlength="2000"></textarea></label>
      <label>排序（小值靠前）<input v-model.number="form.sort_order" type="number" class="input" /></label>
      <label>城市<input v-model="form.info.city" class="input" maxlength="40" /></label>
      <label>校训<input v-model="form.info.motto" class="input" maxlength="120" /></label>
      <label>主题色<input v-model="form.info.color" type="color" /></label>
      <label>上传校徽<input type="file" accept="image/jpeg,image/png,image/webp" :disabled="busy" @change="upload($event, true)" /></label>
      <BlobImage v-if="form.logo_key" class="preview" :src="form.logo_key" alt="校徽" />
      <button v-if="form.logo_key" class="btn btn-outline btn-sm" :disabled="busy" @click="form.logo_key = ''">使用默认校徽</button>
      <label>上传校园图<input type="file" accept="image/jpeg,image/png,image/webp" multiple :disabled="busy" @change="upload($event)" /></label>
      <div class="album"><div v-for="(key, i) in form.album_keys" :key="key + i"><BlobImage class="preview" :src="key" alt="校园图" />
        <button :disabled="busy" @click="form.album_keys.splice(i, 1)">移除</button></div></div>
      <button class="btn btn-primary btn-block mt16" :disabled="busy" @click="save">{{ busy ? '处理中…' : '保存院校' }}</button>
    </div>
  </div>
</template>
<style scoped>
label { display: block; margin: 12px 0; font-size: 13px; }
label .input { margin-top: 6px; }
.preview { width: 90px; height: 70px; object-fit: contain; }
.album { display: flex; gap: 8px; flex-wrap: wrap; }
.album button { display: block; }
</style>
