<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Copy, Plus, UserPlus, Megaphone, Users, Trash2, Ban, KeyRound } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'
import { adminApi } from '../api'
import { SCHOOL_MAP } from '../data/schools'
import { useToast } from '../composables/useToast'

const router = useRouter()
const auth = useAuthStore()
const { toast } = useToast()

const overview = ref(null)
const members = ref([])
const invites = ref([])
const announcements = ref([])
const tab = ref('invite')

const sheet = ref(null)
const inviteForm = ref({ remark: '', expires_days: '' })
const memberForm = ref({ email: '', nickname: '', password: '' })
const announcementForm = ref('')
const resetTarget = ref(null)
const newPwd = ref('')

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

async function copyCode(code) {
  try {
    await navigator.clipboard.writeText(code)
    toast('邀请码已复制：' + code)
  } catch {
    toast('请手动复制：' + code)
  }
}

async function createInvite() {
  try {
    const payload = { remark: inviteForm.value.remark }
    if (inviteForm.value.expires_days) payload.expires_days = Number(inviteForm.value.expires_days)
    const row = await adminApi.createInvite(payload)
    invites.value.unshift(row)
    sheet.value = null
    inviteForm.value = { remark: '', expires_days: '' }
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

async function removeMember(m) {
  if (!confirm(`确认删除成员 ${m.nickname}？此操作不可恢复`)) return
  try {
    await adminApi.deleteMember(m.id)
    members.value = members.value.filter((x) => x.id !== m.id)
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
</script>

<template>
  <div class="admin-page">
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">后台管理</div>
    </div>

    <div class="page">
      <!-- 概览 -->
      <div v-if="overview" class="ov-grid">
        <div class="ov"><div class="ov-n tnum">{{ overview.member_count }}/{{ overview.room_capacity }}</div><div class="ov-l">成员</div></div>
        <div class="ov"><div class="ov-n tnum">{{ overview.online_count }}</div><div class="ov-l">在线</div></div>
        <div class="ov"><div class="ov-n tnum">{{ fmtSec(overview.total_focus_sec) }}</div><div class="ov-l">累计专注</div></div>
        <div class="ov"><div class="ov-n tnum">{{ fmtBytes(overview.attachment_bytes) }}</div><div class="ov-l">图片占用</div></div>
        <div class="ov"><div class="ov-n tnum">{{ overview.record_count }}</div><div class="ov-l">同步记录</div></div>
        <div class="ov"><div class="ov-n tnum">{{ overview.conversation_count }}</div><div class="ov-l">AI 会话</div></div>
      </div>

      <div class="tabs">
        <button :class="{ on: tab === 'invite' }" @click="tab = 'invite'">邀请码</button>
        <button :class="{ on: tab === 'member' }" @click="tab = 'member'">成员</button>
        <button :class="{ on: tab === 'announce' }" @click="tab = 'announce'">公告</button>
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
              {{ c.remark || '无备注' }}
              <span v-if="c.expires_at"> · 有效期至 {{ c.expires_at.slice(0, 10) }}</span>
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
              <span v-if="m.status === 'banned'" class="tag tag-ban">已封禁</span>
              <span v-if="m.status === 'deleted'" class="tag tag-used">已注销</span>
            </div>
            <div class="member-sub">{{ m.email }} · {{ SCHOOL_MAP[m.target_school]?.short || '未填梦校' }}</div>
          </div>
          <div class="member-actions">
            <button class="mini" title="重置密码" @click="sheet = 'reset'; resetTarget = m; newPwd = ''"><KeyRound :size="15" /></button>
            <button v-if="m.role !== 'admin'" class="mini" title="封禁/恢复" @click="toggleBan(m)"><Ban :size="15" /></button>
            <button v-if="m.role !== 'admin'" class="mini danger" title="删除" @click="removeMember(m)"><Trash2 :size="15" /></button>
          </div>
        </div>
      </div>

      <!-- 公告 -->
      <div v-if="tab === 'announce'" class="card">
        <button class="btn btn-primary btn-block" @click="sheet = 'announce'"><Megaphone :size="16" />发布公告</button>
        <div v-for="a in announcements" :key="a.id" class="ann-row">
          <div class="ann-content">{{ a.content }}</div>
          <div class="ann-foot">
            <span>{{ a.created_at?.slice(0, 16).replace('T', ' ') }}</span>
            <span v-if="!a.is_active" class="tag tag-used">已停用</span>
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
.member-actions { display: flex; gap: 6px; }
.mini { width: 34px; height: 34px; border-radius: 9px; border: 1px solid var(--line); background: #fff; color: var(--sub); display: flex; align-items: center; justify-content: center; cursor: pointer; }
.mini.danger { color: var(--red); }
.tag { font-size: 10px; padding: 1px 6px; border-radius: 6px; font-weight: 600; }
.tag-new { background: #e7f6f0; color: #1f9d63; }
.tag-used { background: #eef1f6; color: var(--faint); }
.tag-admin { background: #fff3df; color: var(--accent-deep); }
.tag-ban { background: #fdecec; color: var(--red); }
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
