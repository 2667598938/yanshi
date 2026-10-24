<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Lock, Users, Send, Trash2, Flag, Trophy, Flame } from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
import { useAuthStore } from '../stores/auth'
import { roomApi } from '../api'
import { SCHOOL_MAP } from '../data/schools'
import BlobImage from '../components/BlobImage.vue'
import { useToast } from '../composables/useToast'

const timer = useTimerStore()
const subjects = useSubjectsStore()
const auth = useAuthStore()
const { toast } = useToast()

const room = ref(null)
const members = ref([])
const ranking = ref({ today: [], week: [], all: [] })
const messages = ref([])
const rankTab = ref('today')
const loading = ref(false)
const msgInput = ref('')
const showGoal = ref(false)
const goalDraft = ref({ target_school: '', target_score: '', words: '' })

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
  if (!m.online) return { label: '离线', color: '#b6bfcc' }
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
const onlineCount = computed(() => members.value.filter((m) => m.online).length)

const rankList = computed(() => {
  const ids = ranking.value[rankTab.value] || []
  const byId = Object.fromEntries(members.value.map((m) => [m.user_id, m]))
  return ids.map((x) => ({ ...x, member: byId[x.user_id] }))
})

function buildHeartbeat() {
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
  return { status: 'online', subject_client_id: null, subject_name: null, activity_type: null, mode: null, focus_started_at: null }
}

async function fetchRoom() {
  try {
    const data = await roomApi.get()
    room.value = data.room
    members.value = data.members || []
    ranking.value = data.ranking || { today: [], week: [], all: [] }
    messages.value = data.messages || []
  } catch (e) {
    // 静默，轮询下次再试
  }
}

async function beat(statusOverride) {
  try {
    const body = buildHeartbeat()
    if (statusOverride) body.status = statusOverride
    await roomApi.heartbeat(body)
  } catch {
    /* 忽略单次心跳失败 */
  }
}

async function sendMessage() {
  const content = msgInput.value.trim()
  if (!content) return
  try {
    await roomApi.postMessage(content)
    msgInput.value = ''
    await fetchRoom()
  } catch (e) {
    toast(e.message)
  }
}

async function removeMessage(id) {
  try {
    await roomApi.deleteMessage(id)
    messages.value = messages.value.filter((m) => m.id !== id)
  } catch (e) {
    toast(e.message)
  }
}

function openGoal() {
  const me = members.value.find((m) => m.user_id === auth.user?.id)
  goalDraft.value = {
    target_school: me?.goal?.target_school || auth.user?.target_school || '',
    target_score: me?.goal?.target_score ?? auth.user?.exam_year ?? '',
    words: me?.goal?.words || '',
  }
  showGoal.value = true
}

async function saveGoal() {
  try {
    await roomApi.putGoal({
      target_school: goalDraft.value.target_school || null,
      target_score: goalDraft.value.target_score ? Number(goalDraft.value.target_score) : null,
      words: goalDraft.value.words || null,
    })
    showGoal.value = false
    toast('目标已更新')
    await fetchRoom()
  } catch (e) {
    toast(e.message)
  }
}

let pollTimer = null
let beatTimer = null
onMounted(async () => {
  loading.value = true
  await fetchRoom()
  loading.value = false
  beat('online')
  pollTimer = setInterval(fetchRoom, 15000)
  beatTimer = setInterval(() => beat(), 20000)
  document.addEventListener('visibilitychange', onVisibility)
  window.addEventListener('beforeunload', onLeave)
})

function onVisibility() {
  beat(document.visibilityState === 'visible' ? (timer.current ? 'focusing' : 'online') : 'offline')
}
function onLeave() {
  // 页面关闭尽力上报 offline
  try {
    const token = auth.accessToken
    const payload = JSON.stringify({ status: 'offline', subject_client_id: null, subject_name: null, activity_type: null, mode: null, focus_started_at: null })
    navigator.sendBeacon &&
      navigator.sendBeacon('/api/v1/room/heartbeat', new Blob([payload], { type: 'application/json' }))
  } catch {
    /* 关闭页面无法保证 */
  }
}
onBeforeUnmount(() => {
  clearInterval(pollTimer)
  clearInterval(beatTimer)
  document.removeEventListener('visibilitychange', onVisibility)
  window.removeEventListener('beforeunload', onLeave)
  beat('offline')
})
</script>

<template>
  <div>
    <div class="nav">
      <div>
        <div class="nav-title">四人自习室</div>
        <div class="nav-sub">大雪深埋，与同道并肩</div>
      </div>
    </div>

    <div class="page">
      <!-- 房间头卡 -->
      <div class="room-head">
        <div class="room-top">
          <div class="room-icon"><Users :size="22" /></div>
          <div class="room-meta">
            <div class="room-name">{{ room?.name || '研时 · 四人自习室' }}</div>
            <div class="room-private">
              <Lock :size="11" :stroke-width="2.5" />私密 · 仅四人可见 · 无摄像头 · 不对外开放
            </div>
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

      <!-- 座位 -->
      <div class="seat-grid">
        <div
          v-for="(seat, i) in seats"
          :key="i"
          class="seat-card"
          :class="{ me: !seat.empty && seat.user_id === auth.user?.id, empty: seat.empty, filled: !seat.empty && seat.user_id !== auth.user?.id }"
        >
          <template v-if="!seat.empty">
            <BlobImage class="seat-avatar" :src="seat.avatar_key" :fallback="schoolLogo(seat.target_school)" :alt="seat.nickname" />
            <div class="seat-info">
              <div class="seat-name">
                {{ seat.nickname }}
                <span v-if="seat.user_id === auth.user?.id" class="me-tag">我</span>
                <span v-if="seat.role === 'admin'" class="admin-tag">管理员</span>
              </div>
              <div class="seat-school">{{ schoolName(seat.target_school) }}<span v-if="seat.streak"> · 连续{{ seat.streak }}天</span></div>
              <div class="seat-state">
                <span class="state-dot" :style="{ background: presenceText(seat).color }"></span>
                {{ presenceText(seat).label }}
              </div>
            </div>
            <div class="seat-min tnum">{{ fmtSec(seat.today_sec) }}</div>
          </template>
          <template v-else>
            <div class="seat-empty-ic"><Users :size="22" :stroke-width="1.8" /></div>
            <div class="seat-empty-txt">虚位以待</div>
            <div class="seat-empty-sub">邀请研友加入</div>
          </template>
        </div>
      </div>

      <!-- 排行榜 -->
      <div class="card rank-card">
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
      <div class="card goal-wall">
        <div class="wall-head">
          <span class="rank-title"><Flag :size="16" />目标墙</span>
          <button class="link-btn" @click="openGoal">填写我的目标</button>
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
              <template v-else>{{ schoolName(m.target_school) }}<span class="g-score">暂未填写目标</span></template>
            </div>
            <div v-if="m.goal?.words" class="g-words">「{{ m.goal.words }}」</div>
          </div>
        </div>
        <div v-if="!members.length" class="rank-empty">成员加入后显示</div>
      </div>

      <!-- 留言板 -->
      <div class="card msg-card">
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
        <div class="msg-input">
          <input v-model="msgInput" maxlength="500" placeholder="给大家留句打气的话…" @keyup.enter="sendMessage" />
          <button @click="sendMessage"><Send :size="17" /></button>
        </div>
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
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; margin-bottom: 14px; }
.sf { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.sf span { font-size: 13px; color: var(--sub); }
.sf input, .sf select { height: 44px; border: 1px solid var(--line); border-radius: 10px; padding: 0 12px; font-size: 15px; background: #fafbfe; }
.sf input:focus, .sf select:focus { outline: none; border-color: var(--primary); background: #fff; }
</style>
