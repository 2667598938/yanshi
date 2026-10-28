<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, ArrowRight, ImagePlus, Send, X, Clock3 } from 'lucide-vue-next'
import { inspirationApi, attachmentApi } from '../api'
import { fmtDate } from '../utils/time'
import BlobImage from '../components/BlobImage.vue'
import { useToast } from '../composables/useToast'

const router = useRouter()
const { toast } = useToast()

const items = ref([])
const mine = ref([])
const index = ref(0)
const showSubmit = ref(false)
const draft = ref('')
const imageKey = ref('')
const uploading = ref(false)
const submitting = ref(false)
const fileInput = ref(null)
let timer = null

const DEFAULTS = [
  { id: 'd1', content: '大雪深埋，静候春来。', image_key: '' },
  { id: 'd2', content: '你现在的每一次早起，都是在给春天铺路。', image_key: '' },
  { id: 'd3', content: '别急，种子在土里也在长。', image_key: '' },
]

const slides = () => (items.value.length ? items.value : DEFAULTS)

function next() {
  index.value = (index.value + 1) % slides().length
}
function prev() {
  index.value = (index.value - 1 + slides().length) % slides().length
}

async function load() {
  try {
    const [pub, own] = await Promise.all([inspirationApi.list(), inspirationApi.mine()])
    items.value = pub
    mine.value = own
  } catch (e) {
    toast(e.message)
  }
}

async function pickImage(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const data = await attachmentApi.uploadImage(file, 'inspiration')
    imageKey.value = data.key
  } catch (err) {
    toast(err.message)
  } finally {
    uploading.value = false
    e.target.value = ''
  }
}

async function submit() {
  if (!draft.value.trim()) return toast('写一句话再投递')
  submitting.value = true
  try {
    await inspirationApi.submit({ content: draft.value.trim(), image_key: imageKey.value })
    toast('已提交，等待审核')
    showSubmit.value = false
    draft.value = ''
    imageKey.value = ''
    await load()
  } catch (e) {
    toast(e.message)
  } finally {
    submitting.value = false
  }
}

function statusCls(s) {
  return s === 'approved' ? 'ok' : ['rejected', 'withdrawn', 'taken_down'].includes(s) ? 'no' : 'wait'
}

async function withdraw(row) {
  if (!confirm('撤回后将从励志区和梦校弹幕池移除，且不能直接恢复。确认撤回？')) return
  try {
    await inspirationApi.withdraw(row.id)
    toast('已撤回')
    await load()
  } catch (e) {
    toast(e.message)
  }
}

onMounted(async () => {
  await load()
  timer = setInterval(next, 4500)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">励志区</div>
      <button class="submit-btn" @click="showSubmit = true">投稿</button>
    </div>

    <div class="page">
      <p class="contribution-note">每位成员都可以投稿；审核通过后，将进入励志区和梦校弹幕池。弹幕最多展示前80字。</p>
      <div class="hero">
        <div class="hero-top">
          <span class="hero-tag">大雪深埋</span>
          <span class="hero-count">{{ index + 1 }} / {{ slides().length }}</span>
        </div>
        <transition name="fade" mode="out-in">
          <div :key="slides()[index]?.id" class="slide">
            <BlobImage
              v-if="slides()[index]?.image_key"
              class="slide-img"
              :src="slides()[index].image_key"
              alt=""
            />
            <div class="slide-quote">「{{ slides()[index]?.content }}」</div>
          </div>
        </transition>
        <div class="hero-ctrl">
          <button @click="prev"><ArrowLeft :size="16" /></button>
          <div class="dots">
            <span
              v-for="(s, i) in slides()"
              :key="s.id"
              class="dot"
              :class="{ on: i === index }"
              @click="index = i"
            ></span>
          </div>
          <button @click="next"><ArrowRight :size="16" /></button>
        </div>
      </div>

      <div class="section-title">我的投稿</div>
      <div v-if="!mine.length" class="empty">还没有投过稿</div>
      <div v-else class="card mine-list">
        <div v-for="m in mine" :key="m.id" class="mine-row">
          <div class="mine-main">
            <div class="mine-text">{{ m.content }}</div>
            <div class="mine-time">{{ fmtDate(m.created_at) }}</div>
            <div v-if="m.review_note" class="mine-note">审核备注：{{ m.review_note }}</div>
          </div>
          <span class="status" :class="statusCls(m.status)">{{ m.status_label }}</span>
          <button v-if="['pending', 'approved'].includes(m.status)" class="mine-withdraw" @click="withdraw(m)">撤回</button>
        </div>
      </div>
    </div>

    <div v-if="showSubmit" class="mask" @click.self="showSubmit = false">
      <div class="sheet">
        <div class="sheet-title">投稿到励志区</div>
        <textarea
          v-model="draft"
          class="ta"
          rows="4"
          maxlength="200"
          placeholder="一句支撑你走到现在的话…"
        ></textarea>
        <div class="img-row">
          <BlobImage v-if="imageKey" class="preview" :src="imageKey" alt="" />
          <button class="img-pick" :disabled="uploading" @click="fileInput?.click()">
            <ImagePlus :size="18" />{{ uploading ? '上传中…' : imageKey ? '更换配图' : '添加配图（可选）' }}
          </button>
          <button v-if="imageKey" class="img-clear" @click="imageKey = ''"><X :size="15" /></button>
          <input ref="fileInput" type="file" accept="image/*" hidden @change="pickImage" />
        </div>
        <div class="sheet-foot">
          <span class="hint"><Clock3 :size="13" />审核通过后进入轮播</span>
          <button class="btn btn-primary btn-sm" :disabled="submitting" @click="submit">
            <Send :size="15" />{{ submitting ? '提交中…' : '提交' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back { border: none; background: #fff; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.submit-btn { margin-left: auto; border: none; border-radius: 10px; background: var(--primary); color: #fff; font-size: 12.5px; font-weight: 600; padding: 9px 14px; cursor: pointer; }
.hero { position: relative; border-radius: 18px; overflow: hidden; background: linear-gradient(150deg, #0f1f3a, #274a76); color: #eef4ff; min-height: 230px; display: flex; flex-direction: column; padding: 16px; box-sizing: border-box; }
.hero-top { display: flex; justify-content: space-between; font-size: 11px; color: rgba(238, 244, 255, .6); }
.hero-tag { letter-spacing: 2px; }
.slide { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 8px 0; }
.slide-img { max-width: 100%; max-height: 150px; border-radius: 12px; object-fit: cover; }
.slide-quote { font-size: 17px; line-height: 1.8; font-weight: 600; text-align: center; text-shadow: 0 1px 10px rgba(0,0,0,.25); }
.hero-ctrl { display: flex; align-items: center; gap: 10px; }
.hero-ctrl button { border: none; background: rgba(255,255,255,.12); color: #fff; width: 28px; height: 28px; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.dots { flex: 1; display: flex; justify-content: center; gap: 5px; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: rgba(255,255,255,.3); cursor: pointer; transition: .2s; }
.dot.on { width: 16px; border-radius: 999px; background: #fff; }
.fade-enter-active, .fade-leave-active { transition: opacity .3s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
.mine-list { padding: 4px 16px; }
.mine-row { display: flex; gap: 10px; padding: 11px 0; border-bottom: 1px solid var(--line); }
.mine-row:last-child { border-bottom: none; }
.mine-main { flex: 1; min-width: 0; }
.mine-text { font-size: 13.5px; line-height: 1.6; }
.mine-time { font-size: 10.5px; color: var(--faint); margin-top: 3px; }
.mine-note { font-size: 11px; color: var(--tomato-deep); margin-top: 4px; }
.status { height: 20px; padding: 0 8px; border-radius: 999px; font-size: 10.5px; font-weight: 700; display: inline-flex; align-items: center; flex-shrink: 0; }
.status.ok { background: #e7f7ee; color: #1f9d55; }
.status.no { background: #fdecec; color: var(--red); }
.status.wait { background: #fff3df; color: var(--accent-deep); }
.mine-withdraw { border: 1px solid var(--line); background: #fff; color: var(--sub); border-radius: 8px; font-size: 11px; padding: 3px 8px; cursor: pointer; flex-shrink: 0; align-self: center; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; margin-bottom: 12px; }
.ta { width: 100%; box-sizing: border-box; border: 1.5px solid var(--line); border-radius: 12px; padding: 12px 14px; font-size: 14px; font-family: inherit; background: #fafbfe; resize: vertical; outline: none; }
.ta:focus { border-color: var(--primary); }
.img-row { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.preview { width: 54px; height: 54px; border-radius: 10px; object-fit: cover; }
.img-pick { flex: 1; height: 42px; border: 1.5px dashed var(--line); border-radius: 10px; background: #fff; color: var(--sub); font-size: 12.5px; display: flex; align-items: center; justify-content: center; gap: 5px; cursor: pointer; }
.img-clear { border: none; background: #f1f4fa; color: var(--faint); width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.sheet-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 14px; }
.hint { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--faint); }
</style>

<style scoped>.contribution-note{font-size:13px;line-height:1.7;color:var(--sub);margin:0 0 16px}</style>
