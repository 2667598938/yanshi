<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft, Copy, Plus, UserPlus, Megaphone, Users, Trash2, Ban, KeyRound,
  Crown, ClipboardCheck, Check, X, Sparkles,
} from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { adminApi, inspirationApi } from '../api'
import BlobImage from '../components/BlobImage.vue'
import { fmtDate, fmtShort, fmtDateTime } from '../utils/time'
import { SCHOOL_MAP } from '../data/schools'
import { useToast } from '../composables/useToast'
import { useClipboard } from '../composables/useClipboard'
import CopyFallback from '../components/CopyFallback.vue'

const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()
const { copy: copyToClipboard, manualCopy } = useClipboard(toast)

const overview = ref(null)
const members = ref([])
const invites = ref([])
const announcements = ref([])
const requests = ref([])
const requestFilter = ref('pending')
const inspirations = ref([])
const inspFilter = ref('pending')
const inspTarget = ref(null)
const inspNote = ref('')
const takedownTarget = ref(null)
const takedownNote = ref('')
const tab = ref('invite')

const sheet = ref(null)
const inviteForm = ref({ remark: '', expires_days: '', vip_days: '' })
const memberForm = ref({ email: '', nickname: '', password: '' })
const announcementForm = ref('')
const resetTarget = ref(null)
const newPwd = ref('')
const vipTarget = ref(null)
const vipForm = ref({ action: 'grant', days: 30, until: '', note: '' })
const reviewTarget = ref(null)
const reviewNote = ref('')

function fmtBytes(n) {
  if (n > 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB'
  return Math.round(n / 1024) + ' KB'
}
function fmtSec(sec) {
  const m = Math.round((sec || 0) / 60)
  return m >= 60 ? (m / 60).toFixed(1) + 'h' : m + 'm'
}

async function loadAll() {
  try {
    const [ov, ms, inv, ans] = await Promise.all([
      adminApi.overview(), adminApi.members(), adminApi.invites(), adminApi.announcements(),
    ])
    overview.value = ov
    members.value = ms
    invites.value = inv
    announcements.value = ans
  } catch (e) {
    toast(e.message)
  }
}

async function loadRequests(status = requestFilter.value) {
  requestFilter.value = status
  try {
    requests.value = await adminApi.requests(status)
  } catch (e) {
    toast(e.message)
  }
}

async function loadInspirations(status = inspFilter.value) {
  inspFilter.value = status
  try {
    inspirations.value = await inspirationApi.adminList(status)
  } catch (e) {
    toast(e.message)
  }
}

async function approveInspiration(row) {
  try {
    const next = await inspirationApi.adminReview(row.id, { action: 'approve', note: '' })
    Object.assign(row, next)
    toast('已通过')
  } catch (e) {
    toast(e.message)
  }
}

function openInspReject(row) {
  inspTarget.value = row
  inspNote.value = ''
  sheet.value = 'insp-reject'
}

async function rejectInspiration() {
  if (!inspNote.value.trim()) return toast('请填写驳回原因')
  try {
    const next = await inspirationApi.adminReview(inspTarget.value.id, {
      action: 'reject', note: inspNote.value.trim(),
    })
    Object.assign(inspTarget.value, next)
    toast('已驳回')
    sheet.value = null
    inspTarget.value = null
  } catch (e) {
    toast(e.message)
  }
}

function openTakedown(row) {
  takedownTarget.value = row
  takedownNote.value = ''
  sheet.value = 'insp-takedown'
}

async function takedownInspiration() {
  if (takedownNote.value.trim().length < 5) return toast('下架原因至少5字')
  try {
    const next = await inspirationApi.takedown(takedownTarget.value.id, takedownNote.value.trim())
    Object.assign(takedownTarget.value, next)
    toast('已下架，新的列表与弹幕请求不会再返回')
    sheet.value = null
    takedownTarget.value = null
    await loadInspirations(inspFilter.value)
  } catch (e) {
    toast(e.message)
  }
}

function switchTab(next) {
  tab.value = next
  if (next === 'request') loadRequests('pending')
  if (next === 'content') loadInspirations('pending')
}

function openVip(m) {
  vipTarget.value = m
  vipForm.value = { action: 'grant', days: 30, until: '', note: '' }
  sheet.value = 'vip'
}

async function submitVip() {
  const f = vipForm.value
  if (f.note.trim().length < 5) return toast('请填写至少 5 个字的操作备注')
  const payload = { vip_action: f.action, note: f.note.trim() }
    if (['grant', 'renew'].includes(f.action)) payload.vip_days = Number(f.days) || 30
    if (f.action === 'set_expiry') {
      if (!f.until) return toast('请选择到期日期')
      payload.vip_until = new Date(`${f.until}T23:59:59+08:00`).toISOString()
    }
  try {
    const row = await adminApi.updateMember(vipTarget.value.id, payload)
    Object.assign(vipTarget.value, row)
    if (overview.value) overview.value.vip_count = members.value.filter((x) => x.is_vip).length
    sheet.value = null
    toast(`${row.nickname} ${f.action === 'revoke' ? '已降级' : '会员已更新'}`)
  } catch (e) {
    toast(e.message)
  }
}

async function approveRequest(r) {
  try {
    const row = await adminApi.reviewRequest(r.id, { action: 'approve', note: '' })
    Object.assign(r, row)
    if (requestFilter.value !== row.status) {
      requests.value = requests.value.filter((x) => x.id !== row.id)
    }
    toast('已通过')
  } catch (e) {
    toast(e.message)
  }
}

async function revokeRequest(r) {
  try {
    const row = await adminApi.revokeRequest(r.id)
    Object.assign(r, row)
    if (requestFilter.value !== row.status) {
      requests.value = requests.value.filter((x) => x.id !== row.id)
    }
    toast('已撤销授权')
  } catch (e) {
    toast(e.message)
  }
}

function openReject(r) {
  reviewTarget.value = r
  reviewNote.value = ''
  sheet.value = 'reject'
}

async function submitReject() {
  if (reviewNote.value.trim().length < 5) return toast('驳回原因至少5个字')
  try {
    const row = await adminApi.reviewRequest(reviewTarget.value.id, {
      action: 'reject', note: reviewNote.value.trim(),
    })
    Object.assign(reviewTarget.value, row)
    if (requestFilter.value !== row.status) {
      requests.value = requests.value.filter((x) => x.id !== row.id)
    }
    sheet.value = null
    toast('已驳回')
  } catch (e) {
    toast(e.message)
  }
}

async function copyCode(code) {
  await copyToClipboard(code, '邀请码已复制：' + code)
}

async function createInvite() {
  try {
    const payload = { remark: inviteForm.value.remark }
    if (inviteForm.value.expires_days) payload.expires_days = Number(inviteForm.value.expires_days)
    if (inviteForm.value.vip_days) payload.vip_days = Number(inviteForm.value.vip_days)
    const row = await adminApi.createInvite(payload)
    invites.value.unshift(row)
    sheet.value = null
    inviteForm.value = { remark: '', expires_days: '', vip_days: '' }
    toast('邀请码已生成：' + row.code)
  } catch (e) {
    toast(e.message)
  }
}

async function removeInvite(id) {
  try {
    await adminApi.deleteInvite(id)
    invites.value = invites.value.filter((x) => x.id !== id)
  } catch (e) {
    toast(e.message)
  }
}

async function createMember() {
  const { email, nickname, password } = memberForm.value
  if (!email || nickname.length < 2 || password.length < 8) return toast('请完整填写，密码至少 8 位含字母数字')
  try {
    const row = await adminApi.createMember(memberForm.value)
    members.value.push(row)
    sheet.value = null
    memberForm.value = { email: '', nickname: '', password: '' }
    toast('已为 ' + row.nickname + ' 建号')
  } catch (e) {
    toast(e.message)
  }
}

async function toggleBan(m) {
  const next = m.status === 'banned' ? 'active' : 'banned'
  try {
    const row = await adminApi.updateMember(m.id, { status: next })
    Object.assign(m, row)
    toast(next === 'banned' ? '已封禁并强制下线' : '已恢复')
  } catch (e) {
    toast(e.message)
  }
}

async function submitReset() {
  if (!resetTarget.value || newPwd.value.length < 8) return toast('新密码至少 8 位含字母数字')
  try {
    await adminApi.resetMemberPassword(resetTarget.value.id, newPwd.value)
    toast('密码已重置')
    sheet.value = null
    resetTarget.value = null
    newPwd.value = ''
  } catch (e) {
    toast(e.message)
  }
}


async function createAnnouncement() {
  if (!announcementForm.value.trim()) return
  try {
    const row = await adminApi.createAnnouncement(announcementForm.value.trim())
    announcements.value.unshift(row)
    announcementForm.value = ''
    sheet.value = null
  } catch (e) {
    toast(e.message)
  }
}
async function removeAnnouncement(id) {
  try {
    await adminApi.deleteAnnouncement(id)
    announcements.value = announcements.value.filter((x) => x.id !== id)
  } catch (e) {
    toast(e.message)
  }
}

onMounted(() => {
  if (!auth.isAdmin) {
    toast('仅管理员可访问')
    router.replace('/me')
    return
  }
  loadAll()
})
async function editAnnouncement(row){
 const content=prompt('编辑公告',row.content);if(content===null||!content.trim())return
 try{const data=await adminApi.updateAnnouncement(row.id,{content:content.trim(),expected_revision:row.revision});Object.assign(row,data);toast('公告已更新')}catch(e){toast(e.message);if(e.status===409)await loadAll()}
}
async function toggleAnnouncement(row){
 try{const data=await adminApi.updateAnnouncement(row.id,{is_active:!row.is_active,expected_revision:row.revision});Object.assign(row,data)}catch(e){toast(e.message);if(e.status===409)await loadAll()}
}
</script>

<template>
  <div class="admin-page">
    <CopyFallback v-model="manualCopy" />
    <div class="page"><button class="btn btn-ghost btn-sm" @click="router.push('/admin/email-jobs')">通知邮件任务与重试</button><button class="btn btn-ghost btn-sm" @click="router.push('/admin/resources')">资料审核</button><button class="btn btn-ghost btn-sm" @click="router.push('/admin/operations')">设置、日志与运行状态</button></div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">后台管理</div>
    </div>

    <div class="page">
      <router-link class="btn btn-outline" to="/admin/group">小组邀请与入组申请审批</router-link>
      <!-- 概览 -->
      <div v-if="overview" class="ov-grid">
        <div class="ov"><div class="ov-n tnum">{{ overview.member_count }}</div><div class="ov-l">成员</div></div>
        <div class="ov"><div class="ov-n tnum">{{ overview.vip_count || 0 }}</div><div class="ov-l">VIP</div></div>

        <div class="ov"><div class="ov-n tnum">{{ overview.room_member_count }}</div><div class="ov-l">有效房间席位占用（人次）</div></div>
        <div class="ov"><div class="ov-n tnum">{{ overview.online_count }}</div><div class="ov-l">可见在线成员（去重）</div></div>
        <div class="ov"><div class="ov-n tnum">{{ fmtBytes(overview.attachment_bytes) }}</div><div class="ov-l">图片占用</div></div>
        <div class="ov"><div class="ov-n tnum">{{ overview.record_count }}</div><div class="ov-l">同步记录</div></div>
      </div>

      <p v-if="overview" class="field-hint">席位统计全部未解散房间的成员关系，同一人在不同房间分别计次。在线人数按90秒有效心跳去重，并遵守小组共享与隐私权限。</p>

      <div class="tabs">
        <button :class="{ on: tab === 'invite' }" @click="switchTab('invite')">邀请码</button>
        <button :class="{ on: tab === 'member' }" @click="switchTab('member')">成员</button>
        <button :class="{ on: tab === 'request' }" @click="switchTab('request')">功能审批</button>
        <button :class="{ on: tab === 'content' }" @click="switchTab('content')">励志内容审核</button>
        <button :class="{ on: tab === 'announce' }" @click="switchTab('announce')">公告</button>
      </div>

      <!-- 邀请码 -->
      <div v-if="tab === 'invite'" class="card">
        <button class="btn btn-primary btn-block" @click="sheet = 'invite'"><Plus :size="16" />生成邀请码</button>
        <div v-for="c in invites" :key="c.id" class="invite-row">
          <div class="invite-main">
            <div class="invite-code tnum">{{ c.code }}</div>
            <div class="invite-sub">
              <span v-if="c.is_used" class="tag tag-used">已使用</span>
              <span v-else class="tag tag-new">可用</span>
              <span v-if="c.vip_days" class="tag tag-vip">VIP +{{ c.vip_days }}天</span>
              {{ c.remark || '无备注' }}
              <span v-if="c.expires_at"> · 有效期至 {{ fmtDate(c.expires_at) }}</span>
            </div>
          </div>
          <button class="mini" @click="copyCode(c.code)"><Copy :size="15" /></button>
          <button v-if="!c.is_used" class="mini danger" @click="removeInvite(c.id)"><Trash2 :size="15" /></button>
        </div>
        <div v-if="!invites.length" class="empty">还没有邀请码，生成一个发给研友注册</div>
      </div>

      <!-- 成员 -->
      <div v-if="tab === 'member'" class="card">
        <button class="btn btn-primary btn-block" @click="sheet = 'member'"><UserPlus :size="16" />直接创建账号</button>
        <div v-for="m in members" :key="m.id" class="member-row">
          <div class="member-main">
            <div class="member-name">
              {{ m.nickname }}
              <span v-if="m.role === 'admin'" class="tag tag-admin">管理员</span>
              <span v-if="m.is_vip" class="tag tag-vip">VIP</span>
              <span v-if="m.status === 'banned'" class="tag tag-ban">已封禁</span>
              <span v-if="m.status === 'deleted'" class="tag tag-used">已注销</span>
            </div>
            <div class="member-sub">
              {{ m.email }}
              <span v-if="m.is_vip"> · {{ m.vip_permanent ? '永久VIP' : `到期 ${fmtDate(m.vip_until)}` }}</span>
            </div>
          </div>
          <div class="member-actions">
            <button class="mini" title="会员调整" @click="openVip(m)"><Crown :size="15" /></button>
            <button class="mini" title="重置密码" @click="sheet = 'reset'; resetTarget = m; newPwd = ''"><KeyRound :size="15" /></button>
            <button v-if="m.role !== 'admin'" class="mini" title="封禁/恢复" @click="toggleBan(m)"><Ban :size="15" /></button>

          </div>
        </div>
      </div>

      <!-- 审批 -->
      <div v-if="tab === 'request'" class="card">
        <div class="seg">
          <button :class="{ on: requestFilter === 'pending' }" @click="loadRequests('pending')">待审核</button>
          <button :class="{ on: requestFilter === 'approved' }" @click="loadRequests('approved')">已通过</button>
          <button :class="{ on: requestFilter === 'rejected' }" @click="loadRequests('rejected')">已驳回</button>
          <button :class="{ on: requestFilter === 'revoked' }" @click="loadRequests('revoked')">已撤销</button>
        </div>
        <div v-if="!requests.length" class="empty">暂无记录</div>
        <div v-for="r in requests" :key="r.id" class="req-card">
          <div class="req-top">
            <span class="req-avatar">{{ r.user.nickname.slice(0, 1) }}</span>
            <div class="req-user">
              <div class="req-nick">{{ r.user.nickname }}</div>
              <div class="req-time">{{ fmtShort(r.created_at) }}</div>
            </div>
            <span class="tag tag-feature">{{ r.feature_label }}</span>
          </div>
          <div class="req-body">{{ r.reason }}</div>
          <div v-if="r.review_note" class="req-note">审批备注：{{ r.review_note }}</div>
          <div v-if="r.status === 'pending'" class="req-actions">
            <button class="req-reject" @click="openReject(r)"><X :size="14" />驳回</button>
            <button class="req-approve" @click="approveRequest(r)"><Check :size="14" />通过</button>
          </div>
          <div v-else class="req-status">
            {{ r.status === 'approved' ? '已通过' : r.status === 'revoked' ? '已撤销' : '已驳回' }} · {{ fmtDate(r.reviewed_at) }}
            <button v-if="r.status === 'approved'" class="req-revoke" @click="revokeRequest(r)">撤销授权</button>
          </div>
        </div>
      </div>

      <!-- 内容审核（励志区） -->
      <div v-if="tab === 'content'" class="card">
        <div class="seg">
          <button :class="{ on: inspFilter === 'pending' }" @click="loadInspirations('pending')">待审核</button>
          <button :class="{ on: inspFilter === 'approved' }" @click="loadInspirations('approved')">已通过</button>
          <button :class="{ on: inspFilter === 'rejected' }" @click="loadInspirations('rejected')">已驳回</button>
          <button :class="{ on: inspFilter === 'taken_down' }" @click="loadInspirations('taken_down')">已下架</button>
          <button :class="{ on: inspFilter === 'withdrawn' }" @click="loadInspirations('withdrawn')">作者撤回</button>
        </div>
        <div v-if="!inspirations.length" class="empty">暂无投稿</div>
        <div v-for="it in inspirations" :key="it.id" class="req-card">
          <div class="req-top">
            <span class="req-avatar"><Sparkles :size="14" /></span>
            <div class="req-user">
              <div class="req-nick">{{ it.user?.nickname }}</div>
              <div class="req-time">{{ fmtShort(it.created_at) }}</div>
            </div>
            <span class="tag" :class="it.status === 'approved' ? 'tag-new' : it.status === 'rejected' ? 'tag-ban' : 'tag-used'">
              {{ it.status_label }}
            </span>
          </div>
          <BlobImage v-if="it.image_key" class="insp-thumb" :src="it.image_key" alt="" />
          <div class="req-body">{{ it.content }}</div>
          <div v-if="it.review_note" class="req-note">审核备注：{{ it.review_note }}</div>
          <div v-if="it.status === 'pending'" class="req-actions">
            <button class="req-reject" @click="openInspReject(it)"><X :size="14" />驳回</button>
            <button class="req-approve" @click="approveInspiration(it)"><Check :size="14" />通过</button>
          </div>
          <div v-if="it.status === 'approved'" class="req-actions">
            <button class="req-reject" @click="openTakedown(it)">下架</button>
          </div>
        </div>
      </div>

      <!-- 公告 -->
      <div v-if="tab === 'announce'" class="card">
        <button class="btn btn-primary btn-block" @click="sheet = 'announce'"><Megaphone :size="16" />发布公告</button>
        <div v-for="a in announcements" :key="a.id" class="ann-row">
          <div class="ann-content">{{ a.content }}</div>
          <div class="ann-foot">
            <span>{{ fmtDateTime(a.created_at) }}</span>
            <span v-if="!a.is_active" class="tag tag-used">已停用</span>
            <button class="mini" @click="editAnnouncement(a)">编辑</button><button class="mini" @click="toggleAnnouncement(a)">{{a.is_active?'停用':'启用'}}</button>
            <button class="mini danger" @click="removeAnnouncement(a.id)"><Trash2 :size="14" /></button>
          </div>
        </div>
        <div v-if="!announcements.length" class="empty">还没有公告</div>
      </div>
    </div>

    <!-- 弹层 -->
    <div v-if="sheet" class="mask" @click.self="sheet = null">
      <div class="sheet">
        <template v-if="sheet === 'invite'">
          <div class="sheet-title">生成邀请码</div>
          <label class="sf"><span>备注（发给谁）</span><input v-model="inviteForm.remark" maxlength="50" placeholder="如：室友小王" /></label>
          <label class="sf"><span>有效天数（可空 = 长期）</span><input v-model="inviteForm.expires_days" type="number" min="1" max="365" placeholder="如 7" /></label>
          <label class="sf"><span>附带 VIP 天数（0 或空 = 仅注册）</span><input v-model="inviteForm.vip_days" type="number" min="0" max="3650" placeholder="如 30" /></label>
          <button class="btn btn-primary btn-block mt16" @click="createInvite">生成</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>

        <template v-else-if="sheet === 'member'">
          <div class="sheet-title">直接创建账号</div>
          <label class="sf"><span>邮箱</span><input v-model="memberForm.email" type="email" placeholder="研友邮箱" /></label>
          <label class="sf"><span>昵称</span><input v-model="memberForm.nickname" maxlength="40" placeholder="昵称" /></label>
          <label class="sf"><span>初始密码</span><input v-model="memberForm.password" placeholder="8-64 位含字母数字" /></label>
          <button class="btn btn-primary btn-block mt16" @click="createMember">创建</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>

        <template v-else-if="sheet === 'reset'">
          <div class="sheet-title">重置「{{ resetTarget?.nickname }}」密码</div>
          <label class="sf"><span>新密码</span><input v-model="newPwd" placeholder="8-64 位含字母数字" /></label>
          <button class="btn btn-primary btn-block mt16" @click="submitReset">确认重置</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>

        <template v-else-if="sheet === 'vip'">
          <div class="sheet-title">会员调整 · {{ vipTarget?.nickname }}</div>
          <div class="vip-current">
            当前状态：{{ vipTarget?.vip_permanent ? '永久VIP' : vipTarget?.is_vip ? `VIP · ${fmtDate(vipTarget.vip_until)} 到期` : '未开通' }}
          </div>
          <div class="seg" style="margin-bottom: 12px">
            <button :class="{ on: vipForm.action === 'grant' }" @click="vipForm.action = 'grant'">开通</button>
            <button :class="{ on: vipForm.action === 'renew' }" @click="vipForm.action = 'renew'">续期</button>
            <button :class="{ on: vipForm.action === 'revoke' }" @click="vipForm.action = 'revoke'">降级</button>
            <button :class="{ on: vipForm.action === 'permanent' }" @click="vipForm.action = 'permanent'">永久</button>
            <button :class="{ on: vipForm.action === 'set_expiry' }" @click="vipForm.action = 'set_expiry'">指定到期</button>
          </div>
          <label v-if="['grant', 'renew'].includes(vipForm.action)" class="sf">
            <span>会员天数</span>
            <input v-model="vipForm.days" type="number" min="1" max="3650" placeholder="30" />
          </label>
          <label v-if="vipForm.action === 'set_expiry'" class="sf"><span>到期日期（当天23:59）</span><input v-model="vipForm.until" type="date" /></label>
          <label class="sf">
            <span>操作备注（必填 ≥5 字）</span>
            <input v-model="vipForm.note" maxlength="300" placeholder="如：研友续期一个月" />
          </label>
          <button class="btn btn-primary btn-block mt16" @click="submitVip">确认调整</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>

        <template v-else-if="sheet === 'reject'">
          <div class="sheet-title">驳回申请 · {{ reviewTarget?.feature_label }}</div>
          <div class="vip-current">{{ reviewTarget?.user.nickname }}：{{ reviewTarget?.reason }}</div>
          <label class="sf">
            <span>驳回原因</span>
            <textarea v-model="reviewNote" class="ta" rows="3" maxlength="300" placeholder="写清楚原因，申请人可见"></textarea>
          </label>
          <button class="btn btn-danger btn-block mt16" @click="submitReject">确认驳回</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>

        <template v-else-if="sheet === 'insp-reject'">
          <div class="sheet-title">驳回励志投稿</div>
          <div class="vip-current">{{ inspTarget?.user?.nickname }}：{{ inspTarget?.content }}</div>
          <label class="sf">
            <span>驳回原因</span>
            <textarea v-model="inspNote" class="ta" rows="3" maxlength="300" placeholder="写清楚原因，投稿人可见"></textarea>
          </label>
          <button class="btn btn-danger btn-block mt16" @click="rejectInspiration">确认驳回</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>

        <template v-else-if="sheet === 'insp-takedown'">
          <div class="sheet-title">下架励志投稿</div>
          <div class="vip-current">{{ takedownTarget?.user?.nickname }}：{{ takedownTarget?.content }}</div>
          <label class="sf">
            <span>下架原因（至少5字，投稿人可见）</span>
            <textarea v-model="takedownNote" class="ta" rows="3" maxlength="300" placeholder="下架后会从励志区和弹幕池移除"></textarea>
          </label>
          <button class="btn btn-danger btn-block mt16" @click="takedownInspiration">确认下架</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>

        <template v-else-if="sheet === 'announce'">
          <div class="sheet-title">发布公告</div>
          <textarea v-model="announcementForm" class="ta" rows="4" maxlength="1000" placeholder="四名成员在首页可见的公告"></textarea>
          <button class="btn btn-primary btn-block mt16" @click="createAnnouncement">发布</button>
          <button class="btn btn-ghost btn-block mt8" @click="sheet = null">取消</button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nav { display: flex; align-items: center; gap: 10px; }
.back { border: none; background: #fff; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.ov-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }
.ov { background: #fff; border-radius: 14px; padding: 14px 8px; text-align: center; box-shadow: var(--shadow-soft); }
.ov-n { font-size: 18px; font-weight: 800; color: var(--primary); }
.ov-l { font-size: 11.5px; color: var(--faint); margin-top: 3px; }
.tabs { display: flex; gap: 6px; background: #fff; border-radius: 12px; padding: 4px; margin-bottom: 12px; box-shadow: var(--shadow-soft); }
.tabs button { flex: 1; border: none; background: transparent; padding: 10px 0; border-radius: 9px; font-size: 14px; color: var(--sub); cursor: pointer; }
.tabs button.on { background: var(--primary); color: #fff; font-weight: 600; }
.invite-row, .member-row, .ann-row { display: flex; align-items: center; gap: 10px; padding: 12px 0; border-bottom: 1px solid var(--line); }
.invite-row:last-child, .member-row:last-child, .ann-row:last-child { border-bottom: none; }
.invite-main, .member-main { flex: 1; min-width: 0; }
.invite-code { font-size: 19px; font-weight: 800; letter-spacing: 2px; color: var(--ink); }
.invite-sub, .member-sub { font-size: 12px; color: var(--faint); margin-top: 3px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.member-name { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 6px; }
.member-actions { display: flex; gap: 6px; flex-shrink: 0; }
.mini { width: 34px; height: 34px; border-radius: 9px; border: 1px solid var(--line); background: #fff; color: var(--sub); display: flex; align-items: center; justify-content: center; cursor: pointer; }
.mini.danger { color: var(--red); }
.tag { font-size: 10px; padding: 1px 6px; border-radius: 6px; font-weight: 600; }
.tag-new { background: #ecfdf5; color: #10b981; }
.tag-used { background: #eef1f6; color: var(--faint); }
.tag-admin { background: #fff3df; color: var(--accent-deep); }
.tag-ban { background: #fdecec; color: var(--red); }
.tag-vip { background: #fff3df; color: #b06000; }
.tag-feature { background: #eef0fe; color: var(--purple); }

.seg { display: flex; gap: 2px; background: #f1f4fa; border-radius: 10px; padding: 3px; }
.seg button { flex: 1; border: none; background: transparent; padding: 7px 0; border-radius: 7px; font-size: 12.5px; color: var(--sub); cursor: pointer; }
.seg button.on { background: #fff; color: var(--primary); font-weight: 700; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.req-card { padding: 13px 0; border-bottom: 1px solid var(--line); }
.req-card:last-child { border-bottom: none; }
.req-top { display: flex; align-items: center; gap: 9px; }
.req-avatar { width: 30px; height: 30px; border-radius: 50%; background: #e6f0fb; color: var(--primary); display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; }
.req-user { flex: 1; min-width: 0; }
.req-nick { font-size: 13.5px; font-weight: 700; }
.req-time { font-size: 10.5px; color: var(--faint); margin-top: 1px; }
.req-body { margin-top: 9px; font-size: 12.5px; color: var(--sub); line-height: 1.65; background: #f6f9fd; border-radius: 9px; padding: 8px 10px; }
.insp-thumb { width: 100%; max-height: 150px; object-fit: cover; border-radius: 10px; margin-top: 9px; }
.req-note { margin-top: 7px; font-size: 11.5px; color: var(--primary-deep); }
.req-actions { display: flex; gap: 8px; margin-top: 10px; }
.req-reject, .req-approve { flex: 1; height: 34px; border: none; border-radius: 9px; display: flex; align-items: center; justify-content: center; gap: 4px; font-size: 12.5px; font-weight: 600; cursor: pointer; }
.req-reject { background: #f1f4fa; color: var(--sub); }
.req-approve { background: var(--primary); color: #fff; }
.req-status { margin-top: 8px; font-size: 11.5px; color: var(--faint); }
.req-revoke { margin-left: 8px; border: 1px solid var(--line); background: #fff; color: var(--sub); border-radius: 7px; padding: 3px 8px; font-size: 11px; cursor: pointer; }
.vip-current { font-size: 12.5px; color: var(--sub); margin-bottom: 12px; line-height: 1.6; }
.ann-content { font-size: 14px; line-height: 1.6; color: var(--ink); }
.ann-foot { display: flex; align-items: center; gap: 8px; margin-top: 6px; font-size: 11px; color: var(--faint); }
.empty { text-align: center; color: var(--faint); font-size: 13px; padding: 20px 0; }

.mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; padding: 22px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-title { font-size: 17px; font-weight: 800; text-align: center; margin-bottom: 14px; }
.sf { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.sf span { font-size: 13px; color: var(--sub); }
.sf input { height: 44px; border: 1px solid var(--line); border-radius: 10px; padding: 0 12px; font-size: 15px; background: #fafbfe; }
.sf input:focus { outline: none; border-color: var(--primary); }
.ta { width: 100%; box-sizing: border-box; border: 1px solid var(--line); border-radius: 10px; padding: 12px; font-size: 14px; font-family: inherit; background: #fafbfe; resize: vertical; }
.ta:focus { outline: none; border-color: var(--primary); }
</style>
