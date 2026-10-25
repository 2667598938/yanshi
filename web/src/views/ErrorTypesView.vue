<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Plus, Pencil, Trash2, Check, X } from 'lucide-vue-next'
import { errorTypeApi } from '../api'
import { useToast } from '../composables/useToast'

const router = useRouter()
const { toast } = useToast()

const presets = ref([])
const custom = ref([])
const newName = ref('')
const editingId = ref(null)
const editName = ref('')
const loading = ref(true)
const saving = ref(false)

async function load() {
  try {
    const data = await errorTypeApi.list()
    presets.value = data.presets || []
    custom.value = data.custom || []
  } catch (e) {
    toast(e.message)
  } finally {
    loading.value = false
  }
}

async function add() {
  const name = newName.value.trim()
  if (!name) return toast('请输入类型名称')
  saving.value = true
  try {
    const row = await errorTypeApi.create(name)
    custom.value.push(row)
    newName.value = ''
    toast('已添加')
  } catch (e) {
    toast(e.message)
  } finally {
    saving.value = false
  }
}

function startEdit(row) {
  editingId.value = row.id
  editName.value = row.name
}

async function saveEdit(row) {
  const name = editName.value.trim()
  if (!name) return toast('名称不能为空')
  try {
    const next = await errorTypeApi.rename(row.id, name)
    Object.assign(row, next)
    editingId.value = null
    toast('已重命名')
  } catch (e) {
    toast(e.message)
  }
}

async function remove(row) {
  if (!confirm(`删除错误类型「${row.name}」？历史错题仍保留原名称。`)) return
  try {
    await errorTypeApi.remove(row.id)
    custom.value = custom.value.filter((x) => x.id !== row.id)
    toast('已删除')
  } catch (e) {
    toast(e.message)
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">错误类型管理</div>
    </div>

    <div class="page">
      <div class="card">
        <div class="card-title">新增自定义类型</div>
        <div class="add-row">
          <input
            v-model="newName"
            class="input"
            maxlength="20"
            placeholder="如：单位换算"
            @keyup.enter="add"
          />
          <button class="btn btn-primary btn-sm" :disabled="saving" @click="add">
            <Plus :size="15" />添加
          </button>
        </div>
        <div class="hint">最多 30 个，名称不可重复；删除类型不会影响已记录的错题。</div>
      </div>

      <div class="section-title">系统预置</div>
      <div class="card">
        <div class="chips">
          <span v-for="p in presets" :key="p.id" class="chip-static">{{ p.name }}</span>
        </div>
      </div>

      <div class="section-title">我的自定义</div>
      <div v-if="loading" class="empty">读取中…</div>
      <div v-else-if="!custom.length" class="empty">还没有自定义类型</div>
      <div v-else class="card list">
        <div v-for="row in custom" :key="row.id" class="row">
          <template v-if="editingId === row.id">
            <input v-model="editName" class="input inline-input" maxlength="20" @keyup.enter="saveEdit(row)" />
            <button class="mini ok" @click="saveEdit(row)"><Check :size="15" /></button>
            <button class="mini" @click="editingId = null"><X :size="15" /></button>
          </template>
          <template v-else>
            <span class="row-name">{{ row.name }}</span>
            <button class="mini" @click="startEdit(row)"><Pencil :size="15" /></button>
            <button class="mini danger" @click="remove(row)"><Trash2 :size="15" /></button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back {
  border: none;
  background: #fff;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sub);
  cursor: pointer;
  box-shadow: var(--shadow-soft);
}
.card-title { font-size: 14px; font-weight: 700; margin-bottom: 10px; }
.add-row { display: flex; gap: 8px; }
.add-row .input { flex: 1; }
.hint { font-size: 11.5px; color: var(--faint); margin-top: 9px; line-height: 1.6; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip-static {
  background: #eef3f9;
  color: var(--sub);
  border-radius: 999px;
  padding: 6px 13px;
  font-size: 12.5px;
  font-weight: 600;
}
.list { padding: 2px 16px; }
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 0;
  border-bottom: 1px solid var(--line);
}
.row:last-child { border-bottom: none; }
.row-name { flex: 1; font-size: 14.5px; font-weight: 600; }
.inline-input { flex: 1; padding: 8px 10px; font-size: 14px; }
.mini {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--sub);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.mini.ok { color: var(--green); }
.mini.danger { color: var(--red); }
</style>
