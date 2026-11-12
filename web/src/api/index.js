// 后端接口集中封装（统一前缀 /api/v1）。所有方法返回 data 部分。
import { http, streamPost } from './http';
import { PENDING_LOGOUT_KEY } from '../utils/pendingLogout';

// 多标签页共享 refresh Cookie，按顺序轮换，避免同时续期互相作废。
function sessionCookieRequest(request) {
  const locks = globalThis.navigator?.locks;
  return locks?.request ? locks.request('yanshi:auth-cookie', request) : request();
}

function acceptNewSession(request) {
  return sessionCookieRequest(async () => {
    const session = await request();
    localStorage.removeItem(PENDING_LOGOUT_KEY);
    return session;
  });
}

// ------------------------------------------------------------ 公共
export const publicApi = {
  config: () => http.get('/config/public', { auth: false }),
  legal: () => http.get('/legal', { auth: false }),
  announcements: () => http.get('/announcements', { auth: false }),
};

// ------------------------------------------------------------ 认证 / 账号
export const authApi = {
  bindPhoneCode: (phone) => http.post('/users/me/phone/send-code', { phone }),
  bindPhone: (phone, code) => http.put('/users/me/phone', { phone, code }),
  sendCode: (email, scene = 'register') =>
    http.post('/auth/email-code', { email, scene }, { auth: false }),
  emailLogin: (body) =>
    acceptNewSession(() => http.post('/auth/email-login', body, { auth: false })),
  oauthAuthorize: (provider, accepted = false) =>
    http.get(`/auth/oauth/${provider}/authorize`, {
      auth: false,
      query: { accepted_terms: accepted },
    }),
  oauthExchange: (ticket) =>
    acceptNewSession(() => http.post('/auth/oauth/exchange', { ticket }, { auth: false })),
  phoneSendCode: (phone) => http.post('/auth/phone/send-code', { phone }, { auth: false }),
  phoneVerify: (phone, code, accepted = false) =>
    acceptNewSession(() =>
      http.post(
        '/auth/phone/verify-code',
        { phone, code, accepted_terms: accepted },
        { auth: false },
      ),
    ),
  register: (body) => acceptNewSession(() => http.post('/auth/register', body, { auth: false })),
  login: (email, password) =>
    acceptNewSession(() => http.post('/auth/login', { email, password }, { auth: false })),
  refresh: () => sessionCookieRequest(() => http.post('/auth/refresh', {}, { auth: false })),
  logout: ({ pendingOnly = false } = {}) =>
    sessionCookieRequest(async () => {
      if (pendingOnly && !localStorage.getItem(PENDING_LOGOUT_KEY)) return;
      const result = await http.post('/auth/logout', {});
      localStorage.removeItem(PENDING_LOGOUT_KEY);
      return result;
    }),
  resetPassword: (body) => http.post('/auth/reset-password', body, { auth: false }),
  me: () => http.get('/auth/me'),
  updateMe: (body) => http.put('/users/me', body),
  changePassword: (old_password, new_password) =>
    http.put('/users/me/password', { old_password, new_password }),
};

// ------------------------------------------------------------ 数据同步
export const syncApi = {
  records: (query) => http.get('/sync/records', { query }),
  commands: (operationId, changes) => http.post('/sync/commands', { operationId, changes }),
};

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
  join: (id, code = '', acceptSharing = false) =>
    http.post(`/rooms/${id}/join`, { code, accept_sharing: acceptSharing }),
  joinByCode: (code, acceptSharing = false) =>
    http.post('/rooms/join-by-code', { code, accept_sharing: acceptSharing }),
  confirmSharing: (id) => http.post(`/rooms/${id}/sharing/confirm`, { accept_sharing: true }),
  preview: (id) => http.get(`/rooms/${id}/preview`),
  apply: (id, message = '', acceptSharing = false) =>
    http.post(`/rooms/${id}/apply`, { message, accept_sharing: acceptSharing }),
  applies: (id, status = 'pending') => http.get(`/rooms/${id}/applies`, { query: { status } }),
  reviewApply: (id, applyId, approve) =>
    http.post(`/rooms/${id}/applies/${applyId}/review`, { approve }),
  leave: (id) => http.post(`/rooms/${id}/leave`, {}),
  update: (id, body) => http.patch(`/rooms/${id}`, body),
  newCode: (id) => http.post(`/rooms/${id}/code`, {}),
  kick: (id, uid) => http.del(`/rooms/${id}/members/${uid}`),
  dissolve: (id) => http.del(`/rooms/${id}`),
};

import { cacheImage } from '../db/imageCache';
import { localAccountScope } from '../db';

// ------------------------------------------------------------ 附件 / 图片
export const attachmentApi = {
  viewUrl: (key) => `/api/v1/attachments/view?key=${encodeURIComponent(key)}`,
  uploadAvatar: (file) => {
    const fd = new FormData();
    fd.append('file', file);
    const scope = localAccountScope();
    return http.post('/attachments/avatar', fd).then(async (result) => {
      await cacheImage(result.key, file, scope);
      return result;
    });
  },
  uploadImage: (file, biz) => {
    const fd = new FormData();
    fd.append('file', file);
    const scope = localAccountScope();
    return http.post('/attachments/image', fd, { query: { biz } }).then(async (result) => {
      await cacheImage(result.key, file, scope);
      return result;
    });
  },
  remove: (key) => http.del('/attachments', { query: { key } }),
  storage: () => http.get('/attachments/storage'),
  reclaim: () => http.post('/attachments/reclaim', {}),
};

// ------------------------------------------------------------ 院校
export const groupApi = {
  members: (roomId) => http.get('/group/members', { query: roomId ? { room_id: roomId } : {} }),
  changes: (id, since, roomId) =>
    http.get(`/group/members/${id}/learning/changes`, {
      query: { since, ...(roomId ? { room_id: roomId } : {}) },
    }),
  learning: (id, after = '', roomId) =>
    http.get(`/group/members/${id}/learning`, {
      query: { after, ...(roomId ? { room_id: roomId } : {}) },
    }),
  presence: (body) => http.post('/group/presence', body),
};
export const timeNodeApi = { list: () => http.get('/time-nodes') };
export const schoolApi = {
  create: (body) => http.post('/schools', body),
  update: (key, body) => http.put(`/schools/${key}`, body),
  remove: (key) => http.del(`/schools/${key}`),
  list: () => http.get('/schools'),
  get: (key) => http.get(`/schools/${key}`),
  adminCreate: (body) => http.post('/admin/schools', body),
  adminUpdate: (key, body) => http.put(`/admin/schools/${key}`, body),
};

// ------------------------------------------------------------ AI
export const aiApi = {
  importTasks: (id, selected, edits) =>
    http.post(`/ai/messages/${id}/import-tasks`, {
      confirmed: true,
      ...(selected ? { selected } : {}),
      ...(edits ? { edits } : {}),
    }),
  undoTasks: (id) => http.post(`/ai/messages/${id}/undo-tasks`, { confirmed: true }),
  usage: () => http.get('/ai/usage'),
  preferences: (body) => http.put('/ai/preferences', body),
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
};

// ------------------------------------------------------------ 运营 / 会员
export const vipApi = {
  status: () => http.get('/vip/status'),
  redeem: (code) => http.post('/vip/redeem', { code }),
};

export const requestApi = {
  mine: () => http.get('/requests/mine'),
  create: (body) => http.post('/requests', body),
  withdraw: (id) => http.post(`/requests/${id}/withdraw`, {}),
};

export const errorTypeApi = {
  list: () => http.get('/mistake/error-types'),
  create: (name) => http.post('/mistake/error-types', { name }),
  rename: (id, name) => http.put(`/mistake/error-types/${id}`, { name }),
  remove: (id) => http.del(`/mistake/error-types/${id}`),
};

export const messageApi = {
  list: (limit = 50, beforeId = null) =>
    http.get('/messages', { query: { limit, ...(beforeId ? { before_id: beforeId } : {}) } }),
  unread: () => http.get('/messages/unread-count'),
  read: (id) => http.post(`/messages/${id}/read`, {}),
  readAll: () => http.post('/messages/read-all', {}),
};

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
  favoriteMirror: (afterId = 0) =>
    http.get('/resources/favorite-mirror', { query: { after_id: afterId } }),
  setFavorite: (id, favorited, revision) =>
    http.put(`/resources/${id}/favorite`, { favorited, expected_revision: revision }),
};

export const postApi = {
  mirror: (afterId = 0) => http.get('/posts/mirror', { query: { after_id: afterId } }),
  update: (id, content, revision) =>
    http.put(`/posts/${id}`, { content, expected_revision: revision }),
  list: (params = {}) => http.get('/posts', { query: params }),
  mine: () => http.get('/posts/mine'),
  get: (id) => http.get(`/posts/${id}`),
  create: (content, clientId = '') =>
    http.post('/posts', clientId ? { content, client_id: clientId } : { content }),
  remove: (id, reason = '', revision) =>
    http.del('/posts/' + id, { query: { reason, expected_revision: revision } }),
  comments: (id) => http.get(`/posts/${id}/comments`),
  comment: (id, body) => http.post(`/posts/${id}/comments`, body),
  deleteComment: (id, reason = '') => http.del('/comments/' + id, { query: { reason } }),
};

export const inspirationApi = {
  bullets: () => http.get('/inspirations/bullets', { auth: false }),
  list: () => http.get('/inspirations', { auth: false }),
  mine: () => http.get('/inspirations/mine'),
  submit: (body) => http.post('/inspirations', body),
  adminList: (status = 'pending') => http.get('/admin/inspirations', { query: { status } }),
  adminReview: (id, body) => http.post(`/admin/inspirations/${id}/review`, body),
  withdraw: (id, note = '') => http.post(`/inspirations/${id}/withdraw`, { note }),
  takedown: (id, note) => http.post(`/admin/inspirations/${id}/takedown`, { note }),
};

// ------------------------------------------------------------ 后台
export const adminApi = {
  resourceQueue: (status = 'pending', after_id = 0) =>
    http.get('/admin/resources', { query: { status, after_id } }),
  reviewResource: (id, body) => http.post(`/admin/resources/${id}/review`, body),
  config: () => http.get('/admin/config'),
  diagnostics: () => http.get('/admin/diagnostics'),
  batchInvites: (body) => http.post('/admin/invites/batch', body),
  emailJobs: (status = 'all') => http.get('/admin/email-jobs', { query: { status } }),
  retryEmail: (id) => http.post(`/admin/email-jobs/${id}/retry`, {}),
  overview: () => http.get('/admin/overview'),
  members: () => http.get('/admin/members'),
  createMember: (body) => http.post('/admin/members', body),
  updateMember: (id, body) => http.put(`/admin/members/${id}`, body),
  resetMemberPassword: (id, new_password) =>
    http.post(`/admin/members/${id}/reset-password`, { new_password }),
  deleteMember: (id) => http.del(`/admin/members/${id}`),
  requests: (status = 'pending') => http.get('/admin/requests', { query: { status } }),
  reviewRequest: (id, body) => http.post(`/admin/requests/${id}/review`, body),
  revokeRequest: (id) => http.post(`/admin/requests/${id}/revoke`, {}),
  invites: () => http.get('/admin/invites'),
  createInvite: (body) => http.post('/admin/invites', body),
  deleteInvite: (id) => http.del(`/admin/invites/${id}`),
  announcements: () => http.get('/admin/announcements'),
  createAnnouncement: (content) => http.post('/admin/announcements', { content }),
  updateAnnouncement: (id, body) => http.put(`/admin/announcements/${id}`, body),
  deleteAnnouncement: (id) => http.del(`/admin/announcements/${id}`),
  auditLogs: (limit = 100, filters = {}) =>
    http.get('/admin/audit-logs', { query: { limit, ...filters } }),
  updateConfig: (body) => http.put('/admin/config', body),
  exportData: () => http.get('/admin/export'),
};

export const timerApi = {
  current: () => http.get('/timer/current'),
  start: (body) => http.post('/timer/start', body),
  heartbeat: (body) => http.put('/timer/heartbeat', body),
  release: (body) => http.post('/timer/release', body),
  conflicts: () => http.get('/timer/conflicts'),
  resolve: (body) => http.post('/timer/resolve', body),
};
