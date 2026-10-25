<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronRight, Pencil, Target, Clock3, Bell, NotebookPen,
  Sparkles, Trash2, Info, Check, ListChecks, Download, Camera,
  LogOut, ShieldCheck, FileText, BookMarked, Crown, ClipboardCheck, Shapes,
  BookOpen, Star, MessagesSquare, MessageSquare, School, RefreshCw, EyeOff,
} from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import { useProfileStore } from '../stores/profile'
import { useNotificationsStore } from '../stores/notifications'
import { SCHOOLS, SCHOOL_MAP } from '../data/schools'
import { fmtDate } from '../utils/time'
import { FIGURES, FIGURE_MAP } from '../data/figures'
import { db, currentKey } from '../db'
import { syncNow, enqueueDelete, pauseSyncForAccountSwitch, resumeSyncAfterAccountSwitch } from '../sync/engine'
import { buildBackup } from '../utils/backup'
import { inspectBackup, restoreBackup } from '../utils/restore'
import { fmtMinutes, todayKey } from '../utils/date'
import { authApi, publicApi, attachmentApi, messageApi } from '../api'
import BlobImage from '../components/BlobImage.vue'
import { useToast } from '../composables/useToast'

const router = useRouter()
const timer = useTimerStore()
const app = useAppStore()
const auth = useAuthStore()
const profile = useProfileStore()
const { toast } = useToast()

const sheetType = ref(null)
const nickDraft = ref(app.nickname)
const signatureDraft = ref('')
const figureDraft = ref('figure-1')
const notifications = useNotificationsStore()
const unread = computed(() => notifications.unread)
const uploading = ref(false)
const fileInput = ref(null)
const showLegal = ref(false)
const legal = ref(null)
const legalTab = ref('terms')
const syncing = ref(false)
const lastSyncAt = ref(0)
const backupInput = ref(null)
const restorePreview = ref(null)
const overwriteBackup = ref(false)
const restoring = ref(false)
const deleteCloudRecords = ref(false)

async function readBackup(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  try {
    if (file.size > 100 * 1024 * 1024) throw new Error('备份文件不能超过100MB')
    const backup = JSON.parse(await file.text())
    const counts = inspectBackup(backup)
    restorePreview.value = { backup, counts }
    overwriteBackup.value = false
  } catch (error) { toast(error.message || '备份文件读取失败') }
}
async function importBackup() {
  if (restoring.value || !restorePreview.value) return
  restoring.value = true
  await pauseSyncForAccountSwitch()
  try {
    const result = await restoreBackup(restorePreview.value.backup, { overwrite: overwriteBackup.value })
    const modules = await Promise.all([import('../stores/subjects'), import('../stores/tasks'), import('../stores/mistakes'), import('../stores/learningSettings')])
    const ss = modules[0].useSubjectsStore(); ss.loaded = false; await ss.load()
    const ts = modules[1].useTasksStore(); ts.loaded = false; await ts.load()
    await modules[2].useMistakesStore().load(true)
    await modules[3].useLearningSettingsStore().load(true)
    timer.sessions = await db.sessions.toArray()
    await profile.load(true)
    restorePreview.value = null
    toast(`已恢复${result.imported}条，跳过${result.skipped}条重复记录`)
  } catch (error) { toast(error.message || '恢复失败，数据未完整写入') }
  finally { restoring.value = false; resumeSyncAfterAccountSwitch() }
}

const lastSyncText = computed(() => {
  if (!lastSyncAt.value) return '离线优先'
  const d = new Date(lastSyncAt.value)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `最近 ${hh}:${mm}`
})

async function manualSync() {
  if (syncing.value) return
  syncing.value = true
  try {
    const ok = await syncNow()
    const meta = await db.syncMeta.get('lastSyncAt')
    lastSyncAt.value = meta?.value || 0
    toast(ok === false ? '同步失败，请稍后再试' : '已同步')
  } catch {
    toast('同步失败，请稍后再试')
  } finally {
    syncing.value = false
  }
}

const school = computed(() => SCHOOL_MAP[auth.user?.target_school || app.dreamSchool] || SCHOOL_MAP[app.dreamSchool] || Object.values(SCHOOL_MAP)[0])
const avatar = computed(() => auth.user?.avatar_key || '')
const vipUntil = computed(() => auth.user?.vip_permanent ? '永久有效' : fmtDate(auth.user?.vip_until))
const figure = computed(() => FIGURE_MAP[auth.user?.figure_id || 'figure-1'] || FIGURES[0])

const goals = [
  { min: 120, label: '2 小时' },
  { min: 240, label: '4 小时' },
  { min: 300, label: '5 小时' },
  { min: 480, label: '8 小时' },
  { min: 600, label: '10 小时' },
]

function open(type) {
  if (type === 'clear') deleteCloudRecords.value = false
  if (type === 'nickname' || type === 'profile') {
    nickDraft.value = auth.user?.nickname || app.nickname
    signatureDraft.value = auth.user?.signature || ''
    figureDraft.value = auth.user?.figure_id || 'figure-1'
    sheetType.value = 'profile'
    return
  }
  sheetType.value = type
}
function close() {
  sheetType.value = null
}

async function saveProfile() {
  const name = nickDraft.value.trim()
  if (name.length < 2) return toast('昵称至少 2 个字')
  if (signatureDraft.value.trim().length > 80) return toast('签名最多 80 个字')
  try {
    await profile.save({
      nickname: name,
      signature: signatureDraft.value.trim(),
      figure_id: figureDraft.value,
    })
    app.setNickname(name)
    close()
    toast('资料已更新')
  } catch (e) {
    toast(e.message)
  }
}

async function pickSchool(key) {
  try {
    await profile.save({ target_school: key })
    app.setDreamSchool(key)
    close()
    toast('梦校已更新')
  } catch (e) {
    toast(e.message)
  }
}

async function pickGoal(min) {
  try {
    await profile.save({ daily_goal_min: min })
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
  // 各账号使用独立本地库，登出后切换到游客库，未同步数据仍保留在原账号库
  await auth.logout()
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
    const payload = await buildBackup(db,
      JSON.parse(localStorage.getItem('yanshi:app') || '{}'))
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `研时备份_${todayKey()}.json`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    toast('已导出备份（含本地题图、解析图及云端图片引用）')
  } catch {
    toast('导出失败，图片可能无法读取，请重试')
  }
}

async function clearData() {
  await pauseSyncForAccountSwitch()
  try {
    await db.transaction('rw', db.sessions, db.tasks, db.mistakes, db.outbox, db.syncMeta, async () => {
      for (const table of ['sessions', 'tasks', 'mistakes']) {
        for (const row of await db[table].toArray()) {
          if (deleteCloudRecords.value) await enqueueDelete(table, row.id)
          else {
            const pending = await db.outbox.where('recordId').equals(row.id).first()
            const conflict = await db.syncMeta.get(`conflict:${row.id}`)
            if (row._rev && !pending && !conflict) await db[table].delete(row.id)
          }
        }
      }
      await db.syncMeta.delete('pullCursor')
    })
    if (deleteCloudRecords.value) {
      timer.current = null; timer.rest = null; timer.saveCycle(); timer.stopTicker()
      localStorage.removeItem(currentKey())
    }
    close()
    toast(deleteCloudRecords.value ? '学习记录已删除，联网后同步删除' : '已清除已同步缓存，未同步内容保留')
    setTimeout(() => location.reload(), 600)
  } catch { toast('删除失败，请重试') }
  finally { resumeSyncAfterAccountSwitch() }
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
    await profile.save({ notify_enabled: enabled })
    app.setNotifyEnabled(enabled)
    toast(enabled ? '已开启到点通知' : '已关闭通知')
  } catch (e) {
    toast(e.message)
  }
}

async function togglePrivacy() {
  const next = !auth.user?.privacy_mode
  try {
    await profile.save({ privacy_mode: next })
    toast(next ? '已开启隐私模式：成员列表与排行榜将匿名显示' : '已关闭隐私模式')
  } catch (e) {
    toast(e.message)
  }
}

onMounted(() => {
  auth.fetchMe().catch(() => {})
  notifications.refresh()
  db.syncMeta.get('lastSyncAt').then((m) => { lastSyncAt.value = m?.value || 0 }).catch(() => {})
  if (auth.user) {
    app.setNickname(auth.user.nickname)
    if (auth.user.target_school) app.setDreamSchool(auth.user.target_school)
    if (auth.user.daily_goal_min) app.setDailyGoal(auth.user.daily_goal_min)
  }
})
</script>

<template>
  <div>
    <input ref="backupInput" type="file" accept="application/json,.json" hidden @change="readBackup" />
    <div v-if="restorePreview" class="mask" @click.self="!restoring && (restorePreview = null)">
      <div class="sheet">
        <div class="sheet-title">恢复研时备份</div>
        <p class="sheet-sub">科目{{ restorePreview.counts.subjects }}条、专注{{ restorePreview.counts.sessions }}条、任务{{ restorePreview.counts.tasks }}条、错题{{ restorePreview.counts.mistakes }}条。</p>
        <p class="sheet-sub">默认保留相同ID的现有记录；云端图片引用需要原账号和对应存储仍可访问。</p>
        <label><input v-model="overwriteBackup" type="checkbox" :disabled="restoring" /> 覆盖相同ID记录（保留云端版本校验）</label>
        <button class="btn btn-primary btn-block mt16" :disabled="restoring" @click="importBackup">{{ restoring ? '正在恢复…' : '合并恢复' }}</button>
        <button class="btn btn-ghost btn-block mt8" :disabled="restoring" @click="restorePreview = null">取消</button>
      </div>
    </div>
    <div class="nav"><div class="nav-title">我的</div></div>

    <div class="page">
      <!-- 个人卡 -->
      <div class="profile">
        <img class="watermark" :src="school.logo" alt="" />
        <div class="pf-main">
          <div class="avatar-wrap" @click="pickAvatar">
            <BlobImage class="pf-avatar" :src="avatar" :fallback="school.logo" :alt="auth.user?.nickname" />
            <span class="figure-chip" :style="{ background: figure.bg }">{{ figure.emoji }}</span>
            <span class="cam"><Camera :size="15" /></span>
          </div>
          <div class="pf-meta">
            <div class="pf-name" @click="open('profile')">
              {{ auth.user?.nickname || app.nickname }}
              <span v-if="auth.isVip" class="pf-vip"><Crown :size="11" />VIP</span>
              <Pencil :size="14" class="edit-ic" />
            </div>
            <div class="pf-sign">{{ auth.user?.signature || '点此编辑昵称、签名与形象' }}</div>
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
          <div class="row" @click="router.push('/settings/learning')">
            <span class="row-ic c-orange"><Clock3 :size="18" /></span>
            <span class="row-label">专注与休息设置</span><ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="toggleNotify">
            <span class="row-ic c-purple"><Bell :size="18" /></span>
            <span class="row-label">到点浏览器通知</span>
            <span class="switch" :class="{ on: app.notifyEnabled }"><span class="knob"></span></span>
          </div>
          <div class="row" @click="togglePrivacy">
            <span class="row-ic c-purple"><EyeOff :size="18" /></span>
            <span class="row-label">隐私模式</span>
            <span class="row-val">房间匿名 / 不上榜</span>
            <span class="switch" :class="{ on: auth.user?.privacy_mode }"><span class="knob"></span></span>
          </div>
        </div>
      </div>

      <!-- 学习工具 -->
      <div class="group">
        <div class="group-title">学习工具</div>
        <div class="card menu">
          <div class="row" @click="manualSync">
            <span class="row-ic c-blue"><RefreshCw :size="18" /></span>
            <span class="row-label">立即同步</span>
            <span class="row-val">{{ syncing ? '同步中…' : lastSyncText }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
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
          <div class="row" @click="router.push('/error-types')">
            <span class="row-ic c-purple"><Shapes :size="18" /></span>
            <span class="row-label">错误类型管理</span>
            <span class="row-val">自定义 / 增删改</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/ai')">
            <span class="row-ic c-ink"><Sparkles :size="18" /></span>
            <span class="row-label">AI 助教</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
        </div>
      </div>

      <!-- 资料与消息 -->
      <div class="group">
        <div class="group-title">资料与消息</div>
        <div class="card menu">
          <div class="row" @click="router.push('/resources')">
            <span class="row-ic c-blue"><BookOpen :size="18" /></span>
            <span class="row-label">资料库</span>
            <span class="row-val">{{ auth.isVip ? '可发布' : 'VIP 可发布' }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/resources?tab=fav')">
            <span class="row-ic c-gold"><Star :size="18" /></span>
            <span class="row-label">我的收藏</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/messages')">
            <span class="row-ic c-purple"><MessagesSquare :size="18" /></span>
            <span class="row-label">消息中心</span>
            <span v-if="unread" class="unread-badge">{{ unread > 99 ? '99+' : unread }}</span>
            <span v-else class="row-val">暂无未读</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/posts')">
            <span class="row-ic c-blue"><MessageSquare :size="18" /></span>
            <span class="row-label">研友动态</span>
            <span class="row-val">发帖 · 评论</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/inspirations')">
            <span class="row-ic c-gold"><Sparkles :size="18" /></span>
            <span class="row-label">励志区</span>
            <span class="row-val">投稿轮播</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/dream-wall')">
            <span class="row-ic c-purple"><School :size="18" /></span>
            <span class="row-label">梦校墙</span>
            <span class="row-val">七所梦校</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
        </div>
      </div>

      <!-- 会员与申请 -->
      <div class="group">
        <div class="group-title">会员与申请</div>
        <div class="card menu">
          <div class="row" @click="router.push('/vip')">
            <span class="row-ic c-gold"><Crown :size="18" /></span>
            <span class="row-label">会员中心</span>
            <span class="row-val">{{ auth.isVip ? `VIP · ${vipUntil} 到期` : '未开通' }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="router.push('/requests')">
            <span class="row-ic c-blue"><ClipboardCheck :size="18" /></span>
            <span class="row-label">功能申请</span>
            <span class="row-val">提交 / 查看进度</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
        </div>
      </div>

      <div class="group">
        <div class="group-title">账号安全</div>
        <div class="card menu"><div class="row" @click="router.push('/me/phone')">
          <span class="row-label">绑定手机号</span><span class="row-val">{{ auth.user?.phone ? '已绑定' : '未绑定' }}</span><ChevronRight :size="17" />
        </div></div>
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
            <span class="row-label">导出备份（本地图片及云端引用）</span>
            <ChevronRight :size="17" class="row-arrow" />
          </div>
          <div class="row" @click="backupInput?.click()">
            <span class="row-ic c-blue"><Download :size="18" /></span><span class="row-label">从备份恢复</span><ChevronRight :size="17" class="row-arrow" />
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
          <div class="row" @click="openLegal('disclaimer')">
            <span class="row-ic c-blue"><FileText :size="18" /></span>
            <span class="row-label">免责声明</span>
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
        <template v-if="sheetType === 'profile'">
          <div class="sheet-title">编辑资料</div>
          <label class="edit-label">昵称</label>
          <input v-model="nickDraft" class="input" maxlength="40" placeholder="给自己起个名字" />
          <label class="edit-label">个性签名</label>
          <input v-model="signatureDraft" class="input" maxlength="80" placeholder="一句话介绍自己" />
          <label class="edit-label">虚拟形象</label>
          <div class="figure-grid">
            <button
              v-for="f in FIGURES"
              :key="f.id"
              class="figure-cell"
              :class="{ on: figureDraft === f.id }"
              :style="{ background: f.bg }"
              @click="figureDraft = f.id"
            >
              <span class="figure-emoji">{{ f.emoji }}</span>
              <span class="figure-name">{{ f.name }}</span>
              <Check v-if="figureDraft === f.id" :size="12" class="figure-tick" />
            </button>
          </div>
          <button class="btn btn-primary btn-block mt16" @click="saveProfile"><Check :size="17" />保存</button>
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
          <div class="sheet-sub">默认清除本机已同步缓存，保留未同步记录；联网后可重新拉取。勾选下方选项会删除所有设备上的学习记录，请先导出备份。</div>
          <label><input v-model="deleteCloudRecords" type="checkbox" /> 同时删除云端学习记录（所有设备）</label>
          <button class="btn btn-danger btn-block" @click="clearData"><Trash2 :size="17" />确认清空</button>
          <button class="btn btn-ghost btn-block mt8" @click="close">取消</button>
        </template>
      </div>
    </div>

    <!-- 协议 -->
    <div v-if="showLegal" class="modal-mask" @click.self="showLegal = false">
      <div class="modal">
        <div class="modal-head">
          <h3>{{ legalTab === 'terms' ? '用户协议' : legalTab === 'privacy' ? '隐私政策' : '免责声明' }}</h3>
          <button @click="showLegal = false">关闭</button>
        </div>
        <pre class="modal-body">{{ legalTab === 'terms' ? legal?.terms : legalTab === 'privacy' ? legal?.privacy : legal?.disclaimer }}</pre>
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
.figure-chip {
  position: absolute;
  left: -4px;
  bottom: -4px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  border: 2px solid #fff;
  box-shadow: 0 2px 6px rgba(0,0,0,.18);
}
.edit-label {
  display: block;
  font-size: 12.5px;
  color: var(--sub);
  margin: 12px 2px 6px;
}
.figure-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 9px;
}
.figure-cell {
  position: relative;
  border: 1.5px solid transparent;
  border-radius: 13px;
  padding: 10px 4px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.figure-cell.on {
  border-color: var(--primary);
}
.figure-emoji { font-size: 22px; line-height: 1; }
.figure-name { font-size: 10.5px; color: var(--sub); }
.figure-tick {
  position: absolute;
  top: 4px;
  right: 4px;
  color: var(--primary);
  background: #fff;
  border-radius: 50%;
}
.pf-meta { flex: 1; min-width: 0; }
.pf-name { font-size: 20px; font-weight: 800; display: inline-flex; align-items: center; gap: 7px; }
.pf-vip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  font-weight: 800;
  color: #3a2700;
  background: linear-gradient(120deg, #ffd88a, #f0a830);
  border-radius: 999px;
  padding: 2px 7px;
}
.edit-ic { color: rgba(255,255,255,.6); }
.pf-email { font-size: 12px; color: rgba(255,255,255,.75); margin-top: 2px; }
.pf-sign { font-size: 12px; color: rgba(255,255,255,.86); margin-top: 3px; font-style: italic; }
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
.unread-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--tomato);
  color: #fff;
  font-size: 10.5px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
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
