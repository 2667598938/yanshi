import { defineStore } from 'pinia';
import { authApi } from '../api';
import { afterLogin, afterLogout } from '../sync/account';
import { PENDING_LOGOUT_KEY } from '../utils/pendingLogout';

// 只缓存非敏感的展示资料；access token 常驻内存，refresh token 在 httpOnly Cookie
const SESSION_KEY = 'yanshi:session';
const LEGACY_KEY = 'yanshi:auth';
const refreshRequests = new WeakMap();

function loadCachedUser() {
  try {
    if (localStorage.getItem(PENDING_LOGOUT_KEY)) return null;
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: '',
    user: loadCachedUser(),
    vipNow: Date.now(),
    avatarRevision: 0,
  }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    canRefresh: (s) => !!s.user,
    isAdmin: (s) => s.user?.role === 'admin',
    isSuperAdmin: (s) => s.user?.is_super_admin ?? s.user?.role === 'admin',
    isVip: (s) =>
      !!s.user?.vip_permanent ||
      (!!s.user?.vip_until && new Date(s.user.vip_until).getTime() > s.vipNow),
  },
  actions: {
    persist() {
      if (this.user) localStorage.setItem(SESSION_KEY, JSON.stringify(this.user));
      else localStorage.removeItem(SESSION_KEY);
    },
    async acceptSession({ access_token, user }) {
      const sync = await import('../sync/engine');
      await sync.pauseSyncForAccountSwitch();
      try {
        this.accessToken = access_token;
        this.user = user;
        this.persist();
        await afterLogin(user.id);
      } finally {
        sync.resumeSyncAfterAccountSwitch();
      }
    },
    setUser(user) {
      this.vipNow = Date.now();
      this.user = user;
      this.persist();
    },
    async authenticate(request) {
      const sync = await import('../sync/engine');
      await sync.pauseSyncForAccountSwitch();
      try {
        const data = await request();
        await this.acceptSession(data);
        return data;
      } finally {
        sync.resumeSyncAfterAccountSwitch();
      }
    },
    async login(email, password) {
      return this.authenticate(() => authApi.login(email, password));
    },
    async emailLogin(payload) {
      return this.authenticate(() => authApi.emailLogin(payload));
    },
    async exchangeOAuth(ticket) {
      return this.authenticate(() => authApi.oauthExchange(ticket));
    },
    async phoneLogin(phone, code, accepted = false) {
      return this.authenticate(() => authApi.phoneVerify(phone, code, accepted));
    },
    async register(payload) {
      return this.authenticate(() => authApi.register(payload));
    },
    // 启动/刷新时用 httpOnly Cookie 恢复会话；离线时保留本地缓存资料
    async restore() {
      localStorage.removeItem(LEGACY_KEY); // 清理旧版本遗留的 token
      if (localStorage.getItem(PENDING_LOGOUT_KEY)) {
        this.clear();
        await this.retryPendingLogout();
        return false;
      }
      try {
        const data = await authApi.refresh();
        if (localStorage.getItem(PENDING_LOGOUT_KEY)) return false;
        this.accessToken = data.access_token;
        if (data.user) this.user = data.user;
        this.persist();
        return true;
      } catch (error) {
        this.accessToken = '';
        // 明确失效不能把缓存昵称当登录凭证；断网才保留已有账号的离线入口。
        if (error.status && error.status < 500) this.clear();
        return false;
      }
    },
    // 用 refresh Cookie 换新 access，成功返回 true
    async tryRefresh() {
      if (!this.user || localStorage.getItem(PENDING_LOGOUT_KEY)) return false;
      const owner = this.user.id,
        avatarRevision = this.avatarRevision;
      const pending = refreshRequests.get(this);
      if (pending?.owner === owner) return pending.promise;
      const entry = { owner, promise: null };
      entry.promise = (async () => {
        try {
          const data = await authApi.refresh();
          if (this.user?.id !== owner || localStorage.getItem(PENDING_LOGOUT_KEY)) return false;
          // Cookie 可能已在另一标签页切换账号；必须先核对身份，再接受凭证。
          if (data.user?.id !== owner) {
            this.clear();
            return false;
          }
          this.accessToken = data.access_token;
          this.mergeServerUser(data.user, avatarRevision);
          this.persist();
          return true;
        } catch (e) {
          // 限流与网络错误可以重试；只有明确的认证失效才登出。
          if (this.user?.id === owner && [401, 403].includes(e.status)) this.clear();
          return false;
        } finally {
          if (refreshRequests.get(this) === entry) refreshRequests.delete(this);
        }
      })();
      refreshRequests.set(this, entry);
      return entry.promise;
    },
    updateAvatar(key) {
      if (!this.user) return;
      this.avatarRevision += 1;
      this.setUser({ ...this.user, avatar_key: key });
    },
    mergeServerUser(user, avatarRevision) {
      if (!user || this.user?.id !== user.id) return;
      const value =
        avatarRevision === this.avatarRevision
          ? user
          : { ...user, avatar_key: this.user.avatar_key };
      this.setUser(value);
    },
    async fetchMe() {
      const owner = this.user?.id,
        revision = this.avatarRevision;
      const data = await authApi.me();
      if (this.user?.id === owner) this.mergeServerUser(data, revision);
      return this.user;
    },
    async retryPendingLogout() {
      if (!localStorage.getItem(PENDING_LOGOUT_KEY)) return;
      try {
        await authApi.logout({ pendingOnly: true });
      } catch {
        // Keep the marker for the next reconnect or startup.
      }
    },
    async logout() {
      const sync = await import('../sync/engine');
      await sync.pauseSyncForAccountSwitch();
      try {
        localStorage.setItem(PENDING_LOGOUT_KEY, '1');
        try {
          const { groupApi } = await import('../api');
          const { presenceDeviceId } = await import('../utils/presence');
          await groupApi
            ?.presence?.({ device_id: presenceDeviceId(), status: 'offline' })
            ?.catch(() => {});
        } catch {
          /* 忽略在线状态上报失败 */
        }
        await this.retryPendingLogout();
        this.clear();
        await afterLogout();
      } finally {
        sync.resumeSyncAfterAccountSwitch();
      }
    },
    clear() {
      this.accessToken = '';
      this.user = null;
      localStorage.removeItem(SESSION_KEY);
      localStorage.removeItem(LEGACY_KEY);
    },
  },
});
