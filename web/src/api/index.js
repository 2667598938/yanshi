// 后端接口集中封装（统一前缀 /api/v1）。所有方法返回 data 部分。
import { http } from './http'

// ------------------------------------------------------------ 公共
export const publicApi = {
  config: () => http.get('/config/public', { auth: false }),
  legal: () => http.get('/legal', { auth: false }),
  announcements: () => http.get('/announcements', { auth: false }),
}

// ------------------------------------------------------------ 认证 / 账号
export const authApi = {
  sendCode: (email, scene = 'register') =>
    http.post('/auth/email-code', { email, scene }, { auth: false }),
  register: (body) => http.post('/auth/register', body, { auth: false }),
  login: (email, password) => http.post('/auth/login', { email, password }, { auth: false }),
  refresh: (refresh_token) =>
    http.post('/auth/refresh', { refresh_token }, { auth: false }),
  logout: () => http.post('/auth/logout', {}),
  resetPassword: (body) => http.post('/auth/reset-password', body, { auth: false }),
  me: () => http.get('/auth/me'),
  updateMe: (body) => http.put('/users/me', body),
  changePassword: (old_password, new_password) =>
    http.put('/users/me/password', { old_password, new_password }),
}

// ------------------------------------------------------------ 数据同步
export const syncApi = {
  records: () => http.get('/sync/records'),
  commands: (operationId, changes) =>
    http.post('/sync/commands', { operationId, changes }),
}

// ------------------------------------------------------------ 自习室
export const roomApi = {
  get: () => http.get('/room'),
  heartbeat: (body) => http.post('/room/heartbeat', body),
  ranking: (range) => http.get('/room/ranking', { query: { range } }),
  postMessage: (content) => http.post('/room/messages', { content }),
  deleteMessage: (id) => http.del(`/room/messages/${id}`),
  putGoal: (body) => http.put('/room/goal', body),
}

// ------------------------------------------------------------ 附件 / 图片
export const attachmentApi = {
  viewUrl: (key) => `/api/v1/attachments/view?key=${encodeURIComponent(key)}`,
  uploadAvatar: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post('/attachments/avatar', fd)
  },
  uploadImage: (file, biz) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post('/attachments/image', fd, { query: { biz } })
  },
  remove: (key) => http.del('/attachments', { query: { key } }),
}

// ------------------------------------------------------------ 院校
export const schoolApi = {
  list: () => http.get('/schools'),
  get: (key) => http.get(`/schools/${key}`),
  adminCreate: (body) => http.post('/admin/schools', body),
  adminUpdate: (key, body) => http.put(`/admin/schools/${key}`, body),
}

// ------------------------------------------------------------ AI
export const aiApi = {
  enabled: () => http.get('/ai/enabled'),
  scenes: () => http.get('/ai/scenes'),
  chat: (body) => http.post('/ai/chat', body),
  conversations: () => http.get('/ai/conversations'),
  createConversation: (body) => http.post('/ai/conversations', body),
  conversation: (id) => http.get(`/ai/conversations/${id}`),
  renameConversation: (id, title) => http.put(`/ai/conversations/${id}`, { title }),
  deleteConversation: (id) => http.del(`/ai/conversations/${id}`),
}

// ------------------------------------------------------------ 后台
export const adminApi = {
  overview: () => http.get('/admin/overview'),
  members: () => http.get('/admin/members'),
  createMember: (body) => http.post('/admin/members', body),
  updateMember: (id, body) => http.put(`/admin/members/${id}`, body),
  resetMemberPassword: (id, new_password) =>
    http.post(`/admin/members/${id}/reset-password`, { new_password }),
  deleteMember: (id) => http.del(`/admin/members/${id}`),
  invites: () => http.get('/admin/invites'),
  createInvite: (body) => http.post('/admin/invites', body),
  deleteInvite: (id) => http.del(`/admin/invites/${id}`),
  announcements: () => http.get('/admin/announcements'),
  createAnnouncement: (content) => http.post('/admin/announcements', { content }),
  updateAnnouncement: (id, body) => http.put(`/admin/announcements/${id}`, body),
  deleteAnnouncement: (id) => http.del(`/admin/announcements/${id}`),
  auditLogs: (limit = 100) => http.get('/admin/audit-logs', { query: { limit } }),
  updateConfig: (body) => http.put('/admin/config', body),
  exportData: () => http.get('/admin/export'),
}
