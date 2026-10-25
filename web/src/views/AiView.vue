<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles, MessageCircle, Send, Plus, History, Sigma, Cpu,
  PenLine, CalendarClock, RotateCcw, Settings2, Crown, ChevronRight,
} from 'lucide-vue-next'
import { aiApi } from '../api'
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
  const content = input.value.trim()
  if (!content || sending.value) return
  if (blocked.value) return
  if (!enabled.value) {
    toast('AI 未启用，请先在 AI 设置中配置 Key')
    return
  }
  messages.value.push({ role: 'user', content })
  input.value = ''
  sending.value = true
  const reply = { role: 'assistant', content: '', streaming: true }
  messages.value.push(reply)
  scrollBottom()
  try {
    await aiApi.chatStream(
      {
        scene: scene.value,
        content,
        conversation_id: conversationId.value || undefined,
      },
      (evt) => {
        if (evt.type === 'delta') {
          reply.content += evt.text
          scrollBottom()
        } else if (evt.type === 'error') {
          reply.content += (reply.content ? '\n\n' : '') + `出错了：${evt.message}`
        } else if (evt.type === 'done') {
          reply.streaming = false
          reply.prompt_tokens = evt.prompt_tokens
          reply.completion_tokens = evt.completion_tokens
          reply.latency_ms = evt.latency_ms
          if (evt.conversation_id) {
            conversationId.value = evt.conversation_id
            if (evt.title) conversationTitle.value = evt.title
          }
        }
      }
    )
  } catch (e) {
    if (!reply.content) reply.content = `出错了：${e.message}，稍后再试。`
    else reply.content += `\n\n（连接中断：${e.message}）`
  } finally {
    reply.streaming = false
    sending.value = false
    scrollBottom()
  }
}

function newChat(s) {
  if (s) scene.value = s
  conversationId.value = null
  conversationTitle.value = ''
  messages.value = []
  showHistory.value = false
}

async function loadHistory() {
  try {
    historyList.value = await aiApi.conversations()
    showHistory.value = true
  } catch (e) {
    toast(e.message)
  }
}

async function openConversation(id) {
  try {
    const data = await aiApi.conversation(id)
    conversationId.value = data.id
    conversationTitle.value = data.title
    scene.value = data.scene || 'general'
    messages.value = (data.messages || []).map((m) => ({
      role: m.role, content: m.content,
      prompt_tokens: m.prompt_tokens, completion_tokens: m.completion_tokens,
      latency_ms: m.latency_ms,
    }))
    showHistory.value = false
    scrollBottom()
  } catch (e) {
    toast(e.message)
  }
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
    await auth.fetchMe().catch(() => {})
    const cfg = await aiApi.enabled()
    enabled.value = cfg.enabled
    access.value = cfg.access !== false
    if (access.value) {
      const k = await aiApi.key()
      keyReady.value = !!k.configured
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

    <div v-if="blocked" class="ai-guide">
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

    <div v-else ref="scrollEl" class="chat-scroll">
      <div v-if="!messages.length" class="chat-empty">
        <div class="empty-badge"><Sparkles :size="26" /></div>
        <div class="empty-title">{{ scenes.find((x) => x.key === scene)?.label }}</div>
        <div class="empty-desc">{{ welcome }}</div>
      </div>
      <div v-for="(m, i) in messages" :key="i" class="chat-msg" :class="m.role">
        <div v-if="m.role === 'assistant'" class="msg-ava"><Sparkles :size="16" /></div>
        <div class="msg-main">
          <div class="bubble">{{ m.content }}<span v-if="m.streaming" class="caret">▍</span></div>
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

    <div v-if="!blocked" class="composer">
      <input
        v-model="input"
        :placeholder="enabled ? '输入你的问题…' : 'AI 未启用'"
        maxlength="4000"
        @keyup.enter="send"
      />
      <button class="send-btn" :disabled="sending || !input.trim()" @click="send">
        <Send :size="18" />
      </button>
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

.chat-scroll { flex: 1; overflow-y: auto; padding: 6px 16px 12px; }
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
