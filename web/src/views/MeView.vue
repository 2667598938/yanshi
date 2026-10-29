<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronRight, Pencil, Target, Clock3, Bell, NotebookPen,
  Sparkles, Trash2, Info, Check, ListChecks, Download, Camera,
  LogOut, ShieldCheck, FileText, BookMarked, Crown, ClipboardCheck, Shapes,
  BookOpen, Star, MessagesSquare, MessageSquare, School, RefreshCw, EyeOff,
  HardDrive, Archive,
} from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import { useProfileStore } from '../stores/profile'
import { useNotificationsStore } from '../stores/notifications'
import { SCHOOL_MAP } from '../data/schools'
import { fmtDate } from '../utils/time'
import { FIGURES, FIGURE_MAP } from '../data/figures'
import { db, currentKey } from '../db'
import { syncNow, enqueueDelete, pauseSyncForAccountSwitch, resumeSyncAfterAccountSwitch } from '../sync/engine'
import { buildBackup } from '../utils/backup'
import { inspectBackup, restoreBackup } from '../utils/restore'
import { fmtMinutes, todayKey } from '../utils/date'
import { authApi, publicApi, attachmentApi, messageApi } from '../api'
import { useSchoolsStore } from '../stores/schools'
import BlobImage from '../components/BlobImage.vue'
import { useLearningSettingsStore } from '../stores/learningSettings'
import { useToast } from '../composables/useToast'

const router = useRouter()
const timer = useTimerStore()
const app = useAppStore()
const auth = useAuthStore()
const profile = useProfileStore()
const learningSettings = useLearningSettingsStore()
const phoneAvailable = ref(false)
onMounted(async()=>{try{phoneAvailable.value=(await publicApi.config()).enabled_auth_channels?.includes('phone') || false}catch{/* Closed by default. */}})
onMounted(() => learningSettings.load(true).catch(() => {}))
async function toggleBullets() {
  try { await learningSettings.save({ ...learningSettings.value, bulletEnabled: !learningSettings.value.bulletEnabled }) }
  catch (e) { toast(e.message || '设置保存失败') }
}
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
const savingSheet = ref(false)

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
    const pending = await db.outbox.count() + await db.syncMeta.filter(row => row.key.startsWith('conflict:')).count()
    toast(ok === false ? '同步失败，请稍后再试' : pending ? `本轮同步完成，仍有${pending}项待同步或待处理` : '已同步')
  } catch {
    toast('同步失败，请稍后再试')
  } finally {
    syncing.value = false
  }
}

const catalog = useSchoolsStore()
const schoolCatalog = computed(() => catalog.rows)
const imageSpace = ref(null)
const storageBusy = ref(false)
function fmtBytes(n) {
  const value = Number(n) || 0
  if (value >= 1024 * 1024) return (value / 1024 / 1024).toFixed(1) + 'MB'
  return Math.round(value / 1024) + 'KB'
}
const schoolChoices = computed(()=>schoolCatalog.value.map(row=>({...SCHOOL_MAP[row.key],...row,key:row.key,short:row.short||row.name,logo:row.logo_key||SCHOOL_MAP[row.key]?.logo||''})))
const school = computed(() => {
  const key = auth.user?.target_school || app.dreamSchool
  const saved = schoolCatalog.value.find(row => row.key === key)
  return saved ? { ...SCHOOL_MAP[key], ...saved.info, name: saved.name, short:saved.short || saved.name, logo:saved.logo_key || SCHOOL_MAP[key]?.logo || '' }
    : SCHOOL_MAP[key] || { name: key || '尚未选择梦校', motto: '', logo: '' }
})
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
  if (savingSheet.value) return
  const name = nickDraft.value.trim()
  if (name.length < 2) return toast('昵称至少 2 个字')
  if (signatureDraft.value.trim().length > 80) return toast('签名最多 80 个字')
  savingSheet.value = true
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
  } finally {
    savingSheet.value = false
  }
}

async function pickSchool(key) {
  if (savingSheet.value) return
  savingSheet.value = true
  try {
    await profile.save({ target_school: key })
    app.setDreamSchool(key)
    close()
    toast('梦校已更新')
  } catch (e) {
    toast(e.message)
  } finally {
    savingSheet.value = false
  }
}

async function pickGoal(min) {
  if (savingSheet.value) return
  savingSheet.value = true
  try {
    await profile.save({ daily_goal_min: min })
    app.setDailyGoal(min)
    close()
    toast('今日目标已更新')
  } catch (e) {
    toast(e.message)
  } finally {
    savingSheet.value = false
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
    a.download = `研时个人学习备份_${todayKey()}.json`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    toast('已导出个人学习备份（不含全站数据库、图片二进制与管理员配置）')
  } catch {
    toast('导出失败，图片可能无法读取，请重试')
  }
}

async function openStorage() {
  sheetType.value = 'storage'
  imageSpace.value = null
  try {
    imageSpace.value = await attachmentApi.storage()
  } catch (e) {
    toast(e.message)
  }
}

async function reclaimImages() {
  if (storageBusy.value) return
  if (!confirm('只回收超过 24 小时且未被题目、相册、聊天、头像或励志投稿引用的图片。确认回收？')) return
  storageBusy.value = true
  try {
    const result = await attachmentApi.reclaim()
    toast(`已回收 ${result.deleted} 张，释放 ${fmtBytes(result.freed_bytes)}`)
    imageSpace.value = await attachmentApi.storage()
  } catch (e) {
    toast(e.message)
  } finally {
    storageBusy.value = false
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
  const next = !auth.user?.is_private_mode
  if (next && !confirm('开启隐私模式后，小组内其他成员将无法查看你的自习状态、错题、任务、番茄记录、学习热力等全部学习数据；仅管理员仍可管理你的账号（管理员后台用于运维，不展示学习明细）。')) return
  try {
    const result = await authApi.updateMe({ is_private_mode: next })
    auth.setUser({ ...auth.user, is_private_mode: result.is_private_mode, privacy_mode: result.is_private_mode })
    toast(next ? '隐私模式已开启，组员无法读取你的学习数据' : '已关闭隐私，恢复受邀小组共享')
  } catch (e) { toast('隐私设置未生效，请联网后重试：' + e.message) }
}

onMounted(() => {
  auth.fetchMe().then(() => profile.load(true)).catch(() => {})
  catalog.load()
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
        <p class="sheet-sub">科目{{ restorePreview.counts.subjects }}条、专注{{ restorePreview.counts.sessions }}条、任务{{ restorePreview.counts.tasks }}条、错题{{ restorePreview.counts.mistakes }}条、时间节点{{ restorePreview.counts.timeNodes }}条。</p>
        <p class="sheet-sub">默认保留相同ID的现有记录；云端图片引用需要原账号和对应存储仍可访问。</p>
        <label><input v-model="overwriteBackup" type="checkbox" :disabled="restoring" /> 覆盖相同ID记录（保留云端版本校验）</label>
        <button class="btn btn-primary btn-block mt16" :disabled="restoring" @click="importBackup">{{ restoring ? '正在恢复…' : '合并恢复' }}</button>
        <button class="btn btn-ghost btn-block mt8" :disabled="restoring" @click="restorePreview = null">取消</button>
      </div>
    </div>
    <div class="nav"><div class="nav-title">我的</div></div>

    <div class="page settings-layout">
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
          <button type="button" class="row" @click="open('school')">
            <span class="row-ic c-blue"><Target :size="18" /></span>
            <span class="row-label">我的梦校</span>
            <span class="row-val">{{ school.short }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button class="row" @click="router.push('/schools/manage')"><span class="row-ic c-purple"><School :size="18" /></span><span class="row-label">梦校管理</span><span class="row-val">新增 / 相册 / 排序</span><ChevronRight :size="17" class="row-arrow" /></button>
          <button class="row" @click="router.push('/settings/time-nodes')"><span class="row-ic c-blue"><Clock3 :size="18" /></span><span class="row-label">时间节点与专属寄语</span><ChevronRight :size="17" class="row-arrow" /></button>
          <button class="row" role="switch" :aria-checked="learningSettings.value.bulletEnabled" @click="toggleBullets"><span class="row-ic c-gold"><Sparkles :size="18" /></span><span class="row-label">梦校励志弹幕</span><span class="row-val">{{ learningSettings.value.bulletEnabled ? '开启' : '关闭' }}</span></button>
          <button type="button" class="row" @click="router.push('/subjects')">
            <span class="row-ic c-purple"><BookMarked :size="18" /></span>
            <span class="row-label">科目管理</span>
            <span class="row-val">自定义 / 归档</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="open('goal')">
            <span class="row-ic c-orange"><Clock3 :size="18" /></span>
            <span class="row-label">每日专注目标</span>
            <span class="row-val">{{ fmtMinutes(auth.user?.daily_goal_min || app.dailyGoalMin) }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/settings/learning')">
            <span class="row-ic c-orange"><Clock3 :size="18" /></span>
            <span class="row-label">专注与休息设置</span><ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" role="switch" :aria-checked="app.notifyEnabled" @click="toggleNotify">
            <span class="row-ic c-purple"><Bell :size="18" /></span>
            <span class="row-label">到点浏览器通知</span>
            <span class="switch" :class="{ on: app.notifyEnabled }"><span class="knob"></span></span>
          </button>

        </div>
      </div>

      <!-- 学习工具 -->
      <div class="group">
        <div class="group-title">学习工具</div>
        <div class="card menu">
          <button type="button" class="row" @click="manualSync">
            <span class="row-ic c-blue"><RefreshCw :size="18" /></span>
            <span class="row-label">立即同步</span>
            <span class="row-val">{{ syncing ? '同步中…' : lastSyncText }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/tasks')">
            <span class="row-ic c-blue"><ListChecks :size="18" /></span>
            <span class="row-label">任务清单</span>
            <span class="row-val">计划 / 验收</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/mistakes')">
            <span class="row-ic c-red"><NotebookPen :size="18" /></span>
            <span class="row-label">错题本</span>
            <span class="row-val">艾宾浩斯复习</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/error-types')">
            <span class="row-ic c-purple"><Shapes :size="18" /></span>
            <span class="row-label">错误类型管理</span>
            <span class="row-val">自定义 / 增删改</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/ai')">
            <span class="row-ic c-ink"><Sparkles :size="18" /></span>
            <span class="row-label">AI 助教</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
        </div>
      </div>

      <!-- 资料与消息 -->
      <div class="group">
        <div class="group-title">资料与消息</div>
        <div class="card menu">
          <button type="button" class="row" @click="router.push('/resources')">
            <span class="row-ic c-blue"><BookOpen :size="18" /></span>
            <span class="row-label">资料库</span>
            <span class="row-val">{{ auth.isVip ? '可发布' : 'VIP 可发布' }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/resources?tab=fav')">
            <span class="row-ic c-gold"><Star :size="18" /></span>
            <span class="row-label">我的收藏</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/messages')">
            <span class="row-ic c-purple"><MessagesSquare :size="18" /></span>
            <span class="row-label">消息中心</span>
            <span v-if="unread" class="unread-badge">{{ unread > 99 ? '99+' : unread }}</span>
            <span v-else class="row-val">暂无未读</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/posts')">
            <span class="row-ic c-blue"><MessageSquare :size="18" /></span>
            <span class="row-label">研友动态</span>
            <span class="row-val">发帖 · 评论</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/inspirations')">
            <span class="row-ic c-gold"><Sparkles :size="18" /></span>
            <span class="row-label">励志区</span>
            <span class="row-val">投稿轮播</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/dream-wall')">
            <span class="row-ic c-purple"><School :size="18" /></span>
            <span class="row-label">梦校墙</span>
            <span class="row-val">自定义院校 / 多图相册</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
        </div>
      </div>

      <!-- 会员与申请 -->
      <div class="group">
        <div class="group-title">会员与申请</div>
        <div class="card menu">
          <button type="button" class="row" @click="router.push('/vip')">
            <span class="row-ic c-gold"><Crown :size="18" /></span>
            <span class="row-label">会员中心</span>
            <span class="row-val">{{ auth.isVip ? (auth.user?.vip_permanent ? 'VIP · 永久有效' : `VIP · ${vipUntil} 到期`) : '未开通' }}</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="router.push('/requests')">
            <span class="row-ic c-blue"><ClipboardCheck :size="18" /></span>
            <span class="row-label">功能申请</span>
            <span class="row-val">提交 / 查看进度</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
        </div>
      </div>

      <div v-if="phoneAvailable || auth.user?.phone" class="group">
        <div class="group-title">账号安全</div>
        <div class="card menu"><button type="button" class="row" @click="router.push('/me/phone')">
          <span class="row-ic c-blue"><ShieldCheck :size="18" /></span><span class="row-label">绑定手机号</span><span class="row-val">{{ auth.user?.phone ? '已绑定' : '未绑定' }}</span><ChevronRight :size="17" />
        </button></div>
      </div>
      <!-- 管理与账号 -->
      <div class="group" v-if="auth.isAdmin">
        <div class="group-title">管理</div>
        <div class="card menu">
          <button type="button" class="row" @click="router.push('/admin')">
            <span class="row-ic c-gold"><ShieldCheck :size="18" /></span>
            <span class="row-label">后台管理</span>
            <span class="row-val">邀请码 / 成员 / 公告</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
        </div>
      </div>

      <div class="group">
        <div class="group-title">小组与共享</div>
        <p class="group-help">受邀加入后互看学习数据；房间准入和会员权益分别管理。</p>
        <div class="card menu">
          <button class="row" @click="router.push('/group/admission')"><span class="row-ic c-blue"><ClipboardCheck :size="18" /></span><span class="row-label">入组申请与记录</span><ChevronRight :size="17" class="row-arrow" /></button>
          <button type="button" class="row" role="switch" :aria-checked="!!auth.user?.is_private_mode" @click="togglePrivacy">
            <span class="row-ic c-purple"><EyeOff :size="18" /></span>
            <span class="row-label">小组隐私模式</span>
            <span class="row-val">一键停止全部学习数据共享</span>
            <span class="switch" :class="{ on: auth.user?.is_private_mode }"><span class="knob"></span></span>
          </button>
          <button class="row" @click="router.push('/group')"><span class="row-ic c-green"><BookOpen :size="18" /></span><span class="row-label">小组学习数据</span><span class="row-val">只读互助</span><ChevronRight :size="17" class="row-arrow" /></button>
        </div>
      </div>
      <!-- 数据与关于 -->
      <div class="group">
        <div class="group-title">数据与关于</div>
        <div class="card menu">
          <button type="button" class="row" @click="exportBackup">
            <span class="row-ic c-green"><Download :size="18" /></span>
            <span class="row-label">导出个人学习备份（JSON）</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="open('backup-scope')">
            <span class="row-ic c-blue"><Archive :size="18" /></span>
            <span class="row-label">个人学习备份包含什么</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="openStorage">
            <span class="row-ic c-purple"><HardDrive :size="18" /></span>
            <span class="row-label">图片空间与回收</span>
            <span class="row-val">查看配额 / 安全回收</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="backupInput?.click()">
            <span class="row-ic c-blue"><Download :size="18" /></span><span class="row-label">从备份恢复</span><ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="openLegal('terms')">
            <span class="row-ic c-blue"><FileText :size="18" /></span>
            <span class="row-label">用户协议</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="openLegal('privacy')">
            <span class="row-ic c-blue"><FileText :size="18" /></span>
            <span class="row-label">隐私政策</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="openLegal('disclaimer')">
            <span class="row-ic c-blue"><FileText :size="18" /></span>
            <span class="row-label">免责声明</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row" @click="open('about')">
            <span class="row-ic c-blue"><Info :size="18" /></span>
            <span class="row-label">关于研时</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row danger" @click="open('clear')">
            <span class="row-ic c-gray"><Trash2 :size="18" /></span>
            <span class="row-label">清空本地记录</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
          <button type="button" class="row danger" @click="logout">
            <span class="row-ic c-gray"><LogOut :size="18" /></span>
            <span class="row-label">退出登录</span>
            <ChevronRight :size="17" class="row-arrow" />
          </button>
        </div>
      </div>

      <div class="version">研时 · 四人学习小组</div>
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
          <button class="btn btn-primary btn-block mt16" :disabled="savingSheet" @click="saveProfile">
            <Check :size="17" />{{ savingSheet ? '保存中…' : '保存' }}
          </button>
          <button class="btn btn-ghost btn-block mt8" @click="close">取消</button>
        </template>

        <template v-else-if="sheetType === 'school'">
          <div class="sheet-title">选择我的梦校</div><button class="btn btn-outline" @click="close();router.push('/schools/manage')">新增与管理梦校</button>
          <div class="school-grid">
            <div v-for="s in schoolChoices" :key="s.key" class="school-cell"
              :class="{ on: s.key === (auth.user?.target_school || app.dreamSchool) }" @click="pickSchool(s.key)">
              <BlobImage :src="s.logo" :alt="s.short" />
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
            <p>番茄专注（倒计时 / 正向计时、学习类型）、任务清单、错题本（艾宾浩斯）、热力图与仪表盘；登录后本人的学习数据可跨设备同步；同受邀小组默认只读互看学习记录，另有自习室与 AI 助教。</p>
            <p class="about-h">数据与隐私</p>
            <p>按配置控制注册，无摄像头。同受邀小组默认共享错题及题图、任务、番茄、时长和自习状态；开启隐私模式后对组员隐藏。AI会话、Key和资料个人备注始终仅本人可见。可导出备份或退出登录。</p>
          </div>
          <button class="btn btn-primary btn-block mt16" @click="close">知道了</button>
        </template>

        <template v-else-if="sheetType === 'backup-scope'">
          <div class="sheet-title">个人学习备份范围</div>
          <div class="about-body">
            <p><b>包含：</b>科目、专注记录、任务、错题、时间节点、个人资料与学习偏好；本机题图/解析图会一起打包，云端图片只保存引用。</p>
            <p><b>不包含：</b>AI 完整会话、API Key、梦校相册图片二进制、其他成员数据、社区全部内容、管理员配置、服务器数据库与全站图片。</p>
            <p class="about-h">整站备份</p>
            <p>不是这个 JSON 的职责。服务器数据库、上传图片、环境配置与密钥应由管理员用部署目录的备份脚本单独管理。</p>
          </div>
          <button class="btn btn-primary btn-block mt16" @click="close">知道了</button>
        </template>

        <template v-else-if="sheetType === 'storage'">
          <div class="sheet-title">图片空间与回收</div>
          <div v-if="!imageSpace" class="sheet-sub">正在读取空间用量…</div>
          <div v-else class="about-body">
            <p>已用 {{ fmtBytes(imageSpace.used_bytes) }} / {{ fmtBytes(imageSpace.quota_bytes) }}</p>
            <p>可安全回收：{{ imageSpace.orphan_count }} 张，约 {{ fmtBytes(imageSpace.orphan_bytes) }}。</p>
            <p class="about-h">回收规则</p>
            <p>只处理上传超过 {{ imageSpace.grace_hours }} 小时、且未被错题图片、梦校相册/校徽、AI 对话、头像或励志投稿引用的本人附件；仍被使用的图片不会被删除。</p>
            <button class="btn btn-outline btn-block" :disabled="storageBusy || !imageSpace.orphan_count" @click="reclaimImages">
              {{ storageBusy ? '回收中…' : `回收 ${imageSpace.orphan_count} 张未引用图片` }}
            </button>
          </div>
          <button class="btn btn-ghost btn-block mt8" @click="close">关闭</button>
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
  background: linear-gradient(150deg, #4f46e5, #312e81 70%);
  border-radius: 20px;
  padding: 24px 16px 16px;
  color: #fff;
  overflow: hidden;
  box-shadow: 0 14px 32px rgba(49, 46, 129, 0.22);
}
.watermark { position: absolute; right: -34px; top: -26px; width: 150px; height: 150px; border-radius: 50%; opacity: 0.08; pointer-events: none; }
.pf-main { position: relative; display: flex; align-items: center; gap: 14px; }
.avatar-wrap { position: relative; flex-shrink: 0; cursor: pointer; }
.pf-avatar { width: 62px; height: 62px; border-radius: 50%; object-fit: cover; background: #fff; border: 2px solid rgba(255,255,255,.8); display: block; }
.cam { position: absolute; right: -2px; bottom: -2px; width: 24px; height: 24px; border-radius: 50%; background: var(--primary-grad); color: #fff; display: flex; align-items: center; justify-content: center; border: 2px solid #fff; }
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
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 8px 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  transition: border-color 0.24s ease, box-shadow 0.24s ease;
}
.figure-cell.on {
  border-color: var(--primary);
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.16);
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
  background: linear-gradient(120deg, #fcd34d, #f59e0b);
  border-radius: 999px;
  padding: 2px 8px;
}
.edit-ic { color: rgba(255,255,255,.6); }
.pf-email { font-size: 12px; color: rgba(255,255,255,.75); margin-top: 4px; }
.pf-sign { font-size: 12px; color: rgba(255,255,255,.86); margin-top: 4px; font-style: italic; }
.pf-school { font-size: 12px; color: rgba(255,255,255,.66); margin-top: 4px; }
.pf-stats { position: relative; display: grid; grid-template-columns: repeat(3, 1fr); margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,.14); text-align: center; }
.ps-num { font-size: 20px; font-weight: 800; }
.ps-label { font-size: 12px; color: rgba(255,255,255,.64); margin-top: 4px; }

.group { margin-top: 16px; }
.group-title { font-size: 12px; font-weight: 700; color: var(--faint); margin: 0 4px 8px; }
.menu { padding: 0 16px; }
.row { display: flex; align-items: center; gap: 8px; padding: 12px 0; border-bottom: 1px solid var(--line); cursor: pointer; }
.row:last-child { border-bottom: none; }
.row-ic { width: 36px; height: 36px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.c-blue { background: rgba(79, 70, 229, 0.08); color: var(--primary); }
.c-orange { background: rgba(239, 68, 68, 0.08); color: var(--tomato); }
.c-purple { background: rgba(139, 92, 246, 0.1); color: var(--purple); }
.c-red { background: rgba(239, 68, 68, 0.1); color: var(--red); }
.c-green { background: rgba(16, 185, 129, 0.1); color: var(--green); }
.c-ink { background: rgba(17, 24, 39, 0.06); color: var(--ink); }
.c-gold { background: rgba(245, 158, 11, 0.12); color: var(--accent-deep); }
.c-gray { background: rgba(17, 24, 39, 0.05); color: var(--faint); }
.row-label { flex: 1; font-size: 14px; font-weight: 600; }
.row-val { font-size: 12px; color: var(--faint); }
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

.switch { width: 44px; height: 26px; border-radius: 999px; background: rgba(79, 70, 229, 0.16); position: relative; transition: background 0.24s ease; margin-right: 2px; }
.switch.on { background: var(--primary-grad); }
.knob { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; box-shadow: 0 2px 5px rgba(79, 70, 229, 0.24); transition: transform 0.24s ease; }
.switch.on .knob { transform: translateX(18px); }
.version { text-align: center; color: var(--faint); font-size: 12px; margin-top: 24px; }

.mask { position: fixed; inset: 0; background: rgba(30, 27, 75, 0.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 24px 24px 0 0; padding: 24px 16px calc(24px + env(safe-area-inset-bottom)); max-height: 80vh; overflow-y: auto; }
.sheet-title { font-size: 20px; font-weight: 800; text-align: center; }
.sheet-sub { text-align: center; color: var(--sub); font-size: 12px; margin: 8px 0 16px; }
.school-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 16px; }
.school-cell { position: relative; border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 12px; padding: 16px 8px; text-align: center; cursor: pointer; transition: border-color 0.24s ease, background-color 0.24s ease, box-shadow 0.24s ease; }
.school-cell.on { border-color: var(--primary); background: rgba(79, 70, 229, 0.06); box-shadow: 0 6px 16px rgba(79, 70, 229, 0.14); }
.school-cell img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; }
.school-cell span { display: block; font-size: 12px; font-weight: 600; margin-top: 8px; }
.tick { position: absolute; top: 4px; right: 4px; width: 18px; height: 18px; border-radius: 50%; background: var(--primary-grad); color: #fff; display: flex; align-items: center; justify-content: center; }
.goal-list { display: flex; flex-direction: column; gap: 8px; margin-top: 16px; }
.goal-opt { display: flex; justify-content: space-between; align-items: center; padding: 16px; border: 1px solid rgba(79, 70, 229, 0.16); border-radius: 12px; background: rgba(255, 255, 255, 0.8); font-size: 14px; font-weight: 600; cursor: pointer; color: var(--ink); transition: border-color 0.24s ease, background-color 0.24s ease; }
.goal-opt.on { border-color: var(--primary); background: rgba(79, 70, 229, 0.06); color: var(--primary); }
.about-body { margin-top: 16px; font-size: 14px; color: var(--sub); line-height: 1.8; }
.about-body p { margin: 0 0 8px; }
.about-h { color: var(--ink); font-weight: 700; margin-bottom: 4px !important; }

.modal-mask { position: fixed; inset: 0; background: rgba(30, 27, 75, 0.5); display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 200; }
.modal { background: #fff; border-radius: 12px; max-width: 560px; width: 100%; max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 24px 48px rgba(30, 27, 75, 0.24); }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 16px; border-bottom: 1px solid var(--line); }
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-head button { border: none; background: rgba(79, 70, 229, 0.08); color: var(--sub); border-radius: 8px; padding: 8px 16px; cursor: pointer; }
.modal-body { padding: 16px; overflow-y: auto; white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 14px; line-height: 1.8; color: var(--sub); margin: 0; }
</style>

<style scoped>
button.row{width:100%;background:transparent;border:0;text-align:left;font:inherit;color:inherit;cursor:pointer}
.group-help{font-size:12px;line-height:1.6;color:var(--sub);margin:0 4px 8px}
.row-label{min-width:0}.row-val{max-width:48%;white-space:normal;text-align:right}
button.row:not(:last-child){border-bottom:1px solid var(--line)}
.switch{flex-shrink:0}
button.row:focus-visible{outline:2px solid var(--primary);outline-offset:-2px;border-radius:8px}
</style>
