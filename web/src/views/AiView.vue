<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles, MessageCircle, Send, Plus, History, Sigma, Cpu,
  PenLine, CalendarClock, RotateCcw, Settings2, Crown, ChevronRight, Square, ArrowDown,
  Copy, RefreshCw, X, Moon, Sun, Monitor, ArrowLeft,
} from 'lucide-vue-next'
import { aiApi, attachmentApi } from '../api'
import { renderMarkdown } from '../utils/markdown'
import { syncNow, waitForSync } from '../sync/engine'
import { db, uid, activeAccountId } from '../db'
import BlobImage from '../components/BlobImage.vue'
import CopyFallback from '../components/CopyFallback.vue'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'
import { useClipboard } from '../composables/useClipboard'

const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()
const { copy: copyToClipboard, manualCopy } = useClipboard(toast)

const enabled = ref(true)
const keyReady = ref(false)
const access = ref(true)
const scenes = ref([
  { key: 'kaoyan', label: '考研答疑', icon: Cpu },
  { key: 'general', label: '通用问答', icon: MessageCircle },
  { key: 'essay', label: '作文批改', icon: PenLine },
  { key: 'plan', label: '计划生成', icon: CalendarClock },
  { key: 'review', label: '学习复盘', icon: RotateCcw },
])
const scene = ref('kaoyan')
const conversationId = ref(null)
const conversationTitle = ref('')
const messages = ref([])
const input = ref('')
const sending = ref(false)
const showHistory = ref(false)
const historyList = ref([])
const historyLoading = ref(false)
const historyError = ref('')
const historyFetched = ref(false)
let historyGeneration = 0
const scrollEl = ref(null)
const fileInput = ref(null)
const attachments = ref([])
const features = ref({ v1_readonly: true, vision: false, tools: false, search: false, model_vision: false, model_tools: false })
const taskPreview = ref(null)
const importing = ref(false)
const taskSelection = ref([])
const useTools = ref(false)
const useSearch = ref(false)
let controller
let alive = true
let conversationGeneration = 0
const loadingConversation = ref(false)

// ===== Neural Expressive 状态机 =====
// idle：进入页面 / 新建对话 / 停止生成 / 生成完成 900ms 后且输入为空
// listening：输入框获得焦点或输入非空；光谱指针移到输入框
// thinking：点发送或“模拟生成”后、第一个流式片段到达前；四星芒形变 + 涟漪 + 粒子
// delivering：收到首个 delta 起直到 done/error；回答卡 ombre 洗扫 + 流式文字
const visualState = ref('idle')
const receiving = ref(false)
const aiWrapEl = ref(null)
const focusX = ref('50%')
const focusY = ref('62%')
const savedTheme = (() => {
  try { return localStorage.getItem('yanshi:ai-theme') || 'dark' } catch { return 'dark' }
})()
const theme = ref(['dark', 'light', 'auto'].includes(savedTheme) ? savedTheme : 'dark')
let idleTimer = null
let focusFrame = 0
const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
const stateLabel = computed(() => ({
  idle: '待提问', listening: '正在聆听', thinking: '正在思考', delivering: '正在输出',
}[visualState.value] || '待提问'))
const themeLabel = computed(() => ({
  dark: '深色', light: '浅色', auto: '跟随系统',
}[theme.value] || '深色'))
const themeIcon = computed(() => theme.value === 'dark' ? Moon : theme.value === 'light' ? Sun : Monitor)
function syncAppChrome() {
  const dark = theme.value === 'dark'
    || (theme.value === 'auto' && !(window.matchMedia?.('(prefers-color-scheme: light)').matches))
  document.documentElement.classList.toggle('ai-neural-dark', !!dark)
}
watch(theme, syncAppChrome, { immediate: true })
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了，先解决哪一道题？'
  if (h < 12) return '早上好，今天想先解决什么？'
  if (h < 18) return '下午好，今天想先解决什么？'
  return '晚上好，今天想先解决什么？'
})

function raf(cb) {
  return typeof requestAnimationFrame === 'function' ? requestAnimationFrame(cb) : setTimeout(cb, 0)
}
function caf(id) {
  if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(id)
  else if (id) clearTimeout(id)
}
function updateFocusPoint() {
  caf(focusFrame)
  focusFrame = raf(() => {
    const wrap = aiWrapEl.value
    if (!wrap) return
    const box = wrap.getBoundingClientRect()
    if (!box.width || !box.height) return
    let el = null
    if (visualState.value === 'thinking') el = wrap.querySelector('.thinking-row')
    else if (visualState.value === 'delivering') el = wrap.querySelector('.chat-msg.assistant:last-of-type .bubble')
    if (!el) el = wrap.querySelector('.composer')
    if (!el) return
    const r = el.getBoundingClientRect()
    const x = ((r.left + r.width / 2 - box.left) / box.width) * 100
    const y = ((r.top + r.height / 2 - box.top) / box.height) * 100
    focusX.value = `${Math.max(8, Math.min(92, x)).toFixed(1)}%`
    focusY.value = `${Math.max(10, Math.min(90, y)).toFixed(1)}%`
  })
}
function scheduleFocus() { updateFocusPoint() }
function onComposerFocus() {
  if (sending.value) return
  visualState.value = 'listening'
  updateFocusPoint()
}
function onComposerBlur() {
  if (sending.value) return
  visualState.value = input.value.trim() ? 'listening' : 'idle'
  updateFocusPoint()
}
function cycleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : theme.value === 'light' ? 'auto' : 'dark'
  try { localStorage.setItem('yanshi:ai-theme', theme.value) } catch { /* 隐身模式忽略 */ }
  updateFocusPoint()
}
function scheduleIdle() {
  clearTimeout(idleTimer)
  idleTimer = setTimeout(() => {
    if (!alive || sending.value) return
    visualState.value = input.value.trim() ? 'listening' : 'idle'
    updateFocusPoint()
  }, 900)
}
onBeforeUnmount(() => {
  alive = false
  conversationGeneration++
  clearTimeout(draftTimer)
  clearTimeout(idleTimer)
  caf(focusFrame)
  window.removeEventListener('resize', scheduleFocus)
  window.removeEventListener('resize', loadDesktopHistory)
  document.documentElement.classList.remove('ai-neural-dark')
  controller?.abort()
})

async function uploadRow(row) {
  if (row.key || row.uploading) return
  row.uploading = true; row.error = ''
  try {
    const suffix = { 'image/png': 'png', 'image/webp': 'webp', 'image/jpeg': 'jpg' }[row.blob.type] || 'jpg'
    const file = row.blob instanceof File ? row.blob : new File([row.blob], `ai-input.${suffix}`, { type: row.blob.type || 'image/jpeg' })
    const result = await attachmentApi.uploadImage(file, 'ai')
    row.key = result.key
  } catch (e) { row.error = e.message || '图片上传失败，可重试' }
  finally { row.uploading = false }
}
async function pickImages(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  for (const file of files) {
    if (attachments.value.length >= 4) { toast('每次最多4张图片'); break }
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      toast('请使用5MB以内的JPEG、PNG或WebP图片'); continue
    }
    attachments.value.push({ id: uid(), key: '', blob: file, uploading: false, error: '' })
  }
  for (const row of attachments.value) if (!row.key) await uploadRow(row)
}

const welcome = computed(
  () => ({
    general: '随便聊聊，疏解焦虑、问方法都可以。',
    kaoyan: '问数一、408、英语、政治的知识点和解题思路，我尽量讲明白。',
    essay: '把英语作文贴进来，我从语法、结构、得分点给你批改。',
    plan: '告诉我你的目标和剩余时间，帮你排复习计划。',
    review: '说说今天学了什么，帮你复盘效率和问题。',
  }[scene.value] || '')
)

// 空态起步问题：点一下填入输入框，降低"不知道问什么"的门槛
const suggestions = computed(() => ({
  kaoyan: ['等价无穷小什么时候不能直接替换？', '408 进程调度几种算法怎么区分？', '英语阅读定位题总错，怎么练？'],
  general: ['最近总焦虑学不进去，怎么调整？', '每天学多久比较合理？'],
  essay: ['帮我批改一篇英语大作文', '作文开头怎么写更稳？'],
  plan: ['我 10 月才开始复习，帮我排个计划', '帮我安排这周的 408 复习'],
  review: ['帮我复盘今天的学习', '最近效率下降，帮我找原因'],
}[scene.value] || []))

const composerEl = ref(null)
function useSuggestion(text) {
  input.value = text
  nextTick(() => composerEl.value?.focus())
}

async function scrollBottom() {
  await nextTick()
  if (scrollEl.value) {
    scrollEl.value.scrollTop = scrollEl.value.scrollHeight
    atBottom.value = true
  }
}

// 是否停留在对话底部：流式输出只在底部时自动跟随，向上翻看不被抢滚动
const atBottom = ref(true)
function onScroll() {
  const el = scrollEl.value
  if (!el) return
  atBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 64
  if (visualState.value === 'delivering') scheduleFocus()
}
// 停止真实模型生成，保留已输出内容。
function stopGeneration() {
  controller?.abort()
}
// 重试：移除失败回复与对应问题，用同一问题重新发送
async function retry(m) {
  if (sending.value) return
  const index = messages.value.indexOf(m)
  const prev = messages.value[index - 1]
  if (index < 0 || !prev || prev.role !== 'user') return toast('未找到对应的问题')
  messages.value.splice(index - 1, 2)
  input.value = prev.content
  attachments.value = (prev.image_keys || []).map((key) => ({ id: uid(), key, blob: null, uploading: false, error: '' }))
  await send()
}

// 读取配置失败与"没有权限/没配Key"分开，前者给重试而不是误导去配 Key
const configError = ref('')
const configLoading = ref(false)
const blocked = computed(() => {
  if (configError.value) return 'error'
  if (!access.value) return 'vip'
  if (!keyReady.value) return 'key'
  return ''
})

async function loadConfig() {
  if (configLoading.value) return
  configLoading.value = true
  configError.value = ''
  try {
    const cfg = await aiApi.enabled()
    enabled.value = cfg.enabled
    features.value = cfg
    keyReady.value = !!cfg.enabled
    access.value = cfg.access !== false
    if (access.value) {
      const k = await aiApi.key()
      keyReady.value = !!k.configured || !!cfg.enabled
    }
    const sc = await aiApi.scenes()
    if (Array.isArray(sc) && sc.length) {
      const iconMap = {
        general: MessageCircle, kaoyan: Cpu, essay: PenLine,
        plan: CalendarClock, review: RotateCcw,
      }
      scenes.value = sc.map((x) => ({ ...x, icon: iconMap[x.key] || Sparkles }))
    }
  } catch (e) {
    configError.value = e.message || 'AI 配置读取失败，请检查网络后重试'
  } finally {
    configLoading.value = false
  }
}

async function send() {
  const content = input.value.trim() || (attachments.value.length ? '请分析这些题目图片，并讲解思路与易错点。' : '')
  if (!content || sending.value || loadingConversation.value || blocked.value) return
  if (!enabled.value) return toast('AI未启用，请先配置Key')
  if (attachments.value.some((row) => !row.key)) return toast('有图片尚未上传成功，请重试或移除该图片')
  const selected = [...attachments.value]
  const imageKeys = selected.map((row) => row.key)
  input.value = ''; attachments.value = []
  // thinking：发送后到首个流式片段到达前
  visualState.value = 'thinking'
  receiving.value = false
  clearTimeout(idleTimer)
  messages.value.push({ role: 'user', content, image_keys: imageKeys })
  sending.value = true
  const reply = reactive({ role: 'assistant', content: '', streaming: true, tools: [], sources: [], failed: false, aborted: false })
  messages.value.push(reply)
  controller = new AbortController()
  const accountAtSend = activeAccountId()
  let completed = false
  let failed = false
  scrollBottom()
  try {
    await waitForSync()
    await syncNow()
    if (!alive || activeAccountId() !== accountAtSend) return
    if (!conversationId.value) {
      const convo = await aiApi.createConversation({ scene: scene.value })
      if (!alive) return
      conversationId.value = convo.id
    }
    await aiApi.chatStream({ scene: scene.value, content, image_keys: imageKeys,
      conversation_id: conversationId.value, use_tools: useTools.value, use_search: useSearch.value },
      (evt) => {
        if (!alive) return
        if (evt.type === 'delta') {
          // delivering：首个 delta 起，回答卡进入洗扫/流式输出状态
          if (!receiving.value) {
            receiving.value = true
            visualState.value = 'delivering'
            updateFocusPoint()
          }
          reply.content += evt.text
          if (atBottom.value) scrollBottom()
        } else if (evt.type === 'error') {
          failed = true
          reply.failed = true
          reply.content += (reply.content ? '\n\n' : '') + `出错了：${evt.message}`
        } else if (evt.type === 'done') {
          completed = true
          reply.streaming = false
          Object.assign(reply, { prompt_tokens: evt.prompt_tokens, completion_tokens: evt.completion_tokens,
            id: evt.message_id, suggested_tasks: evt.suggested_tasks || [], latency_ms: evt.latency_ms, tools: evt.tools || [], sources: evt.sources || [] })
          if (evt.conversation_id) conversationId.value = evt.conversation_id
          if (evt.title) conversationTitle.value = evt.title
        }
      }, { signal: controller.signal })
  } catch (e) {
    if (!completed) {
      // 主动停止与网络失败分开标记，前者不弹错误色
      if (controller?.signal.aborted || e?.name === 'AbortError') {
        reply.aborted = true
        if (!reply.content) reply.content = '已停止生成。'
      } else {
        failed = true
        reply.failed = true
        reply.content += `\n请求未完成：${e.message}`
      }
    }
  } finally {
    reply.streaming = false
    sending.value = false
    receiving.value = false
    visualState.value = 'idle'
    scheduleIdle()
    updateFocusPoint()
    if (failed && alive) {
      if (!input.value) input.value = content
      if (!attachments.value.length) attachments.value = selected
    }
    if (completed && alive && activeAccountId() === accountAtSend) {
      await db.kv.delete('ai:draft')
      historyFetched.value = false
      loadDesktopHistory()
    }
    scrollBottom()
  }
}

function newChat(s) {
  if (sending.value) return
  clearTimeout(idleTimer)
  conversationGeneration++; loadingConversation.value = false
  taskPreview.value = null
  if (s) scene.value = s
  conversationId.value = null
  conversationTitle.value = ''
  messages.value = []
  showHistory.value = false
  visualState.value = 'idle'
  receiving.value = false
  updateFocusPoint()
}

async function loadHistory(open = true) {
  if (open === true) showHistory.value = true
  if (historyLoading.value) return
  const generation = ++historyGeneration
  historyLoading.value = true
  historyError.value = ''
  try {
    const rows = await aiApi.conversations()
    if (!alive || generation !== historyGeneration) return
    if (!Array.isArray(rows)) throw new Error('历史会话数据无效，请重试')
    historyList.value = rows
    historyFetched.value = true
  } catch (e) {
    if (alive && generation === historyGeneration) historyError.value = e.message || '历史会话读取失败'
  } finally {
    if (generation === historyGeneration) historyLoading.value = false
  }
}
function loadDesktopHistory() {
  if (window.matchMedia?.('(min-width: 960px)').matches && !historyFetched.value) loadHistory(false)
}

async function openConversation(id) {
  if (sending.value) return
  const generation = ++conversationGeneration
  loadingConversation.value = true
  taskPreview.value = null
  try {
    const data = await aiApi.conversation(id)
    if (!alive || generation !== conversationGeneration) return
    conversationId.value = data.id
    conversationTitle.value = data.title
    scene.value = data.scene || 'general'
    messages.value = (data.messages || []).map((m) => ({
      task_import:m.task_import || {state:'not_imported'}, id: m.id, suggested_tasks: m.suggested_tasks || [], role: m.role, content: m.content, image_keys: m.image_keys || [], tools: m.tools || [], sources: m.sources || [],
      prompt_tokens: m.prompt_tokens, completion_tokens: m.completion_tokens,
      latency_ms: m.latency_ms,
    }))
    showHistory.value = false
    visualState.value = 'idle'
    receiving.value = false
    scrollBottom()
    updateFocusPoint()
  } catch (e) {
    if (alive && generation === conversationGeneration) toast(e.message)
  } finally { if (generation === conversationGeneration) loadingConversation.value = false }
}

async function removeConversation(id) {
  if (!confirm('删除这条对话记录？删除后无法恢复。')) return
  try {
    await aiApi.deleteConversation(id)
    historyList.value = historyList.value.filter((c) => c.id !== id)
    if (conversationId.value === id) newChat()
  } catch (e) {
    toast(e.message)
  }
}

// 复制回答：Markdown 原文复制，便于贴到笔记里
function copyAnswer(m) {
  if (!m?.content) return
  copyToClipboard(m.content, '回答已复制')
}

onMounted(async () => {
  await loadConfig()
  loadDesktopHistory()
  await nextTick()
  updateFocusPoint()
  window.addEventListener('resize', scheduleFocus)
  window.addEventListener('resize', loadDesktopHistory)
  try {
    const draft = await db.kv.get('ai:draft')
    if (draft?.value) {
      input.value = draft.value.content || ''
      attachments.value = (draft.value.images || []).slice(0, 4).map((image) => ({ id: uid(),
        key: typeof image === 'string' ? image : '', blob: typeof image === 'string' ? null : image,
        uploading: false, error: '' }))
    }
  } catch {
    // 草稿读取失败不影响正常对话
  }
})

// 输入即存草稿（防抖 400ms）：切走再回来不丢已经写了一半的问题
let draftTimer
watch(
  [input, () => attachments.value.map((row) => row.key || row.blob)],
  ([text, images]) => {
    clearTimeout(draftTimer)
    draftTimer = setTimeout(() => {
      if (!alive) return
      if (text.trim() || images.length) {
        db.kv.put({ key: 'ai:draft', value: { content: text, images } }).catch(() => {})
      } else {
        db.kv.delete('ai:draft').catch(() => {})
      }
    }, 400)
  }
)
watch(input, (value) => {
  if (sending.value) return
  visualState.value = value.trim() ? 'listening' : (document.activeElement === composerEl.value ? 'listening' : 'idle')
  updateFocusPoint()
})
watch(visualState, () => updateFocusPoint())
function previewTasks(message){taskSelection.value=message.suggested_tasks.map((_,i)=>i);taskPreview.value=message}
async function undoTasks(message){
 if(importing.value||!confirm('撤销本次导入？仅删除未修改、未完成的任务，其他任务保留。'))return
 importing.value=true
 try{message.task_import=await aiApi.undoTasks(message.id);await waitForSync();await syncNow();toast(`已撤销${message.task_import.undo.deleted}项，保留${message.task_import.undo.kept.length}项（已修改、完成或删除）`)}
 catch(e){toast(e.message)}finally{importing.value=false}
}
function regenerateTasks(message){
 if(sending.value)return
 scene.value='plan';input.value='请把上面的建议转换为可导入的任务清单，直接输出yanshi_tasks JSON代码块，字段title、accept_criteria、estimated_min、subject_id、due_date；未设日期可留空。不要只说等待我确认。参考内容：'+message.content.slice(0,2000)
 send()
}
async function importTasks(){
 if(!taskPreview.value || importing.value || !taskSelection.value.length)return
 const message=taskPreview.value
 const selected=[...taskSelection.value]
 importing.value=true
 try{
  const result=await aiApi.importTasks(message.id,selected)
  message.task_import=result
  if(taskPreview.value===message)taskPreview.value=null
  await waitForSync();await syncNow()
  toast('任务已导入，可在任务清单查看；重复确认不会重复新增')
 }catch(e){toast(e.message)}finally{importing.value=false}
}
</script>

<template>
  <div
    ref="aiWrapEl"
    class="ai-wrap neural"
    :class="['theme-' + theme, 'state-' + visualState, { 'has-sheet': showHistory || taskPreview, 'is-empty': !messages.length }]"
    :style="{ '--focus-x': focusX, '--focus-y': focusY }"
  >
    <div class="neural-bg" aria-hidden="true">
      <div class="spectrum-flow"></div>
      <div class="spectrum-tail"></div>
      <div class="spectrum-beam"></div>
      <div class="spectrum-focus"></div>
    </div>
    <CopyFallback v-model="manualCopy" />
    <aside class="ai-history-panel" aria-label="会话列表">
      <div class="ai-history-heading"><strong>我的对话</strong><button class="icon-btn" title="刷新会话列表" @click="loadHistory(false)"><History :size="16" /></button></div>
      <button class="btn btn-outline btn-block" :disabled="sending" @click="newChat()"><Plus :size="16" />新建对话</button>
      <p v-if="historyLoading" role="status">正在读取…</p>
      <div v-else-if="historyError"><p>{{ historyError }}</p><button class="btn btn-outline btn-sm" @click="loadHistory(false)">重试</button></div>
      <p v-else-if="!historyList.length" class="msg-usage">还没有历史对话</p>
      <div v-for="c in historyList" :key="c.id" class="ai-history-entry" :class="{ on: c.id === conversationId }">
        <button :disabled="sending" class="ai-history-select" @click="openConversation(c.id)">{{ c.title || '未命名对话' }}</button>
        <button class="hist-del" :disabled="sending" :aria-label="'删除对话：' + (c.title || '未命名对话')" @click="removeConversation(c.id)">×</button>
      </div>
      <p class="msg-usage">聊天记录仅本人可见</p>
    </aside>

    <div class="nav ai-nav">
      <div class="nav-brand">
        <button type="button" class="nav-back" title="返回今日" @click="router.push('/')"><ArrowLeft :size="18" /></button>
        <span class="brand-spark" aria-hidden="true"></span>
        <div class="nav-copy">
          <div class="nav-title">AI 助教</div>
          <div class="nav-sub">{{ conversationTitle || '考研专项答疑' }}</div>
        </div>
      </div>
      <div class="nav-actions">
        <button class="icon-btn" title="AI 设置" @click="router.push('/ai/settings')"><Settings2 :size="18" /></button>
        <button class="icon-btn" title="新建对话" @click="newChat()"><Plus :size="18" /></button>
        <button class="icon-btn history-trigger" title="历史对话" @click="loadHistory()"><History :size="18" /></button>
        <button class="icon-btn" :title="`主题：${themeLabel}（点击切换）`" @click="cycleTheme"><component :is="themeIcon" :size="17" /></button>
      </div>
    </div>

    <div class="scene-bar">
      <button
        v-for="s in scenes"
        :key="s.key"
        class="scene-chip"
        :class="{ on: s.key === scene && !conversationId }"
        :disabled="sending"
        @click="newChat(s.key)"
      >
        <component :is="s.icon" :size="13" />{{ s.label }}
      </button>
    </div>

    <div v-if="blocked && !messages.length" class="ai-guide">
      <div class="guide-badge">
        <RefreshCw v-if="blocked === 'error'" :size="26" />
        <Crown v-else :size="26" />
      </div>
      <div class="guide-title">
        {{ blocked === 'vip' ? 'AI 需要 VIP 或审批授权' : blocked === 'error' ? 'AI 服务暂时连不上' : '还差一步：配置你的 API Key' }}
      </div>
      <div class="guide-desc">
        <template v-if="blocked === 'vip'">
          AI 问答需要 VIP 权限，或申请「AI 问答权限」并通过审批；使用时可填写你自己的模型 API Key，站内不会保存明文。
        </template>
        <template v-else-if="blocked === 'error'">
          {{ configError }}。网络恢复后点下方重新连接，不会影响已有历史对话。
        </template>
        <template v-else>
          你已获得 AI 权限。前往 AI 设置填写自己的 API Key，即可开始对话；Key 使用 AES-256-GCM 加密存储。
        </template>
      </div>
      <button
        v-if="blocked === 'vip'"
        class="btn btn-accent btn-block"
        @click="router.push('/vip')"
      >
        <Crown :size="17" />开通 VIP
      </button>
      <button v-else-if="blocked === 'error'" class="btn btn-primary btn-block" :disabled="configLoading" @click="loadConfig">
        <RefreshCw :size="17" />{{ configLoading ? '重新连接中…' : '重新连接' }}
      </button>
      <button v-else class="btn btn-primary btn-block" @click="router.push('/ai/settings')">
        <Settings2 :size="17" />去配置 Key
      </button>
      <button class="guide-link" @click="router.push('/requests')">
        没有邀请码？提交功能申请<ChevronRight :size="15" />
      </button>
    </div>

    <div v-if="loadingConversation && !messages.length" class="skeleton-list" role="status">
      <span class="sr-only">正在读取所选对话，请稍候…</span>
      <div class="sk-msg">
        <div class="sk-ava"></div>
        <div class="sk-lines"><i></i><i></i><i class="short"></i></div>
      </div>
      <div class="sk-msg mine"><div class="sk-lines"><i class="short"></i></div></div>
    </div>
    <p v-if="blocked && messages.length" class="msg-usage" style="padding:8px 16px">历史记录可继续查看；恢复权限并配置可用Key后才能发送新消息。</p>
    <div v-if="!blocked || messages.length" ref="scrollEl" class="chat-scroll" @scroll.passive="onScroll">
      <div v-if="!messages.length && !blocked" class="chat-empty">
        <div class="empty-badge"><span class="brand-spark lg" aria-hidden="true"></span></div>
        <div class="empty-kicker">研时 · NEURAL STUDY</div>
        <div class="empty-title">{{ greeting }}</div>
        <div class="empty-desc"><strong>{{ scenes.find((x) => x.key === scene)?.label }}</strong> · {{ welcome }}</div>
        <div v-if="suggestions.length" class="starter-list">
          <button v-for="text in suggestions" :key="text" class="starter" @click="useSuggestion(text)">
            {{ text }}<ChevronRight :size="13" />
          </button>
        </div>
      </div>
      <div v-for="(m, i) in messages" :key="i" class="chat-msg" :class="m.role">
        <div v-if="m.role === 'assistant'" class="msg-ava"><span class="brand-spark sm" aria-hidden="true"></span></div>
        <div class="msg-main">
          <div v-if="m.image_keys?.length" class="ai-images"><BlobImage v-for="key in m.image_keys" :key="key" :src="key" alt="题目图片" /></div>
          <div
            v-if="!m.streaming || m.content"
            class="bubble"
            :class="{ answer: m.role === 'assistant', err: m.failed, muted: m.aborted, delivering: m.streaming && visualState === 'delivering' }"
          >
            <div v-if="m.content" class="md" v-html="renderMarkdown(m.content)"></div>
            <span v-if="m.streaming" class="caret">▍</span>
          </div>
          <div v-if="m.failed || m.aborted" class="msg-usage retry-row">
            {{ m.aborted ? '已停止生成' : '回复中断，可重试' }}
            <button class="btn btn-outline btn-sm" :disabled="sending" @click="retry(m)">重试</button>
          </div>
          <button v-if="access && m.id && m.suggested_tasks?.length && !m.streaming && (!m.task_import || m.task_import.state==='not_imported')" class="btn btn-outline" @click="previewTasks(m)">一键导入为系统任务</button>
          <div v-if="m.id && m.task_import?.state === 'imported'" class="msg-usage">已导入 {{m.task_import.imported_count}} 项任务 <button class="btn btn-outline" :disabled="importing" @click="undoTasks(m)">撤销本次导入</button></div>
          <div v-if="m.task_import?.state === 'undone'" class="msg-usage">已撤销 {{m.task_import.undo?.deleted}} 项；保留 {{m.task_import.undo?.kept?.length}} 项（已修改、完成或删除）</div>
          <div v-if="!blocked && m.id && m.role==='assistant' && !m.streaming && !m.suggested_tasks?.length" class="msg-usage">此回复未包含有效的可导入任务。<button class="btn btn-outline" :disabled="sending" @click="regenerateTasks(m)">生成可导入任务</button></div>
          <div v-if="m.tools?.length" class="msg-usage">已调用：{{ m.tools.map(t => `${t.name}${t.status === 'failed' ? '（失败）' : ''}`).join('、') }}</div>
          <details v-if="m.sources?.length" class="ai-sources">
            <summary>参考资料 {{ m.sources.length }} 条</summary>
            <a v-for="source in m.sources" :key="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title || '查看来源' }}</a>
          </details>
          <div v-if="m.role === 'assistant' && (m.completion_tokens || m.latency_ms)" class="msg-usage">
            <template v-if="m.prompt_tokens || m.completion_tokens">
              {{ (m.prompt_tokens || 0) + (m.completion_tokens || 0) }} tokens
            </template>
            <template v-if="m.prompt_tokens || m.completion_tokens"> · </template>
            {{ ((m.latency_ms || 0) / 1000).toFixed(1) }}s
          </div>
          <div v-if="m.role === 'assistant' && m.content && !m.streaming && !m.failed && !m.aborted" class="msg-actions">
            <button class="act-btn" title="复制 Markdown 原文" @click="copyAnswer(m)"><Copy :size="13" />复制回答</button>
          </div>
        </div>
      </div>
      <div v-if="visualState === 'thinking'" class="thinking-row" role="status">
        <div class="think-spark"><span class="brand-spark" aria-hidden="true"></span></div>
        <div class="think-copy">
          <strong>正在整理思路</strong>
          <p>检索你的任务与学习摘要，组织成可执行答案…</p>
        </div>
        <div class="think-ripple" aria-hidden="true"><i></i><i></i></div>
        <div class="think-particles" aria-hidden="true"><i v-for="n in 6" :key="n"></i></div>
      </div>
    </div>

    <div v-if="!blocked" class="ai-options">
      <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" multiple style="display:none" @change="pickImages" />
      <button class="btn btn-outline btn-sm" :disabled="sending || !features.vision" @click="fileInput?.click()">添加题图（最多4张）</button>
      <label v-if="!features.v1_readonly"><input v-model="useTools" type="checkbox" :disabled="sending || !features.tools || !features.model_tools" />只读学习工具</label>
      <label v-if="!features.v1_readonly"><input v-model="useSearch" type="checkbox" :disabled="sending || !features.search || !features.model_tools" />联网搜索</label>
      <div class="msg-usage">对话自动携带本人已同步任务、自习状态与近30天学习摘要；不会读取组员数据或操控页面。回复与密钥仅本人可见。</div>
      <div v-if="!features.model_vision" class="msg-usage">图片需在AI设置中确认模型支持；也可移除图片仅发送文字。</div>
      <div v-if="useTools || useSearch" class="msg-usage">工具模式等待完整结果；仅读取本人已同步数据，最多3次模型请求，不修改学习记录。联网时关键词会发送给搜索服务。</div>
      <div class="ai-images"><div v-for="row in attachments" :key="row.id">
        <BlobImage :blob="row.key ? null : row.blob" :src="row.key" alt="待发送题图" />
        <button :disabled="sending || row.uploading" @click="attachments = attachments.filter(x => x.id !== row.id)">移除</button>
        <button v-if="!row.key" :disabled="row.uploading" @click="uploadRow(row)">{{ row.uploading ? '上传中' : '上传/重试' }}</button>
        <small v-if="row.error">{{ row.error }}</small>
      </div></div>
    </div>
    <div v-if="!blocked" class="composer-meta">
      <span class="state-dot" :class="'dot-' + visualState"></span>
      {{ stateLabel }}
      <span class="meta-spacer"></span>
      <span>Enter 发送</span>
    </div>
    <div v-if="!blocked" class="composer">
      <input
        ref="composerEl"
        v-model="input"
        :placeholder="enabled ? '输入你的问题…' : 'AI 未启用'"
        maxlength="4000"
        @focus="onComposerFocus"
        @blur="onComposerBlur"
        @keyup.enter="send"
      />
      <button v-if="sending" class="send-btn stop" title="停止生成" @click="stopGeneration">
        <Square :size="15" fill="currentColor" />
      </button>
      <button v-else class="send-btn" :aria-busy="loadingConversation" :disabled="sending || (!input.trim() && !attachments.length)" @click="send">
        <Send :size="18" />
      </button>
    </div>

    <!-- 向上翻看历史时提供回底 -->
    <button v-if="!atBottom && messages.length" class="jump-btn" @click="scrollBottom">
      <ArrowDown :size="16" />回到底部
    </button>

    <div v-if="taskPreview" class="mask" @click.self="!importing && (taskPreview=null)">
      <div class="sheet" style="max-height:75vh;overflow:auto">
        <div class="sheet-title">导入任务前请确认</div>
        <p>下列任务将写入你的任务清单，并遵循小组共享与隐私模式规则。同一回复只能确认一组选项；撤销后不能再次导入这批任务。如需补充或重导，请重新向AI生成清单。</p>
        <div v-for="(task,i) in taskPreview.suggested_tasks" :key="i" class="card">
          <label><input v-model="taskSelection" type="checkbox" :value="i" :disabled="importing" /> {{task.title}}</label><p>{{task.due_date || '未设日期'}} · 预计 {{task.estimated_min}} 分钟</p><p>{{task.accept_criteria}}</p>
        </div>
        <div class="task-actions"><button class="btn btn-outline" :disabled="importing" @click="taskPreview=null">取消</button>
        <button class="btn btn-primary" :disabled="importing || !taskSelection.length" @click="importTasks">{{importing?'导入中…':'确认批量导入'}}</button></div>
      </div>
    </div>
    <!-- 历史会话 -->
    <div v-if="showHistory" class="mask" @click.self="showHistory = false">
      <div class="sheet hist-sheet">
        <div class="sheet-head">
          <div class="sheet-title">历史对话</div>
          <button type="button" class="sheet-close" aria-label="关闭历史对话" @click="showHistory = false"><X :size="18" /></button>
        </div>
        <div v-if="historyLoading" class="hist-loading" role="status">
          <span class="sr-only">正在读取历史对话，请稍候…</span>
          <div v-for="i in 3" :key="i" class="hist-sk"><i></i><i class="short"></i></div>
        </div>
        <div v-else-if="historyError" class="hist-error">
          <span>{{ historyError }}</span>
          <button class="btn btn-outline btn-sm" @click="loadHistory">重试</button>
        </div>
        <div v-else-if="!historyList.length" class="hist-empty">还没有历史对话</div>
        <div
          v-for="c in historyList"
          :key="c.id"
          class="hist-row"
          :class="{ on: c.id === conversationId }"
          @click="openConversation(c.id)"
        >
          <MessageCircle :size="16" class="hist-ic" />
          <div class="hist-meta">
            <div class="hist-title">{{ c.title || '未命名对话' }}</div>
            <div class="hist-scene">{{ scenes.find((x) => x.key === c.scene)?.label || c.scene }}</div>
          </div>
          <button class="hist-del" @click.stop="removeConversation(c.id)"><Sigma :size="15" style="display:none" />×</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-actions{position:sticky;bottom:0;background:rgba(248,250,255,.92);backdrop-filter:blur(12px);padding:8px 0 0;display:flex;gap:8px;z-index:2}

.ai-options { padding: 8px 16px; background: rgba(248, 250, 255, 0.86); border-top: 1px solid var(--line); max-height: 32vh; overflow: auto; }
.ai-options label { font-size: 12px; margin: 4px 8px; display: inline-flex; align-items: center; gap: 4px; color: var(--sub); }
.ai-images { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0; }
.ai-images img { width: 80px; height: 70px; object-fit: contain; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.ai-images button, .ai-images small { display: block; font-size: 12px; }
.ai-images button { border: none; background: none; padding: 4px 0; color: var(--primary); cursor: pointer; }
.ai-images small { color: var(--red); }
.ai-sources a { display: block; font-size: 12px; padding: 4px 0; word-break: break-all; color: var(--primary); }
.ai-sources summary {
  cursor: pointer; font-size: 12px; color: var(--sub); padding: 4px 0;
  list-style: none;
}
.ai-sources summary::-webkit-details-marker { display: none; }
.ai-sources summary::before { content: '▸ '; color: var(--faint); }
.ai-sources[open] summary::before { content: '▾ '; }
.ai-sources summary:hover { color: var(--primary); }

/* 读取对话时的骨架占位，避免空白等待 */
.sr-only {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap;
}
.skeleton-list { padding: 16px; display: flex; flex-direction: column; gap: 16px; }
.sk-msg { display: flex; gap: 8px; }
.sk-msg.mine { justify-content: flex-end; }
.sk-ava { width: 32px; height: 32px; border-radius: 12px; background: rgba(79, 70, 229, 0.1); flex-shrink: 0; }
.sk-lines { display: flex; flex-direction: column; gap: 8px; width: 70%; }
.sk-lines i { height: 12px; border-radius: 6px; background: rgba(79, 70, 229, 0.08); }
.sk-lines i.short { width: 56%; }

/* 停止生成：与发送键同尺寸，色调区分 */
.send-btn.stop { background: linear-gradient(135deg, #4f46e5, #312e81); box-shadow: 0 8px 18px rgba(49, 46, 129, 0.24); }

/* 回到底部 */
.jump-btn {
  position: absolute; right: 16px; bottom: 88px;
  display: inline-flex; align-items: center; gap: 4px;
  border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 999px;
  background: rgba(255, 255, 255, 0.92); color: var(--primary);
  font-size: 12px; font-weight: 600; padding: 8px 16px; cursor: pointer;
  box-shadow: 0 8px 20px rgba(79, 70, 229, 0.16);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  transition: transform 0.24s ease, box-shadow 0.24s ease;
}
@media (hover: hover) and (pointer: fine) {
  .jump-btn:hover { transform: translateY(-2px); box-shadow: 0 12px 24px rgba(79, 70, 229, 0.2); }
}

.ai-wrap {
  position: fixed;
  top: var(--notice-h, 0px);
  left: max(0px, calc(50% - 260px));
  width: min(100%, 520px);
  bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  background: radial-gradient(900px 480px at 50% -10%, #eef1ff, #f8faff 60%);
  z-index: 10;
}
.ai-wrap.has-sheet { z-index: 320; }
.ai-nav { display: flex; align-items: center; justify-content: space-between; }
.nav-actions { display: flex; gap: 8px; }
/* 次按钮：毛玻璃 + 细边框，hover 缓慢上浮 */
.icon-btn {
  width: 40px; height: 40px; border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
  color: var(--sub); display: flex; align-items: center; justify-content: center;
  cursor: pointer; box-shadow: var(--shadow-soft);
  transition: transform 0.24s ease, color 0.24s ease, box-shadow 0.24s ease;
}
.icon-btn:active { transform: scale(0.96); }
@media (hover: hover) and (pointer: fine) {
  .icon-btn:hover { transform: translateY(-2px); color: var(--primary); box-shadow: 0 8px 20px rgba(79, 70, 229, 0.18); }
}

.scene-bar { display: flex; flex-wrap: wrap; gap: 6px 8px; padding: 0 16px 12px; }
.scene-chip {
  flex: 1 1 auto; min-width: 0; display: inline-flex; align-items: center; justify-content: center; gap: 4px;
  border: 1px solid var(--line); background: rgba(255, 255, 255, 0.7);
  color: var(--sub); border-radius: 999px; padding: 7px 12px;
  font-size: 11px; font-weight: 600; cursor: pointer; white-space: nowrap;
  transition: color 0.24s ease, background 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
}
.scene-chip.on {
  background: var(--primary-grad);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.24);
}
.scene-chip:disabled { opacity: .5; cursor: default; box-shadow: none; }

.chat-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 8px 16px 16px; }
.chat-empty { text-align: center; padding: 48px 24px; }
/* 空态起步问题 */
.starter-list { margin-top: 24px; display: flex; flex-direction: column; gap: 8px; }
.starter {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  border: 1px solid var(--line); background: rgba(255, 255, 255, 0.7);
  color: var(--sub); border-radius: 12px; padding: 8px 16px;
  font-size: 12px; text-align: left; cursor: pointer;
  transition: color 0.24s ease, background 0.24s ease, border-color 0.24s ease, transform 0.24s ease;
}
.starter svg { flex-shrink: 0; color: var(--faint); }
.starter:active { transform: scale(0.99); }
@media (hover: hover) and (pointer: fine) {
  .starter:hover { color: var(--primary); border-color: rgba(79, 70, 229, 0.28); background: rgba(79, 70, 229, 0.04); }
}
.empty-badge {
  width: 60px; height: 60px; margin: 0 auto 16px; border-radius: 20px;
  background: var(--primary-grad); color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 12px 28px rgba(79, 70, 229, 0.3);
}
.empty-title { font-size: 20px; font-weight: 800; }
.empty-desc { margin-top: 8px; font-size: 12px; color: var(--sub); line-height: 1.8; }

.chat-msg { display: flex; gap: 8px; margin-bottom: 16px; }
.chat-msg.user { justify-content: flex-end; }
.msg-ava {
  width: 32px; height: 32px; border-radius: 12px; background: var(--primary-grad);
  color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  box-shadow: 0 6px 14px rgba(79, 70, 229, 0.22);
}
.bubble {
  max-width: 78%; padding: 8px 16px; border-radius: 12px;
  font-size: 14px; line-height: 1.7; white-space: normal; word-break: break-word;
  box-shadow: var(--shadow-soft);
}
/* 回复中断 / 主动停止：低饱和提示，不与正文抢注意力 */
.bubble.err { border: 1px solid rgba(239, 68, 68, 0.22); background: rgba(255, 247, 247, 0.9); }
.bubble.muted { opacity: 0.8; }
.retry-row { display: flex; align-items: center; gap: 8px; }
.retry-row .btn { margin-left: 4px; }

/* ---------- Markdown 正文 ---------- */
.bubble .md > :first-child { margin-top: 0; }
.bubble .md > :last-child { margin-bottom: 0; }
.bubble .md p { margin: 0 0 8px; }
.bubble .md h3,
.bubble .md h4,
.bubble .md h5,
.bubble .md h6 { margin: 8px 0; font-size: 14px; font-weight: 800; color: var(--ink); }
.bubble .md ul,
.bubble .md ol { margin: 0 0 8px; padding-left: 20px; }
.bubble .md li { margin: 4px 0; }
.bubble .md blockquote { margin: 8px 0; padding: 4px 8px; border-left: 2px solid rgba(79, 70, 229, 0.32); color: var(--sub); }
.bubble .md hr { border: none; border-top: 1px solid var(--line); margin: 8px 0; }
.bubble .md a { color: var(--primary); text-decoration: underline; text-underline-offset: 2px; }
.bubble .md code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px; background: rgba(79, 70, 229, 0.08); color: #4338ca;
  border-radius: 4px; padding: 1px 4px;
}
.bubble .md pre {
  margin: 8px 0; padding: 8px 16px; border-radius: 8px;
  background: rgba(30, 27, 75, 0.94); overflow-x: auto;
}
.bubble .md pre code { background: none; color: #e9e7ff; padding: 0; font-size: 12px; line-height: 1.7; }
.bubble .md .md-table { margin: 8px 0; overflow-x: auto; }
.bubble .md table { border-collapse: collapse; font-size: 12px; width: 100%; }
.bubble .md th,
.bubble .md td { border: 1px solid var(--line); padding: 4px 8px; text-align: left; }
.bubble .md th { background: rgba(79, 70, 229, 0.06); font-weight: 700; }
.chat-msg.user .bubble .md code { background: rgba(255, 255, 255, 0.22); color: #fff; }
.chat-msg.user .bubble .md pre { background: rgba(17, 20, 50, 0.6); }
.chat-msg.assistant .bubble {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  border-top-left-radius: 4px;
}
.chat-msg.user .bubble {
  background: var(--primary-grad); color: #fff; border-top-right-radius: 4px;
  box-shadow: 0 8px 20px rgba(79, 70, 229, 0.2);
}
/* 打字光标：缓慢呼吸，不做高频闪烁 */
.caret { display: inline-block; margin-left: 2px; color: var(--primary); animation: caret-pulse 1.2s ease-in-out infinite; }
@keyframes caret-pulse { 50% { opacity: 0.25; } }
.msg-main { display: flex; flex-direction: column; min-width: 0; max-width: 86%; }
.msg-main .bubble { max-width: 100%; }
.msg-usage { font-size: 12px; color: var(--faint); margin-top: 4px; padding-left: 2px; }
.msg-actions { margin-top: 8px; display: flex; gap: 8px; }
.act-btn {
  display: inline-flex; align-items: center; gap: 4px;
  border: 1px solid var(--line); background: rgba(255, 255, 255, 0.7);
  color: var(--faint); border-radius: 8px; padding: 4px 8px;
  font-size: 12px; cursor: pointer;
  transition: color 0.24s ease, border-color 0.24s ease, background 0.24s ease;
}
@media (hover: hover) and (pointer: fine) {
  .act-btn:hover { color: var(--primary); border-color: rgba(79, 70, 229, 0.28); }
}

.ai-guide {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 24px 40px;
  text-align: center;
}
.guide-badge {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: rgba(245, 158, 11, 0.12);
  color: var(--accent-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.guide-title { font-size: 20px; font-weight: 800; color: var(--ink); }
.guide-desc { font-size: 12px; color: var(--sub); line-height: 1.8; margin: 8px 0 16px; max-width: 320px; }
.guide-link {
  margin-top: 16px;
  border: none;
  background: none;
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

/* 输入条：玻璃底 + 圆角胶囊输入框 */
.composer {
  display: flex; gap: 8px; padding: 8px 16px calc(16px + env(safe-area-inset-bottom));
  border-top: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
}
.composer input {
  flex: 1; height: 44px; border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 999px;
  padding: 0 16px; font-size: 14px; background: rgba(255, 255, 255, 0.9);
  transition: border-color 0.24s ease, box-shadow 0.24s ease;
}
.composer input:focus { outline: none; border-color: rgba(79, 70, 229, 0.5); box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12); }
.send-btn {
  width: 44px; height: 44px; border-radius: 50%; border: none;
  background: var(--primary-grad); color: #fff;
  display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0;
  box-shadow: 0 8px 18px rgba(79, 70, 229, 0.28);
  transition: transform 0.24s ease, filter 0.24s ease;
}
.send-btn:active { transform: scale(0.96); }
@media (hover: hover) and (pointer: fine) {
  .send-btn:hover:not(:disabled) { transform: scale(1.05); filter: brightness(1.06); }
}
.send-btn:disabled { opacity: 0.45; cursor: not-allowed; box-shadow: none; }

.mask { position: fixed; inset: 0; background: rgba(30, 27, 75, 0.45); display: flex; align-items: flex-end; justify-content: center; z-index: 320; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 24px 24px 0 0; padding: 24px 16px calc(24px + env(safe-area-inset-bottom)); max-height: 82vh; overflow-y: auto; }
.sheet-title { font-size: 20px; font-weight: 800; text-align: center; margin-bottom: 8px; }
.sheet-head { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 10px; background: #fff; }
.sheet-head .sheet-title { margin: 0; text-align: left; }
.sheet-close { width: 36px; height: 36px; flex-shrink: 0; border: 1px solid var(--line); border-radius: 50%; background: #fff; color: var(--sub); display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
.hist-sheet { max-height: min(86vh, calc(100dvh - 24px)); }
.hist-empty { text-align: center; color: var(--faint); font-size: 12px; padding: 24px 0; }
.hist-loading { display: flex; flex-direction: column; gap: 8px; padding: 8px 0; }
.hist-sk { padding: 16px 8px; border-bottom: 1px solid var(--line); display: flex; flex-direction: column; gap: 8px; }
.hist-sk i { display: block; width: 100%; height: 12px; border-radius: 6px; background: rgba(79, 70, 229, 0.08); }
.hist-sk i.short { width: 40%; height: 8px; }
.hist-loading i { animation: hist-breathe 1.6s ease-in-out infinite; }
@keyframes hist-breathe { 0%, 100% { opacity: .5; } 50% { opacity: 1; } }
.hist-error { display: flex; align-items: center; gap: 8px; padding: 24px 0; font-size: 12px; color: var(--sub); }
.hist-error span { flex: 1; min-width: 0; }
@media (prefers-reduced-motion: reduce) { .hist-loading i { animation: none; } }
.hist-row { display: flex; align-items: center; gap: 8px; padding: 16px 8px; border-bottom: 1px solid var(--line); cursor: pointer; border-radius: 8px; transition: background-color 0.24s ease; }
.hist-row:last-child { border-bottom: none; }
.hist-row.on { background: rgba(79, 70, 229, 0.06); }
@media (hover: hover) and (pointer: fine) {
  .hist-row:hover { background: rgba(79, 70, 229, 0.04); }
}
.hist-ic { color: var(--primary); flex-shrink: 0; }
.hist-meta { flex: 1; min-width: 0; }
.hist-title { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hist-scene { font-size: 12px; color: var(--faint); margin-top: 2px; }
.hist-del { border: none; background: none; color: var(--faint); font-size: 20px; cursor: pointer; padding: 0 8px; }

/* ==================================================================
   Neural Expressive · Spectrum Shift / Intentional Motion
   深色优先；浅色变量在 .theme-light 与 theme-auto 的媒体查询中。
   ================================================================== */
.ai-wrap.neural {
  --n-bg: #070a13;
  --n-text: #eef2ff;
  --n-sub: #a8b2c8;
  --n-faint: #74809a;
  --n-line: rgba(255, 255, 255, 0.1);
  --n-panel: rgba(255, 255, 255, 0.065);
  --n-panel-strong: rgba(255, 255, 255, 0.1);
  --n-stroke: rgba(255, 255, 255, 0.13);
  --n-card: rgba(255, 255, 255, 0.055);
  --n-card-solid: rgba(17, 22, 39, 0.92);
  --n-shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
  --n-grad: linear-gradient(120deg, #4285F4 0%, #9B72CF 34%, #D65AC0 64%, #FBBC05 100%);
  --n-ombre: linear-gradient(90deg, #8ab4f8, #c7a6f0, #f0a6d8, #f7d58a);
  --n-error: #ff9aa8;
  --primary: #8ab4f8;
  --primary-grad: var(--n-grad);
  --ink: var(--n-text);
  --sub: var(--n-sub);
  --faint: var(--n-faint);
  --line: var(--n-line);
  --card: var(--n-card);
  --bg: var(--n-bg);
  --shadow-soft: var(--n-shadow);
  --content-pad: 16px;
  left: 0;
  width: 100%;
  transform: none;
  overflow: hidden;
  border-radius: 0;
  background: var(--n-bg);
  color: var(--n-text);
  font-family: "Google Sans", Inter, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 15px;
  line-height: 1.7;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.04), 0 40px 100px rgba(0, 0, 0, 0.35);
  color-scheme: dark;
  transition: background-color 0.35s cubic-bezier(0.2, 0, 0, 1), color 0.35s cubic-bezier(0.2, 0, 0, 1);
}
.ai-wrap.neural.theme-light {
  --n-bg: #f7f8ff;
  --n-text: #172033;
  --n-sub: #4e5a70;
  --n-faint: #7c879b;
  --n-line: rgba(23, 32, 51, 0.14);
  --n-panel: rgba(255, 255, 255, 0.78);
  --n-panel-strong: rgba(255, 255, 255, 0.94);
  --n-stroke: rgba(23, 32, 51, 0.08);
  --n-card: rgba(255, 255, 255, 0.88);
  --n-card-solid: rgba(255, 255, 255, 0.96);
  --n-shadow: 0 18px 48px rgba(31, 45, 80, 0.1);
  --n-ombre: linear-gradient(90deg, #1a73e8, #7b4fc4, #c23b91, #b78300);
  --primary: #1a73e8;
  --ink: var(--n-text);
  --sub: var(--n-sub);
  --faint: var(--n-faint);
  --line: var(--n-line);
  --card: var(--n-card);
  --bg: var(--n-bg);
  --shadow-soft: var(--n-shadow);
  color-scheme: light;
}
@media (prefers-color-scheme: light) {
  .ai-wrap.neural.theme-auto {
    --n-bg: #f7f8ff;
    --n-text: #172033;
    --n-sub: #4e5a70;
    --n-faint: #7c879b;
    --n-line: rgba(23, 32, 51, 0.14);
    --n-panel: rgba(255, 255, 255, 0.78);
    --n-panel-strong: rgba(255, 255, 255, 0.94);
    --n-stroke: rgba(23, 32, 51, 0.08);
    --n-card: rgba(255, 255, 255, 0.88);
    --n-card-solid: rgba(255, 255, 255, 0.96);
    --n-shadow: 0 18px 48px rgba(31, 45, 80, 0.1);
    --n-ombre: linear-gradient(90deg, #1a73e8, #7b4fc4, #c23b91, #b78300);
    --primary: #1a73e8;
    --ink: var(--n-text);
    --sub: var(--n-sub);
    --faint: var(--n-faint);
    --line: var(--n-line);
    --card: var(--n-card);
    --bg: var(--n-bg);
    --shadow-soft: var(--n-shadow);
    color-scheme: light;
  }
}
@media (min-width: 900px) {
  .ai-wrap.neural {
    --content-pad: max(16px, calc((100% - 760px) / 2));
    left: 50%;
    transform: translateX(-50%);
    width: min(100%, 840px);
    bottom: 0;
    z-index: 130;
    border-radius: 28px 28px 0 0;
    border-left: 1px solid rgba(255, 255, 255, 0.06);
    border-right: 1px solid rgba(255, 255, 255, 0.06);
  }
  .ai-wrap.neural.has-sheet { z-index: 340; }
}
.ai-wrap.neural.has-sheet { z-index: 340; }

/* 背景：流动光谱 + 指向焦点的锐利前缘/高斯尾部 */
.ai-wrap.neural .neural-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  background: var(--n-bg);
  pointer-events: none;
}
.ai-wrap.neural .neural-bg::after {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(130% 100% at 50% 38%, rgba(7, 10, 19, 0) 0%, rgba(7, 10, 19, 0.22) 55%, rgba(7, 10, 19, 0.65) 100%);
  pointer-events: none;
}
.ai-wrap.neural.theme-light .neural-bg::after {
  background: radial-gradient(130% 100% at 50% 38%, rgba(247, 248, 255, 0) 0%, rgba(247, 248, 255, 0.35) 55%, rgba(247, 248, 255, 0.7) 100%);
}
.ai-wrap.neural .spectrum-flow {
  position: absolute;
  inset: -34%;
  background: linear-gradient(115deg, #4285F4 0%, #9B72CF 28%, #D65AC0 55%, #FBBC05 78%, #4285F4 100%);
  background-size: 260% 260%;
  filter: blur(120px);
  opacity: 0.12;
  animation: neural-drift 32s cubic-bezier(0.2, 0, 0.2, 1) infinite;
}
.ai-wrap.neural .spectrum-tail {
  position: absolute;
  inset: -20%;
  background:
    radial-gradient(60% 52% at 72% 62%, rgba(214, 90, 192, 0.18), transparent 70%),
    radial-gradient(52% 46% at 28% 38%, rgba(66, 133, 244, 0.18), transparent 72%);
  filter: blur(110px);
  opacity: 0.3;
}
.ai-wrap.neural .spectrum-beam {
  position: absolute;
  left: var(--focus-x, 50%);
  top: var(--focus-y, 62%);
  width: min(620px, 82vw);
  aspect-ratio: 1;
  transform: translate(-50%, -50%);
  background: conic-gradient(from 210deg at 50% 50%, transparent 0deg, rgba(66, 133, 244, 0) 34deg, rgba(66, 133, 244, 0.2) 60deg, rgba(214, 90, 192, 0.1) 82deg, transparent 118deg);
  filter: blur(26px);
  opacity: 0.2;
  -webkit-mask-image: radial-gradient(circle, #000 0%, rgba(0, 0, 0, 0.7) 30%, transparent 68%);
  mask-image: radial-gradient(circle, #000 0%, rgba(0, 0, 0, 0.7) 30%, transparent 68%);
  transition: left 0.6s cubic-bezier(0.2, 0, 0, 1), top 0.6s cubic-bezier(0.2, 0, 0, 1);
}
.ai-wrap.neural .spectrum-focus {
  position: absolute;
  inset: 0;
  background: radial-gradient(460px 340px at var(--focus-x, 50%) var(--focus-y, 62%), rgba(66, 133, 244, 0.28) 0%, rgba(155, 114, 207, 0.16) 22%, rgba(214, 90, 192, 0.1) 38%, rgba(251, 188, 5, 0.04) 52%, transparent 72%);
  filter: blur(18px);
  opacity: 0.42;
  transition: opacity 0.5s cubic-bezier(0.2, 0, 0, 1), background 0.6s cubic-bezier(0.2, 0, 0, 1);
}
.ai-wrap.neural.state-listening .spectrum-focus { opacity: 0.7; }
.ai-wrap.neural.state-thinking .spectrum-focus { opacity: 0.85; animation: neural-focus-breathe 2.6s cubic-bezier(0.2, 0, 0.2, 1) infinite; }
.ai-wrap.neural.state-delivering .spectrum-focus { opacity: 0.6; }
.ai-wrap.neural.state-idle .spectrum-focus { opacity: 0.42; }
.ai-wrap.neural.theme-light .spectrum-flow { opacity: 0.06; }
.ai-wrap.neural.theme-light .spectrum-tail { opacity: 0.15; }
.ai-wrap.neural.theme-light .spectrum-beam { opacity: 0.1; }
.ai-wrap.neural.theme-light.state-listening .spectrum-focus { opacity: 0.5; }
.ai-wrap.neural.theme-light.state-thinking .spectrum-focus { opacity: 0.6; }
.ai-wrap.neural.theme-light.state-delivering .spectrum-focus { opacity: 0.45; }
.ai-wrap.neural.theme-light.state-idle .spectrum-focus { opacity: 0.3; }

/* 内容层：全部在光谱之上；弹层仍保持最高层级 */
.ai-wrap.neural .ai-nav,
.ai-wrap.neural .scene-bar,
.ai-wrap.neural .ai-guide,
.ai-wrap.neural .chat-scroll,
.ai-wrap.neural .ai-options,
.ai-wrap.neural .composer-meta,
.ai-wrap.neural .composer,
.ai-wrap.neural .skeleton-list,
.ai-wrap.neural > .msg-usage {
  position: relative;
  z-index: 1;
}
.ai-wrap.neural .jump-btn { z-index: 2; }

/* 四星芒：用 SVG mask 做出四向尖角，填充光谱渐变 */
.ai-wrap.neural .brand-spark {
  width: 20px;
  height: 20px;
  display: inline-block;
  flex-shrink: 0;
  background: var(--n-grad);
  -webkit-mask-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20100%20100'%3E%3Cpath%20d='M50,2C54,32,68,46,98,50C68,54,54,68,50,98C46,68,32,54,2,50C32,46,46,32,50,2Z'/%3E%3C/svg%3E");
  -webkit-mask-repeat: no-repeat;
  -webkit-mask-position: center;
  -webkit-mask-size: contain;
  mask-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%20100%20100'%3E%3Cpath%20d='M50,2C54,32,68,46,98,50C68,54,54,68,50,98C46,68,32,54,2,50C32,46,46,32,50,2Z'/%3E%3C/svg%3E");
  mask-repeat: no-repeat;
  mask-position: center;
  mask-size: contain;
  mask-mode: alpha;
  filter: drop-shadow(0 0 10px rgba(155, 114, 207, 0.42));
}
.ai-wrap.neural .brand-spark.lg { width: 64px; height: 64px; filter: drop-shadow(0 0 24px rgba(155, 114, 207, 0.5)); }
.ai-wrap.neural .brand-spark.sm { width: 15px; height: 15px; filter: none; }
.ai-wrap.neural.state-thinking .brand-spark {
  animation: neural-spark-breathe 2.2s cubic-bezier(0.2, 0, 0.2, 1) infinite;
}

/* 顶部 */
.ai-wrap.neural .ai-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px var(--content-pad) 8px;
}
.ai-wrap.neural .nav-brand { display: flex; align-items: center; gap: 10px; min-width: 0; }
.ai-wrap.neural .nav-copy { min-width: 0; }
.ai-wrap.neural .nav-back {
  display: none;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--n-stroke);
  background: var(--n-panel);
  color: var(--n-sub);
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
@media (min-width: 900px) {
  .ai-wrap.neural .nav-back { display: inline-flex; }
}
.ai-wrap.neural .nav-title {
  font-size: 21px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--n-text);
  line-height: 1.2;
}
.ai-wrap.neural .nav-sub {
  margin-top: 3px;
  color: var(--n-sub);
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ai-wrap.neural .nav-actions { display: flex; align-items: center; gap: 6px; }
.ai-wrap.neural .icon-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid var(--n-stroke);
  background: var(--n-panel);
  color: var(--n-sub);
  box-shadow: none;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s cubic-bezier(0.2, 0, 0, 1);
}
.ai-wrap.neural .icon-btn:hover { color: var(--n-text); background: var(--n-panel-strong); transform: scale(1.04); }
.ai-wrap.neural .icon-btn:active { transform: scale(0.97); }
.ai-wrap.neural .icon-btn:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }
.ai-wrap.neural .icon-sim { color: #c7a6f0; }
@media (max-width: 380px) {
  .ai-wrap.neural .icon-btn { width: 32px; height: 32px; }
  .ai-wrap.neural .nav-title { font-size: 19px; }
}

/* 场景胶囊 */
.ai-wrap.neural .scene-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  padding: 0 var(--content-pad) 10px;
}
.ai-wrap.neural .scene-chip {
  flex: 1 1 auto;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 1px solid var(--n-line);
  background: var(--n-panel);
  color: var(--n-sub);
  border-radius: 999px;
  padding: 7px 10px;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
  backdrop-filter: blur(18px);
  transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}
.ai-wrap.neural .scene-chip.on {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.2);
  background: linear-gradient(120deg, rgba(66, 133, 244, 0.3), rgba(214, 90, 192, 0.2));
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.04), 0 8px 20px rgba(66, 133, 244, 0.12);
}
.ai-wrap.neural.theme-light .scene-chip.on {
  color: #162033;
  border-color: rgba(66, 133, 244, 0.26);
  background: linear-gradient(120deg, rgba(66, 133, 244, 0.16), rgba(214, 90, 192, 0.1));
}
.ai-wrap.neural .scene-demo {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px dashed var(--n-line);
  background: transparent;
  color: var(--n-sub);
  border-radius: 999px;
  padding: 7px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: color 0.18s ease, border-color 0.18s ease, background-color 0.18s ease;
}
.ai-wrap.neural .scene-demo:hover { color: var(--n-text); border-color: rgba(138, 180, 248, 0.35); background: var(--n-panel); }
.ai-wrap.neural .scene-demo:disabled { opacity: 0.45; cursor: not-allowed; }

/* 空态：编辑式首屏 */
.ai-wrap.neural .chat-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px var(--content-pad) 12px;
}
.ai-wrap.neural .chat-empty {
  min-height: 100%;
  max-width: 680px;
  margin: 0 auto;
  padding: 24px 8px 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.ai-wrap.neural .empty-badge {
  width: 96px;
  height: 96px;
  margin: 0 auto 18px;
  border-radius: 50%;
  border: 1px solid var(--n-stroke);
  background: radial-gradient(circle at 35% 30%, rgba(66, 133, 244, 0.34), rgba(214, 90, 192, 0.16) 60%, transparent 72%);
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.04), 0 20px 60px rgba(66, 133, 244, 0.16);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ai-wrap.neural .empty-kicker {
  margin-bottom: 8px;
  color: var(--n-faint);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}
.ai-wrap.neural .empty-title {
  color: var(--n-text);
  font-size: 26px;
  line-height: 1.35;
  font-weight: 600;
  letter-spacing: -0.5px;
  max-width: 560px;
}
.ai-wrap.neural .empty-desc {
  margin-top: 8px;
  color: var(--n-sub);
  font-size: 13px;
  line-height: 1.8;
  max-width: 560px;
}
.ai-wrap.neural .empty-desc strong { color: var(--n-text); font-weight: 500; }
.ai-wrap.neural .starter-list {
  width: 100%;
  max-width: 560px;
  margin-top: 22px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-wrap.neural .starter {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid var(--n-line);
  background: var(--n-panel);
  color: var(--n-sub);
  border-radius: 16px;
  padding: 10px 14px;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  backdrop-filter: blur(18px);
  transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}
.ai-wrap.neural .starter:hover { color: var(--n-text); border-color: rgba(138, 180, 248, 0.3); background: var(--n-panel-strong); }


/* 消息：编辑式回答卡，不做传统聊天气泡墙 */
.ai-wrap.neural .chat-msg { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 18px; }
.ai-wrap.neural .chat-msg.user { justify-content: flex-end; }
.ai-wrap.neural .msg-ava {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--n-panel);
  border: 1px solid var(--n-stroke);
  box-shadow: none;
  backdrop-filter: blur(16px);
}
.ai-wrap.neural .msg-main { flex: 1; min-width: 0; max-width: 100%; display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.ai-wrap.neural .chat-msg.user .msg-main { align-items: flex-end; }
.ai-wrap.neural .chat-msg.user .bubble {
  max-width: 78%;
  padding: 12px 16px;
  border-radius: 22px 22px 8px 22px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: linear-gradient(120deg, rgba(66, 133, 244, 0.24), rgba(214, 90, 192, 0.14));
  color: var(--n-text);
  box-shadow: none;
  backdrop-filter: blur(18px);
}
.ai-wrap.neural .bubble.answer {
  width: 100%;
  max-width: 100%;
  padding: 18px 18px 14px;
  border-radius: 22px;
  border: 1px solid var(--n-line);
  background: var(--n-card);
  color: var(--n-text);
  box-shadow: var(--n-shadow);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  position: relative;
  overflow: hidden;
}
.ai-wrap.neural .bubble.answer .md { color: var(--n-text); font-size: 15px; line-height: 1.75; }
.ai-wrap.neural .bubble.answer .md > p:first-child {
  margin-top: 0;
  color: var(--n-text);
  font-size: 16.5px;
  line-height: 1.65;
  font-weight: 600;
  letter-spacing: -0.15px;
}
.ai-wrap.neural .bubble.answer .md p { color: var(--n-sub); }
.ai-wrap.neural .bubble.answer .md strong {
  background: var(--n-ombre);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-weight: 600;
}
.ai-wrap.neural .bubble.answer .md h3,
.ai-wrap.neural .bubble.answer .md h4,
.ai-wrap.neural .bubble.answer .md h5,
.ai-wrap.neural .bubble.answer .md h6 { color: var(--n-text); }
.ai-wrap.neural .bubble.answer .md a { color: #8ab4f8; }
.ai-wrap.neural .bubble.answer .md code { background: rgba(255, 255, 255, 0.08); color: #dbe4ff; }
.ai-wrap.neural .bubble.answer .md pre { background: rgba(0, 0, 0, 0.28); border: 1px solid var(--n-line); }
.ai-wrap.neural .bubble.answer .md blockquote { border-left: 2px solid rgba(138, 180, 248, 0.45); color: var(--n-sub); }
.ai-wrap.neural .bubble.answer .md li::marker { color: #8ab4f8; }
.ai-wrap.neural .bubble.answer.delivering::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(105deg, transparent 28%, rgba(255, 255, 255, 0.09) 44%, rgba(214, 90, 192, 0.08) 55%, transparent 72%);
  background-size: 220% 100%;
  animation: neural-ombre-sweep 1.3s cubic-bezier(0.4, 0, 0.6, 1) 1;
  pointer-events: none;
}
.ai-wrap.neural .bubble.err { border-color: rgba(255, 154, 168, 0.3); background: rgba(255, 154, 168, 0.07); }
.ai-wrap.neural .bubble.muted { opacity: 0.76; }
.ai-wrap.neural .caret {
  display: inline-block;
  width: 2px;
  height: 1.05em;
  margin-left: 3px;
  border-radius: 2px;
  background: var(--n-grad);
  vertical-align: -0.12em;
  animation: neural-caret 1s steps(1) infinite;
}
.ai-wrap.neural .msg-usage { color: var(--n-faint); font-size: 11px; line-height: 1.7; }
.ai-wrap.neural .msg-actions .act-btn {
  border: 1px solid var(--n-line);
  background: var(--n-panel);
  color: var(--n-sub);
  border-radius: 999px;
  padding: 5px 10px;
}
.ai-wrap.neural .ai-images img {
  border-radius: 14px;
  border-color: var(--n-line);
  background: rgba(255, 255, 255, 0.06);
}
.ai-wrap.neural .ai-sources summary { color: var(--n-sub); }
.ai-wrap.neural .ai-sources a { color: #8ab4f8; }
.ai-wrap.neural .btn-outline {
  border-color: var(--n-line);
  background: var(--n-panel);
  color: var(--n-text);
}
.ai-wrap.neural .btn-primary { border: none; background: var(--n-grad); color: #fff; }
.ai-wrap.neural .btn-ghost { color: var(--n-sub); }

/* thinking：四星芒 + 径向涟漪 + 少量柔和粒子 */
.ai-wrap.neural .thinking-row {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 0 0 18px;
  padding: 16px;
  border: 1px solid var(--n-line);
  border-radius: 22px;
  background: var(--n-card);
  overflow: hidden;
  backdrop-filter: blur(24px);
}
.ai-wrap.neural .think-spark {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid var(--n-stroke);
  background: var(--n-panel);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ai-wrap.neural .think-copy strong { display: block; color: var(--n-text); font-size: 14px; font-weight: 600; }
.ai-wrap.neural .think-copy p { margin: 4px 0 0; color: var(--n-sub); font-size: 12px; line-height: 1.6; }
.ai-wrap.neural .think-ripple i {
  position: absolute;
  left: 17px;
  top: 17px;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(138, 180, 248, 0.35);
  border-radius: 50%;
  animation: neural-ripple 2.4s cubic-bezier(0.2, 0, 0.2, 1) infinite;
}
.ai-wrap.neural .think-ripple i:nth-child(2) { animation-delay: 1.2s; }
.ai-wrap.neural .think-particles { position: absolute; right: 14px; top: 12px; width: 86px; height: 44px; }
.ai-wrap.neural .think-particles i {
  position: absolute;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #8ab4f8;
  opacity: 0.55;
  animation: neural-particle 2.6s cubic-bezier(0.2, 0, 0.2, 1) infinite;
}
.ai-wrap.neural .think-particles i:nth-child(1) { left: 6%; top: 28%; animation-delay: 0s; }
.ai-wrap.neural .think-particles i:nth-child(2) { left: 28%; top: 64%; animation-delay: 0.3s; background: #c7a6f0; }
.ai-wrap.neural .think-particles i:nth-child(3) { left: 48%; top: 18%; animation-delay: 0.6s; }
.ai-wrap.neural .think-particles i:nth-child(4) { left: 68%; top: 52%; animation-delay: 0.9s; background: #f0a6d8; }
.ai-wrap.neural .think-particles i:nth-child(5) { left: 84%; top: 30%; animation-delay: 1.2s; }
.ai-wrap.neural .think-particles i:nth-child(6) { left: 58%; top: 78%; animation-delay: 1.5s; background: #f7d58a; }

/* 输入：胶囊 + 圆形按钮 */
.ai-wrap.neural .ai-options {
  padding: 6px var(--content-pad) 0;
  background: transparent;
  border-top: none;
  max-height: 32vh;
  overflow: auto;
}
.ai-wrap.neural .ai-options label { color: var(--n-sub); font-size: 11px; }
.ai-wrap.neural .ai-options input[type="checkbox"] { accent-color: #8ab4f8; }
.ai-wrap.neural .composer-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 var(--content-pad) 6px;
  color: var(--n-faint);
  font-size: 10px;
}
.ai-wrap.neural .meta-spacer { flex: 1; }
.ai-wrap.neural .demo-flag { color: #c7a6f0; }
.ai-wrap.neural .state-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--n-faint);
  transition: background-color 0.2s ease, box-shadow 0.2s ease;
}
.ai-wrap.neural .dot-listening { background: #8ab4f8; box-shadow: 0 0 0 4px rgba(66, 133, 244, 0.12); }
.ai-wrap.neural .dot-thinking { background: #f0a6d8; animation: neural-dot-pulse 1.4s ease-in-out infinite; }
.ai-wrap.neural .dot-delivering { background: #f7d58a; }
.ai-wrap.neural .composer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 var(--content-pad) 14px;
  padding: 6px 6px 6px 18px;
  border-radius: 999px;
  border: 1px solid var(--n-stroke);
  background: var(--n-panel-strong);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(32px);
  -webkit-backdrop-filter: blur(32px);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.ai-wrap.neural .composer input {
  flex: 1;
  min-width: 0;
  height: 42px;
  border: none;
  outline: none;
  background: transparent;
  color: var(--n-text);
  font-size: 15px;
}
.ai-wrap.neural .composer input::placeholder { color: var(--n-faint); }
.ai-wrap.neural .send-btn {
  width: 42px;
  height: 42px;
  border: none;
  border-radius: 50%;
  background: var(--n-grad);
  color: #fff;
  box-shadow: 0 8px 24px rgba(66, 133, 244, 0.3);
  transition: transform 0.18s cubic-bezier(0.2, 0, 0, 1), filter 0.18s ease;
}
.ai-wrap.neural .send-btn:hover:not(:disabled) { transform: scale(1.04); filter: brightness(1.06); }
.ai-wrap.neural .send-btn:disabled { opacity: 0.4; box-shadow: none; }
.ai-wrap.neural .send-btn.stop { background: linear-gradient(135deg, #9B72CF, #D65AC0); box-shadow: 0 8px 24px rgba(155, 114, 207, 0.3); }
.ai-wrap.neural.state-listening .composer {
  border-color: rgba(138, 180, 248, 0.4);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.28), 0 0 0 1px rgba(138, 180, 248, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.ai-wrap.neural .jump-btn {
  right: calc(var(--content-pad) + 4px);
  bottom: 96px;
  border-color: var(--n-line);
  background: var(--n-panel-strong);
  color: var(--n-text);
  box-shadow: var(--n-shadow);
}
.ai-wrap.neural .ai-guide {
  margin: 10px var(--content-pad) 18px;
  padding: 22px;
  border: 1px solid var(--n-line);
  border-radius: 24px;
  background: var(--n-card);
  backdrop-filter: blur(24px);
}
.ai-wrap.neural .guide-title { color: var(--n-text); }
.ai-wrap.neural .guide-desc { color: var(--n-sub); }
.ai-wrap.neural .guide-link { color: #8ab4f8; }

/* 弹层：深色磨砂面板 */
.ai-wrap.neural .mask { background: rgba(3, 5, 12, 0.66); backdrop-filter: blur(6px); }
.ai-wrap.neural .sheet {
  border: 1px solid var(--n-line);
  background: var(--n-card-solid);
  color: var(--n-text);
  box-shadow: 0 32px 90px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(32px);
  -webkit-backdrop-filter: blur(32px);
}
.ai-wrap.neural .sheet-title { color: var(--n-text); }
.ai-wrap.neural .sheet-head {
  background: var(--n-card-solid);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}
.ai-wrap.neural .sheet-close { border-color: var(--n-line); background: var(--n-panel); color: var(--n-sub); }
.ai-wrap.neural .sheet p,
.ai-wrap.neural .sheet label { color: var(--n-sub); }
.ai-wrap.neural .sheet .card { background: var(--n-panel); border-color: var(--n-line); color: var(--n-text); }
.ai-wrap.neural .hist-row { border-color: var(--n-line); }
.ai-wrap.neural .hist-row.on { background: var(--n-panel); }
.ai-wrap.neural .hist-title { color: var(--n-text); }
.ai-wrap.neural .hist-scene,
.ai-wrap.neural .hist-empty,
.ai-wrap.neural .hist-error { color: var(--n-faint); }
.ai-wrap.neural .hist-ic { color: #8ab4f8; }
.ai-wrap.neural .hist-del { color: var(--n-faint); }
.ai-wrap.neural .hist-sk i { background: rgba(255, 255, 255, 0.08); }
.ai-wrap.neural .task-actions {
  background: rgba(17, 22, 39, 0.9);
  backdrop-filter: blur(12px);
}
.ai-wrap.neural .skeleton-list .sk-ava { background: var(--n-panel); }
.ai-wrap.neural .skeleton-list .sk-lines i { background: rgba(255, 255, 255, 0.08); }

/* 浅色弹层/输入适配 */
.ai-wrap.neural.theme-light .mask { background: rgba(20, 30, 50, 0.35); }
.ai-wrap.neural.theme-light .bubble.answer .md code { background: rgba(23, 32, 51, 0.06); color: #26324a; }
.ai-wrap.neural.theme-light .bubble.answer .md pre { background: #f2f5ff; }
.ai-wrap.neural.theme-light .bubble.answer.delivering::after { background: linear-gradient(105deg, transparent 28%, rgba(255, 255, 255, 0.55) 44%, rgba(214, 90, 192, 0.08) 55%, transparent 72%); }
.ai-wrap.neural.theme-light .caret { background: var(--n-grad); }
.ai-wrap.neural.theme-light .composer { box-shadow: 0 14px 40px rgba(31, 45, 80, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.8); }
.ai-wrap.neural.theme-light .composer-meta { color: var(--n-faint); }
.ai-wrap.neural.theme-light .task-actions { background: rgba(255, 255, 255, 0.9); }
.ai-wrap.neural.theme-light .hist-sk i { background: rgba(23, 32, 51, 0.08); }
.ai-wrap.neural.theme-light .skeleton-list .sk-lines i { background: rgba(23, 32, 51, 0.08); }

/* 动效：先蓄力后释放，微交互 150–300ms，转场 300–500ms */
@keyframes neural-drift {
  0% { background-position: 0% 50%; transform: rotate(0deg) scale(1); }
  50% { background-position: 100% 50%; transform: rotate(5deg) scale(1.06); }
  100% { background-position: 0% 50%; transform: rotate(0deg) scale(1); }
}
@keyframes neural-focus-breathe {
  0%, 100% { opacity: 0.82; transform: scale(0.98); }
  50% { opacity: 1; transform: scale(1.03); }
}
@keyframes neural-spark-breathe {
  0%, 100% { transform: scale(1) rotate(0deg); filter: drop-shadow(0 0 10px rgba(155, 114, 207, 0.42)); }
  50% { transform: scale(1.12) rotate(6deg); filter: drop-shadow(0 0 18px rgba(214, 90, 192, 0.55)); }
}
@keyframes neural-ripple {
  0% { transform: scale(0.7); opacity: 0.6; }
  70% { transform: scale(1.9); opacity: 0; }
  100% { transform: scale(1.9); opacity: 0; }
}
@keyframes neural-particle {
  0%, 100% { transform: translate3d(0, 0, 0) scale(0.8); opacity: 0.25; }
  50% { transform: translate3d(4px, -6px, 0) scale(1.15); opacity: 0.7; }
}
@keyframes neural-ombre-sweep {
  0% { background-position: 180% 0; opacity: 0; }
  20% { opacity: 1; }
  100% { background-position: -80% 0; opacity: 0; }
}
@keyframes neural-caret { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0; } }
@keyframes neural-dot-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(240, 166, 216, 0.28); }
  50% { box-shadow: 0 0 0 5px rgba(240, 166, 216, 0); }
}

@media (prefers-reduced-motion: reduce) {
  .ai-wrap.neural .spectrum-flow,
  .ai-wrap.neural .spectrum-beam,
  .ai-wrap.neural .spectrum-focus,
  .ai-wrap.neural .brand-spark,
  .ai-wrap.neural .think-ripple i,
  .ai-wrap.neural .think-particles i,
  .ai-wrap.neural .dot-thinking,
  .ai-wrap.neural .caret,
  .ai-wrap.neural .hist-loading i { animation: none !important; }
  .ai-wrap.neural .bubble.answer.delivering::after { display: none; }
  .ai-wrap.neural * { transition-duration: 0.01ms !important; }
}
</style>
