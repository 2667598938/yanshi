<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, Users, Send, Trash2, Flag, Trophy, Flame, ArrowLeft, Copy, LogIn, Settings, UserMinus, Check, X } from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
import { useAuthStore } from '../stores/auth'
import { roomApi } from '../api'
import { SCHOOL_MAP } from '../data/schools'
import BlobImage from '../components/BlobImage.vue'
import { useToast } from '../composables/useToast'
import { useClipboard } from '../composables/useClipboard'
import CopyFallback from '../components/CopyFallback.vue'
import { FIGURES, FIGURE_MAP } from '../data/figures'

const timer = useTimerStore()
const subjects = useSubjectsStore()
const auth = useAuthStore()
const { toast } = useToast()
const { copy: copyToClipboard, manualCopy } = useClipboard(toast)
const route = useRoute()
const router = useRouter()
const roomId = computed(() => (route.params.id ? Number(route.params.id) : null))

let alive = true
const room = ref(null)
const joined = ref(true)
const members = ref([])
const ranking = ref({ today: [], week: [], all: [] })
const messages = ref([])
const rankTab = ref('today')
const loading = ref(false)
const msgInput = ref('')
const showGoal = ref(false)
const goalDraft = ref({ target_school: '', target_score: '', words: '' })
const showManage = ref(false)
const manageForm = ref({ name: '', intro: '', visibility: 'public' })
const isOwner = computed(() => room.value?.my_role === 'owner' || auth.isAdmin)
const preview = ref(null)
const joinCode = ref('')
const applyDraft = ref('')
const applying = ref(false)
const applies = ref([])
const applyBusyId = ref(0)
const joinRequired = computed(() => !!preview.value?.join_required)
const myApply = computed(() => preview.value?.apply || null)

function schoolLogo(key) {
  return SCHOOL_MAP[key]?.logo || ''
}
function schoolName(key) {
  return SCHOOL_MAP[key]?.short || key || '未填写'
}
function fmtSec(sec) {
  const m = Math.round((sec || 0) / 60)
  if (m >= 60) return `${(m / 60).toFixed(1)}h`
  return `${m}m`
}
function fmtTime(iso) {
  try {
    const d = new Date(iso)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return ''
  }
}

function presenceText(m) {
  const p = m.presence || {}
  if (p.status === 'private') return { label: '隐私中', color: '#8d7fa3' }
  if (p.status === 'unshared') return { label: '仅同组可见', color: '#8d7fa3' }
  if (!m.online) return { label: '离线', color: '#b6bfcc' }
  if (p.status === 'resting') return { label: '休息中', color: '#8b6ccc' }
  if (p.status === 'idle') return { label: '空闲', color: '#d49b32' }
  if (p.status === 'focusing') {
    return { label: `专注中 · ${p.subject_name || '学习'}${p.focus_sec ? ' ' + fmtSec(p.focus_sec) : ''}`, color: '#1f9d63' }
  }
  return { label: '在线', color: '#2f6bff' }
}

// 4 个座位：成员在前，空位补满 capacity
const seats = computed(() => {
  const cap = room.value?.capacity || 4
  const filled = members.value.map((m) => ({ ...m, empty: false }))
  const empties = Math.max(0, cap - filled.length)
  return [...filled, ...Array.from({ length: empties }, () => ({ empty: true }))]
})

const todayTotal = computed(() => members.value.reduce((a, m) => a + (m.today_sec || 0), 0))
const onlineCount = computed(() => room.value?.online_count || 0)
const isFull = computed(() =>
  Math.max(room.value?.member_count || 0, members.value.length) >= (room.value?.capacity || 4))

const rankList = computed(() => {
  const ids = ranking.value[rankTab.value] || []
  const byId = Object.fromEntries(members.value.map((m) => [m.user_id, m]))
  return ids.map((x) => ({ ...x, member: byId[x.user_id] }))
})

function buildHeartbeat() {
  if(document.visibilityState !== 'visible')return {status:'offline'}
  if(timer.isPaused)return {status:'idle'}
  if (timer.rest && !timer.rest.finished) return { status: 'resting' }
  const c = timer.current
  if (c) {
    const subj = subjects.byId[c.subjectId]
    return {
      status: 'focusing',
      subject_client_id: c.subjectId,
      subject_name: subj?.name || '学习',
      activity_type: c.activityType || '',
      mode: c.mode,
      focus_started_at: c.startedAt,
    }
  }
  return { status: 'idle', subject_client_id: '', subject_name: '', activity_type: '', mode: '', focus_started_at: null }
}

async function fetchRoom() {
  if (!alive) return
  // 私密房间未加入：轮询预览，房主通过后自动切换到正式房间状态
  if (!joined.value && preview.value) return loadPreview()
  try {
    const data = await roomApi.get(roomId.value)
    if (!alive) return
    room.value = data.room
    if(route.name==='room' && data.joined!==false)router.replace(`/rooms/${data.room.id}`)
    joined.value = data.joined !== false
    preview.value = null
    members.value = data.members || []
    ranking.value = data.ranking || { today: [], week: [], all: [] }
    messages.value = data.messages || []
  } catch (e) {
    if (!alive) return
    if (e.status === 403) return loadPreview()
    if (e.status === 404) {
      toast(e.message)
      router.replace('/rooms')
    }
  }
}

async function loadPreview() {
  try {
    const data = await roomApi.preview(roomId.value)
    if (!alive) return
    if (data.joined) {
      preview.value = null
      joined.value = true
      return fetchRoom()
    }
    room.value = data.room
    if(route.name==='room' && data.joined!==false)router.replace(`/rooms/${data.room.id}`)
    joined.value = false
    preview.value = data
    members.value = []
    ranking.value = { today: [], week: [], all: [] }
    messages.value = []
  } catch (e) {
    if (!alive) return
    toast(e.message)
    router.replace('/rooms')
  }
}

let beatTimer = null
function startBeating() {
  if (!alive) return
  if (beatTimer) return
  beat()
  beatTimer = setInterval(() => beat(), 30000)
}

async function join() {
  try {
    await roomApi.join(roomId.value, joinCode.value.trim())
    toast('已加入自习室')
    applyDraft.value = ''
    preview.value = null
    await fetchRoom()
    startBeating()
  } catch (e) {
    toast(e.message)
  }
}

async function applyJoin() {
  if (applying.value || myApply.value?.status === 'pending') return
  applying.value = true
  try {
    await roomApi.apply(roomId.value, applyDraft.value.trim())
    toast('申请已提交，等待房主审批')
    await loadPreview()
  } catch (e) {
    toast(e.message)
  } finally {
    applying.value = false
  }
}

async function loadApplies() {
  applies.value = []
  if (!isOwner.value) return
  try {
    const data = await roomApi.applies(roomId.value)
    applies.value = data.items || []
  } catch {
    applies.value = []
  }
}

async function reviewApply(row, approve) {
  if (applyBusyId.value) return
  applyBusyId.value = row.id
  try {
    await roomApi.reviewApply(roomId.value, row.id, approve)
    toast(approve ? `已通过，${row.nickname} 已加入` : '已驳回该申请')
    applies.value = applies.value.filter((x) => x.id !== row.id)
    if (approve) await fetchRoom()
  } catch (e) {
    toast(e.message)
  } finally {
    applyBusyId.value = 0
  }
}

async function copyCode() {
  await copyToClipboard(room.value?.code, '房间码已复制，发给研友')
}
async function copyInvite() {
  const url = new URL(`/rooms/${room.value.id}`, location.origin)
  await copyToClipboard(url.href, room.value.visibility === 'private' ? '申请链接已复制，房主审批后加入' : '房间链接已复制')
}
async function leaveRoom() {
  if (!confirm('退出这个自习室？')) return
  try {
    await roomApi.leave(roomId.value)
    joined.value = false
    clearInterval(beatTimer)
    toast('已退出自习室')
    router.replace('/rooms')
  } catch (error) { toast(error.message) }
}

async function beat() { window.dispatchEvent(new Event('yanshi:presence')) }

async function sendMessage() {
  const content = msgInput.value.trim()
  if (!content) return
  try {
    await roomApi.postMessage(content, roomId.value)
    msgInput.value = ''
    await fetchRoom()
  } catch (e) {
    toast(e.message)
  }
}

async function removeMessage(id) {
  try {
    await roomApi.deleteMessage(id, roomId.value)
    messages.value = messages.value.filter((m) => m.id !== id)
  } catch (e) {
    toast(e.message)
  }
}

function openGoal() {
  const me = members.value.find((m) => m.user_id === auth.user?.id)
  goalDraft.value = {
    target_school: me?.goal?.target_school || auth.user?.target_school || '',
    target_score: me?.goal?.target_score || '',
    words: me?.goal?.words || '',
  }
  showGoal.value = true
}

async function saveGoal() {
  try {
    await roomApi.putGoal({
      target_school: String(goalDraft.value.target_school || '').trim(),
      target_score: String(goalDraft.value.target_score || '').trim(),
      words: String(goalDraft.value.words || '').trim(),
    }, roomId.value)
    showGoal.value = false
    toast('目标已更新')
    await fetchRoom()
  } catch (e) {
    toast(e.message)
  }
}

function openManage() {
  manageForm.value = {
    name: room.value?.name || '',
    intro: room.value?.intro || '',
    visibility: room.value?.visibility || 'public',
  }
  loadApplies()
  showManage.value = true
}

async function saveManage() {
  try {
    await roomApi.update(roomId.value, {
      name: manageForm.value.name.trim(),
      intro: manageForm.value.intro.trim(),
      visibility: manageForm.value.visibility,
    })
    showManage.value = false
    toast('房间信息已更新')
    await fetchRoom()
  } catch (e) {
    toast(e.message)
  }
}

async function changeCode() {
  if (!confirm('更换房间码？旧码会立即失效。')) return
  try {
    const next = await roomApi.newCode(roomId.value)
    room.value = { ...room.value, ...next }
    toast(`新房间码：${next.code}`)
  } catch (e) {
    toast(e.message)
  }
}

async function dissolve() {
  if (!confirm('解散后成员会被移出，且不可恢复，确定解散？')) return
  try {
    await roomApi.dissolve(roomId.value)
    toast('自习室已解散')
    router.replace('/rooms')
  } catch (e) {
    toast(e.message)
  }
}

async function kick(member) {
  if (!confirm(`将「${member.nickname}」移出自习室？`)) return
  try {
    await roomApi.kick(roomId.value, member.user_id)
    toast('已移出')
    await fetchRoom()
  } catch (e) {
    toast(e.message)
  }
}

let pollTimer = null
onMounted(async () => {
  loading.value = true
  await fetchRoom()
  if (!alive) return
  loading.value = false
  if (joined.value) startBeating()
  pollTimer = setInterval(fetchRoom, 15000)
  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('beforeunload', onLeave)
})

function onVisibility() {
  if (!joined.value) return
  beat(document.visibilityState === 'visible' ? undefined : 'offline')
}
function onLeave() { /* App级pagehide按设备上报 */ }
onBeforeUnmount(() => {
  alive = false
  clearInterval(pollTimer)
  clearInterval(beatTimer)
  document.removeEventListener('visibilitychange', onVisibility)
  window.removeEventListener('beforeunload', onLeave)
  // 在其他页面保持在线，由App级心跳接管；仅关闭/后台才上报离线。
})
</script>

<template>
  <div>
    <CopyFallback v-model="manualCopy" />
    <div class="nav">
      <button class="back" @click="router.push('/rooms')"><ArrowLeft :size="20" /></button>
      <div>
        <div class="nav-title">{{ room?.name || '四人自习室' }}</div>
        <div class="nav-sub">大雪深埋，与同道并肩</div>
      </div>
      <button v-if="isOwner" class="switch-btn gear" @click="openManage"><Settings :size="15" /></button>
      <button class="switch-btn" @click="router.push('/rooms')">换房间</button>
    </div>

    <div class="page">
      <!-- 房间头卡 -->
      <div class="room-head">
        <div class="room-top">
          <div class="room-icon"><Users :size="22" /></div>
          <div class="room-meta">
            <div class="room-name">{{ room?.name || '研时 · 四人自习室' }}</div>
            <div class="room-private">
              <Lock v-if="room?.visibility === 'private'" :size="11" :stroke-width="2.5" />
              {{ room?.visibility === 'private' ? '私密 · 凭房间码加入' : '公开 · 欢迎同频研友' }}
              · 无摄像头 · 状态同步
            </div>
            <button v-if="joined && room?.code" class="room-code" @click="copyCode">
              房间码 {{ room.code }}<Copy :size="11" />
            </button>
            <button v-if="joined" class="room-code" @click="copyInvite">{{ room?.visibility === 'private' ? '申请链接' : '房间链接' }}</button>
            <button v-if="joined && room?.my_role !== 'owner'" class="room-code" @click="leaveRoom">退出房间</button>
          </div>
        </div>
        <div class="room-stat">
          <div>
            <div class="rs-num tnum">{{ onlineCount }} / {{ room?.capacity || 4 }}</div>
            <div class="rs-label">当前在线</div>
          </div>
          <div class="rs-line"></div>
          <div>
            <div class="rs-num tnum">{{ fmtSec(todayTotal) }}</div>
            <div class="rs-label">今日房间总时长</div>
          </div>
        </div>
      </div>

      <!-- 未加入 -->
      <div v-if="!joined" class="full-banner">
        <component :is="joinRequired ? Lock : Users" :size="18" />
        <div v-if="isFull">
          <div class="fb-title">自习室已满（{{ room?.member_count || members.length }} / {{ room?.capacity || 4 }}）</div>
          <div class="fb-sub">暂时没有座位，可以换一个自习室，或等成员退出后再加入。</div>
        </div>
        <div v-else-if="joinRequired">
          <div class="fb-title">私密自习室 · 需房主通过</div>
          <div class="fb-sub">
            <template v-if="myApply?.status === 'pending'">申请已提交，等待房主审批，通过后自动进入。</template>
            <template v-else-if="myApply?.status === 'rejected'">上次申请未通过，可以补充说明后再次申请。</template>
            <template v-else>有房间码可直接加入；没有房间码可提交申请，由房主审核。</template>
          </div>
        </div>
        <div v-else>
          <div class="fb-title">你还未加入这个自习室</div>
          <div class="fb-sub">加入后即可同步在线状态、留言和目标墙。</div>
        </div>
        <button v-if="!isFull && !joinRequired" class="join-btn" @click="join"><LogIn :size="14" />加入</button>
      </div>

      <!-- 私密房：房间码直入 / 申请加入 -->
      <div v-if="!joined && joinRequired" class="card apply-card">
        <div class="ac-title"><Lock :size="14" /> 凭房间码直接加入</div>
        <div class="ac-code-row">
          <input v-model="joinCode" maxlength="32" placeholder="输入 6 位房间码" @keyup.enter="join" />
          <button class="cc-btn" @click="join">加入</button>
        </div>
        <div class="ac-divider"></div>
        <div class="ac-title">没有房间码？申请加入</div>
        <template v-if="myApply?.status === 'pending'">
          <div class="ac-pending">
            <span class="ac-dot"></span>
            申请已提交（{{ fmtTime(myApply.created_at) }}），等待房主审批
          </div>
          <div v-if="myApply.message" class="ac-quote">「{{ myApply.message }}」</div>
        </template>
        <template v-else>
          <textarea
            v-model="applyDraft"
            maxlength="200"
            rows="2"
            placeholder="简单说明来意，方便房主判断（选填）"
          ></textarea>
          <div v-if="myApply?.status === 'rejected'" class="ac-reject">上次申请未通过，可补充说明后再次申请。</div>
          <button class="btn btn-primary btn-block mt8" :disabled="applying" @click="applyJoin">
            {{ applying ? '提交中…' : '提交入房申请' }}
          </button>
        </template>
      </div>

      <!-- 座位 -->
      <div v-if="joined || !joinRequired" class="seat-grid">
        <div
          v-for="(seat, i) in seats"
          :key="i"
          class="seat-card"
          :class="{ me: !seat.empty && seat.user_id === auth.user?.id, empty: seat.empty, filled: !seat.empty && seat.user_id !== auth.user?.id }"
        >
          <template v-if="!seat.empty">
            <div class="seat-identity">
              <BlobImage class="seat-avatar" :src="seat.avatar_key" :fallback="schoolLogo(seat.target_school)" :alt="seat.nickname" />
              <span class="seat-figure" :style="{ background: (FIGURE_MAP[seat.figure_id] || FIGURES[0]).bg }" :title="(FIGURE_MAP[seat.figure_id] || FIGURES[0]).name">{{ (FIGURE_MAP[seat.figure_id] || FIGURES[0]).emoji }}</span>
            </div>
            <div class="seat-info">
              <div class="seat-name">
                {{ seat.nickname }}
                <span v-if="seat.user_id === auth.user?.id" class="me-tag">我</span>
                <span v-if="seat.role === 'owner'" class="admin-tag">房主</span>
              </div>
              <div class="seat-school">{{ schoolName(seat.target_school) }}<span v-if="seat.streak"> · 连续{{ seat.streak }}天</span></div>
              <div class="seat-state">
                <span class="state-dot" :style="{ background: presenceText(seat).color }"></span>
                {{ presenceText(seat).label }}
              </div>
            </div>
            <div v-if="seat.today_sec != null" class="seat-min tnum">{{ fmtSec(seat.today_sec) }}</div>
            <button
              v-if="isOwner && seat.user_id !== auth.user?.id && seat.role !== 'owner'"
              class="kick-btn"
              title="移出成员"
              @click.stop="kick(seat)"
            ><UserMinus :size="13" /></button>
          </template>
          <template v-else>
            <div class="seat-empty-ic"><Users :size="22" :stroke-width="1.8" /></div>
            <div class="seat-empty-txt">虚位以待</div>
            <div class="seat-empty-sub">邀请研友加入</div>
          </template>
        </div>
      </div>

      <!-- 排行榜 -->
      <div v-if="joined || !joinRequired" class="card rank-card">
        <div class="rank-head">
          <span class="rank-title"><Trophy :size="16" />专注排行榜</span>
          <div class="rank-tabs">
            <button :class="{ on: rankTab === 'today' }" @click="rankTab = 'today'">今日</button>
            <button :class="{ on: rankTab === 'week' }" @click="rankTab = 'week'">本周</button>
            <button :class="{ on: rankTab === 'all' }" @click="rankTab = 'all'">累计</button>
          </div>
        </div>
        <div v-for="(item, i) in rankList" :key="item.user_id" class="rank-row">
          <span class="rank-no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
          <span class="rank-name">{{ item.member?.nickname || '成员' }}</span>
          <span class="rank-bar"><i :style="{ width: Math.min(100, (item.sec / (rankList[0]?.sec || 1)) * 100) + '%' }"></i></span>
          <span class="rank-sec tnum">{{ fmtSec(item.sec) }}</span>
        </div>
        <div v-if="!rankList.length" class="rank-empty">还没有专注记录</div>
      </div>

      <!-- 目标墙 -->
      <div v-if="joined || !joinRequired" class="card goal-wall">
        <div class="wall-head">
          <span class="rank-title"><Flag :size="16" />目标墙</span>
          <button v-if="joined" class="link-btn" @click="openGoal">填写我的目标</button>
        </div>
        <div v-for="m in members" :key="m.user_id" class="goal-row">
          <BlobImage class="g-avatar" :src="m.avatar_key" :fallback="schoolLogo(m.target_school)" />
          <div class="g-meta">
            <div class="g-name">{{ m.nickname }}</div>
            <div class="g-target">
              <template v-if="m.goal">
                {{ schoolName(m.goal.target_school || m.target_school) }}
                <span v-if="m.goal.target_score" class="g-score">目标 {{ m.goal.target_score }} 分</span>
              </template>
              <template v-else-if="m.presence?.status === 'private'">隐私中</template><template v-else-if="m.presence?.status === 'unshared'">仅同组可见</template><template v-else>{{ schoolName(m.target_school) }}<span class="g-score">暂未填写目标</span></template>
            </div>
            <div v-if="m.goal?.words" class="g-words">「{{ m.goal.words }}」</div>
          </div>
        </div>
        <div v-if="!members.length" class="rank-empty">成员加入后显示</div>
      </div>

      <!-- 留言板 -->
      <div v-if="joined" class="card msg-card">
        <div class="rank-title"><Flame :size="16" />互相打气留言板</div>
        <div class="msg-list">
          <div v-for="m in messages" :key="m.id" class="msg" :class="{ mine: m.mine }">
            <div class="msg-bubble">
              <div class="msg-meta">
                <span>{{ m.nickname }}</span>
                <i>{{ fmtTime(m.created_at) }}</i>
                <button
                  v-if="m.mine || auth.isAdmin"
                  class="msg-del"
                  @click="removeMessage(m.id)"
                ><Trash2 :size="13" /></button>
              </div>
              <div class="msg-content">{{ m.content }}</div>
            </div>
          </div>
          <div v-if="!messages.length" class="rank-empty">还没有留言，说句加油吧</div>
        </div>
        <div v-if="joined" class="msg-input">
          <input v-model="msgInput" maxlength="500" placeholder="给大家留句打气的话…" @keyup.enter="sendMessage" />
          <button @click="sendMessage"><Send :size="17" /></button>
        </div>
      </div>
    </div>

    <!-- 房主管理 -->
    <div v-if="showManage" class="mask" @click.self="showManage = false">
      <div class="sheet">
        <div class="sheet-title">房间管理</div>
        <div v-if="isOwner" class="am-box">
          <div class="am-head">
            入房申请
            <span v-if="applies.length" class="am-count">{{ applies.length }}</span>
          </div>
          <div v-if="!applies.length" class="am-empty">暂无待审申请</div>
          <div v-for="a in applies" :key="a.id" class="am-row">
            <div class="am-info">
              <div class="am-name">
                {{ a.nickname }}<span class="am-time">{{ fmtTime(a.created_at) }}</span>
              </div>
              <div v-if="a.target_school" class="am-school">目标 {{ schoolName(a.target_school) }}</div>
              <div v-if="a.message" class="am-msg">{{ a.message }}</div>
            </div>
            <button class="am-btn ok" :disabled="applyBusyId === a.id" @click="reviewApply(a, true)">通过</button>
            <button class="am-btn no" :disabled="applyBusyId === a.id" @click="reviewApply(a, false)">驳回</button>
          </div>
        </div>
        <label class="sf"><span>房间名</span>
          <input v-model="manageForm.name" maxlength="20" />
        </label>
        <label class="sf"><span>简介</span>
          <input v-model="manageForm.intro" maxlength="200" />
        </label>
        <label class="sf"><span>可见性</span>
          <div class="vis-row">
            <button :class="{ on: manageForm.visibility === 'public' }" @click="manageForm.visibility = 'public'">公开</button>
            <button :class="{ on: manageForm.visibility === 'private' }" @click="manageForm.visibility = 'private'">私密（凭码）</button>
          </div>
        </label>
        <button class="btn btn-primary btn-block mt16" @click="saveManage">保存</button>
        <button class="btn btn-outline btn-block mt8" @click="changeCode">更换房间码</button>
        <button class="btn btn-danger btn-block mt8" @click="dissolve">解散自习室</button>
        <button class="btn btn-ghost btn-block mt8" @click="showManage = false">取消</button>
      </div>
    </div>

    <!-- 目标弹层 -->
    <div v-if="showGoal" class="mask" @click.self="showGoal = false">
      <div class="sheet">
        <div class="sheet-title">我的目标</div>
        <label class="sf"><span>目标院校</span>
          <select v-model="goalDraft.target_school">
            <option value="">请选择</option>
            <option v-for="(s, k) in SCHOOL_MAP" :key="k" :value="k">{{ s.name }}</option>
          </select>
        </label>
        <label class="sf"><span>目标分数</span>
          <input v-model="goalDraft.target_score" type="number" inputmode="numeric" placeholder="如 400" />
        </label>
        <label class="sf"><span>上岸寄语</span>
          <input v-model="goalDraft.words" maxlength="50" placeholder="写给自己的一句话" />
        </label>
        <button class="btn btn-primary btn-block mt16" @click="saveGoal">保存</button>
        <button class="btn btn-ghost btn-block mt8" @click="showGoal = false">取消</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.seat-identity { position: relative; flex-shrink: 0; }.seat-figure { position: absolute; right: -6px; bottom: -3px; border-radius: 50%; width: 25px; height: 25px; display: grid; place-items: center; font-size: 16px; border: 2px solid #fff; }
.room-head {
  background: linear-gradient(150deg, var(--night2), var(--night));
  border-radius: var(--radius);
  padding: 18px;
  color: #fff;
  box-shadow: var(--shadow);
}
.room-top { display: flex; align-items: center; gap: 12px; }
.room-icon {
  width: 44px; height: 44px; border-radius: 13px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex; align-items: center; justify-content: center;
}
.room-name { font-size: 17px; font-weight: 800; }
.full-banner {
  margin-top: 12px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  border-radius: var(--radius-sm);
  background: #fff3df;
  color: #8a5a00;
}
.fb-title { font-size: 14px; font-weight: 800; }
.fb-sub { font-size: 11.5px; line-height: 1.65; margin-top: 3px; }
.join-btn { margin-left: auto; align-self: center; flex-shrink: 0; border: none; border-radius: 9px; background: #b06000; color: #fff; font-size: 12.5px; font-weight: 600; padding: 8px 12px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.nav .back { border: none; background: #fff; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.switch-btn { margin-left: auto; border: 1px solid var(--line); background: #fff; color: var(--sub); border-radius: 9px; padding: 8px 11px; font-size: 12px; cursor: pointer; }
.room-code { margin-top: 6px; border: 1px solid rgba(255,255,255,.28); background: rgba(255,255,255,.14); color: #fff; border-radius: 7px; padding: 3px 8px; font-size: 11px; font-weight: 700; letter-spacing: .5px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.room-private { display: flex; align-items: center; gap: 4px; font-size: 11.5px; color: rgba(255,255,255,.72); margin-top: 3px; }
.room-stat { display: flex; align-items: center; margin-top: 16px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,.14); }
.room-stat > div { flex: 1; text-align: center; }
.rs-num { font-size: 18px; font-weight: 800; }
.rs-label { font-size: 11.5px; color: rgba(255,255,255,.68); margin-top: 2px; }
.rs-line { flex: 0 0 1px; width: 1px; height: 30px; align-self: center; background: rgba(255,255,255,.2); }

.seat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 14px; }
.seat-card { background: var(--card); border-radius: var(--radius); box-shadow: var(--shadow-soft); min-height: 132px; }
.seat-card.me { padding: 14px; grid-column: span 2; display: flex; align-items: center; gap: 12px; }
.seat-card.filled { padding: 12px; display: flex; flex-direction: column; align-items: center; text-align: center; gap: 6px; }
.seat-avatar { width: 54px; height: 54px; border-radius: 50%; object-fit: cover; background: #fff; border: 2px solid #fff; box-shadow: 0 0 0 2px var(--primary); flex-shrink: 0; }
.seat-card.filled .seat-avatar { width: 50px; height: 50px; }
.seat-info { flex: 1; min-width: 0; }
.seat-name { font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
.seat-card.filled .seat-name { justify-content: center; }
.me-tag { font-size: 10px; background: var(--primary); color: #fff; border-radius: 6px; padding: 1px 6px; font-weight: 600; }
.admin-tag { font-size: 10px; background: #fff3df; color: var(--accent-deep); border-radius: 6px; padding: 1px 6px; }
.seat-school { font-size: 12px; color: var(--sub); margin-top: 2px; }
.seat-state { display: flex; align-items: center; gap: 5px; font-size: 12px; color: var(--sub); margin-top: 4px; }
.seat-card.filled .seat-state { justify-content: center; }
.state-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.seat-min { font-size: 13px; font-weight: 700; color: var(--primary); }
.seat-card { position: relative; }
.kick-btn { position: absolute; right: 8px; bottom: 8px; border: 1px solid var(--line); background: #fff; color: var(--faint); width: 24px; height: 24px; border-radius: 7px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.switch-btn.gear { margin-left: auto; width: 32px; height: 32px; padding: 0; display: flex; align-items: center; justify-content: center; }
.switch-btn.gear + .switch-btn { margin-left: 6px; }
.vis-row { display: flex; gap: 8px; }
.vis-row button { flex: 1; height: 40px; border: 1.5px solid var(--line); border-radius: 10px; background: #fff; color: var(--sub); font-size: 12.5px; font-weight: 600; cursor: pointer; }
.vis-row button.on { border-color: transparent; background: var(--primary); color: #fff; }
.seat-card.empty { border: 1.5px dashed #d3deea; box-shadow: none; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 18px; }
.seat-empty-ic { color: #c2cfdf; margin-bottom: 8px; }
.seat-empty-txt { font-size: 14px; font-weight: 700; color: var(--faint); }
.seat-empty-sub { font-size: 11px; color: var(--faint); margin-top: 2px; }

.rank-card, .goal-wall, .msg-card { margin-top: 14px; }
.rank-head, .wall-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.rank-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 700; }
.rank-tabs { display: flex; background: #f1f4fa; border-radius: 8px; padding: 3px; }
.rank-tabs button { border: none; background: transparent; padding: 5px 12px; border-radius: 6px; font-size: 12px; color: var(--sub); cursor: pointer; }
.rank-tabs button.on { background: #fff; color: var(--primary); font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.rank-row { display: flex; align-items: center; gap: 10px; padding: 7px 0; }
.rank-no { width: 22px; height: 22px; border-radius: 50%; background: #eef1f6; color: var(--faint); font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rank-no.top { background: var(--primary); color: #fff; }
.rank-name { width: 56px; font-size: 13px; font-weight: 600; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-bar { flex: 1; height: 8px; background: #f1f4fa; border-radius: 999px; overflow: hidden; }
.rank-bar i { display: block; height: 100%; background: linear-gradient(90deg, #2f6bff, #6aa0ff); border-radius: 999px; }
.rank-sec { font-size: 12.5px; font-weight: 700; color: var(--primary); width: 52px; text-align: right; }
.rank-empty { text-align: center; color: var(--faint); font-size: 13px; padding: 14px 0; }

.link-btn { border: none; background: none; color: var(--primary); font-size: 13px; cursor: pointer; }
.goal-row { display: flex; gap: 11px; padding: 10px 0; border-bottom: 1px solid var(--line); }
.goal-row:last-child { border-bottom: none; }
.g-avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; background: #f1f4fa; flex-shrink: 0; }
.g-meta { flex: 1; min-width: 0; }
.g-name { font-size: 14px; font-weight: 700; }
.g-target { font-size: 12.5px; color: var(--sub); margin-top: 2px; }
.g-score { color: var(--faint); margin-left: 8px; }
.g-words { font-size: 12px; color: var(--accent-deep); margin-top: 3px; }

.msg-list { display: flex; flex-direction: column; gap: 10px; margin: 12px 0; max-height: 320px; overflow-y: auto; }
.msg { display: flex; }
.msg.mine { justify-content: flex-end; }
.msg-bubble { max-width: 78%; background: #f4f6fb; border-radius: 14px; padding: 8px 12px; }
.msg.mine .msg-bubble { background: #e8f0ff; }
.msg-meta { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--faint); }
.msg-del { border: none; background: none; color: var(--faint); cursor: pointer; padding: 0; display: flex; }
.msg-content { font-size: 13.5px; color: var(--ink); margin-top: 3px; line-height: 1.5; word-break: break-word; }
.msg-input { display: flex; gap: 8px; }
.msg-input input { flex: 1; height: 42px; border: 1px solid var(--line); border-radius: 999px; padding: 0 16px; font-size: 14px; background: #fafbfe; }
.msg-input input:focus { outline: none; border-color: var(--primary); background: #fff; }
.msg-input button { width: 42px; height: 42px; border-radius: 50%; border: none; background: var(--primary); color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }

.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); max-height: 86vh; overflow-y: auto; }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; margin-bottom: 14px; }
.sf { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.sf span { font-size: 13px; color: var(--sub); }
.sf input, .sf select { height: 44px; border: 1px solid var(--line); border-radius: 10px; padding: 0 12px; font-size: 15px; background: #fafbfe; }
.sf input:focus, .sf select:focus { outline: none; border-color: var(--primary); background: #fff; }

/* 私密房：房间码 / 入房申请 */
.apply-card { margin-top: 12px; padding: 16px; }
.ac-title { display: flex; align-items: center; gap: 6px; font-size: 13.5px; font-weight: 700; }
.ac-code-row { display: flex; gap: 8px; margin-top: 10px; }
.ac-code-row input { flex: 1; height: 40px; border: 1px solid var(--line); border-radius: 10px; padding: 0 12px; font-size: 14px; background: #fafbfe; letter-spacing: 2px; min-width: 0; }
.ac-code-row input:focus { outline: none; border-color: var(--primary); background: #fff; }
.cc-btn { border: none; background: var(--primary); color: #fff; border-radius: 10px; padding: 0 16px; font-size: 13px; font-weight: 700; cursor: pointer; }
.ac-divider { height: 1px; background: var(--line); margin: 14px 0; }
.apply-card textarea { width: 100%; margin-top: 9px; border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; font-size: 13.5px; font-family: inherit; resize: vertical; background: #fafbfe; box-sizing: border-box; }
.apply-card textarea:focus { outline: none; border-color: var(--primary); background: #fff; }
.ac-pending { display: flex; align-items: center; gap: 7px; margin-top: 10px; font-size: 13px; color: #8a5a00; background: #fff3df; border-radius: 10px; padding: 10px 12px; }
.ac-dot { width: 7px; height: 7px; border-radius: 50%; background: #e8a33d; flex-shrink: 0; }
.ac-quote { margin-top: 8px; font-size: 12.5px; color: var(--sub); }
.ac-reject { margin-top: 8px; font-size: 12px; color: #c0392b; }

/* 房主待审列表 */
.am-box { background: #f7f9fd; border-radius: 12px; padding: 12px; margin-bottom: 14px; }
.am-head { display: flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 700; }
.am-count { background: var(--primary); color: #fff; border-radius: 999px; font-size: 11px; padding: 1px 7px; }
.am-empty { font-size: 12px; color: var(--faint); margin-top: 8px; }
.am-row { display: flex; align-items: center; gap: 8px; padding: 9px 0; border-bottom: 1px solid var(--line); }
.am-row:last-child { border-bottom: none; }
.am-info { flex: 1; min-width: 0; }
.am-name { font-size: 13px; font-weight: 700; display: flex; align-items: baseline; gap: 6px; }
.am-time { font-size: 10.5px; color: var(--faint); font-weight: 400; }
.am-school { font-size: 11.5px; color: var(--sub); margin-top: 2px; }
.am-msg { font-size: 12px; color: var(--sub); margin-top: 2px; word-break: break-word; }
.am-btn { border: none; border-radius: 8px; font-size: 12px; font-weight: 600; padding: 7px 10px; cursor: pointer; flex-shrink: 0; }
.am-btn.ok { background: var(--primary); color: #fff; }
.am-btn.no { background: #fff; color: var(--sub); border: 1px solid var(--line); }
.am-btn:disabled { opacity: .6; cursor: default; }
</style>
