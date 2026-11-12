import { it, expect, vi } from 'vitest';
import { roomApi } from '../src/api';
import { streamPost } from '../src/api/http';
vi.mock('../src/stores/auth', () => ({
  useAuthStore: () => ({ accessToken: 'test-access', canRefresh: false }),
}));

it('房间编辑能实际发送PATCH请求', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue(
      new Response(JSON.stringify({ code: 0, data: { name: 'new room' } }), { status: 200 }),
    );
  vi.stubGlobal('fetch', fetch);
  expect(await roomApi.update(8, { name: 'new room' })).toEqual({ name: 'new room' });
  expect(fetch.mock.calls[0][1].method).toBe('PATCH');
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ name: 'new room' });
});

it('SSE没有完成事件时不会把半截回答当成成功；CRLF事件正常解析', async () => {
  const callback = vi.fn();
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(new Response('data: {"type":"delta","text":"partial"}\n\n'))
      .mockResolvedValueOnce(
        new Response('data: {"type":"delta","text":"answer"}\r\n\r\ndata: {"type":"done"}\r\n\r\n'),
      ),
  );
  await expect(streamPost('/ai/chat/stream', {}, callback)).rejects.toThrow('提前结束');
  await expect(streamPost('/ai/chat/stream', {}, callback)).resolves.toBeUndefined();
  expect(callback).toHaveBeenLastCalledWith({ type: 'done' });
});
