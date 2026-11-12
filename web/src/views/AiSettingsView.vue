<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft, KeyRound, RefreshCw, Save, Trash2, Crown, ChevronRight } from 'lucide-vue-next';
import { aiApi } from '../api';
import { useAuthStore } from '../stores/auth';
import { useToast } from '../composables/useToast';

const router = useRouter();
const auth = useAuthStore();
const { toast } = useToast();

const PROVIDERS = [
  {
    id: 'deepseek',
    label: 'DeepSeek',
    base: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
  },
  { id: 'moonshot', label: 'Kimi', base: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  {
    id: 'zhipu',
    label: '智谱 GLM',
    base: 'https://open.bigmodel.cn/api/paas/v4',
    model: 'glm-4-flash',
  },
  {
    id: 'siliconflow',
    label: '硅基流动',
    base: 'https://api.siliconflow.cn/v1',
    model: 'Qwen/Qwen2.5-7B-Instruct',
  },
  { id: 'openai', label: 'OpenAI', base: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
  { id: 'custom', label: '自定义', base: '', model: '' },
];

const provider = ref('deepseek');
const baseUrl = ref('https://api.deepseek.com/v1');
const apiKey = ref('');
const model = ref('');
const supportsImages = ref(false);
const supportsTools = ref(false);
const status = ref(null);
const models = ref([]);
const modelSearch = ref('');
const filteredModels = computed(() => {
  const q = modelSearch.value.trim().toLowerCase();
  return q ? models.value.filter((m) => m.id.toLowerCase().includes(q)) : models.value;
});
const fetching = ref(false);
const saving = ref(false);
const deleting = ref(false);
const loading = ref(true);
const loadError = ref('');
const usage = ref(null);
const contextTurns = ref(10);
let catalogGeneration = 0;
watch(
  [provider, baseUrl, apiKey],
  () => {
    if (loading.value || saving.value) return;
    catalogGeneration++;
    models.value = [];
    model.value = '';
    fetching.value = false;
  },
  { flush: 'sync' },
);

async function saveContext() {
  try {
    await aiApi.preferences({ context_turns: Number(contextTurns.value) });
    toast('上下文轮数已保存');
  } catch (e) {
    toast(e.message);
  }
}

const isVip = computed(() => auth.isVip);
const canUse = ref(false);
const configured = computed(() => !!status.value?.configured);
const canReuseKey = computed(
  () =>
    configured.value &&
    provider.value === status.value.provider &&
    baseUrl.value.trim().replace(/\/+$/, '') === status.value.base_url?.replace(/\/+$/, ''),
);
const currentProvider = computed(() => PROVIDERS.find((p) => p.id === provider.value));

function pickProvider(p) {
  if (saving.value || deleting.value) return;
  provider.value = p.id;
  baseUrl.value = p.base || '';
  model.value = '';
  models.value = [];
  apiKey.value = '';
  supportsImages.value = false;
  supportsTools.value = false;
}

async function load() {
  loading.value = true;
  loadError.value = '';
  try {
    const cfg = await aiApi.enabled();
    canUse.value = !!cfg.access;
    status.value = await aiApi.key();
    if (!canUse.value) return;
    if (status.value.configured) {
      provider.value = status.value.provider || 'deepseek';
      baseUrl.value = status.value.base_url || '';
      model.value = status.value.model || '';
      supportsImages.value = !!status.value.supports_images;
      supportsTools.value = !!status.value.supports_tools;
    }
    // 用量故障不应阻止本人已保存配置回填。
    try {
      usage.value = await aiApi.usage();
      contextTurns.value = usage.value.context_turns;
    } catch (e) {
      toast(e.message || '用量暂时无法读取');
    }
  } catch (e) {
    loadError.value = e.message || '配置读取失败，请重试';
  } finally {
    loading.value = false;
  }
}

async function fetchModels() {
  if (fetching.value || saving.value || deleting.value) return;
  if (!apiKey.value.trim() && !canReuseKey.value) return toast('请先填写当前服务商的 API Key');
  fetching.value = true;
  const generation = catalogGeneration;
  const requestedProvider = provider.value,
    requestedBase = baseUrl.value,
    requestedKey = apiKey.value;
  try {
    const data = await aiApi.models({
      provider: provider.value,
      base_url: baseUrl.value.trim(),
      api_key: apiKey.value.trim(),
      force_refresh: true,
    });
    if (
      generation !== catalogGeneration ||
      provider.value !== requestedProvider ||
      baseUrl.value !== requestedBase ||
      apiKey.value !== requestedKey
    )
      return;
    const details = new Map((data.details || []).map((item) => [item.id, item]));
    models.value = (data.models || []).map((id) => ({ id, ...details.get(id) }));
    if (data.fallback) {
      toast(data.error?.message || '未拉取到模型列表，可手动填写模型名');
    } else {
      toast(`${data.cached ? '使用24小时缓存' : '已拉取'} ${models.value.length} 个模型`);
    }
    if (!model.value && models.value.length) model.value = models.value[0].id;
  } catch (e) {
    toast(e.message);
  } finally {
    if (generation === catalogGeneration) fetching.value = false;
  }
}

async function save() {
  if (saving.value || deleting.value) return;
  if (!apiKey.value.trim() && !canReuseKey.value) return toast('请填写当前服务商的 API Key');
  if (!baseUrl.value.trim()) return toast('请填写服务商地址');
  if (!model.value.trim()) return toast('请选择或填写模型名');
  saving.value = true;
  catalogGeneration++;
  fetching.value = false;
  try {
    status.value = await aiApi.saveKey({
      provider: provider.value,
      base_url: baseUrl.value.trim(),
      model: model.value.trim(),
      supports_images: supportsImages.value,
      supports_tools: false,
      ...(apiKey.value.trim() ? { api_key: apiKey.value.trim() } : {}),
    });
    apiKey.value = '';
    models.value = [];
    modelSearch.value = '';
    toast('已保存，Key 已加密');
  } catch (e) {
    toast(e.message);
  } finally {
    saving.value = false;
  }
}

async function removeKey() {
  if (saving.value || deleting.value) return;
  if (!confirm('删除已保存的 AI Key？历史对话仍会保留。')) return;
  catalogGeneration++;
  fetching.value = false;
  deleting.value = true;
  try {
    status.value = await aiApi.deleteKey();
    models.value = [];
    model.value = '';
    modelSearch.value = '';
    apiKey.value = '';
    toast('已删除');
  } catch (e) {
    toast(e.message);
  } finally {
    deleting.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">AI 设置</div>
    </div>

    <div class="page">
      <div v-if="loading" class="empty">读取中…</div>
      <div v-else-if="loadError" class="card" role="alert">
        <p>AI 配置未能读取：{{ loadError }}</p>
        <button class="btn btn-outline" @click="load">重新读取</button>
      </div>

      <div v-else-if="!canUse" class="card guide">
        <div class="guide-badge"><Crown :size="24" /></div>
        <div class="guide-title">AI 需要 VIP 或审批授权</div>
        <div class="guide-desc">
          开通 VIP 或申请并获批「AI 问答权限」后，可填写自己的 API Key
          调用模型额度，站内不保存明文。
        </div>
        <button class="btn btn-accent btn-block" @click="router.push('/vip')">
          <Crown :size="17" />去开通 VIP
        </button>
      </div>

      <div v-if="!loading && !loadError && !canUse && configured" class="card mt16">
        <p>已保存的Key：{{ status.key_mask }} · {{ status.model }}</p>
        <p class="field-hint">调用权限到期不影响你删除自己的Key，历史会话仍保留。</p>
        <button class="btn btn-outline" :disabled="deleting" @click="removeKey">删除我的Key</button>
      </div>

      <template v-if="!loading && !loadError && canUse">
        <div v-if="usage" class="card">
          <div>
            今日 AI 请求 {{ usage.requests }} / {{ usage.daily_limit }} · 剩余 {{ usage.remaining }}
          </div>
          <div class="field-hint">
            北京时间零点重置，失败尝试计入请求预算。成功 {{ usage.succeeded }} 次，失败
            {{ usage.failed }} 次。
          </div>
          <div class="field-hint">
            服务商已报告的 Token：输入 {{ usage.prompt_tokens }} / 输出
            {{ usage.completion_tokens }}（不含未报告用量）。
          </div>
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
            :disabled="saving || deleting"
            @click="pickProvider(p)"
          >
            {{ p.label }}
          </button>
        </div>

        <div class="card form-card">
          <label class="field-label">服务地址</label>
          <input
            v-model="baseUrl"
            :disabled="saving || deleting"
            class="input"
            placeholder="https://api.deepseek.com/v1"
          />
          <div v-if="currentProvider?.id === 'custom'" class="field-hint">
            兼容 OpenAI 协议的服务地址，如 OneAPI、Ollama、vLLM
          </div>

          <label class="field-label">API Key</label>
          <input
            v-model="apiKey"
            :disabled="saving || deleting"
            class="input"
            type="password"
            autocomplete="off"
            :placeholder="canReuseKey ? `已保存 ${status.key_mask}，留空继续使用` : 'sk-...'"
          />
          <div class="field-hint">Key 使用 AES-256-GCM 加密存储，页面不回显明文。</div>

          <label class="field-label">模型</label>
          <div class="model-row">
            <input
              v-model="model"
              :disabled="saving || deleting"
              class="input"
              placeholder="模型名"
            />
            <button
              class="btn btn-outline btn-sm"
              :disabled="fetching || saving || deleting"
              @click="fetchModels"
            >
              <RefreshCw :size="15" />{{ fetching ? '拉取中…' : '拉取列表' }}
            </button>
          </div>
          <div v-if="models.length" class="model-filter">
            <input
              v-model="modelSearch"
              class="input"
              placeholder="搜索模型 ID"
              aria-label="搜索模型 ID"
            />
            <span class="model-count">{{ filteredModels.length }} / {{ models.length }}</span>
          </div>
          <div v-if="models.length" class="model-list">
            <button
              v-for="m in filteredModels"
              :key="m.id"
              class="model-chip"
              :class="{ on: model === m.id }"
              :disabled="saving || deleting"
              @click="model = m.id"
            >
              {{ m.id }}{{ m.id === currentProvider?.model ? ' · 推荐' : '' }} ·
              {{
                m.supports_images == null
                  ? '图片能力未知'
                  : m.supports_images
                    ? '支持图片'
                    : '不支持图片'
              }}
              · 上下文{{ m.context_length || '未知' }}
            </button>
            <p v-if="!filteredModels.length" class="field-hint">
              没有匹配的模型，可直接在上方输入完整模型 ID。
            </p>
          </div>

          <div class="field-hint">
            模型列表不保证提供能力信息；请根据服务商说明确认当前模型能力。
          </div>
          <label class="field-label"
            ><input v-model="supportsImages" :disabled="saving || deleting" type="checkbox" />
            该模型支持图片输入</label
          >
          <label v-if="false" class="field-label"
            ><input v-model="supportsTools" type="checkbox" /> 该模型支持工具调用</label
          >
          <button
            class="btn btn-primary btn-block mt16"
            :disabled="saving || deleting"
            @click="save"
          >
            <Save :size="17" />{{ saving ? '保存中…' : '保存设置' }}
          </button>
          <button
            v-if="configured"
            class="btn btn-danger btn-block mt8"
            :disabled="deleting || saving"
            @click="removeKey"
          >
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
.guide {
  text-align: center;
  padding: 26px 18px 20px;
}
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
.guide-title {
  font-size: 16px;
  font-weight: 800;
}
.guide-desc {
  font-size: 14px;
  color: var(--sub);
  line-height: 1.7;
  margin: 8px 4px 18px;
}
.status-card {
  padding: 14px 16px;
}
.status-head {
  display: flex;
  align-items: center;
  gap: 11px;
}
.status-ic {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #eef3f9;
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
}
.status-main {
  flex: 1;
  min-width: 0;
}
.status-title {
  font-size: 14px;
  font-weight: 700;
}
.status-sub {
  font-size: 12px;
  color: var(--faint);
  margin-top: 2px;
  word-break: break-all;
}
.provider-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.provider-pill {
  border: 1.5px solid var(--line);
  background: #fff;
  color: var(--sub);
  border-radius: 11px;
  padding: 10px 4px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.provider-pill.on {
  border-color: transparent;
  background: var(--primary);
  color: #fff;
}
.form-card {
  margin-top: 14px;
}
.field-label {
  display: block;
  font-size: 14px;
  color: var(--sub);
  margin: 13px 2px 6px;
}
.field-label:first-child {
  margin-top: 0;
}
.field-hint {
  font-size: 12px;
  color: var(--faint);
  margin-top: 5px;
  line-height: 1.6;
}
.model-row {
  display: flex;
  gap: 8px;
}
.model-row .input {
  flex: 1;
}
.model-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
  max-height: 30vh;
  overflow-y: auto;
}
.model-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 9px;
}
.model-filter .input {
  flex: 1;
}
.model-count {
  font-size: 12px;
  color: var(--faint);
  white-space: nowrap;
}
.model-chip {
  border: 1px solid var(--line);
  background: #fafbfe;
  color: var(--sub);
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.model-chip.on {
  border-color: var(--primary);
  color: var(--primary);
  background: #eef4fb;
}
.benefit-link {
  width: 100%;
  margin-top: 14px;
  border: none;
  background: none;
  color: var(--sub);
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  cursor: pointer;
}
</style>
