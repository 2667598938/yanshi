<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, Plus, Users, Lock, Globe2, KeyRound, Copy, ChevronRight, Check,
} from 'lucide-vue-next'
import { roomApi } from '../api'
import { useToast } from '../composables/useToast'
import { useClipboard } from '../composables/useClipboard'
import CopyFallback from '../components/CopyFallback.vue'

const router = useRouter()
const { toast } = useToast()
const { copy: copyToClipboard, manualCopy } = useClipboard(toast)

const rows = ref([])
const loading = ref(true)
const sheet = ref(null)
const form = ref({ name: '', intro: '', visibility: 'public' })
const codeInput = ref('')
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    rows.value = await roomApi.list()
  } catch (e) {
    toast(e.message)
  } finally {
    loading.value = false
  }
}

function openRoom(row) {
  router.push(`/rooms/${row.id}`)
}

function openCreate() {
  form.value = { name: '', intro: '', visibility: 'public' }
  sheet.value = 'create'
}

async function create() {
  if (form.value.name.trim().length < 2) return toast('房间名至少 2 个字')
  saving.value = true
  try {
    const row = await roomApi.create({
      name: form.value.name.trim(),
      intro: form.value.intro.trim(),
      visibility: form.value.visibility,
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
  saving.value = true
  try {
    const data = await roomApi.joinByCode(codeInput.value.trim())
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
      <button class="icon-btn" title="凭房间码加入" @click="codeInput = ''; sheet = 'join'">
        <KeyRound :size="17" />
      </button>
      <button class="create-btn" @click="openCreate"><Plus :size="16" />创建</button>
    </div>

    <div class="page">
      <div class="hero">
        <div class="hero-title">四人一桌，各学各的</div>
        <div class="hero-sub">公开房间可直接加入；私密房间凭 6 位房间码进入</div>
      </div>

      <div v-if="loading" class="empty">读取中…</div>
      <div v-else-if="!rows.length" class="empty">还没有自习室，创建一个</div>
      <div v-else class="room-list">
        <button v-for="r in rows" :key="r.id" class="room-card" @click="openRoom(r)">
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
                · {{ r.member_count }}/{{ r.capacity }} 人
                <span v-if="r.online_count"> · {{ r.online_count }} 在线</span>
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
      </div>
    </div>

    <div v-if="sheet" class="mask" @click.self="sheet = null">
      <div class="sheet">
        <template v-if="sheet === 'create'">
          <div class="sheet-title">创建自习室</div>
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
          <p class="sheet-tip">向房主要 6 位房间码；公开房间也可以直接在列表里进入。</p>
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
.back { border: none; background: #fff; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.icon-btn { margin-left: auto; border: 1px solid var(--line); background: #fff; width: 34px; height: 34px; border-radius: 10px; color: var(--sub); display: inline-flex; align-items: center; justify-content: center; cursor: pointer; }
.create-btn { border: none; border-radius: 10px; background: var(--primary); color: #fff; font-size: 12.5px; font-weight: 600; padding: 9px 13px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.hero { border-radius: 16px; padding: 18px; background: linear-gradient(140deg, #0f1f3a, #31547f); color: #eef4ff; margin-bottom: 14px; }
.hero-title { font-size: 16.5px; font-weight: 700; }
.hero-sub { font-size: 11.5px; color: rgba(238,244,255,.62); margin-top: 5px; }
.room-list { display: flex; flex-direction: column; gap: 10px; }
.room-card { text-align: left; background: #fff; border: none; border-radius: var(--radius); padding: 14px 16px; box-shadow: var(--shadow-soft); color: var(--ink); cursor: pointer; }
.rc-top { display: flex; align-items: center; gap: 10px; }
.rc-icon { width: 38px; height: 38px; border-radius: 12px; background: #eef4fb; color: var(--primary); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rc-main { flex: 1; min-width: 0; }
.rc-name { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.rc-sub { font-size: 11px; color: var(--faint); margin-top: 3px; }
.rc-arrow { color: #cad2de; }
.rc-intro { margin-top: 9px; font-size: 12.5px; color: var(--sub); line-height: 1.6; }
.rc-foot { display: flex; align-items: center; gap: 10px; margin-top: 10px; font-size: 10.5px; color: var(--faint); }
.rc-vis { display: inline-flex; align-items: center; gap: 3px; color: var(--primary); }
.rc-code { display: inline-flex; align-items: center; gap: 3px; color: var(--accent-deep); font-weight: 700; }
.rc-owner { margin-left: auto; }
.tag { font-size: 9.5px; padding: 1px 6px; border-radius: 6px; font-weight: 700; }
.tag-owner { background: #fff3df; color: var(--accent-deep); }
.tag-joined { background: #e7f6f0; color: #1f9d63; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; margin-bottom: 6px; }
.sheet-tip { font-size: 12px; color: var(--faint); text-align: center; margin: 0 0 12px; }
.sf { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.sf > span { font-size: 12.5px; color: var(--sub); }
.sf input { height: 44px; border: 1.5px solid var(--line); border-radius: 11px; padding: 0 13px; font-size: 14px; outline: none; }
.sf input:focus { border-color: var(--primary); }
.vis-row { display: flex; gap: 8px; }
.vis-row button { flex: 1; height: 42px; border: 1.5px solid var(--line); border-radius: 11px; background: #fff; color: var(--sub); font-size: 12.5px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 5px; cursor: pointer; }
.vis-row button.on { border-color: transparent; background: var(--primary); color: #fff; }
.code-input { width: 100%; box-sizing: border-box; height: 52px; border: 1.5px solid var(--line); border-radius: 12px; padding: 0 14px; font-size: 20px; font-weight: 700; letter-spacing: 3px; text-align: center; text-transform: uppercase; outline: none; }
.code-input:focus { border-color: var(--primary); }
</style>
