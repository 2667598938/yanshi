// 后端接口集中封装（统一前缀 /api/v1）。所有方法返回 data 部分。
import { http, streamPost } from './http'

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
  emailLogin: (body) => http.post('/auth/email-login', body, { auth: false }),
  oauthAuthorize: (provider) =>
    http.get(`/auth/oauth/${provider}/authorize`, { auth: false }),
  oauthExchange: (ticket) =>
    http.post('/auth/oauth/exchange', { ticket }, { auth: false }),
  phoneSendCode: (phone) => http.post('/auth/phone/send-code', { phone }, { auth: false }),
  phoneVerify: (phone, code) =>
    http.post('/auth/phone/verify-code', { phone, code }, { auth: false }),
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
  get: (id) => http.get(id ? `/rooms/${id}` : '/room'),
  heartbeat: (body, id) => http.post(id ? `/rooms/${id}/heartbeat` : '/room/heartbeat', body),
  ranking: (range, id) =>
    http.get(id ? `/rooms/${id}/ranking` : '/room/ranking', { query: { range } }),
  postMessage: (content, id) =>
    http.post(id ? `/rooms/${id}/messages` : '/room/messages', { content }),
  deleteMessage: (messageId, id) =>
    http.del(id ? `/rooms/${id}/messages/${messageId}` : `/room/messages/${messageId}`),
  putGoal: (body, id) => http.put(id ? `/rooms/${id}/goal` : '/room/goal', body),
  list: () => http.get('/rooms'),
  create: (body) => http.post('/rooms', body),
  join: (id, code = '') => http.post(`/rooms/${id}/join`, { code }),
  joinByCode: (code) => http.post('/rooms/join-by-code', { code }),
  leave: (id) => http.post(`/rooms/${id}/leave`, {}),
  update: (id, body) => http.patch(`/rooms/${id}`, body),
  newCode: (id) => http.post(`/rooms/${id}/code`, {}),
  kick: (id, uid) => http.del(`/rooms/${id}/members/${uid}`),
  dissolve: (id) => http.del(`/rooms/${id}`),
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
  chatStream: (body, onEvent, opts) => streamPost('/ai/chat/stream', body, onEvent, opts),
  key: () => http.get('/ai/key'),
  saveKey: (body) => http.put('/ai/key', body),
  deleteKey: () => http.del('/ai/key'),
  models: (body) => http.post('/ai/models', body),
  conversations: () => http.get('/ai/conversations'),
  createConversation: (body) => http.post('/ai/conversations', body),
  conversation: (id) => http.get(`/ai/conversations/${id}`),
  renameConversation: (id, title) => http.put(`/ai/conversations/${id}`, { title }),
  deleteConversation: (id) => http.del(`/ai/conversations/${id}`),
}

// ------------------------------------------------------------ 运营 / 会员
export const vipApi = {
  status: () => http.get('/vip/status'),
  redeem: (code) => http.post('/vip/redeem', { code }),
}

export const requestApi = {
  mine: () => http.get('/requests/mine'),
  create: (body) => http.post('/requests', body),
  withdraw: (id) => http.post(`/requests/${id}/withdraw`, {}),
}

export const errorTypeApi = {
  list: () => http.get('/mistake/error-types'),
  create: (name) => http.post('/mistake/error-types', { name }),
  rename: (id, name) => http.put(`/mistake/error-types/${id}`, { name }),
  remove: (id) => http.del(`/mistake/error-types/${id}`),
}

export const messageApi = {
  list: (limit = 50) => http.get('/messages', { query: { limit } }),
  unread: () => http.get('/messages/unread-count'),
  read: (id) => http.post(`/messages/${id}/read`, {}),
  readAll: () => http.post('/messages/read-all', {}),
}

export const resourceApi = {
  list: (params = {}) => http.get('/resources', { query: params }),
  favorites: () => http.get('/resources/favorites'),
  mine: () => http.get('/resources/mine'),
  get: (id) => http.get(`/resources/${id}`),
  create: (body) => http.post('/resources', body),
  update: (id, body) => http.put(`/resources/${id}`, body),
  remove: (id, reason = '') => http.del('/resources/' + id, { query: { reason } }),
  like: (id) => http.post(`/resources/${id}/like`, {}),
  favorite: (id) => http.post(`/resources/${id}/favorite`, {}),
  setFavorite: (id, favorited) => http.put(`/resources/${id}/favorite`, { favorited }),
}

export const postApi = {
  list: () => http.get('/posts'),
  mine: () => http.get('/posts/mine'),
  get: (id) => http.get(`/posts/${id}`),
  create: (content, clientId = '') =>
    http.post('/posts', clientId ? { content, client_id: clientId } : { content }),
  remove: (id, reason = '') => http.del('/posts/' + id, { query: { reason } }),
  comments: (id) => http.get(`/posts/${id}/comments`),
  comment: (id, body) => http.post(`/posts/${id}/comments`, body),
  deleteComment: (id, reason = '') => http.del('/comments/' + id, { query: { reason } }),
}

export const inspirationApi = {
  list: () => http.get('/inspirations', { auth: false }),
  mine: () => http.get('/inspirations/mine'),
  submit: (body) => http.post('/inspirations', body),
  adminList: (status = 'pending') => http.get('/admin/inspirations', { query: { status } }),
  adminReview: (id, body) => http.post(`/admin/inspirations/${id}/review`, body),
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
  requests: (status = 'pending') => http.get('/admin/requests', { query: { status } }),
  reviewRequest: (id, body) => http.post(`/admin/requests/${id}/review`, body),
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
