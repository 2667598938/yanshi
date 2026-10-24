<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronRight, Pencil, Target, Clock3, Bell, NotebookPen,
  Sparkles, Trash2, Info, Check, ListChecks, Download, Camera,
  LogOut, ShieldCheck, FileText, BookMarked,
} from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import { SCHOOLS, SCHOOL_MAP } from '../data/schools'
import { db } from '../db'
import { resetSyncState } from '../sync/engine'
import { blobToDataUrl } from '../utils/image'
import { fmtMinutes, todayKey } from '../utils/date'
import { authApi, publicApi, attachmentApi } from '../api'
import BlobImage from '../components/BlobImage.vue'
import { useToast } from '../composables/useToast'

const router = useRouter()
const timer = useTimerStore()
const app = useAppStore()
const auth = useAuthStore()
const { toast } = useToast()

const sheetType = ref(null)
const nickDraft = ref(app.nickname)
const uploading = ref(false)
const fileInput = ref(null)
const showLegal = ref(false)
const legal = ref(null)
const legalTab = ref('terms')

const school = computed(() => SCHOOL_MAP[auth.user?.target_school || app.dreamSchool] || SCHOOL_MAP[app.dreamSchool])
const avatar = computed(() => auth.user?.avatar_key || '')

const goals = [
  { min: 120, label: '2 小时' },
  { min: 240, label: '4 小时' },
  { min: 300, label: '5 小时' },
  { min: 480, label: '8 小时' },
  { min: 600, label: '10 小时' },
]

function open(type) {
  if (type === 'nickname') nickDraft.value = auth.user?.nickname || app.nickname
  sheetType.value = type
}
function close() {
  sheetType.value = null
}

async function saveNickname() {
  const name = nickDraft.value.trim()
  if (name.length < 2) return toast('昵称至少 2 个字')
  try {
    const user = await authApi.updateMe({ nickname: name })
    auth.setUser(user)
    app.setNickname(name)
    close()
    toast('昵称已更新')
  } catch (e) {
    toast(e.message)
  }
}

async function pickSchool(key) {
  try {
    const user = await authApi.updateMe({ target_school: key })
    auth.setUser(user)
    app.setDreamSchool(key)
    close()
    toast('梦校已更新')
  } catch (e) {
    toast(e.message)
  }
}

async function pickGoal(min) {
  try {
    const user = await authApi.updateMe({ daily_goal_min: min })
    auth.setUser(user)
    app.setDailyGoal(min)
    close()
    toast('今日目标已更新')
  } catch (e) {
    toast(e.message)
  }
}

function pickAvatar() {
  fileInput.value?.click()
}
async function onAvatarChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    await attachmentApi.uploadAvatar(file)
    await auth.fetchMe()
    toast('头像已更新')
  } catch (err) {
    toast(err.message || '头像上传失败')
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function logout() {
  await auth.logout()
  // 清理待发队列与同步状态，防止换号/公用设备时把上一个账号的本地改动推到新账号
  await resetSyncState()
  router.replace('/login')
}

async function openLegal(tab) {
  legalTab.value = tab
  if (!legal.value) {
    try {
      legal.value = await publicApi.legal()
    } catch {
      legal.value = { terms: '加载失败', privacy: '加载失败' }
    }
  }
  showLegal.value = true
}

async function exportBackup() {
  try {
    const [subjects_, sessions_, tasks_, mistakes_] = await Promise.all([
      db.subjects.toArray(), db.sessions.toArray(), db.tasks.toArray(), db.mistakes.toArray(),
    ])
    const mm = []
    for (const m of mistakes_) {
      const images = []
      for (const b of m.images || []) {
        if (typeof b === 'string') { images.push(b); continue }
        try { images.push(await blobToDataUrl(b)) } catch { /* 跳过 */ }
      }
      mm.push({ ...m, images })
    }
    const payload = {
      app: 'yanshi', version: 3, exportedAt: new Date().toISOString(),
      settings: JSON.parse(localStorage.getItem('yanshi:app') || '{}'),
      subjects: subjects_, sessions: sessions_, tasks: tasks_, mistakes: mm,
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `研时备份_${todayKey()}.json`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    toast('已导出完整备份（含错题图片）')
  } catch {
    toast('导出失败，请稍后再试')
  }
}

async function clearData() {
  await db.sessions.clear()
  await db.tasks.clear()
  await db.mistakes.clear()
  localStorage.removeItem('yanshi:current')
  close()
  toast('已清空专注 / 任务 / 错题记录')
  setTimeout(() => location.reload(), 600)
}

async function toggleNotify() {
  if (!('Notification' in window)) return toast('当前浏览器不支持通知')
  let enabled = app.notifyEnabled
  if (Notification.permission === 'granted') {
    enabled = !enabled
  } else {
    const p = await Notification.requestPermission()
    if (p !== 'granted') return toast('未获得通知权限')
    enabled = true
  }
  try {
    const user = await authApi.updateMe({ notify_enabled: enabled })
    auth.setUser(user)
    app.setNotifyEnabled(enabled)
    toast(enabled ? '已开启到点通知' : '已关闭通知')
  } catch (e) {
    toast(e.message)
  }
}

onMounted(() => {
  if (auth.user) {
    app.setNickname(auth.user.nickname)
    if (auth.user.target_school) app.setDreamSchool(auth.user.target_school)
    if (auth.user.daily_goal_min) app.setDailyGoal(auth.user.daily_goal_min)
  }
})
</script>

<template>
  <div>
    <div class="nav"><div class="nav-title">我的</div></div>

    <div class="page">
      <!-- 个人卡 -->
      <div class="profile">
        <img class="watermark" :src="school.logo" alt="" />
        <div class="pf-main">
          <div class="avatar-wrap" @click="pickAvatar">
            <BlobImage class="pf-avatar" :src="avatar" :fallback="school.logo" :alt="auth.user?.nickname" />
            <span class="cam"><Camera :size="15" /></span>
          </div>
          <div class="pf-meta">
            <div class="pf-name" @click="open('nickname')">
              {{ auth.user?.nickname || app.nickname }}
              <Pencil :size="14" class="edit-ic" />
            </div>
            <div class="pf-email">{{ auth.user?.email }}</div>
            <div class="pf-school">{{ school.name }} · {{ school.motto }}</div>
          </div>
        </div>
        <div class="pf-stats">
          <div><div class="ps-num tnum">{{ fmtMinutes(timer.totalMin) }}</div><div class="ps-label">累计</div></div>
          <div><div class="ps-num tnum">{{ timer.streak }}</div><div class="ps-label">连续(天)</div></div>
          <div><div class="ps-num tnum">{{ timer.totalCount }}</div><div class="ps-label">番茄(颗)</div></div>
        </div>
        <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onAvatarChange" />
      </div>

      <!-- 学习设置 -->
      <div class="group">
        <div class="group-title">学习设置</div>
        <div class="card menu">
          <div class="row" @click="open('school')">
            <span class="row-ic c-blue"><Target :size="18" /></span>
            <span class="row-label">我的梦校</span>
            <span class="row-val">{{ school.short }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/subjects')">
            <span class="row-ic c-purple"><BookMarked :size="18" /></span>
            <span class="row-label">科目管理</span>
            <span class="row-val">自定义 / 归档</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="open('goal')">
            <span class="row-ic c-orange"><Clock3 :size="18" /></span>
            <span class="row-label">每日专注目标</span>
            <span class="row-val">{{ fmtMinutes(auth.user?.daily_goal_min || app.dailyGoalMin) }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="toggleNotify">
            <span class="row-ic c-purple"><Bell :size="18" /></span>
            <span class="row-label">到点浏览器通知</span>
            <span class="switch" :class="{ on: app.notifyEnabled }"><span class="knob"></span></span>
          </div>
        </div>
      </div>

      <!-- 学习工具 -->
      <div class="group">
        <div class="group-title">学习工具</div>
        <div class="card menu">
          <div class="row" @click="router.push('/tasks')">
            <span class="row-ic c-blue"><ListChecks :size="18" /></span>
            <span class="row-label">任务清单</span>
            <span class="row-val">计划 / 验收</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/mistakes')">
            <span class="row-ic c-red"><NotebookPen :size="18" /></span>
            <span class="row-label">错题本</span>
            <span class="row-val">艾宾浩斯复习</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/ai')">
            <span class="row-ic c-ink"><Sparkles :size="18" /></span>
            <span class="row-label">AI 助教</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
        </div>
      </div>

      <!-- 管理与账号 -->
      <div class="group" v-if="auth.isAdmin">
        <div class="group-title">管理</div>
        <div class="card menu">
          <div class="row" @click="router.push('/admin')">
            <span class="row-ic c-gold"><ShieldCheck :size="18" /></span>
            <span class="row-label">后台管理</span>
            <span class="row-val">邀请码 / 成员 / 公告</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
        </div>
      </div>

      <!-- 数据与关于 -->
      <div class="group">
        <div class="group-title">数据与关于</div>
        <div class="card menu">
          <div class="row" @click="exportBackup">
            <span class="row-ic c-green"><Download :size="18" /></span>
            <span class="row-label">导出完整备份（JSON）</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="openLegal('terms')">
            <span class="row-ic c-blue"><FileText :size="18" /></span>
            <span class="row-label">用户协议</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="openLegal('privacy')">
            <span class="row-ic c-blue"><FileText :size="18" /></span>
            <span class="row-label">隐私政策</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="open('about')">
            <span class="row-ic c-blue"><Info :size="18" /></span>
            <span class="row-label">关于研时</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row danger" @click="open('clear')">
            <span class="row-ic c-gray"><Trash2 :size="18" /></span>
            <span class="row-label">清空本地记录</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row danger" @click="logout">
            <span class="row-ic c-gray"><LogOut :size="18" /></span>
            <span class="row-label">退出登录</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
        </div>
      </div>

      <div class="version">研时 v0.3 · 四人私密版</div>
    </div>

    <!-- 弹层 -->
    <div v-if="sheetType" class="mask" @click.self="close">
      <div class="sheet">
        <template v-if="sheetType === 'nickname'">
          <div class="sheet-title">修改昵称</div>
          <input v-model="nickDraft" class="input mt12" maxlength="40" placeholder="给自己起个名字" />
          <button class="btn btn-primary btn-block mt16" @click="saveNickname"><Check :size="17" />保存</button>
          <button class="btn btn-ghost btn-block mt8" @click="close">取消</button>
        </template>

        <template v-else-if="sheetType === 'school'">
          <div class="sheet-title">选择我的梦校</div>
          <div class="school-grid">
            <div v-for="s in SCHOOLS" :key="s.key" class="school-cell"
              :class="{ on: s.key === (auth.user?.target_school || app.dreamSchool) }" @click="pickSchool(s.key)">
              <img :src="s.logo" :alt="s.short" />
              <span>{{ s.short }}</span>
              <i v-if="s.key === (auth.user?.target_school || app.dreamSchool)" class="tick"><Check :size="11" :stroke-width="3" /></i>
            </div>
          </div>
        </template>

        <template v-else-if="sheetType === 'goal'">
          <div class="sheet-title">每日专注目标</div>
          <div class="goal-list">
            <button v-for="g in goals" :key="g.min" class="goal-opt"
              :class="{ on: g.min === (auth.user?.daily_goal_min || app.dailyGoalMin) }" @click="pickGoal(g.min)">
              <span class="tnum">{{ g.label }}</span>
              <Check v-if="g.min === (auth.user?.daily_goal_min || app.dailyGoalMin)" :size="16" />
            </button>
          </div>
        </template>

        <template v-else-if="sheetType === 'about'">
          <div class="sheet-title">关于研时</div>
          <div class="about-body">
            <p>研时是只属于你和三位研友的考研陪伴小工具，以「大雪深埋」为信念：沉潜蓄力，静候春来。</p>
            <p class="about-h">核心功能</p>
            <p>番茄专注（倒计时 / 正向计时、学习类型）、任务清单、错题本（艾宾浩斯）、热力图与仪表盘；登录后数据在四人之间按账号云端同步，另有四人自习室与 AI 助教。</p>
            <p class="about-h">数据与隐私</p>
            <p>不开放注册、不公开、不收费、无摄像头；错题与个人图片仅本人可见。可随时导出备份或退出登录。</p>
          </div>
          <button class="btn btn-primary btn-block mt16" @click="close">知道了</button>
        </template>

        <template v-else-if="sheetType === 'clear'">
          <div class="sheet-title">清空本地记录？</div>
          <div class="sheet-sub">仅清空本设备的专注 / 任务 / 错题显示副本，云端数据不受影响；建议先导出备份。</div>
          <button class="btn btn-danger btn-block" @click="clearData"><Trash2 :size="17" />确认清空</button>
          <button class="btn btn-ghost btn-block mt8" @click="close">取消</button>
        </template>
      </div>
    </div>

    <!-- 协议 -->
    <div v-if="showLegal" class="modal-mask" @click.self="showLegal = false">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ legalTab === 'terms' ? '用户协议' : '隐私政策' }}</h3>
          <button @click="showLegal = false">关闭</button>
        </div>
        <pre class="modal-body">{{ legalTab === 'terms' ? legal?.terms : legal?.privacy }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile {
  position: relative;
  background: linear-gradient(150deg, var(--night2), var(--night));
  border-radius: 22px;
  padding: 20px 18px 16px;
  color: #fff;
  overflow: hidden;
  box-shadow: var(--shadow);
}
.watermark { position: absolute; right: -34px; top: -26px; width: 150px; height: 150px; border-radius: 50%; opacity: 0.08; pointer-events: none; }
.pf-main { position: relative; display: flex; align-items: center; gap: 14px; }
.avatar-wrap { position: relative; flex-shrink: 0; cursor: pointer; }
.pf-avatar { width: 62px; height: 62px; border-radius: 50%; object-fit: cover; background: #fff; border: 2px solid rgba(255,255,255,.8); display: block; }
.cam { position: absolute; right: -2px; bottom: -2px; width: 24px; height: 24px; border-radius: 50%; background: var(--primary); color: #fff; display: flex; align-items: center; justify-content: center; border: 2px solid #fff; }
.pf-meta { flex: 1; min-width: 0; }
.pf-name { font-size: 20px; font-weight: 800; display: inline-flex; align-items: center; gap: 7px; }
.edit-ic { color: rgba(255,255,255,.6); }
.pf-email { font-size: 12px; color: rgba(255,255,255,.75); margin-top: 2px; }
.pf-school { font-size: 12px; color: rgba(255,255,255,.66); margin-top: 2px; }
.pf-stats { position: relative; display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 18px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,.14); text-align: center; }
.ps-num { font-size: 17px; font-weight: 800; }
.ps-label { font-size: 11.5px; color: rgba(255,255,255,.64); margin-top: 2px; }

.group { margin-top: 18px; }
.group-title { font-size: 13px; font-weight: 700; color: var(--faint); margin: 0 4px 9px; }
.menu { padding: 2px 14px; }
.row { display: flex; align-items: center; gap: 12px; padding: 13px 0; border-bottom: 1px solid var(--line); cursor: pointer; }
.row:last-child { border-bottom: none; }
.row-ic { width: 36px; height: 36px; border-radius: 11px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.c-blue { background: #e6f0fb; color: var(--primary); }
.c-orange { background: #fdeee4; color: var(--tomato); }
.c-purple { background: #eef0fe; color: var(--purple); }
.c-red { background: #fdecec; color: var(--red); }
.c-green { background: #e7f6f0; color: var(--green); }
.c-ink { background: #eef1f6; color: var(--ink); }
.c-gold { background: #fff3df; color: var(--accent-deep); }
.c-gray { background: #f1f4f8; color: var(--faint); }
.row-label { flex: 1; font-size: 15px; font-weight: 600; }
.row-val { font-size: 13px; color: var(--faint); }
.row-arrow { color: var(--faint); flex-shrink: 0; }
.row.danger .row-label { color: var(--red); }

.switch { width: 44px; height: 26px; border-radius: 999px; background: #d7e0ec; position: relative; transition: background .2s; margin-right: 2px; }
.switch.on { background: var(--primary); }
.knob { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; box-shadow: 0 2px 5px rgba(0,0,0,.2); transition: transform .2s; }
.switch.on .knob { transform: translateX(18px); }
.version { text-align: center; color: var(--faint); font-size: 12px; margin-top: 22px; }

.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); max-height: 80vh; overflow-y: auto; }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; }
.sheet-sub { text-align: center; color: var(--sub); font-size: 13px; margin: 10px 0 16px; }
.school-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 16px; }
.school-cell { position: relative; border: 1.5px solid var(--line); border-radius: 14px; padding: 14px 8px; text-align: center; cursor: pointer; }
.school-cell.on { border-color: var(--primary); background: #f2f7fd; }
.school-cell img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; }
.school-cell span { display: block; font-size: 12.5px; font-weight: 600; margin-top: 6px; }
.tick { position: absolute; top: 5px; right: 5px; width: 18px; height: 18px; border-radius: 50%; background: var(--primary); color: #fff; display: flex; align-items: center; justify-content: center; }
.goal-list { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }
.goal-opt { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border: 1.5px solid var(--line); border-radius: 14px; background: #fff; font-size: 15px; font-weight: 600; cursor: pointer; color: var(--ink); }
.goal-opt.on { border-color: var(--tomato); background: #fff5f3; color: var(--tomato-deep); }
.about-body { margin-top: 12px; font-size: 13.5px; color: var(--sub); line-height: 1.8; }
.about-body p { margin: 0 0 10px; }
.about-h { color: var(--ink); font-weight: 700; margin-bottom: 4px !important; }

.modal-mask { position: fixed; inset: 0; background: rgba(20,30,50,.5); display: flex; align-items: center; justify-content: center; padding: 20px; z-index: 200; }
.modal { background: #fff; border-radius: 14px; max-width: 560px; width: 100%; max-height: 80vh; display: flex; flex-direction: column; }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 16px 18px; border-bottom: 1px solid #eef1f6; }
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-head button { border: none; background: #f1f4fa; border-radius: 8px; padding: 6px 12px; cursor: pointer; }
.modal-body { padding: 16px 18px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 13px; line-height: 1.8; color: #3a4256; margin: 0; }
</style>
