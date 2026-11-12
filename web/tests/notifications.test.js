import { expect, it, vi } from 'vitest';
import { messageApi } from '../src/api';
import { useAuthStore } from '../src/stores/auth';
import { useNotificationsStore } from '../src/stores/notifications';

vi.mock('../src/api', () => ({ messageApi: { unread: vi.fn() } }));

it('换号和后到的旧请求不能覆盖当前账号的未读数；隐藏页面不轮询', async () => {
  const auth = useAuthStore();
  const store = useNotificationsStore();
  vi.stubGlobal('document', { visibilityState: 'visible' });
  auth.user = { id: 1 };
  let finishOld;
  messageApi.unread.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finishOld = resolve;
      }),
  );
  const old = store.refresh();
  auth.user = { id: 2 };
  messageApi.unread.mockResolvedValueOnce({ count: 3 });
  await store.refresh();
  finishOld({ count: 99 });
  await old;
  expect(store.unread).toBe(3);
  document.visibilityState = 'hidden';
  await store.refresh();
  expect(messageApi.unread).toHaveBeenCalledTimes(2);
  store.stop();
  expect(store.unread).toBe(0);
});
