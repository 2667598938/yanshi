<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles, MessageCircle, Send, Plus, History, Sigma, Cpu,
  PenLine, CalendarClock, RotateCcw, Settings2, Crown, ChevronRight, Square, ArrowDown,
  Copy, RefreshCw, X, Moon, Sun, Monitor, ArrowLeft, Play,
} from 'lucide-vue-next'
import { aiApi, attachmentApi } from '../api'
import { renderMarkdown } from '../utils/markdown'
import { syncNow, waitForSync } from '../sync/engine'
import { db, uid, activeAccountId } from '../db'
import BlobImage from '../components/BlobImage.vue'
import CopyFallback from '../components/CopyFallback.vue'
import AiAnswer from '../components/AiAnswer.vue'
import { useAuthStore } from '../stores/auth'
import { useSubjectsStore } from '../stores/subjects'
import { useTasksStore } from '../stores/tasks'
import { useToast } from '../composables/useToast'
import { useClipboard } from '../composables/useClipboard'

const router = useRouter()
const auth = useAuthStore()
const subjects = useSubjectsStore()
const tasksStore = useTasksStore()
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
const taskEdits = ref([])
const contextWarning = ref('')
const retryingSync = ref(false)
const showVisualDemo = import.meta.env.DEV && new URLSearchParams(location.search).has('visual_demo')
const importSubjects = computed(() => {
  const rows = subjects.active || []
  return rows.some(s => s.id === 'other') ? rows : [...rows, { id: 'other', name: '其他' }]
})
const importDays = computed(() => {
  const result = new Map()
  for (const i of taskSelection.value) {
    const t = taskEdits.value[i]
    if (t) result.set(t.due_date || '', (result.get(t.due_date || '') || 0) + Number(t.estimated_min || 0))
  }
  return [...result].map(([day, minutes]) => ({ day, minutes,
    existing: (tasksStore.open || []).filter(t => (t.dueDate || '') === day).reduce((a,t)=>a+(t.estimatedMin||0),0) }))
})
const useTools = ref(false)
const useSearch = ref(false)
let controller
let alive = true
let conversationGeneration = 0
const loadingConversation = ref(false)

// ===== Neural Expressive 状态机 =====
// idle：进入页面 / 新建对话 / 停止生成 / 生成完成 900ms 后且输入为空
// listening：输入框获得焦点或输入非空；光谱指针移到输入框
// thinking：点发送后、第一个流式片段到达前；四星芒形变 + 涟漪 + 粒子（模拟按钮在独立演示页）
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
const motionMedia = window.matchMedia?.('(prefers-reduced-motion: reduce)')
const colorMedia = window.matchMedia?.('(prefers-color-scheme: light)')
const reducedMotion = ref(motionMedia?.matches ?? false)
const pagePaused = ref(document.hidden)
const visibleHeight = ref(window.visualViewport?.height || window.innerHeight)
const bottomGap = ref('calc(68px + env(safe-area-inset-bottom))')
function motionChanged(event) { reducedMotion.value = event.matches }
function visibilityChanged() { pagePaused.value = document.hidden }
function viewportChanged() {
  visibleHeight.value = window.visualViewport?.height || window.innerHeight
  bottomGap.value = window.innerHeight - visibleHeight.value > 140 ? '0px' : 'calc(68px + env(safe-area-inset-bottom))'
  updateFocusPoint()
}
const stateLabel = computed(() => ({
  idle: '准备好了', listening: '正在输入', thinking: '正在思考', delivering: '正在输出',
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
    else if (visualState.value === 'delivering') el = [...wrap.querySelectorAll('.chat-msg.assistant .bubble')].at(-1)
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
  window.visualViewport?.removeEventListener('resize', viewportChanged)
  motionMedia?.removeEventListener('change', motionChanged)
  colorMedia?.removeEventListener('change', syncAppChrome)
  document.removeEventListener('visibilitychange', visibilityChanged)
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
function resizeComposer() {
  const el = composerEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.max(40, Math.min(el.scrollHeight, 144)) + 'px'
}
function onComposerKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    send()
  }
}
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
// Retry appends a new attempt, matching persistent history after reload.
async function retry(m) {
  if (sending.value) return
  const index = messages.value.indexOf(m)
  const prev = messages.value[index - 1]
  if (index < 0 || !prev || prev.role !== 'user') return toast('未找到对应的问题')
  toast('保留上次中断的回答，正在追加一次重试')
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
    const synced = await syncNow()
    contextWarning.value = synced === true ? '' : '学习数据未完整同步，本次回答可能没有包含你刚做的修改。可以重试同步后重新提问。'
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
          if (evt.message_id) reply.id = evt.message_id
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
      // 生成期间可以编辑下一问，完成当前回答不能把下一问的草稿一起删掉。
      if (!input.value.trim() && !attachments.value.length) await db.kv.delete('ai:draft')
      historyFetched.value = false
      loadDesktopHistory()
    }
    if (atBottom.value) scrollBottom()
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
function changeScene(s) {
  if (sending.value || loadingConversation.value) return
  scene.value = s
}
async function retryContextSync() {
  if (retryingSync.value) return
  retryingSync.value = true
  try {
    await waitForSync()
    contextWarning.value = await syncNow() === true
      ? '同步已恢复；已有回答可能基于旧摘要，请重新提问以使用最新数据。'
      : '同步仍未完成，账号摘要可能不是最新。'
  } finally { retryingSync.value = false }
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
      failed: !!m.failed, aborted: !!m.aborted,
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
  motionMedia?.addEventListener('change', motionChanged)
  colorMedia?.addEventListener('change', syncAppChrome)
  document.addEventListener('visibilitychange', visibilityChanged)
  window.visualViewport?.addEventListener('resize', viewportChanged)
  viewportChanged()
  await loadConfig()
  if (!alive) return
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
  nextTick(resizeComposer)
  if (sending.value) return
  visualState.value = value.trim() ? 'listening' : (document.activeElement === composerEl.value ? 'listening' : 'idle')
  updateFocusPoint()
})
watch(visualState, () => updateFocusPoint())
function previewTasks(message){
 taskSelection.value=message.suggested_tasks.map((_,i)=>i)
 taskEdits.value=message.suggested_tasks.map((task,index)=>{
  const match=importSubjects.value.find(s=>s.id===task.subject_id)||importSubjects.value.find(s=>s.name===task.subject_id)
  return {due_date:'',estimated_min:0,accept_criteria:'',...task,index,subject_id:match?.id||'other'}
 })
 taskPreview.value=message
}
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
  const edits=selected.map(i=>({...taskEdits.value[i]}))
  if(edits.some(t=>!t.title.trim()||!Number.isInteger(t.estimated_min)||t.estimated_min<0||t.estimated_min>1440))throw new Error('请检查任务标题和预计分钟（0–1440的整数）')
  const result=await aiApi.importTasks(message.id,selected,edits)
  message.task_import=result
  if(taskPreview.value===message)taskPreview.value=null
  await waitForSync();const synced=await syncNow()
  if(synced===true)toast('任务已导入，可在任务清单查看；重复确认不会重复新增')
  else{
   contextWarning.value='任务已保存到云端，本机同步未完成。请重试同步后查看任务清单，不要重复导入。'
   toast('任务已导入云端；本机尚未同步，请重试同步')
  }
 }catch(e){toast(e.message)}finally{importing.value=false}
}
</script>

<template>
  <div
    ref="aiWrapEl"
    class="ai-wrap neural"
    :class="['theme-' + theme, 'state-' + visualState, { 'has-sheet': showHistory || taskPreview, 'is-empty': !messages.length, 'reduce-motion': reducedMotion, 'is-paused': pagePaused }]"
    :style="{ '--focus-x': focusX, '--focus-y': focusY, '--ai-visible-height': visibleHeight + 'px', '--ai-bottom-gap': bottomGap }"
  >
    <div class="neural-bg" aria-hidden="true">
      <div class="spectrum-flow"></div>
      <div class="spectrum-tail"></div>
      <div class="spectrum-beam"></div>
      <div class="spectrum-focus"></div>
    </div>
    <CopyFallback v-model="manualCopy" />
    <aside class="ai-history-panel" aria-label="会话列表">
      <div class="ai-history-heading"><strong>我的对话</strong><button class="icon-btn" title="刷新会话列表" aria-label="刷新会话列表" @click="loadHistory(false)"><History :size="16" /></button></div>
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

    <div class="ai-workspace">
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
        <button class="icon-btn" title="AI 设置" aria-label="AI 设置" @click="router.push('/ai/settings')"><Settings2 :size="18" /></button>
        <button class="icon-btn" title="新建对话" aria-label="新建对话" @click="newChat()"><Plus :size="18" /></button>
        <button class="icon-btn history-trigger" title="历史对话" aria-label="历史对话" @click="loadHistory()"><History :size="18" /></button>
        <button class="icon-btn" :title="`主题：${themeLabel}（点击切换）`" :aria-label="`切换主题，当前：${themeLabel}`" @click="cycleTheme"><component :is="themeIcon" :size="17" /></button>
        <a v-if="showVisualDemo" class="icon-btn" href="/previews/ai-neural.html" target="_blank" rel="noopener" title="视觉动效演示" aria-label="打开视觉动效演示"><Play :size="17" /></a>
      </div>
    </div>

    <div class="scene-bar">
      <button
        v-for="s in scenes"
        :key="s.key"
        class="scene-chip"
        :class="{ on: s.key === scene }"
        :aria-pressed="s.key === scene"
        :title="`在当前对话中切换为${s.label}，保留聊天上下文`"
        :disabled="sending"
        @click="changeScene(s.key)"
      >
        <component :is="s.icon" :size="13" />{{ s.label }}
      </button>
    </div>

    <div v-if="contextWarning" class="context-warning" role="status">{{contextWarning}} <button :disabled="retryingSync || sending" @click="retryContextSync">{{retryingSync?'同步中…':'重试同步'}}</button></div>

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
          AI 问答需要 VIP 权限，或申请「AI 问答权限」并通过审批；获得权限后仍须填写本人的模型 API Key，密钥在服务端加密保存。
        </template>
        <template v-else-if="blocked === 'error'">
          {{ configError }}。网络恢复后点下方重新连接，不会影响已有历史对话。
        </template>
        <template v-else>
          你已获得 AI 权限。前往 AI 设置填写自己的 API Key，即可开始对话；密钥在服务端加密保存，不向组员共享。
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
        <a v-if="showVisualDemo" class="empty-demo" href="/previews/ai-neural.html" target="_blank" rel="noopener" title="打开独立动效演示">
          <Play :size="13" />看动效演示 <span>thinking → delivering</span>
        </a>
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
            <AiAnswer v-if="m.role === 'assistant' && m.content" :content="m.content" :streaming="m.streaming" :reduced="reducedMotion" />
            <div v-else-if="m.content" class="md" v-html="renderMarkdown(m.content)"></div>
            <span v-if="m.streaming" class="caret">▍</span>
          </div>
          <div v-if="m.failed || m.aborted" class="msg-usage retry-row">
            {{ m.aborted ? '已停止生成' : '回复中断，可重试' }}
            <button class="btn btn-outline btn-sm" :disabled="sending" @click="retry(m)">重试</button>
          </div>
          <button v-if="access && m.id && m.suggested_tasks?.length && !m.streaming && (!m.task_import || m.task_import.state==='not_imported')" class="btn btn-outline" @click="previewTasks(m)">一键导入为系统任务</button>
          <div v-if="m.id && m.task_import?.state === 'imported'" class="msg-usage">已导入 {{m.task_import.imported_count}} 项任务 <button class="btn btn-outline" :disabled="importing" @click="undoTasks(m)">撤销本次导入</button></div>
          <div v-if="m.task_import?.state === 'undone'" class="msg-usage">已撤销 {{m.task_import.undo?.deleted}} 项；保留 {{m.task_import.undo?.kept?.length}} 项（已修改、完成或删除）</div>
          <div v-if="!blocked && m.id && m.role==='assistant' && !m.streaming && !m.failed && !m.aborted && !m.suggested_tasks?.length" class="msg-usage"><button class="act-btn" :disabled="sending" @click="regenerateTasks(m)">将建议转为练习任务</button></div>
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
          <p>结合你的问题与本人已同步学习摘要…</p>
        </div>
        <div class="think-ripple" aria-hidden="true"><i></i><i></i></div>
        <div class="think-particles" aria-hidden="true"><i v-for="n in 6" :key="n"></i></div>
      </div>
    </div>

    <div v-if="!blocked" class="composer-dock">
    <details class="ai-options">
      <summary>本人学习摘要 · 私密对话<span>题图与数据说明</span></summary>
      <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" multiple style="display:none" @change="pickImages" />
      <button class="btn btn-outline btn-sm" :disabled="sending || !features.vision" @click="fileInput?.click()">添加题图（最多4张）</button>
      <label v-if="!features.v1_readonly"><input v-model="useTools" type="checkbox" :disabled="sending || !features.tools || !features.model_tools" />只读学习工具</label>
      <label v-if="!features.v1_readonly"><input v-model="useSearch" type="checkbox" :disabled="sending || !features.search || !features.model_tools" />联网搜索</label>
      <div class="msg-usage">会向你选择的模型服务商发送本人已同步的任务、专注统计、少量错题文本和考试节点摘要，可能省略明细；不会读取组员或操控页面。聊天和密钥仅本人可见。</div>
      <div v-if="!features.model_vision" class="msg-usage">图片需在AI设置中确认模型支持；也可移除图片仅发送文字。</div>
      <div v-if="useTools || useSearch" class="msg-usage">工具模式等待完整结果；仅读取本人已同步数据，最多3次模型请求，不修改学习记录。联网时关键词会发送给搜索服务。</div>
      <div class="ai-images"><div v-for="row in attachments" :key="row.id">
        <BlobImage :blob="row.key ? null : row.blob" :src="row.key" alt="待发送题图" />
        <button :disabled="sending || row.uploading" @click="attachments = attachments.filter(x => x.id !== row.id)">移除</button>
        <button v-if="!row.key" :disabled="row.uploading" @click="uploadRow(row)">{{ row.uploading ? '上传中' : '上传/重试' }}</button>
        <small v-if="row.error">{{ row.error }}</small>
      </div></div>
    </details>
    <div v-if="!blocked" class="composer-meta">
      <span class="state-dot" :class="'dot-' + visualState"></span>
      {{ stateLabel }}
      <span class="meta-spacer"></span>
      <span>Enter 发送 · Shift+Enter 换行</span>
    </div>
    <div v-if="!blocked" class="composer">
      <textarea
        ref="composerEl"
        v-model="input"
        aria-label="向 AI 助教提问"
        :placeholder="enabled ? '输入你的问题…' : 'AI 未启用'"
        maxlength="4000"
        rows="1"
        @focus="onComposerFocus"
        @blur="onComposerBlur"
        @keydown="onComposerKeydown"
      />
      <button v-if="sending" class="send-btn stop" title="停止生成" @click="stopGeneration">
        <Square :size="15" fill="currentColor" />
      </button>
      <button v-else class="send-btn" aria-label="发送问题" :aria-busy="loadingConversation" :disabled="sending || loadingConversation || (!input.trim() && !attachments.length)" @click="send">
        <Send :size="18" />
      </button>
    </div>
    </div>

    <!-- 向上翻看历史时提供回底 -->
    <button v-if="!atBottom && messages.length" class="jump-btn" @click="scrollBottom">
      <ArrowDown :size="16" />回到底部
    </button>
    </div>

    <div v-if="taskPreview" class="mask" @click.self="!importing && (taskPreview=null)">
      <div class="sheet" style="max-height:75vh;overflow:auto">
        <div class="sheet-title">导入任务前请确认</div>
        <p>下列任务将写入你的任务清单，并遵循小组共享与隐私模式规则。同一回复只能确认一组选项；撤销后不能再次导入这批任务。如需补充或重导，请重新向AI生成清单。</p>
        <p>可以先修正内容再确认。未设日期的任务保留在“其他待办”；同一回复只能导入一次。</p>
        <div v-for="(task,i) in taskEdits" :key="i" class="card import-task-editor">
          <label><input v-model="taskSelection" type="checkbox" :value="i" :disabled="importing" /> 导入第{{i+1}}项</label>
          <label>标题<input v-model="task.title" class="input" maxlength="200" :disabled="importing" /></label>
          <label>科目<select v-model="task.subject_id" class="select" :disabled="importing"><option v-for="s in importSubjects" :key="s.id" :value="s.id">{{s.name}}</option></select></label>
          <label>截止日期（可不设）<input v-model="task.due_date" class="input" type="date" :disabled="importing" /></label>
          <label>预计分钟<input v-model.number="task.estimated_min" class="input" type="number" min="0" max="1440" step="1" :disabled="importing" /></label>
          <label>做完的标准<textarea v-model="task.accept_criteria" class="input" maxlength="500" :disabled="importing"></textarea></label>
        </div>
        <div class="import-load"><p v-for="day in importDays" :key="day.day">{{day.day || '未设日期'}}：本次 {{day.minutes}} 分钟，已有待办 {{day.existing}} 分钟，合计 {{day.minutes+day.existing}} 分钟。<strong v-if="day.minutes+day.existing>480">任务较多，请结合可用时间调整。</strong></p></div>
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
.context-warning {padding:10px 16px;margin:4px 12px;border-radius:12px;background:var(--ai-panel,rgba(140,130,90,.15));font-size: 14px;line-height:1.7;color:inherit}
.context-warning button {margin-left:8px;color:inherit;text-decoration:underline;background:transparent;border:0;cursor:pointer}
.import-task-editor {padding:14px;margin:10px 0}.import-task-editor label {display:block;margin:8px 0;font-size: 14px}
.import-load {font-size: 14px;line-height:1.7}.import-load strong{color:var(--tomato)}
</style>
<style src="../assets/styles/ai-neural.css"></style>
