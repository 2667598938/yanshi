import { it, expect, vi } from 'vitest';
import { useAuthStore } from '../src/stores/auth';
import { authApi } from '../src/api';
vi.mock('../src/api', () => ({ authApi: { me: vi.fn(), refresh: vi.fn() } }));
it.each(['fetchMe', 'tryRefresh'])('%s 的旧响应不能覆盖刚上传的新头像', async (action) => {
  const auth = useAuthStore();
  auth.user = { id: 8, nickname: '同学', avatar_key: 'old' };
  let resolve;
  authApi[action === 'fetchMe' ? 'me' : 'refresh'].mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const request = auth[action]();
  auth.updateAvatar('new-upload');
  const user = { id: 8, nickname: '同学', avatar_key: 'old' };
  resolve(action === 'fetchMe' ? user : { access_token: 'refreshed', user });
  await request;
  expect(auth.user.avatar_key).toBe('new-upload');
});
it('续期返回其他账号时不能把其凭证写进当前账号', async () => {
  const auth = useAuthStore();
  auth.user = { id: 8, nickname: 'A' };
  auth.accessToken = 'token-A';
  authApi.refresh.mockResolvedValueOnce({
    access_token: 'token-B',
    user: { id: 9, nickname: 'B' },
  });
  expect(await auth.tryRefresh()).toBe(false);
  expect(auth.accessToken).toBe('');
  expect(auth.user).toBeNull();
});
it('同一页面并发续期只发送一次请求', async () => {
  const auth = useAuthStore();
  auth.user = { id: 8, nickname: 'A' };
  let resolve;
  authApi.refresh.mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const first = auth.tryRefresh(),
    second = auth.tryRefresh();
  expect(authApi.refresh).toHaveBeenCalledTimes(1);
  resolve({ access_token: 'refreshed', user: { id: 8, nickname: 'A' } });
  expect(await first).toBe(true);
  expect(await second).toBe(true);
});
it('续期限流保留当前账号，允许稍后重试', async () => {
  const auth = useAuthStore();
  auth.user = { id: 8, nickname: 'A' };
  auth.accessToken = 'token-A';
  authApi.refresh.mockRejectedValueOnce(Object.assign(new Error('稍后重试'), { status: 429 }));
  expect(await auth.tryRefresh()).toBe(false);
  expect(auth.user.id).toBe(8);
  expect(auth.accessToken).toBe('token-A');
});
it('续期途中退出，旧响应不能恢复已退出账号', async () => {
  const auth = useAuthStore();
  auth.user = { id: 8, nickname: 'A' };
  let resolve;
  authApi.refresh.mockImplementationOnce(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const request = auth.tryRefresh();
  auth.clear();
  resolve({ access_token: 'stale', user: { id: 8, nickname: 'A' } });
  expect(await request).toBe(false);
  expect(auth.accessToken).toBe('');
  expect(auth.user).toBeNull();
});
