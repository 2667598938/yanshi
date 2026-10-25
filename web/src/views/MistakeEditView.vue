<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  ChevronLeft, Check, ImagePlus, X, NotebookPen,
} from 'lucide-vue-next'
import BlobImage from '../components/BlobImage.vue'
import { useMistakesStore } from '../stores/mistakes'
import { useSubjectsStore } from '../stores/subjects'
import { errorTypeApi } from '../api'
import { MISTAKE_REASONS, REVIEW_INTERVALS, intervalLabel } from '../data/subjects'
import { compressImage } from '../utils/image'
import { todayKey } from '../utils/date'
import { useToast } from '../composables/useToast'

const router = useRouter()
const route = useRoute()
const mistakes = useMistakesStore()
const subjects = useSubjectsStore()
const { toast } = useToast()

const QUICK_TAGS = ['数一', '408', '英语阅读', '政治', '竞赛', '真题', '高频']

const editingId = ref(null)
const fSubject = ref('')
const fChapter = ref('')
const fReason = ref('concept')
const tags = ref([])
const images = ref([])
const answerImages = ref([])
const fContent = ref('')
const fIdea = ref('')
const fAnalysis = ref('')
const fDate = ref(todayKey())
const sessionId = ref(null)
const tagInput = ref('')
const fileRef = ref(null)
const answerFileRef = ref(null)
const customReasons = ref([])
const saving = ref(false)

const reasonOptions = computed(() => {
  const rows = MISTAKE_REASONS.map((r) => ({ value: r.id, name: r.name }))
  for (const r of customReasons.value) rows.push({ value: r.name, name: r.name })
  if (fReason.value && !rows.some((r) => r.value === fReason.value)) {
    rows.push({ value: fReason.value, name: fReason.value })
  }
  return rows
})

onMounted(async () => {
  try {
    const data = await errorTypeApi.list()
    customReasons.value = data.custom || []
  } catch {
    customReasons.value = []
  }
})

onMounted(() => {
  const q = route.query
  if (q.id) {
    const m = mistakes.list.find((x) => x.id === q.id)
    if (m) {
      editingId.value = m.id
      fSubject.value = m.subjectId
      fChapter.value = m.chapter
      fReason.value = m.reason
      tags.value = [...(m.tags || [])]
      images.value = [...(m.images || [])]
      answerImages.value = [...(m.answerImages || [])]
      fContent.value = m.content
      fIdea.value = m.idea || ''
      fAnalysis.value = m.analysis || ''
      fDate.value = m.sourceDate
      sessionId.value = m.sessionId
    }
  } else {
    fSubject.value = q.subjectId || subjects.active[0]?.id || 'other'
    fDate.value = q.date || todayKey()
    sessionId.value = q.sessionId || null
  }
})

function addTag(t) {
  const v = (t || '').trim()
  if (!v || tags.value.includes(v)) return
  if (tags.value.length >= 8) {
    toast('最多 8 个标签')
    return
  }
  tags.value.push(v)
  tagInput.value = ''
}
function removeTag(t) {
  tags.value = tags.value.filter((x) => x !== t)
}

async function pickInto(list, e) {
  const files = Array.from(e.target.files || [])
  for (const f of files) {
    if (list.value.length >= 9) {
      toast('最多 9 张图')
      break
    }
    try {
      const blob = await compressImage(f, 1280, 0.82)
      list.value.push(blob)
    } catch {
      toast('图片读取失败')
    }
  }
  e.target.value = ''
}
function onPick(e) {
  return pickInto(images, e)
}
function onPickAnswer(e) {
  return pickInto(answerImages, e)
}
function removeImg(i) {
  images.value.splice(i, 1)
}
function removeAnswerImg(i) {
  answerImages.value.splice(i, 1)
}

async function save() {
  if (saving.value) return
  if (!fContent.value.trim() && !images.value.length) {
    toast('至少写点题干或上传一张题目截图')
    return
  }
  saving.value = true
  try {
    // 先保存本机图片与记录，补传由同步队列完成，不让网络请求阻塞收录。
    const payload = {
      subjectId: fSubject.value,
      chapter: fChapter.value.trim(),
      reason: fReason.value,
      tags: tags.value,
      content: fContent.value.trim(),
      idea: fIdea.value.trim(),
      analysis: fAnalysis.value.trim(),
      images: images.value,
      answerImages: answerImages.value,
      sourceDate: fDate.value,
    }
    if (editingId.value) {
      await mistakes.update(editingId.value, payload)
      toast('已更新错题')
    } else {
      payload.sessionId = sessionId.value
      await mistakes.add(payload)
      toast(`已收录，将在 ${intervalLabel(REVIEW_INTERVALS[0])}后提醒复习`)
    }
    await router.push('/mistakes')
  } catch (error) {
    console.error('错题保存失败', error)
    toast('保存失败，请重试；填写的内容仍保留在当前页')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="nav">
    <button class="back-btn" @click="router.back()"><ChevronLeft :size="20" /></button>
    <div>
      <div class="nav-title">{{ editingId ? '编辑错题' : '记一道错题' }}</div>
      <div class="nav-sub">截图 + 错因 + 标签，按艾宾浩斯提醒</div>
    </div>
  </div>

  <div class="page">
    <div class="card">
      <div class="f-label">所属科目</div>
      <select v-model="fSubject" class="select">
        <option v-for="s in subjects.active" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>

      <div class="f-label">章节 / 知识点</div>
      <input v-model="fChapter" class="input" placeholder="如：极限与连续、进程调度" maxlength="30" />

      <div class="f-label">错误原因</div>
      <div class="pill-row">
        <button
          v-for="r in reasonOptions"
          :key="r.value"
          class="pill"
          :class="{ active: fReason === r.value }"
          :style="fReason === r.value ? { background: 'var(--tomato)' } : {}"
          @click="fReason = r.value"
        >{{ r.name }}</button>
      </div>
    </div>

    <div class="card">
      <div class="f-label">标签</div>
      <div class="tag-box">
        <span v-for="t in tags" :key="t" class="tag on">
          {{ t }}<button @click="removeTag(t)"><X :size="12" /></button>
        </span>
        <input
          v-model="tagInput"
          class="tag-input"
          placeholder="回车添加"
          @keyup.enter="addTag(tagInput)"
        />
      </div>
      <div class="pill-row quick">
        <button
          v-for="t in QUICK_TAGS"
          :key="t"
          class="pill"
          :class="{ used: tags.includes(t) }"
          @click="addTag(t)"
        >{{ t }}</button>
      </div>
    </div>

    <div class="card">
      <div class="f-label">题目图（最多 9 张）</div>
      <div class="img-grid">
        <div v-for="(b, i) in images" :key="i" class="img-cell">
          <BlobImage :blob="typeof b === 'string' ? null : b" :src="typeof b === 'string' ? b : ''" />
          <button class="img-del" @click="removeImg(i)"><X :size="14" /></button>
        </div>
        <button class="img-add" @click="fileRef.click()">
          <ImagePlus :size="24" />
          <span>加题目图</span>
        </button>
      </div>
      <input
        ref="fileRef"
        type="file"
        accept="image/*"
        multiple
        hidden
        @change="onPick"
      />
    </div>

    <div class="card">
      <div class="f-label">解析图（最多 9 张）</div>
      <div class="img-grid">
        <div v-for="(b, i) in answerImages" :key="i" class="img-cell">
          <BlobImage :blob="typeof b === 'string' ? null : b" :src="typeof b === 'string' ? b : ''" />
          <button class="img-del" @click="removeAnswerImg(i)"><X :size="14" /></button>
        </div>
        <button class="img-add" @click="answerFileRef.click()">
          <ImagePlus :size="24" />
          <span>加解析图</span>
        </button>
      </div>
      <input
        ref="answerFileRef"
        type="file"
        accept="image/*"
        multiple
        hidden
        @change="onPickAnswer"
      />
    </div>

    <div class="card">
      <div class="f-label">题干摘要 / 笔记（可选）</div>
      <textarea
        v-model="fContent"
        class="big-input"
        rows="3"
        placeholder="题目、正确思路、自己卡在哪……"
      ></textarea>

      <div class="f-label">主要思路</div>
      <textarea
        v-model="fIdea"
        class="big-input"
        rows="2"
        placeholder="这道题的关键切入点、为什么这么做"
      ></textarea>

      <div class="f-label">答案解析</div>
      <textarea
        v-model="fAnalysis"
        class="big-input"
        rows="3"
        placeholder="标准答案或自己的解析，便于复习时对照"
      ></textarea>

      <div class="f-label">归到哪一天</div>
      <input v-model="fDate" type="date" class="input" />
    </div>

    <button class="btn btn-tomato btn-block mt12" :disabled="saving" :aria-busy="saving" @click="save">
      <NotebookPen :size="18" />{{ saving ? '保存中…' : editingId ? '保存修改' : '收录错题' }}
    </button>
  </div>
</template>

<style scoped>
.back-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.f-label {
  font-size: 13px;
  font-weight: 700;
  margin: 12px 0 8px;
}
.f-label:first-child {
  margin-top: 0;
}
.tag-box {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  border: 1.5px solid var(--line);
  border-radius: 12px;
  padding: 9px;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  font-weight: 600;
  padding: 4px 6px 4px 10px;
  border-radius: 999px;
  background: #f1eefd;
  color: var(--purple);
}
.tag button {
  border: none;
  background: none;
  color: var(--purple);
  cursor: pointer;
  display: flex;
  align-items: center;
}
.tag-input {
  flex: 1;
  min-width: 90px;
  border: none;
  outline: none;
  font-size: 13px;
  font-family: inherit;
  padding: 4px;
}
.pill-row.quick {
  margin-top: 10px;
}
.pill.used {
  opacity: 0.45;
}
.img-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 9px;
}
.img-cell {
  position: relative;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  background: #f1f5f9;
}
.img-cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.img-del {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  border: none;
  background: rgba(15, 23, 42, 0.55);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.img-add {
  aspect-ratio: 1;
  border: 1.5px dashed var(--faint);
  border-radius: 12px;
  background: #f8fafc;
  color: var(--faint);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: 12px;
  cursor: pointer;
}
.big-input {
  width: 100%;
  border: 1.5px solid var(--line);
  border-radius: 12px;
  padding: 11px 14px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  background: #f8fafc;
}
.big-input:focus {
  border-color: var(--primary);
}
</style>
