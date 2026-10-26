<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles, MessageCircle, Send, Plus, History, Sigma, Cpu,
  PenLine, CalendarClock, RotateCcw, Settings2, Crown, ChevronRight,
} from 'lucide-vue-next'
import { aiApi, attachmentApi } from '../api'
import { syncNow, waitForSync } from '../sync/engine'
import { db, uid, activeAccountId } from '../db'
import BlobImage from '../components/BlobImage.vue'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

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
onBeforeUnmount(() => { alive = false; conversationGeneration++; controller?.abort() })

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

async function scrollBottom() {
  await nextTick()
  if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight
}

const blocked = computed(() => {
  if (!access.value) return 'vip'
  if (!keyReady.value) return 'key'
  return ''
})

async function send() {
  const content = input.value.trim() || (attachments.value.length ? '请分析这些题目图片，并讲解思路与易错点。' : '')
  if (!content || sending.value || loadingConversation.value || blocked.value) return
  if (!enabled.value) return toast('AI未启用，请先配置Key')
  if (attachments.value.some((row) => !row.key)) return toast('有图片尚未上传成功，请重试或移除该图片')
  const selected = [...attachments.value]
  const imageKeys = selected.map((row) => row.key)
  input.value = ''; attachments.value = []
  messages.value.push({ role: 'user', content, image_keys: imageKeys })
  sending.value = true
  const reply = reactive({ role: 'assistant', content: '', streaming: true, tools: [], sources: [] })
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
        if (evt.type === 'delta') { reply.content += evt.text; scrollBottom() }
        else if (evt.type === 'error') {
          failed = true
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
      failed = true
      reply.content += `\n请求未完成：${e.message}`
    }
  } finally {
    reply.streaming = false
    sending.value = false
    if (failed && alive) {
      if (!input.value) input.value = content
      if (!attachments.value.length) attachments.value = selected
    }
    if (completed && alive && activeAccountId() === accountAtSend) await db.kv.delete('ai:draft')
    scrollBottom()
  }
}

function newChat(s) {
  if (sending.value) return
  conversationGeneration++; loadingConversation.value = false
  taskPreview.value = null
  if (s) scene.value = s
  conversationId.value = null
  conversationTitle.value = ''
  messages.value = []
  showHistory.value = false
}

async function loadHistory() {
  const generation = conversationGeneration
  try {
    const rows = await aiApi.conversations()
    if (!alive || generation !== conversationGeneration) return
    historyList.value = rows
    showHistory.value = true
  } catch (e) {
    toast(e.message)
  }
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
    scrollBottom()
  } catch (e) {
    if (alive && generation === conversationGeneration) toast(e.message)
  } finally { if (generation === conversationGeneration) loadingConversation.value = false }
}

async function removeConversation(id) {
  try {
    await aiApi.deleteConversation(id)
    historyList.value = historyList.value.filter((c) => c.id !== id)
    if (conversationId.value === id) newChat()
  } catch (e) {
    toast(e.message)
  }
}

onMounted(async () => {
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
    const draft = await db.kv.get('ai:draft')
    if (draft?.value) {
      input.value = draft.value.content || ''
      attachments.value = (draft.value.images || []).slice(0, 4).map((image) => ({ id: uid(),
        key: typeof image === 'string' ? image : '', blob: typeof image === 'string' ? null : image,
        uploading: false, error: '' }))
    }
    const sc = await aiApi.scenes()
    if (Array.isArray(sc) && sc.length) {
      const iconMap = {
        general: MessageCircle, kaoyan: Cpu, essay: PenLine,
        plan: CalendarClock, review: RotateCcw,
      }
      scenes.value = sc.map((x) => ({ ...x, icon: iconMap[x.key] || Sparkles }))
    }
  } catch {
    enabled.value = false
  }
})
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
  <div class="ai-wrap">
    <div class="nav ai-nav">
      <div>
        <div class="nav-title">AI 助教</div>
        <div class="nav-sub">{{ conversationTitle || '考研专项答疑' }}</div>
      </div>
      <div class="nav-actions">
        <button class="icon-btn" title="AI 设置" @click="router.push('/ai/settings')"><Settings2 :size="19" /></button>
        <button class="icon-btn" @click="newChat()"><Plus :size="19" /></button>
        <button class="icon-btn" @click="loadHistory"><History :size="19" /></button>
      </div>
    </div>

    <div class="scene-bar">
      <button
        v-for="s in scenes"
        :key="s.key"
        class="scene-chip"
        :class="{ on: s.key === scene && !conversationId }"
        @click="newChat(s.key)"
      >
        <component :is="s.icon" :size="14" />{{ s.label }}
      </button>
    </div>

    <div v-if="blocked && !messages.length" class="ai-guide">
      <div class="guide-badge"><Crown :size="26" /></div>
      <div class="guide-title">
        {{ blocked === 'vip' ? 'AI 需要 VIP 或审批授权' : '还差一步：配置你的 API Key' }}
      </div>
      <div class="guide-desc">
        <template v-if="blocked === 'vip'">
          AI 问答需要 VIP 权限，或申请「AI 问答权限」并通过审批；使用时可填写你自己的模型 API Key，站内不会保存明文。
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
      <button v-else class="btn btn-primary btn-block" @click="router.push('/ai/settings')">
        <Settings2 :size="17" />去配置 Key
      </button>
      <button class="guide-link" @click="router.push('/requests')">
        没有邀请码？提交功能申请<ChevronRight :size="15" />
      </button>
    </div>

    <p v-if="loadingConversation" class="msg-usage" role="status">正在读取所选对话，请稍候…</p>
    <p v-if="blocked && messages.length" class="msg-usage" style="padding:8px 16px">历史记录可继续查看；恢复权限并配置可用Key后才能发送新消息。</p>
    <div v-if="!blocked || messages.length" ref="scrollEl" class="chat-scroll">
      <div v-if="!messages.length && !blocked" class="chat-empty">
        <div class="empty-badge"><Sparkles :size="26" /></div>
        <div class="empty-title">{{ scenes.find((x) => x.key === scene)?.label }}</div>
        <div class="empty-desc">{{ welcome }}</div>
      </div>
      <div v-for="(m, i) in messages" :key="i" class="chat-msg" :class="m.role">
        <div v-if="m.role === 'assistant'" class="msg-ava"><Sparkles :size="16" /></div>
        <div class="msg-main">
          <div v-if="m.image_keys?.length" class="ai-images"><BlobImage v-for="key in m.image_keys" :key="key" :src="key" alt="题目图片" /></div>
          <div class="bubble">{{ m.content }}<span v-if="m.streaming" class="caret">▍</span></div>
          <button v-if="access && m.id && m.suggested_tasks?.length && !m.streaming && (!m.task_import || m.task_import.state==='not_imported')" class="btn btn-outline" @click="previewTasks(m)">一键导入为系统任务</button>
          <div v-if="m.id && m.task_import?.state === 'imported'" class="msg-usage">已导入 {{m.task_import.imported_count}} 项任务 <button class="btn btn-outline" :disabled="importing" @click="undoTasks(m)">撤销本次导入</button></div>
          <div v-if="m.task_import?.state === 'undone'" class="msg-usage">已撤销 {{m.task_import.undo?.deleted}} 项；保留 {{m.task_import.undo?.kept?.length}} 项（已修改、完成或删除）</div>
          <div v-if="!blocked && m.id && m.role==='assistant' && !m.streaming && !m.suggested_tasks?.length" class="msg-usage">此回复未包含有效的可导入任务。<button class="btn btn-outline" :disabled="sending" @click="regenerateTasks(m)">生成可导入任务</button></div>
          <div v-if="m.tools?.length" class="msg-usage">已调用：{{ m.tools.map(t => `${t.name}${t.status === 'failed' ? '（失败）' : ''}`).join('、') }}</div>
          <div v-if="m.sources?.length" class="ai-sources"><a v-for="source in m.sources" :key="source.url" :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title || '查看来源' }}</a></div>
          <div v-if="m.role === 'assistant' && (m.completion_tokens || m.latency_ms)" class="msg-usage">
            <template v-if="m.prompt_tokens || m.completion_tokens">
              {{ (m.prompt_tokens || 0) + (m.completion_tokens || 0) }} tokens
            </template>
            <template v-if="m.prompt_tokens || m.completion_tokens"> · </template>
            {{ ((m.latency_ms || 0) / 1000).toFixed(1) }}s
          </div>
        </div>
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
    <div v-if="!blocked" class="composer">
      <input
        v-model="input"
        :placeholder="enabled ? '输入你的问题…' : 'AI 未启用'"
        maxlength="4000"
        @keyup.enter="send"
      />
      <button class="send-btn" :aria-busy="loadingConversation" :disabled="sending || (!input.trim() && !attachments.length)" @click="send">
        <Send :size="18" />
      </button>
    </div>

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
      <div class="sheet">
        <div class="sheet-title">历史对话</div>
        <div v-if="!historyList.length" class="hist-empty">还没有历史对话</div>
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
.task-actions{position:sticky;bottom:0;background:white;padding:12px 0;display:flex;gap:8px;z-index:2}

.ai-options { padding: 4px 16px; background: white; max-height: 32vh; overflow: auto; }
.ai-options label { font-size: 12px; margin: 4px 8px; display: inline-flex; align-items: center; gap: 4px; }
.ai-images { display: flex; gap: 8px; flex-wrap: wrap; margin: 6px 0; }
.ai-images img { width: 80px; height: 70px; object-fit: contain; border: 1px solid var(--line); border-radius: 6px; }
.ai-images button, .ai-images small { display: block; font-size: 11px; }
.ai-sources a { display: block; font-size: 12px; padding: 4px 0; word-break: break-all; }

.ai-wrap {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  background: var(--bg, #f5f7fb);
  z-index: 10;
}
.ai-nav { display: flex; align-items: center; justify-content: space-between; }
.nav-actions { display: flex; gap: 8px; }
.icon-btn { width: 38px; height: 38px; border-radius: 11px; border: 1px solid var(--line); background: #fff; color: var(--sub); display: flex; align-items: center; justify-content: center; cursor: pointer; }

.scene-bar { display: flex; gap: 8px; padding: 4px 16px 10px; overflow-x: auto; }
.scene-chip { flex-shrink: 0; display: inline-flex; align-items: center; gap: 5px; border: 1px solid var(--line); background: #fff; color: var(--sub); border-radius: 999px; padding: 7px 14px; font-size: 13px; cursor: pointer; }
.scene-chip.on { background: var(--primary); border-color: var(--primary); color: #fff; }

.chat-scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 6px 16px 12px; }
.chat-empty { text-align: center; padding: 48px 20px; }
.empty-badge { width: 60px; height: 60px; margin: 0 auto 16px; border-radius: 18px; background: linear-gradient(135deg, #7c3aed, #5b21b6); color: #fff; display: flex; align-items: center; justify-content: center; box-shadow: 0 10px 24px rgba(124,58,237,.4); }
.empty-title { font-size: 18px; font-weight: 800; }
.empty-desc { margin-top: 8px; font-size: 13px; color: var(--sub); line-height: 1.7; }

.chat-msg { display: flex; gap: 9px; margin-bottom: 14px; }
.chat-msg.user { justify-content: flex-end; }
.msg-ava { width: 32px; height: 32px; border-radius: 10px; background: linear-gradient(135deg, #7c3aed, #5b21b6); color: #fff; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.bubble { max-width: 78%; padding: 10px 13px; border-radius: 14px; font-size: 14px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; box-shadow: var(--shadow-soft); }
.chat-msg.assistant .bubble { background: #fff; border-top-left-radius: 4px; }
.chat-msg.user .bubble { background: var(--primary); color: #fff; border-top-right-radius: 4px; }
.caret { display: inline-block; margin-left: 1px; color: var(--primary); animation: blink 1s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.msg-main { display: flex; flex-direction: column; min-width: 0; max-width: 78%; }
.msg-main .bubble { max-width: 100%; }
.msg-usage { font-size: 10.5px; color: var(--faint); margin-top: 4px; padding-left: 2px; }

.ai-guide {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 26px 30px 40px;
  text-align: center;
}
.guide-badge {
  width: 56px;
  height: 56px;
  border-radius: 17px;
  background: #fff3df;
  color: var(--accent-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 14px;
}
.guide-title { font-size: 17px; font-weight: 800; color: var(--ink); }
.guide-desc { font-size: 12.5px; color: var(--sub); line-height: 1.75; margin: 9px 0 18px; max-width: 320px; }
.guide-link {
  margin-top: 12px;
  border: none;
  background: none;
  color: var(--primary);
  font-size: 12.5px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
}

.composer { display: flex; gap: 9px; padding: 10px 16px calc(12px + env(safe-area-inset-bottom)); border-top: 1px solid var(--line); background: #fff; }
.composer input { flex: 1; height: 46px; border: 1px solid var(--line); border-radius: 999px; padding: 0 18px; font-size: 15px; background: #fafbfe; }
.composer input:focus { outline: none; border-color: var(--primary); background: #fff; }
.send-btn { width: 46px; height: 46px; border-radius: 50%; border: none; background: var(--primary); color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }
.send-btn:disabled { opacity: 0.5; }

.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); max-height: 70vh; overflow-y: auto; }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; margin-bottom: 12px; }
.hist-empty { text-align: center; color: var(--faint); font-size: 13px; padding: 24px 0; }
.hist-row { display: flex; align-items: center; gap: 11px; padding: 13px 6px; border-bottom: 1px solid var(--line); cursor: pointer; }
.hist-row.on { background: #f2f7fd; border-radius: 10px; }
.hist-ic { color: var(--primary); flex-shrink: 0; }
.hist-meta { flex: 1; min-width: 0; }
.hist-title { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hist-scene { font-size: 11.5px; color: var(--faint); margin-top: 2px; }
.hist-del { border: none; background: none; color: var(--faint); font-size: 20px; cursor: pointer; padding: 0 6px; }
</style>
