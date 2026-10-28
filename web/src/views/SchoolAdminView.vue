<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { schoolApi, attachmentApi, aiApi } from '../api'
import { useToast } from '../composables/useToast'
import { useProfileStore } from '../stores/profile'
import BlobImage from '../components/BlobImage.vue'
import { db, uid } from '../db'
import { toPlain } from '../utils/plain'
const router = useRouter()
const { toast } = useToast()
const profile = useProfileStore()
const rows = ref([]), selected = ref(''), busy = ref(false)
const logoInput = ref(null), albumInput = ref(null)
const form = ref({ key: '', name: '', short: '', logo_key: '', album_keys: [], info: {} })
function choose(key) {
  selected.value = key
  const row = rows.value.find(row => row.key === key)
  form.value = row ? JSON.parse(JSON.stringify(row)) : { key: '', name: '', short: '', logo_key: '', album_keys: [], info: {} }
  form.value.logo_key = form.value.logo_key || ''
  form.value.album_keys = form.value.album_keys || []
  form.value.info = { city: '', motto: '', color: '#526484', ...form.value.info }
}
function makeCover(i) {
  if (i <= 0 || i >= form.value.album_keys.length) return
  const [key] = form.value.album_keys.splice(i, 1)
  form.value.album_keys.unshift(key)
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
    if (logo) toast('校徽已上传，点击“保存院校”后生效')
    else if (files.length) toast(`已上传 ${files.length} 张校园图，点击“保存院校”后在首页生效`)
  } catch (e) { toast(e.message) }
  finally { busy.value = false }
}
async function save() {
  if (!form.value.name.trim()) { toast('请填写院校名'); return null }
  busy.value = true
  try {
    const body = { name: form.value.name.trim(), short: form.value.short, logo_key: form.value.logo_key,
      album_keys: form.value.album_keys, info: form.value.info, sort_order: Number(form.value.sort_order || 0) }
    const row = selected.value ? await schoolApi.update(selected.value, body)
      : await schoolApi.create({ ...body, key: form.value.key.trim() || uid('school-') })
    rows.value = [...rows.value.filter(r => r.key !== row.key), row]
    await db.kv.put({key:'schools:catalog',value:toPlain(rows.value)})
    choose(row.key); toast('已保存，返回首页即可看到新校徽与校园图轮播')
    return row
  } catch (e) { toast(e.message); return null }
  finally { busy.value = false }
}
async function saveAsDream() {
  const row = await save()
  if (!row) return
  try {
    await profile.save({ target_school: row.key })
    toast('已保存并设为今日梦校，返回首页即可看到')
  } catch (e) { toast(e.message) }
}
async function removeSchool(){
 if(!selected.value||!confirm('删除自己的这所梦校？其他成员的梦校不受影响。'))return
 try{await schoolApi.remove(selected.value);rows.value=await schoolApi.list();await db.kv.put({key:'schools:catalog',value:toPlain(rows.value)});choose(rows.value[0]?.key||'')}catch(e){toast(e.message)}
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
      <div class="upload-block">
        <div class="upload-label">校徽图片</div>
        <input ref="logoInput" type="file" accept="image/jpeg,image/png,image/webp" hidden :disabled="busy" @change="upload($event, true)" />
        <div class="upload-row">
          <button class="btn btn-outline btn-sm" :disabled="busy" @click="logoInput?.click()">{{ busy ? '上传中…' : (form.logo_key ? '更换校徽图片' : '选择校徽图片') }}</button>
          <button v-if="form.logo_key" class="btn btn-ghost btn-sm" :disabled="busy" @click="form.logo_key = ''">使用默认校徽</button>
        </div>
        <div v-if="form.logo_key" class="badge-preview">
          <BlobImage class="seal-preview" :src="form.logo_key" alt="当前校徽" />
          <span>当前校徽，保存后会在首页、自习室和梦校墙同步显示。</span>
        </div>
        <p v-else class="upload-hint">未上传时使用内置校徽或校名首字；上传后需点击“保存院校”。</p>
      </div>
      <div class="upload-block">
        <div class="upload-label">校园图（可多选）</div>
        <input ref="albumInput" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden :disabled="busy" @change="upload($event)" />
        <div class="upload-row">
          <button class="btn btn-outline btn-sm" :disabled="busy" @click="albumInput?.click()">{{ busy ? '上传中…' : '选择校园图' }}</button>
          <span class="upload-hint">一次可选多张；第一张作为今日主图，其余会在首页自动轮播。校徽请用上方入口，不要重复选进校园图。</span>
        </div>
        <div v-if="form.album_keys.length" class="album">
          <div v-for="(key, i) in form.album_keys" :key="key + i" class="album-item">
            <BlobImage class="preview" :src="key" alt="校园图" />
            <span v-if="i === 0" class="cover-tag">主图</span>
            <div class="album-actions">
              <button v-if="i > 0" class="btn btn-ghost btn-sm" :disabled="busy" @click="makeCover(i)">设为主图</button>
              <button class="btn btn-ghost btn-sm" :disabled="busy" @click="form.album_keys.splice(i, 1)">移除</button>
            </div>
          </div>
        </div>
        <p v-else class="upload-hint">还没有校园图；上传后可在今日首页看到校园图轮播。</p>
      </div>
      <p class="upload-hint save-hint">上传只是暂存，必须点击下方“保存院校”才会同步到首页。</p>
      <button class="btn btn-primary btn-block mt16" :disabled="busy" @click="save">{{ busy ? '处理中…' : '保存院校' }}</button>
      <button class="btn btn-outline btn-block mt8" :disabled="busy" @click="saveAsDream">保存并设为今日梦校</button>
    </div>
  </div>
</template>
<style scoped>
label { display: block; margin: 12px 0; font-size: 13px; }
label .input { margin-top: 6px; }
.upload-block { margin: 16px 0; padding-top: 12px; border-top: 1px dashed var(--line); }
.upload-label { font-size: 13px; font-weight: 600; }
.upload-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.upload-hint { font-size: 11px; color: var(--faint); line-height: 1.6; margin: 6px 0 0; }
.badge-preview { display: flex; align-items: center; gap: 10px; margin-top: 10px; font-size: 11px; color: var(--sub); line-height: 1.6; }
.seal-preview { width: 64px; height: 64px; border-radius: 50%; object-fit: cover; background: #fff; border: 1px solid var(--line); flex-shrink: 0; }
.album { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
.album-item { position: relative; display: flex; flex-direction: column; gap: 4px; width: 96px; }
.album-item .preview { width: 96px; height: 72px; object-fit: cover; border-radius: 10px; border: 1px solid var(--line); }
.cover-tag { position: absolute; top: 4px; left: 4px; padding: 2px 6px; border-radius: 999px; background: rgba(79, 70, 229, 0.9); color: #fff; font-size: 10px; font-weight: 700; }
.album-actions { display: flex; gap: 2px; flex-wrap: wrap; }
.album-actions .btn { padding: 2px 4px; font-size: 10px; min-height: 0; }
.save-hint { margin-top: 12px; }
</style>
