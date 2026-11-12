<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, Plus, Users, Lock, Globe2, KeyRound, Copy, ChevronRight, Check, RefreshCw,
} from 'lucide-vue-next'
import { roomApi, publicApi } from '../api'
import { useToast } from '../composables/useToast'
import { useClipboard } from '../composables/useClipboard'
import CopyFallback from '../components/CopyFallback.vue'
import { ROOM_SHARING_NOTICE } from '../utils/roomSharing'

const router = useRouter()
const { toast } = useToast()
const { copy: copyToClipboard, manualCopy } = useClipboard(toast)

const rows = ref([])
const myRooms=computed(()=>rows.value.filter(room=>room.joined || room.my_role==='owner' || room.legacy_member))
const publicRooms=computed(()=>rows.value.filter(room=>room.visibility==='public' && !myRooms.value.some(mine=>mine.id===room.id)))
const sections=computed(()=>[{title:'我的房间',rooms:myRooms.value,empty:'还没坐下？创建一间，或凭房间码加入研友。'},{title:'公开房间',rooms:publicRooms.value,empty:'暂时没有可加入的公开房间。'}])
const loading = ref(true)
const loadError = ref('')
const sheet = ref(null)
const features = ref([])
const roomTypes = [
  { key: 'text_room', name: '文字自习室' },
  { key: 'av_room', name: '音视频自习室（6人）' },
]
const form = ref({ name: '', intro: '', visibility: 'private', room_type: 'text_room', capacity:50 })
const codeInput = ref('')
const saving = ref(false)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const config = await publicApi.config().catch(() => ({ features: [] }))
    features.value = config.features || []
    rows.value = await roomApi.list()
  } catch (e) {
    loadError.value = e.message || '自习室列表加载失败'
  } finally {
    loading.value = false
  }
}

function openRoom(row) {
  router.push(`/rooms/${row.id}`)
}

function openCreate(type = 'text_room') {
  if (!features.value.includes(type)) return toast('该房间类型暂未开放')
  form.value = { name: '', intro: '', visibility: 'private', room_type: type, capacity:type==='av_room'?6:50 }
  sheet.value = 'create'
}

async function create() {
  if (form.value.name.trim().length < 2) return toast('房间名至少 2 个字')
  if (saving.value || !confirm(ROOM_SHARING_NOTICE)) return
  saving.value = true
  try {
    const row = await roomApi.create({
      name: form.value.name.trim(),
      intro: form.value.intro.trim(),
      visibility: form.value.visibility,
      room_type: form.value.room_type,
      capacity: form.value.capacity,
      accept_sharing: true,
    })
    toast('自习室已创建')
    sheet.value = null
    router.push(`/rooms/${row.id}`)
  } catch (e) {
    toast(e.message)
  } finally {
    saving.value = false
  }
}

async function joinByCode() {
  if (!codeInput.value.trim()) return toast('请输入房间码')
  if (saving.value || !confirm(ROOM_SHARING_NOTICE)) return
  saving.value = true
  try {
    const data = await roomApi.joinByCode(codeInput.value.trim(), true)
    toast('已加入')
    sheet.value = null
    codeInput.value = ''
    router.push(`/rooms/${data.room.id}`)
  } catch (e) {
    toast(e.message)
  } finally {
    saving.value = false
  }
}

async function copyCode(code) {
  await copyToClipboard(code, '房间码已复制')
}

onMounted(load)
</script>

<template>
  <div>
    <CopyFallback v-model="manualCopy" />
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">自习室</div>
    </div>

    <div class="page">
      <div class="room-top-actions"><button class="btn btn-primary" @click="openCreate()">创建自习室</button><button class="btn btn-outline" @click="codeInput='';sheet='join'">凭房间码进入</button></div>
      <div v-if="loading" class="sk-list" role="status">
        <span class="sr-only">正在读取自习室列表，请稍候…</span>
        <div v-for="i in 3" :key="i" class="sk-room">
          <i class="sk-ic"></i>
          <div class="sk-lines"><i></i><i class="w60"></i></div>
        </div>
      </div>
      <div v-else-if="loadError" class="empty-block">
        <div class="empty-ic"><RefreshCw :size="22" /></div>
        <div class="empty-title">列表没有加载出来</div>
        <div class="empty-sub">{{ loadError }}</div>
        <button class="btn btn-primary btn-sm" @click="load">重新加载</button>
      </div>
      <div v-else-if="!rows.length" class="empty-block">
        <div class="empty-ic"><Users :size="22" /></div>
        <div class="empty-title">还没有自习室</div>
        <div class="empty-sub">创建一间，或凭 6 位房间码加入研友的自习室</div>
        <button class="btn btn-primary btn-sm" @click="openCreate()"><Plus :size="14" />创建自习室</button>
      </div>
      <div v-else class="room-sections"><section v-for="section in sections" :key="section.title"><h2>{{section.title}} <small>{{section.rooms.length}}</small></h2><p v-if="!section.rooms.length" class="room-empty">{{section.empty}}</p><div class="room-list">
        <button v-for="r in section.rooms" :key="r.id" class="room-card" @click="openRoom(r)">
          <div class="rc-top">
            <div class="rc-icon"><Users :size="19" /></div>
            <div class="rc-main">
              <div class="rc-name">
                {{ r.name }}
                <span v-if="r.my_role === 'owner'" class="tag tag-owner">房主</span>
                <span v-else-if="r.joined" class="tag tag-joined">已加入</span>
              </div>
              <div class="rc-sub">
                {{ r.visibility === 'private' ? '私密房间' : '公开房间' }}
                · 成员 {{ r.member_count }} · {{ r.capacity > 0 ? r.capacity + '人上限' : '不限人数' }}
                <span> · {{ r.online_count || 0 }} 连接</span>
              </div>
            </div>
            <ChevronRight :size="17" class="rc-arrow" />
          </div>
          <div v-if="r.intro" class="rc-intro">{{ r.intro }}</div>
          <div class="rc-foot">
            <span class="rc-vis">
              <Lock v-if="r.visibility === 'private'" :size="12" />
              <Globe2 v-else :size="12" />
              {{ r.visibility === 'private' ? '凭码加入' : '公开' }}
            </span>
            <span v-if="r.joined && r.code" class="rc-code" @click.stop="copyCode(r.code)">
              房间码 {{ r.code }}<Copy :size="12" />
            </span>
            <span class="rc-owner">{{ r.owner?.nickname || '官方' }} 创建</span>
          </div>
        </button>
      </div></section></div>
    </div>

    <div v-if="sheet" class="mask" @click.self="sheet = null">
      <div class="sheet">
        <template v-if="sheet === 'create'">
          <div class="sheet-title">创建{{ roomTypes.find(t => t.key === form.room_type)?.name }}</div><p class="sheet-tip">文字房看状态、聊学习；音视频房支持最多6人开麦、开摄像头。私密房只展示给已加入的成员。</p>
          <label class="sf"><span>房间类型</span><select v-model="form.room_type" @change="form.capacity=form.room_type==='av_room'?6:50"><option v-for="type in roomTypes.filter(t=>features.includes(t.key))" :key="type.key" :value="type.key">{{type.name}}</option></select></label>
          <label v-if="form.room_type==='text_room'" class="sf"><span>房间容量</span><select v-model.number="form.capacity"><option :value="20">20人</option><option :value="50">50人</option><option :value="100">100人</option></select></label>
          <label class="sf">
            <span>房间名</span>
            <input v-model="form.name" maxlength="20" placeholder="如：冲刺 408 小组" />
          </label>
          <label class="sf">
            <span>简介（可选）</span>
            <input v-model="form.intro" maxlength="200" placeholder="一句话说明这个房间的节奏" />
          </label>
          <div class="vis-row">
            <button :class="{ on: form.visibility === 'public' }" @click="form.visibility = 'public'">
              <Globe2 :size="15" />公开
            </button>
            <button :class="{ on: form.visibility === 'private' }" @click="form.visibility = 'private'">
              <Lock :size="15" />私密（凭码）
            </button>
          </div>
          <button class="btn btn-primary btn-block mt16" :disabled="saving" @click="create">
            <Check :size="16" />{{ saving ? '创建中…' : '创建并进入' }}
          </button>
        </template>

        <template v-else>
          <div class="sheet-title">凭房间码加入</div>
          <p class="sheet-tip">向朋友要 6 位邀请房间码；公开房可申请加入；私密房请向房主要邀请码。加入后默认共享学习数据，隐私模式可隐藏。</p>
          <input v-model="codeInput" class="code-input tnum" maxlength="32" placeholder="输入房间码" />
          <button class="btn btn-primary btn-block mt16" :disabled="saving" @click="joinByCode">
            {{ saving ? '加入中…' : '加入' }}
          </button>
        </template>
        <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.room-sections{display:grid;gap:24px}.room-sections h2{font-size:16px;margin:0 0 12px}.room-sections h2 small{font-size:12px;color:var(--sub)}.room-empty{font-size:14px;color:var(--sub);padding:16px;background:var(--glass);border-radius:16px}.room-top-actions{display:flex;gap:12px;margin-bottom:16px}.room-top-actions .btn{flex:1}.hero,.type-card{display:none}.sf select{min-height:44px;border:1px solid var(--line);border-radius:8px;padding:8px;background:#fff;font-size: 14px}
.back { border: none; background: rgba(255, 255, 255, 0.72); width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); backdrop-filter: blur(10px); transition: transform 0.24s ease, color 0.24s ease; }
.back:active { transform: scale(0.96); }
.icon-btn { margin-left: auto; border: 1px solid rgba(79, 70, 229, 0.14); background: rgba(255, 255, 255, 0.72); width: 40px; height: 40px; border-radius: 12px; color: var(--sub); display: inline-flex; align-items: center; justify-content: center; cursor: pointer; backdrop-filter: blur(10px); transition: transform 0.24s ease, color 0.24s ease, box-shadow 0.24s ease; }
.icon-btn:active { transform: scale(0.96); }
.create-btn { border: none; border-radius: 12px; background: var(--primary-grad); color: #fff; font-size: 14px; font-weight: 600; padding: 8px 16px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; box-shadow: 0 6px 16px rgba(79, 70, 229, 0.24); transition: transform 0.24s ease, filter 0.24s ease; }
@media (hover: hover) and (pointer: fine) {
  .back:hover, .icon-btn:hover { color: var(--primary); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(79, 70, 229, 0.16); }
  .create-btn:hover { transform: translateY(-2px) scale(1.03); filter: brightness(1.06); }
}

/* 页首说明卡：与主色同源的蓝紫渐变 */
.hero { border-radius: 12px; padding: 16px; background: var(--primary-grad); color: #fff; margin-bottom: 16px; box-shadow: 0 10px 24px rgba(79, 70, 229, 0.22); }
.hero-title { font-size: 20px; font-weight: 800; letter-spacing: 0.2px; }
.hero-sub { font-size: 14px; color: rgba(255, 255, 255, 0.78); margin-top: 4px; line-height: 1.6; }

.room-list { display: flex; flex-direction: column; gap: 8px; }
/* 快捷入口：两列等宽网格 */
.type-card { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
.type-btn { height: 40px; border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 8px; background: rgba(255, 255, 255, 0.7); color: var(--primary); font-size: 14px; font-weight: 600; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 8px; transition: background 0.24s ease, box-shadow 0.24s ease, transform 0.24s ease; }
.type-btn.ghost { background: rgba(79, 70, 229, 0.06); border-color: transparent; color: var(--sub); }
.type-btn:active { transform: scale(0.98); }
@media (hover: hover) and (pointer: fine) {
  .type-btn:hover { background: rgba(79, 70, 229, 0.08); box-shadow: 0 6px 16px rgba(79, 70, 229, 0.12); }
}
/* 空态：虚线占位卡 + 主按钮 */
.empty-block { text-align: center; padding: 24px 16px; border: 1px dashed rgba(79, 70, 229, 0.2); border-radius: 12px; background: rgba(255, 255, 255, 0.5); }
.empty-ic { width: 40px; height: 40px; margin: 0 auto 8px; border-radius: 12px; background: rgba(79, 70, 229, 0.08); color: var(--primary); display: flex; align-items: center; justify-content: center; }
.empty-title { font-size: 14px; font-weight: 700; }
.empty-sub { font-size: 14px; color: var(--faint); margin: 4px 0 16px; line-height: 1.6; }
/* 列表骨架：先给出结构，避免"读取中"空等 */
.sk-list { display: flex; flex-direction: column; gap: 8px; }
.sk-room { display: flex; align-items: center; gap: 8px; padding: 16px; border-radius: 12px; background: var(--card); border: 1px solid rgba(255, 255, 255, 0.85); box-shadow: var(--shadow); }
.sk-ic { width: 40px; height: 40px; border-radius: 12px; background: rgba(79, 70, 229, 0.1); flex-shrink: 0; }
.sk-lines { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.sk-lines i { display: block; width: 100%; height: 12px; border-radius: 6px; background: rgba(79, 70, 229, 0.08); }
.sk-lines i.w60 { width: 60%; height: 8px; }
.sk-list i { animation: sk-breathe 1.6s ease-in-out infinite; }
@keyframes sk-breathe { 0%, 100% { opacity: .5; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .sk-list i { animation: none; } }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.room-card { text-align: left; background: var(--card); border: 1px solid rgba(255, 255, 255, 0.85); border-radius: 12px; padding: 16px; box-shadow: var(--shadow); color: var(--ink); cursor: pointer; backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); transition: transform 0.24s ease, box-shadow 0.24s ease; }
.room-card:active { transform: scale(0.995); }
@media (hover: hover) and (pointer: fine) {
  .room-card:hover { transform: translateY(-2px); box-shadow: 0 12px 28px rgba(79, 70, 229, 0.14); }
}
.rc-top { display: flex; align-items: center; gap: 8px; }
.rc-icon { width: 40px; height: 40px; border-radius: 12px; background: rgba(79, 70, 229, 0.1); color: var(--primary); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rc-main { flex: 1; min-width: 0; }
.rc-name { font-size: 14px; font-weight: 700; display: flex; align-items: center; gap: 8px; }
.rc-sub { font-size: 14px; color: var(--faint); margin-top: 4px; }
.rc-arrow { color: #c3c8dd; }
.rc-intro { margin-top: 8px; font-size: 14px; color: var(--sub); line-height: 1.6; }
.rc-foot { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 14px; color: var(--faint); }
.rc-vis { display: inline-flex; align-items: center; gap: 4px; color: var(--primary); }
.rc-code { display: inline-flex; align-items: center; gap: 4px; color: var(--accent-deep); font-weight: 700; }
.rc-owner { margin-left: auto; }
.tag { font-size: 12px; padding: 2px 8px; border-radius: 6px; font-weight: 700; }
.tag-owner { background: rgba(245, 158, 11, 0.12); color: var(--accent-deep); }
.tag-joined { background: rgba(16, 185, 129, 0.1); color: var(--green); }

.mask { position: fixed; inset: 0; background: rgba(30, 27, 75, 0.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 24px 24px 0 0; padding: 24px 16px calc(24px + env(safe-area-inset-bottom)); }
.sheet-title { font-size: 20px; font-weight: 800; text-align: center; margin-bottom: 8px; }
.sheet-tip { font-size: 14px; color: var(--faint); text-align: center; margin: 0 0 16px; }
.sf { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
.sf > span { font-size: 14px; color: var(--sub); }
.sf input { height: 44px; border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 8px; padding: 0 16px; font-size: 14px; outline: none; background: rgba(255, 255, 255, 0.9); transition: border-color 0.24s ease, box-shadow 0.24s ease; }
.sf input:focus { border-color: rgba(79, 70, 229, 0.5); box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12); }
.vis-row { display: flex; gap: 8px; }
.vis-row button { flex: 1; height: 40px; border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 8px; background: rgba(255, 255, 255, 0.8); color: var(--sub); font-size: 14px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 4px; cursor: pointer; transition: background 0.24s ease, color 0.24s ease, box-shadow 0.24s ease; }
.vis-row button.on { border-color: transparent; background: var(--primary-grad); color: #fff; box-shadow: 0 6px 16px rgba(79, 70, 229, 0.22); }
.code-input { width: 100%; box-sizing: border-box; height: 52px; border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 8px; padding: 0 16px; font-size: 20px; font-weight: 700; letter-spacing: 3px; text-align: center; text-transform: uppercase; outline: none; transition: border-color 0.24s ease, box-shadow 0.24s ease; }
.code-input:focus { border-color: rgba(79, 70, 229, 0.5); box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12); }
</style>
