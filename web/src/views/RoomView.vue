<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Lock, Users, Send, Trash2, Flag, Trophy, Flame, ArrowLeft, Copy, LogIn, Settings,
  UserMinus, Check, X, RefreshCw, ArrowDown,
} from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'
import { useAuthStore } from '../stores/auth'
import { useSchoolsStore } from '../stores/schools'
import { roomApi } from '../api'
import { ROOM_SHARING_NOTICE } from '../utils/roomSharing'
import BlobImage from '../components/BlobImage.vue'
import RoomMedia from '../components/RoomMedia.vue'
import { useToast } from '../composables/useToast'
import { useClipboard } from '../composables/useClipboard'
import CopyFallback from '../components/CopyFallback.vue'
import { useStudyRoomStore } from '../stores/studyRoom'
import { FIGURES, FIGURE_MAP } from '../data/figures'

const timer = useTimerStore()
const auth = useAuthStore()
const studyRoom = useStudyRoomStore()
let presenceInitialized = false
const schools = useSchoolsStore()
const { toast } = useToast()
const { copy: copyToClipboard, manualCopy } = useClipboard(toast)
const route = useRoute()
const router = useRouter()
const roomId = computed(() => (route.params.id ? Number(route.params.id) : null))

let alive = true
const room = ref(null)
const joined = ref(true)
const joining = ref(false)
const members = ref([])
const ranking = ref({ today: [], week: [], all: [] })
const messages = ref([])
const rankTab = ref('today')
const loading = ref(false)
const loadError = ref('')
const msgInput = ref('')
const msgListEl = ref(null)
const msgSending = ref(false)
const pendingMsgs = ref([])
const pendingDeletes = ref(new Set())
const removedMessageIds = ref(new Set())
const unread = ref(0)
const atMsgBottom = ref(true)
const displayMessages = computed(() => [...messages.value.filter(m => !pendingDeletes.value.has(m.id) && !removedMessageIds.value.has(m.id)), ...pendingMsgs.value])
const showGoal = ref(false)
const goalDraft = ref({ target_school: '', target_score: '', words: '' })
const showManage = ref(false)
const manageForm = ref({ name: '', intro: '', visibility: 'public' })
const isOwner = computed(() => room.value?.my_role === 'owner')
const preview = ref(null)
const joinCode = ref('')
const applyDraft = ref('')
const applying = ref(false)
const applies = ref([])
const applyBusyId = ref(0)
const joinRequired = computed(() => !!preview.value?.join_required)
const myApply = computed(() => preview.value?.apply || null)

function schoolLogo(key) {
  return schools.logoFor(key)
}
function schoolName(key) {
  return schools.shortFor(key) || '未填写'
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
  if (p.status === 'unshared') return { label: '未确认本房间共享', color: '#8d7fa3' }
  if (!m.online) return { label: '离线', color: '#b6bfcc' }
  if (p.status === 'resting') return { label: '休息中', color: '#46845b' }
  if (p.status === 'away') return { label: '暂离 · 后台', color: '#8d8f96' }
  if (p.status === 'idle') return { label: '空闲', color: '#f59e0b' }
  if (p.status === 'focusing') {
    return { label: `专注中 · ${p.subject_name || '学习'}${p.focus_sec ? ' ' + fmtSec(p.focus_sec) : ''}`, color: '#10b981' }
  }
  return { label: '在线', color: '#32734b' }
}

const showAllMembers=ref(false)
// Keep the first screen compact; the full member list remains available on demand.
const seats = computed(() => {
  const filled = (showAllMembers.value?members.value:members.value.slice(0,4)).map(m => ({ ...m, empty: false }))
  const empties = room.value?.capacity > 0 ? Math.max(0, room.value.capacity - members.value.length) : 1
  return [...filled, ...Array.from({ length: Math.min(empties, 1) }, () => ({ empty: true }))]
})

const todayTotal = computed(() => members.value.reduce((a, m) => a + (m.today_sec || 0), 0))
const onlineCount = computed(() => room.value?.online_count || 0)
const isFull = computed(() =>
  room.value?.capacity > 0 && Math.max(room.value?.member_count || 0, members.value.length) >= room.value.capacity)

const rankList = computed(() => {
  const ids = ranking.value[rankTab.value] || []
  const byId = Object.fromEntries(members.value.map((m) => [m.user_id, m]))
  return ids.map((x) => ({ ...x, member: byId[x.user_id] }))
})
const rankEmptyText = computed(() => ({
  today: '今天还没有人专注，先坐下的同学加油',
  week: '本周还没有专注记录',
  all: '还没有累计专注记录',
}[rankTab.value] || '还没有专注记录'))

// 留言增量合并：只有停留在底部才自动跟随，向上翻看时不抢滚动，改为计数提示
async function applyMessages(list) {
  list = list.filter(m => !removedMessageIds.value.has(m.id))
  const el = msgListEl.value
  const stick = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 32
  const known = new Set(messages.value.map((x) => x.id))
  const added = list.filter((x) => !known.has(x.id)).length
  messages.value = list
  await nextTick()
  if (!msgListEl.value) return
  if (stick) {
    msgListEl.value.scrollTop = msgListEl.value.scrollHeight
    unread.value = 0
  } else if (added > 0) {
    unread.value += added
  }
}

async function pullRoom() {
  const data = await roomApi.get(roomId.value)
  if (!alive) return
  room.value = data.room
  if(route.name==='room' && data.joined!==false)router.replace(`/rooms/${data.room.id}`)
  joined.value = data.joined !== false
  if (joined.value && !presenceInitialized) { studyRoom.enter(data.room,auth.user?.id); presenceInitialized=true }
  preview.value = null
  loadError.value = ''
  members.value = data.members || []
  ranking.value = data.ranking || { today: [], week: [], all: [] }
  await applyMessages(data.messages || [])
}

// 轮询与手动刷新共用一次请求：请求期间再触发会标记后补拉一次，不会并发打接口
let fetching = null
let again = false
function fetchRoom() {
  if (!alive) return Promise.resolve()
  // 私密房间未加入：轮询预览，房主通过后自动切换到正式房间状态
  if (!joined.value && preview.value) return loadPreview()
  if (fetching) {
    again = true
    return fetching
  }
  fetching = (async () => {
    try {
      do {
        again = false
        try {
          await pullRoom()
        } catch (e) {
          if (!alive) return
          if (e.status === 403) return loadPreview()
          if (e.status === 404) {
            if(studyRoom.room?.id===roomId.value)studyRoom.leave()
            toast(e.message)
            router.replace('/rooms')
            return
          }
          loadError.value = e.message || '加载失败，请检查网络后重试'
          break
        }
      } while (again && alive)
    } finally {
      fetching = null
    }
  })()
  return fetching
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

function startBeating() {
  if (!alive) return
  studyRoom.enter(room.value,auth.user?.id)
  beat()
}

async function join() {
  if (joining.value || !confirm(ROOM_SHARING_NOTICE)) return
  joining.value = true
  try {
    await roomApi.join(roomId.value, joinCode.value.trim(), true)
    toast('已加入自习室')
    applyDraft.value = ''
    preview.value = null
    await fetchRoom()
    startBeating()
  } catch (e) {
    toast(e.message)
  } finally { joining.value = false }
}

async function applyJoin() {
  if (applying.value || (myApply.value?.status === 'pending' && myApply.value?.accept_sharing)) return
  if (!confirm(ROOM_SHARING_NOTICE)) return
  applying.value = true
  try {
    await roomApi.apply(roomId.value, applyDraft.value.trim(), true)
    toast('申请已提交，等待房主审批')
    await loadPreview()
  } catch (e) {
    toast(e.message)
  } finally {
    applying.value = false
  }
}

async function confirmRoomSharing() {
  if (joining.value || !confirm(ROOM_SHARING_NOTICE)) return
  joining.value = true
  try { await roomApi.confirmSharing(roomId.value); await fetchRoom(); toast('本房间共享已开启') }
  catch (e) { toast(e.message) }
  finally { joining.value = false }
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
  await copyToClipboard(url.href, '申请链接已复制，确认共享并经房主审批后加入')
}
async function leaveRoom() {
  if (!confirm('退出这个自习室？')) return
  try {
    await roomApi.leave(roomId.value)
    joined.value = false
    if(studyRoom.room?.id===roomId.value)studyRoom.leave()
    toast('已退出自习室')
    router.replace('/rooms')
  } catch (error) { toast(error.message) }
}

async function beat() { window.dispatchEvent(new Event('yanshi:presence')) }

function onMsgScroll() {
  const el = msgListEl.value
  if (!el) return
  atMsgBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 32
  if (atMsgBottom.value) unread.value = 0
}

async function scrollMsgsBottom() {
  await nextTick()
  if (msgListEl.value) msgListEl.value.scrollTop = msgListEl.value.scrollHeight
  atMsgBottom.value = true
  unread.value = 0
}

// 乐观发送：先出现在列表里，失败回滚并还原输入内容
async function sendMessage() {
  const content = msgInput.value.trim()
  if (!content || msgSending.value) return
  const tmp = { tmpId: `tmp-${Date.now()}`, content, nickname: auth.user?.nickname || '我', created_at: new Date().toISOString(), mine: true, pending: true }
  msgInput.value = ''
  pendingMsgs.value.push(tmp)
  msgSending.value = true
  await scrollMsgsBottom()
  try {
    await roomApi.postMessage(content, roomId.value)
  } catch (e) {
    pendingMsgs.value = pendingMsgs.value.filter((x) => x.tmpId !== tmp.tmpId)
    if (!msgInput.value) msgInput.value = content
    toast(e.message)
    return
  } finally {
    msgSending.value = false
  }
  pendingMsgs.value = pendingMsgs.value.filter((x) => x.tmpId !== tmp.tmpId)
  await fetchRoom()
}

// 删除也是先移除再回滚，避免等接口转圈
async function removeMessage(id) {
  if (pendingDeletes.value.has(id)) return
  pendingDeletes.value.add(id)
  try {
    await roomApi.deleteMessage(id, roomId.value)
    removedMessageIds.value.add(id)
    messages.value = messages.value.filter((m) => m.id !== id)
  } catch (e) {
    toast(e.message)
  } finally {
    pendingDeletes.value.delete(id)
  }
}

function openGoal() {
  const me = members.value.find((m) => m.user_id === auth.user?.id)
  const raw = me?.goal?.target_school || auth.user?.target_school || ''
  goalDraft.value = {
    target_school: schools.nameFor(raw),
    target_score: me?.goal?.target_score || '',
    words: me?.goal?.words || '',
  }
  showGoal.value = true
  schools.load().then(() => {
    if (showGoal.value && goalDraft.value.target_school === (raw || '')) {
      goalDraft.value.target_school = schools.nameFor(raw)
    }
  })
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
    if(studyRoom.room?.id===roomId.value)studyRoom.leave()
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
async function retryLoad() {
  if (loading.value) return
  loading.value = true
  loadError.value = ''
  try {
    await fetchRoom()
  } finally {
    if (alive) loading.value = false
  }
}

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
  // 回到前台立刻补一次，避免手机上放很久后看到过期状态
  if (document.visibilityState === 'visible' && alive) fetchRoom()
}
function onLeave() { /* App级pagehide按设备上报 */ }
onBeforeUnmount(() => {
  alive = false
  clearInterval(pollTimer)
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
        <div class="nav-title">{{ room?.name || '好友自习室' }}</div>
        <div class="nav-sub">大雪深埋，与同道并肩</div>
      </div>
      <button v-if="isOwner" class="switch-btn gear" @click="openManage"><Settings :size="15" /></button>
      <button class="switch-btn" @click="router.push('/rooms')">换房间</button>
    </div>

    <div class="page room-layout">
      <!-- 首次进入：骨架屏，避免白屏等待 -->
      <div v-if="loading && !room" class="page-skeleton" role="status">
        <span class="sr-only">正在进入自习室，请稍候…</span>
        <div class="sk-head">
          <i class="sk-ic"></i>
          <div class="sk-lines"><i></i><i class="w60"></i></div>
        </div>
        <div class="sk-seats"><i></i><i></i></div>
        <div class="sk-block"><i></i><i></i><i class="w40"></i></div>
        <div class="sk-block"><i></i><i></i><i class="w60"></i></div>
      </div>

      <!-- 首次加载失败 -->
      <div v-else-if="loadError && !room" class="card load-error">
        <div class="le-title">没能进入这个自习室</div>
        <div class="le-sub">{{ loadError }}</div>
        <button class="btn btn-primary btn-sm" :disabled="loading" @click="retryLoad">
          <RefreshCw :size="14" />{{ loading ? '重试中…' : '重新加载' }}
        </button>
      </div>
      <template v-else>
        <div v-if="loadError" class="sync-bar">
          <span>同步失败：{{ loadError }}</span>
          <button @click="retryLoad">重试</button>
        </div>
        <!-- 房间头卡 -->
        <div class="room-head">
        <div class="room-top">
          <div class="room-icon"><Users :size="22" /></div>
          <div class="room-meta">
            <div class="room-name">{{ room?.name || '研时 · 好友自习室' }}</div>
            <div class="room-private">
              <Lock v-if="room?.visibility === 'private'" :size="11" :stroke-width="2.5" />
              {{ room?.visibility === 'private' ? '私密 · 凭房间码加入' : '公开预览 · 邀请或审批加入' }}
              · 无摄像头 · 状态同步
            </div>
            <button v-if="joined && room?.code" class="room-code" @click="copyCode">
              房间码 {{ room.code }}<Copy :size="11" />
            </button>
            <button v-if="joined" class="room-code" @click="copyInvite">{{ '入房申请链接' }}</button>
            <button v-if="joined && room?.my_role !== 'owner'" class="room-code" @click="leaveRoom">退出房间</button>
          </div>
        </div>
        <div class="room-stat">
          <div>
            <div class="rs-num tnum">{{ onlineCount }}</div>
            <div class="rs-label">当前连接（含暂离）</div>
          </div>
          <div class="rs-line"></div>
          <div>
            <div class="rs-num tnum">{{ fmtSec(todayTotal) }}</div>
            <div class="rs-label">成员今日学习总时长</div>
          </div>
        </div>
      </div>

      <div v-if="joined && room?.sharing_confirmed === false" class="card sharing-consent">
        <strong>旧房间需要重新确认共享</strong><p>当前未向本房间开放你的学习数据。确认后，任务、错题、番茄记录、热力图、学习时长与状态对本房间已确认的成员可见；隐私模式仍可一键隐藏。</p>
        <button class="btn btn-primary" :disabled="joining" @click="confirmRoomSharing">了解并开启本房间共享</button>
      </div>
      <div v-if="joined" class="card co-study-controls">
        <strong>房间成员 {{room?.member_count || members.length}} · {{room?.capacity > 0 ? room.capacity + '人上限' : '不限人数'}}</strong>
        <p>离开共学只停止本次房间状态；成员席位会保留。切到专注、AI 或资料页不会离开共学。</p>
        <button v-if="studyRoom.room?.id!==room?.id" class="btn btn-outline" @click="studyRoom.enter(room,auth.user?.id)">进入共学</button>
        <button v-else class="btn btn-outline" @click="studyRoom.leave()">离开共学</button>
        <button class="btn btn-primary" @click="studyRoom.enter(room,auth.user?.id);router.push('/focus')">{{timer.current?'查看当前专注':'开始专注'}}</button>
        <button class="btn btn-outline" @click="studyRoom.enter(room,auth.user?.id);router.push('/tasks')">选一项任务学习</button>
        <button class="btn btn-outline" @click="router.push({path:'/group',query:{room:room.id}})">查看本房间学习共享</button>
      </div>

      <!-- 未加入 -->
      <div v-if="!joined" class="full-banner">
        <component :is="joinRequired ? Lock : Users" :size="18" />
        <div v-if="isFull">
          <div class="fb-title">自习室已满（{{ room?.member_count || members.length }} / {{ room?.capacity || 50 }}）</div>
          <div class="fb-sub">暂时没有座位，可以换一个自习室，或等成员退出后再加入。</div>
        </div>
        <div v-else-if="joinRequired">
          <div class="fb-title">{{room?.visibility==='private'?'私密自习室 · 凭房间码加入':'公开自习室 · 凭邀请或审批加入'}}</div><p v-if="room?.legacy_member" class="field-hint">旧成员资格不自动开放学习共享，请联系房主获取新的房间码，或重新提交申请。</p>
          <div class="fb-sub">
            <template v-if="room?.visibility==='public' && myApply?.status === 'pending' && myApply?.accept_sharing">申请已提交，等待房主审批，通过后自动进入。</template>
            <template v-else-if="myApply?.status === 'rejected'">上次申请未通过，可以补充说明后再次申请。</template>
            <template v-else>{{room?.visibility==='private'?'请向房主获取房间码，确认共享后加入。':'有房间码可直接加入；也可提交申请，由房主审核。'}}</template>
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
          <button class="cc-btn" :disabled="joining" @click="join">{{ joining ? '加入中…' : '确认共享并加入' }}</button>
        </div>
        <div class="ac-divider"></div>
        <div v-if="room?.visibility==='public'" class="ac-title">申请加入公开房间</div><p class="field-hint">加入后与本房间已确认的成员默认互看历史学习数据；隐私模式可一键隐藏。账号密码、AI 密钥和聊天、个人备注不共享。</p>
        <template v-if="room?.visibility==='public' && myApply?.status === 'pending' && myApply?.accept_sharing">
          <div class="ac-pending">
            <span class="ac-dot"></span>
            申请已提交（{{ fmtTime(myApply.created_at) }}），等待房主审批
          </div>
          <div v-if="myApply.message" class="ac-quote">「{{ myApply.message }}」</div>
        </template>
        <template v-else-if="room?.visibility==='public'">
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
      <RoomMedia v-if="joined && room?.room_type==='av_room' && room?.media_mode==='mesh'" :room-id="room.id" />
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
                <span class="state-dot" :class="{ live: seat.online && seat.presence?.status === 'focusing' }" :style="{ background: presenceText(seat).color }"></span>
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

      <button v-if="members.length>4" class="btn btn-outline btn-block mt8" @click="showAllMembers=!showAllMembers">{{showAllMembers?'收起成员列表':`查看全部 ${members.length} 位成员`}}</button>
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
        <div v-for="(item, i) in rankList" :key="item.user_id" class="rank-row" :class="{ me: item.user_id === auth.user?.id }">
          <span class="rank-no" :class="{ top: i < 3 }">{{ i + 1 }}</span>
          <span class="rank-name">
            {{ item.member?.nickname || '成员' }}
            <em v-if="item.user_id === auth.user?.id" class="rank-me-tag">我</em>
          </span>
          <span class="rank-bar"><i :style="{ width: Math.min(100, (item.sec / (rankList[0]?.sec || 1)) * 100) + '%' }"></i></span>
          <span class="rank-sec tnum">{{ fmtSec(item.sec) }}</span>
        </div>
        <div v-if="!rankList.length" class="rank-empty">{{ rankEmptyText }}</div>
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
        <div class="msg-wrap">
          <div ref="msgListEl" class="msg-list" @scroll.passive="onMsgScroll">
            <div
              v-for="m in displayMessages"
              :key="m.id || m.tmpId"
              class="msg"
              :class="{ mine: m.mine, pending: m.pending }"
            >
              <div class="msg-bubble">
                <div class="msg-meta">
                  <span>{{ m.nickname }}</span>
                  <i>{{ m.pending ? '发送中…' : fmtTime(m.created_at) }}</i>
                  <button
                    v-if="!m.pending && (m.mine || auth.isAdmin)"
                    class="msg-del"
                    title="删除这条留言"
                    @click="removeMessage(m.id)"
                  ><Trash2 :size="13" /></button>
                </div>
                <div class="msg-content">{{ m.content }}</div>
              </div>
            </div>
            <div v-if="!displayMessages.length" class="rank-empty">还没有留言，说句加油吧</div>
          </div>
          <button v-if="unread" class="msg-new" @click="scrollMsgsBottom">
            有 {{ unread }} 条新留言 <ArrowDown :size="13" />
          </button>
        </div>
        <div class="msg-input">
          <input
            v-model="msgInput"
            maxlength="500"
            placeholder="给大家留句打气的话…"
            @keyup.enter="sendMessage"
          />
          <button :disabled="msgSending || !msgInput.trim()" title="发送留言" @click="sendMessage">
            <Send :size="17" />
          </button>
        </div>
      </div>
      </template>
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
            <option v-for="s in schools.choices" :key="s.key" :value="s.name">{{ s.name }}</option>
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
  background: linear-gradient(150deg, #32734b, #312e81 65%);
  border-radius: var(--radius);
  padding: 16px;
  color: #fff;
  box-shadow: 0 10px 24px rgba(49, 46, 129, 0.22);
}
.room-top { display: flex; align-items: center; gap: 8px; }
.room-icon {
  width: 44px; height: 44px; border-radius: 12px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex; align-items: center; justify-content: center;
}
.room-name { font-size: 20px; font-weight: 800; }
.full-banner {
  margin-top: 8px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  background: #fff7ed;
  color: #92400e;
}
.fb-title { font-size: 14px; font-weight: 800; }
.fb-sub { font-size: 14px; line-height: 1.6; margin-top: 4px; }
.join-btn { margin-left: auto; align-self: center; flex-shrink: 0; border: none; border-radius: 8px; background: #b45309; color: #fff; font-size: 14px; font-weight: 600; padding: 8px 16px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.nav .back { border: none; background: rgba(255, 255, 255, 0.72); width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.switch-btn { margin-left: auto; border: 1px solid rgba(50, 115, 75, 0.14); background: rgba(255, 255, 255, 0.72); color: var(--sub); border-radius: 8px; padding: 8px 16px; font-size: 14px; cursor: pointer; }
.room-code { margin-top: 4px; border: 1px solid rgba(255,255,255,.28); background: rgba(255,255,255,.14); color: #fff; border-radius: 8px; padding: 4px 8px; font-size: 14px; font-weight: 700; letter-spacing: .5px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.room-private { display: flex; align-items: center; gap: 4px; font-size: 14px; color: rgba(255,255,255,.72); margin-top: 4px; }
.room-stat { display: flex; align-items: center; margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.14); }
.room-stat > div { flex: 1; text-align: center; }
.rs-num { font-size: 20px; font-weight: 800; }
.rs-label { font-size: 14px; color: rgba(255,255,255,.68); margin-top: 4px; }
.rs-line { flex: 0 0 1px; width: 1px; height: 30px; align-self: center; background: rgba(255,255,255,.2); }

.seat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 16px; }
.seat-card { background: var(--card); border: 1px solid rgba(255, 255, 255, 0.85); border-radius: var(--radius); box-shadow: var(--shadow); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); min-height: 132px; }
.seat-card.me { padding: 16px; grid-column: span 2; display: flex; align-items: center; gap: 8px; }
.seat-card.filled { padding: 16px; display: flex; flex-direction: column; align-items: center; text-align: center; gap: 8px; }
.seat-avatar { width: 54px; height: 54px; border-radius: 50%; object-fit: cover; background: #fff; border: 2px solid #fff; box-shadow: 0 0 0 2px var(--primary); flex-shrink: 0; }
.seat-card.filled .seat-avatar { width: 50px; height: 50px; }
.seat-info { flex: 1; min-width: 0; }
.seat-name { font-size: 14px; font-weight: 800; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.seat-card.filled .seat-name { justify-content: center; }
.me-tag { font-size: 12px; background: var(--primary-grad); color: #fff; border-radius: 6px; padding: 2px 8px; font-weight: 600; }
.admin-tag { font-size: 12px; background: rgba(245, 158, 11, 0.12); color: var(--accent-deep); border-radius: 6px; padding: 2px 8px; }
.seat-school { font-size: 14px; color: var(--sub); margin-top: 4px; }
.seat-state { display: flex; align-items: center; gap: 4px; font-size: 14px; color: var(--sub); margin-top: 4px; }
.seat-card.filled .seat-state { justify-content: center; }
.state-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.seat-min { font-size: 14px; font-weight: 700; color: var(--primary); }
.seat-card { position: relative; }
.kick-btn { position: absolute; right: 8px; bottom: 8px; border: 1px solid var(--line); background: rgba(255, 255, 255, 0.9); color: var(--faint); width: 24px; height: 24px; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.switch-btn.gear { margin-left: auto; width: 32px; height: 32px; padding: 0; display: flex; align-items: center; justify-content: center; }
.switch-btn.gear + .switch-btn { margin-left: 8px; }
.vis-row { display: flex; gap: 8px; }
.vis-row button { flex: 1; height: 40px; border: 1px solid rgba(50, 115, 75, 0.16); border-radius: 8px; background: rgba(255, 255, 255, 0.8); color: var(--sub); font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.24s ease, color 0.24s ease; }
.vis-row button.on { border-color: transparent; background: var(--primary-grad); color: #fff; }
.seat-card.empty { border: 1px dashed rgba(50, 115, 75, 0.22); box-shadow: none; background: rgba(255, 255, 255, 0.5); backdrop-filter: none; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 16px; }
.seat-empty-ic { color: #c3c8dd; margin-bottom: 8px; }
.seat-empty-txt { font-size: 14px; font-weight: 700; color: var(--faint); }
.seat-empty-sub { font-size: 14px; color: var(--faint); margin-top: 4px; }

.rank-card, .goal-wall, .msg-card { margin-top: 16px; }
.rank-head, .wall-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.rank-title { display: flex; align-items: center; gap: 4px; font-size: 14px; font-weight: 700; }
.rank-tabs { display: flex; background: rgba(50, 115, 75, 0.06); border-radius: 8px; padding: 4px; }
.rank-tabs button { border: none; background: transparent; padding: 4px 8px; border-radius: 6px; font-size: 14px; color: var(--sub); cursor: pointer; }
.rank-tabs button.on { background: #fff; color: var(--primary); font-weight: 700; box-shadow: var(--shadow-soft); }
.rank-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; }
.rank-no { width: 24px; height: 24px; border-radius: 50%; background: rgba(50, 115, 75, 0.08); color: var(--faint); font-size: 14px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.rank-no.top { background: var(--primary-grad); color: #fff; }
.rank-name { width: 56px; font-size: 14px; font-weight: 600; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rank-bar { flex: 1; height: 8px; background: rgba(50, 115, 75, 0.08); border-radius: 999px; overflow: hidden; }
.rank-bar i { display: block; height: 100%; background: var(--primary-grad); border-radius: 999px; }
.rank-sec { font-size: 14px; font-weight: 700; color: var(--primary); width: 52px; text-align: right; }
.rank-empty { text-align: center; color: var(--faint); font-size: 14px; padding: 16px 0; }

.link-btn { border: none; background: none; color: var(--primary); font-size: 14px; cursor: pointer; }
.goal-row { display: flex; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.goal-row:last-child { border-bottom: none; }
.g-avatar { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; background: rgba(50, 115, 75, 0.08); flex-shrink: 0; }
.g-meta { flex: 1; min-width: 0; }
.g-name { font-size: 14px; font-weight: 700; }
.g-target { font-size: 14px; color: var(--sub); margin-top: 2px; }
.g-score { color: var(--faint); margin-left: 8px; }
.g-words { font-size: 14px; color: var(--accent-deep); margin-top: 4px; }

.msg-list { display: flex; flex-direction: column; gap: 8px; margin: 8px 0; max-height: 320px; overflow-y: auto; }
.msg { display: flex; }
.msg.mine { justify-content: flex-end; }
.msg-bubble { max-width: 78%; background: rgba(50, 115, 75, 0.06); border-radius: 12px; padding: 8px 16px; }
.msg.mine .msg-bubble { background: rgba(50, 115, 75, 0.14); }
.msg-meta { display: flex; align-items: center; gap: 4px; font-size: 14px; color: var(--faint); }
.msg-del { border: none; background: none; color: var(--faint); cursor: pointer; padding: 0; display: flex; }
.msg-content { font-size: 14px; color: var(--ink); margin-top: 4px; line-height: 1.6; word-break: break-word; }
.msg-input { display: flex; gap: 8px; }
.msg-input input { flex: 1; height: 40px; border: 1px solid rgba(50, 115, 75, 0.16); border-radius: 999px; padding: 0 16px; font-size: 14px; background: rgba(255, 255, 255, 0.9); transition: border-color 0.24s ease, box-shadow 0.24s ease; }
.msg-input input:focus { outline: none; border-color: rgba(50, 115, 75, 0.5); box-shadow: 0 0 0 3px rgba(50, 115, 75, 0.12); }
.msg-input button { width: 40px; height: 40px; border-radius: 50%; border: none; background: var(--primary-grad); color: #fff; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; box-shadow: 0 6px 16px rgba(50, 115, 75, 0.24); }

.mask { position: fixed; inset: 0; background: rgba(30, 27, 75, 0.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 24px 24px 0 0; padding: 24px 16px calc(24px + env(safe-area-inset-bottom)); max-height: 86vh; overflow-y: auto; }
.sheet-title { font-size: 20px; font-weight: 800; text-align: center; margin-bottom: 16px; }
.sf { display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px; }
.sf span { font-size: 14px; color: var(--sub); }
.sf input, .sf select { height: 44px; border: 1px solid rgba(50, 115, 75, 0.16); border-radius: 8px; padding: 0 16px; font-size: 14px; background: rgba(255, 255, 255, 0.9); }
.sf input:focus, .sf select:focus { outline: none; border-color: rgba(50, 115, 75, 0.5); box-shadow: 0 0 0 3px rgba(50, 115, 75, 0.12); }

/* 私密房：房间码 / 入房申请 */
.apply-card { margin-top: 16px; padding: 16px; }
.ac-title { display: flex; align-items: center; gap: 4px; font-size: 14px; font-weight: 700; }
.ac-code-row { display: flex; gap: 8px; margin-top: 8px; }
.ac-code-row input { flex: 1; height: 40px; border: 1px solid rgba(50, 115, 75, 0.16); border-radius: 8px; padding: 0 16px; font-size: 14px; background: rgba(255, 255, 255, 0.9); letter-spacing: 2px; min-width: 0; }
.ac-code-row input:focus { outline: none; border-color: rgba(50, 115, 75, 0.5); box-shadow: 0 0 0 3px rgba(50, 115, 75, 0.12); }
.cc-btn { border: none; background: var(--primary-grad); color: #fff; border-radius: 8px; padding: 0 16px; font-size: 14px; font-weight: 700; cursor: pointer; box-shadow: 0 6px 16px rgba(50, 115, 75, 0.2); }
.ac-divider { height: 1px; background: var(--line); margin: 16px 0; }
.apply-card textarea { width: 100%; margin-top: 8px; border: 1px solid rgba(50, 115, 75, 0.16); border-radius: 8px; padding: 8px 16px; font-size: 14px; font-family: inherit; resize: vertical; background: rgba(255, 255, 255, 0.9); box-sizing: border-box; }
.apply-card textarea:focus { outline: none; border-color: rgba(50, 115, 75, 0.5); box-shadow: 0 0 0 3px rgba(50, 115, 75, 0.12); }
.ac-pending { display: flex; align-items: center; gap: 8px; margin-top: 8px; font-size: 14px; color: #92400e; background: #fff7ed; border-radius: 8px; padding: 8px 16px; }
.ac-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); flex-shrink: 0; }
.ac-quote { margin-top: 8px; font-size: 14px; color: var(--sub); }
.ac-reject { margin-top: 8px; font-size: 14px; color: var(--red); }

/* 房主待审列表 */
.am-box { background: rgba(50, 115, 75, 0.04); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.am-head { display: flex; align-items: center; gap: 4px; font-size: 14px; font-weight: 700; }
.am-count { background: var(--primary-grad); color: #fff; border-radius: 999px; font-size: 12px; padding: 2px 8px; }
.am-empty { font-size: 14px; color: var(--faint); margin-top: 8px; }
.am-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.am-row:last-child { border-bottom: none; }
.am-info { flex: 1; min-width: 0; }
.am-name { font-size: 14px; font-weight: 700; display: flex; align-items: baseline; gap: 4px; }
.am-time { font-size: 14px; color: var(--faint); font-weight: 400; }
.am-school { font-size: 14px; color: var(--sub); margin-top: 2px; }
.am-msg { font-size: 14px; color: var(--sub); margin-top: 2px; word-break: break-word; }
.am-btn { border: none; border-radius: 8px; font-size: 14px; font-weight: 600; padding: 8px 12px; cursor: pointer; flex-shrink: 0; }
.am-btn.ok { background: var(--primary-grad); color: #fff; }
.am-btn.no { background: #fff; color: var(--sub); border: 1px solid var(--line); }
.am-btn:disabled { opacity: .6; cursor: default; }

/* 加载骨架 / 同步失败 */
.page-skeleton { display: flex; flex-direction: column; gap: 16px; }
.sk-head { background: var(--card); border: 1px solid rgba(255, 255, 255, 0.85); border-radius: var(--radius); padding: 16px; display: flex; gap: 8px; align-items: center; box-shadow: var(--shadow); }
.sk-ic { width: 44px; height: 44px; border-radius: 12px; background: rgba(50, 115, 75, 0.1); flex-shrink: 0; }
.sk-lines { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.sk-lines i, .sk-block i { display: block; height: 12px; border-radius: 6px; background: rgba(50, 115, 75, 0.08); width: 100%; }
.sk-lines i.w60, .sk-block i.w60 { width: 60%; height: 8px; }
.sk-block i.w40 { width: 40%; }
.sk-seats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.sk-seats i { height: 132px; border-radius: var(--radius); background: rgba(255, 255, 255, 0.7); border: 1px solid rgba(255, 255, 255, 0.85); }
.sk-block { background: var(--card); border: 1px solid rgba(255, 255, 255, 0.85); border-radius: var(--radius); padding: 16px; display: flex; flex-direction: column; gap: 8px; }
.page-skeleton i { animation: sk-breathe 1.6s ease-in-out infinite; }
@keyframes sk-breathe { 0%, 100% { opacity: .5; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .page-skeleton i { animation: none; } }

.load-error { margin-top: 8px; padding: 24px 16px; text-align: center; }
.le-title { font-size: 14px; font-weight: 800; }
.le-sub { font-size: 14px; color: var(--sub); line-height: 1.6; margin: 8px 0 16px; }
.sync-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; padding: 8px 16px; border-radius: 8px; background: rgba(245, 158, 11, 0.1); color: var(--accent-deep); font-size: 14px; }
.sync-bar span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sync-bar button { border: none; background: none; color: var(--primary); font-size: 14px; font-weight: 700; cursor: pointer; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

/* 留言：乐观发送、向上翻看不被抢滚动 */
.msg-wrap { position: relative; }
.msg.pending { opacity: .6; }
.msg-new { position: absolute; left: 50%; bottom: 8px; transform: translateX(-50%); border: none; border-radius: 999px; background: var(--primary-grad); color: #fff; font-size: 14px; font-weight: 600; padding: 4px 12px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; box-shadow: 0 6px 16px rgba(50, 115, 75, 0.28); transition: transform 0.2s ease; }
.msg-new:active { transform: translateX(-50%) scale(0.96); }
.msg-input button:disabled { opacity: .45; cursor: default; box-shadow: none; }

/* 排行榜高亮自己 */
.rank-name { width: 64px; }
.rank-row.me { background: rgba(50, 115, 75, 0.05); border-radius: 8px; padding-left: 8px; padding-right: 8px; }
.rank-me-tag { font-style: normal; font-size: 12px; background: rgba(50, 115, 75, 0.12); color: var(--primary); border-radius: 4px; padding: 0 4px; margin-left: 2px; }

/* 专注中的状态点轻微呼吸，表示实时同步中；关闭动画偏好时静止 */
.state-dot.live { animation: dot-breathe 2.4s ease-in-out infinite; }
@keyframes dot-breathe {
  0%, 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.32); }
  50% { box-shadow: 0 0 0 4px rgba(16, 185, 129, 0); }
}
@media (prefers-reduced-motion: reduce) { .state-dot.live { animation: none; } }
</style>
