<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, KeyRound, RefreshCw, Save, Trash2, Crown, ChevronRight,
} from 'lucide-vue-next'
import { aiApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useToast } from '../composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

const PROVIDERS = [
  { id: 'deepseek', label: 'DeepSeek', base: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
  { id: 'moonshot', label: 'Kimi', base: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { id: 'zhipu', label: '智谱 GLM', base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
  { id: 'siliconflow', label: '硅基流动', base: 'https://api.siliconflow.cn/v1', model: 'Qwen/Qwen2.5-7B-Instruct' },
  { id: 'openai', label: 'OpenAI', base: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { id: 'custom', label: '自定义', base: '', model: '' },
]

const provider = ref('deepseek')
const baseUrl = ref('https://api.deepseek.com/v1')
const apiKey = ref('')
const model = ref('deepseek-chat')
const supportsImages = ref(false)
const supportsTools = ref(false)
const status = ref(null)
const models = ref([])
const fetching = ref(false)
const saving = ref(false)
const deleting = ref(false)
const loading = ref(true)
const usage = ref(null)
const contextTurns = ref(10)

async function saveContext() {
  try {
    await aiApi.preferences({ context_turns: Number(contextTurns.value) })
    toast('上下文轮数已保存')
  } catch (e) { toast(e.message) }
}

const isVip = computed(() => auth.isVip)
const canUse = ref(false)
const configured = computed(() => !!status.value?.configured)
const currentProvider = computed(() => PROVIDERS.find((p) => p.id === provider.value))

function pickProvider(p) {
  provider.value = p.id
  baseUrl.value = p.base || ''
  model.value = p.model || ''
  models.value = p.model ? [{ id: p.model }] : []
  supportsImages.value = false
  supportsTools.value = false
}

async function load() {
  try {
    const cfg = await aiApi.enabled().catch(() => null)
    canUse.value = cfg ? !!cfg.access : isVip.value
    if (!canUse.value) return
    status.value = await aiApi.key()
    usage.value = await aiApi.usage()
    contextTurns.value = usage.value.context_turns
    if (status.value.configured) {
      provider.value = status.value.provider || 'deepseek'
      baseUrl.value = status.value.base_url || ''
      model.value = status.value.model || ''
      supportsImages.value = !!status.value.supports_images
      supportsTools.value = !!status.value.supports_tools
    }
  } catch (e) {
    if (e.status !== 403) toast(e.message)
  } finally {
    loading.value = false
  }
}

async function fetchModels() {
  if (!apiKey.value.trim() && !configured.value) return toast('请先填写 API Key')
  fetching.value = true
  try {
    const data = await aiApi.models({
      provider: provider.value,
      base_url: baseUrl.value.trim(),
      api_key: apiKey.value.trim(),
    })
    const details = new Map((data.details || []).map(item => [item.id, item]))
    models.value = (data.models || []).map((id) => ({ id, ...details.get(id) }))
    if (data.fallback) {
      toast('未拉取到模型列表，可手动填写模型名')
    } else {
      toast(`${data.cached ? '使用24小时缓存' : '已拉取'} ${models.value.length} 个模型`)
    }
    if (!model.value && models.value.length) model.value = models.value[0].id
  } catch (e) {
    toast(e.message)
  } finally {
    fetching.value = false
  }
}

async function save() {
  if (!apiKey.value.trim()) return toast(configured.value ? '修改请重新输入完整 Key' : '请填写 API Key')
  if (!baseUrl.value.trim()) return toast('请填写服务商地址')
  if (!model.value.trim()) return toast('请选择或填写模型名')
  saving.value = true
  try {
    status.value = await aiApi.saveKey({
      provider: provider.value,
      base_url: baseUrl.value.trim(),
      model: model.value.trim(),
      supports_images: supportsImages.value,
      supports_tools: supportsTools.value,
      api_key: apiKey.value.trim(),
    })
    apiKey.value = ''
    toast('已保存，Key 已加密')
  } catch (e) {
    toast(e.message)
  } finally {
    saving.value = false
  }
}

async function removeKey() {
  if (!confirm('删除 AI Key？删除后 AI 功能将停用，历史对话保留。')) return
  deleting.value = true
  try {
    status.value = await aiApi.deleteKey()
    toast('已删除')
  } catch (e) {
    toast(e.message)
  } finally {
    deleting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">AI 设置</div>
    </div>

    <div class="page">
      <div v-if="loading" class="empty">读取中…</div>

      <div v-else-if="!canUse" class="card guide">
        <div class="guide-badge"><Crown :size="24" /></div>
        <div class="guide-title">AI 需要 VIP 或审批授权</div>
        <div class="guide-desc">开通 VIP 或申请并获批「AI 问答权限」后，可填写自己的 API Key 调用模型额度，站内不保存明文。</div>
        <button class="btn btn-accent btn-block" @click="router.push('/vip')">
          <Crown :size="17" />去开通 VIP
        </button>
      </div>

      <template v-else>
        <div v-if="usage" class="card">
          <div>今日 AI 请求 {{ usage.requests }} / {{ usage.daily_limit }} · 剩余 {{ usage.remaining }}</div>
          <div class="field-hint">北京时间零点重置，失败尝试计入请求预算。成功 {{ usage.succeeded }} 次，失败 {{ usage.failed }} 次。</div>
          <div class="field-hint">服务商已报告的 Token：输入 {{ usage.prompt_tokens }} / 输出 {{ usage.completion_tokens }}（不含未报告用量）。</div>
          <label class="field-label">携带历史对话轮数（0–50）</label>
          <input v-model.number="contextTurns" class="input" type="number" min="0" max="50" />
          <button class="btn btn-outline mt8" @click="saveContext">保存上下文设置</button>
        </div>
        <div class="card status-card">
          <div class="status-head">
            <span class="status-ic"><KeyRound :size="18" /></span>
            <div class="status-main">
              <div class="status-title">{{ configured ? '已配置' : '未配置' }}</div>
              <div class="status-sub">
                <template v-if="configured">{{ status.key_mask }} · {{ status.model }}</template>
                <template v-else>填写后可调用你自己的模型额度</template>
              </div>
            </div>
          </div>
        </div>

        <div class="section-title">服务商</div>
        <div class="provider-grid">
          <button
            v-for="p in PROVIDERS"
            :key="p.id"
            class="provider-pill"
            :class="{ on: provider === p.id }"
            @click="pickProvider(p)"
          >
            {{ p.label }}
          </button>
        </div>

        <div class="card form-card">
          <label class="field-label">服务地址</label>
          <input v-model="baseUrl" class="input" placeholder="https://api.deepseek.com/v1" />
          <div v-if="currentProvider?.id === 'custom'" class="field-hint">
            兼容 OpenAI 协议的服务地址，如 OneAPI、Ollama、vLLM
          </div>

          <label class="field-label">API Key</label>
          <input
            v-model="apiKey"
            class="input"
            type="password"
            autocomplete="off"
            :placeholder="configured ? `已保存 ${status.key_mask}，修改请重新输入` : 'sk-...'"
          />
          <div class="field-hint">Key 使用 AES-256-GCM 加密存储，页面不回显明文。</div>

          <label class="field-label">模型</label>
          <div class="model-row">
            <input v-model="model" class="input" placeholder="模型名" />
            <button class="btn btn-outline btn-sm" :disabled="fetching" @click="fetchModels">
              <RefreshCw :size="15" />{{ fetching ? '拉取中…' : '拉取列表' }}
            </button>
          </div>
          <div v-if="models.length" class="model-list">
            <button
              v-for="m in models.slice(0, 12)"
              :key="m.id"
              class="model-chip"
              :class="{ on: model === m.id }"
              @click="model = m.id"
            >
              {{ m.id }}{{ m.id === currentProvider?.model ? ' · 推荐' : '' }} · {{ m.supports_images == null ? '图片能力未知' : m.supports_images ? '支持图片' : '不支持图片' }} · 上下文{{ m.context_length || '未知' }}
            </button>
          </div>

          <div class="field-hint">模型列表不保证提供能力信息；请根据服务商说明确认当前模型能力。</div>
          <label class="field-label"><input v-model="supportsImages" type="checkbox" /> 该模型支持图片输入</label>
          <label class="field-label"><input v-model="supportsTools" type="checkbox" /> 该模型支持工具调用</label>
          <button class="btn btn-primary btn-block mt16" :disabled="saving" @click="save">
            <Save :size="17" />{{ saving ? '保存中…' : '保存设置' }}
          </button>
          <button v-if="configured" class="btn btn-danger btn-block mt8" :disabled="deleting" @click="removeKey">
            <Trash2 :size="16" />删除 Key
          </button>
        </div>

        <button class="benefit-link" @click="router.push('/vip')">
          <Crown :size="15" />VIP 权益与到期时间<ChevronRight :size="15" />
        </button>
      </template>
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
.guide { text-align: center; padding: 26px 18px 20px; }
.guide-badge {
  width: 54px;
  height: 54px;
  margin: 0 auto 12px;
  border-radius: 16px;
  background: #fff3df;
  color: var(--accent-deep);
  display: flex;
  align-items: center;
  justify-content: center;
}
.guide-title { font-size: 17px; font-weight: 800; }
.guide-desc { font-size: 12.5px; color: var(--sub); line-height: 1.7; margin: 8px 4px 18px; }
.status-card { padding: 14px 16px; }
.status-head { display: flex; align-items: center; gap: 11px; }
.status-ic {
  width: 40px; height: 40px; border-radius: 12px; background: #eef3f9;
  color: var(--primary); display: flex; align-items: center; justify-content: center;
}
.status-main { flex: 1; min-width: 0; }
.status-title { font-size: 14.5px; font-weight: 700; }
.status-sub { font-size: 11.5px; color: var(--faint); margin-top: 2px; word-break: break-all; }
.provider-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.provider-pill {
  border: 1.5px solid var(--line); background: #fff; color: var(--sub);
  border-radius: 11px; padding: 10px 4px; font-size: 12.5px; font-weight: 600; cursor: pointer;
}
.provider-pill.on { border-color: transparent; background: var(--primary); color: #fff; }
.form-card { margin-top: 14px; }
.field-label { display: block; font-size: 12.5px; color: var(--sub); margin: 13px 2px 6px; }
.field-label:first-child { margin-top: 0; }
.field-hint { font-size: 11px; color: var(--faint); margin-top: 5px; line-height: 1.6; }
.model-row { display: flex; gap: 8px; }
.model-row .input { flex: 1; }
.model-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.model-chip {
  border: 1px solid var(--line); background: #fafbfe; color: var(--sub);
  border-radius: 999px; padding: 5px 10px; font-size: 11px; cursor: pointer;
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.model-chip.on { border-color: var(--primary); color: var(--primary); background: #eef4fb; }
.benefit-link {
  width: 100%; margin-top: 14px; border: none; background: none;
  color: var(--sub); font-size: 12.5px; display: flex; align-items: center;
  justify-content: center; gap: 4px; cursor: pointer;
}
</style>
