<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Check } from 'lucide-vue-next'
import { resourceApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

const CATEGORIES = ['英语', '数学', '政治', '专业课', '其他']
const editingId = computed(() => route.params.id ? Number(route.params.id) : null)
const loading = ref(false)
const saving = ref(false)
const form = ref({
  title: '', url: '', code: '', category: '英语', intro: '',
})

async function load() {
  if (!editingId.value) return
  loading.value = true
  try {
    const row = await resourceApi.get(editingId.value)
    form.value = {
      title: row.title, url: row.url, code: row.code || '',
      category: row.category || '其他', intro: row.intro || '',
    }
  } catch (e) {
    toast(e.message)
    router.replace('/resources')
  } finally {
    loading.value = false
  }
}

async function save() {
  const f = form.value
  if (f.title.trim().length < 2) return toast('标题至少 2 个字')
  if (!/^https?:\/\//.test(f.url.trim())) return toast('链接需以 http:// 或 https:// 开头')
  saving.value = true
  try {
    const payload = {
      title: f.title.trim(), url: f.url.trim(), code: f.code.trim(),
      category: f.category, intro: f.intro.trim(),
    }
    if (editingId.value) {
      await resourceApi.update(editingId.value, payload)
      toast('已保存')
      router.replace(`/resources/${editingId.value}`)
    } else {
      const row = await resourceApi.create(payload)
      toast('已发布')
      router.replace(`/resources/${row.id}`)
    }
  } catch (e) {
    toast(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  if (!auth.isVip) {
    toast('仅 VIP 可发布资料')
    router.replace('/vip')
    return
  }
  load()
})
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">{{ editingId ? '编辑资料' : '发布资料' }}</div>
    </div>

    <div class="page">
      <div v-if="loading" class="empty">读取中…</div>
      <div v-else class="card">
        <label class="field">
          <span>标题</span>
          <input v-model="form.title" class="input" maxlength="80" placeholder="如：英语真题精析 2010-2026" />
        </label>
        <label class="field">
          <span>网盘链接</span>
          <input v-model="form.url" class="input" maxlength="600" placeholder="https://pan.quark.cn/s/..." />
        </label>
        <label class="field">
          <span>提取码（可空）</span>
          <input v-model="form.code" class="input" maxlength="20" placeholder="如 x7k2" />
        </label>
        <label class="field">
          <span>分类</span>
          <div class="cat-row">
            <button
              v-for="c in CATEGORIES"
              :key="c"
              class="cat-chip"
              :class="{ on: form.category === c }"
              @click="form.category = c"
            >{{ c }}</button>
          </div>
        </label>
        <label class="field">
          <span>简介（可空）</span>
          <textarea v-model="form.intro" class="ta" rows="3" maxlength="300" placeholder="简单说明资料内容与适用阶段"></textarea>
        </label>
        <button class="btn btn-primary btn-block mt16" :disabled="saving" @click="save">
          <Check :size="17" />{{ saving ? '保存中…' : editingId ? '保存修改' : '发布' }}
        </button>
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
.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 13px; }
.field > span { font-size: 12.5px; color: var(--sub); }
.cat-row { display: flex; flex-wrap: wrap; gap: 7px; }
.cat-chip {
  border: 1.5px solid var(--line);
  background: #fff;
  color: var(--sub);
  border-radius: 999px;
  padding: 7px 13px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
}
.cat-chip.on { border-color: transparent; background: var(--primary); color: #fff; }
.ta {
  width: 100%;
  box-sizing: border-box;
  border: 1.5px solid var(--line);
  border-radius: 12px;
  padding: 11px 13px;
  font-size: 14px;
  font-family: inherit;
  color: var(--ink);
  background: #fff;
  resize: vertical;
  outline: none;
}
.ta:focus { border-color: var(--primary); }
</style>
