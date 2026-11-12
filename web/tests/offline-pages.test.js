import vm from 'node:vm';
import { expect, it, vi } from 'vitest';
import { serviceWorkerSource } from '../build/offline';

function worker() {
  const events = {};
  const cache = { addAll: vi.fn().mockResolvedValue(undefined), put: vi.fn(), match: vi.fn() };
  const caches = {
    open: vi.fn().mockResolvedValue(cache),
    keys: vi.fn().mockResolvedValue([]),
    delete: vi.fn(),
  };
  const fetch = vi.fn();
  const self = {
    addEventListener: (name, handler) => {
      events[name] = handler;
    },
    location: { origin: 'https://test.example' },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn() },
  };
  vm.runInNewContext(serviceWorkerSource(['/assets/app.js'], 'test-version'), {
    self,
    caches,
    fetch,
    URL,
  });
  return { events, cache, caches, fetch };
}

it('API、上传请求和外部附件从不进入离线静态缓存', () => {
  const { events, caches } = worker();
  for (const request of [
    { url: 'https://test.example/api/v1/sync/records', method: 'GET' },
    { url: 'https://test.example/api/v1/attachments/image', method: 'POST' },
    { url: 'https://storage.example/private.jpg', method: 'GET' },
    { url: 'https://test.example/health', method: 'GET' },
  ]) {
    const respondWith = vi.fn();
    events.fetch({ request, respondWith });
    expect(respondWith).not.toHaveBeenCalled();
  }
  expect(caches.open).not.toHaveBeenCalled();
});

it('断网导航使用已预缓存的应用壳，JS资源可独立从缓存恢复', async () => {
  const { events, cache, fetch } = worker();
  fetch.mockRejectedValue(new Error('offline'));
  const response = { status: 200, body: 'cached page' };
  cache.match.mockResolvedValue(response);
  let result;
  events.fetch({
    request: { method: 'GET', url: 'https://test.example/tasks', mode: 'navigate' },
    respondWith: (promise) => {
      result = promise;
    },
  });
  expect(await result).toBe(response);
  expect(cache.match).toHaveBeenCalledWith('/index.html');
  events.fetch({
    request: { method: 'GET', url: 'https://test.example/assets/app.js', mode: 'cors' },
    respondWith: (promise) => {
      result = promise;
    },
  });
  expect(await result).toBe(response);
});

it('安装预缓存静态资源；激活只清理自己的旧缓存，保留上一版本', async () => {
  const { events, cache, caches } = worker();
  let job;
  events.install({
    waitUntil: (promise) => {
      job = promise;
    },
  });
  await job;
  expect(cache.addAll).toHaveBeenCalledWith(['/index.html', '/assets/app.js']);
  caches.keys.mockResolvedValue([
    'other-app',
    'yanshi-static-old1',
    'yanshi-static-old2',
    'yanshi-static-test-version',
  ]);
  events.activate({
    waitUntil: (promise) => {
      job = promise;
    },
  });
  await job;
  expect(caches.delete).toHaveBeenCalledWith('yanshi-static-old1');
  expect(caches.delete).not.toHaveBeenCalledWith('other-app');
  expect(caches.delete).not.toHaveBeenCalledWith('yanshi-static-old2');
});

it('新版在线 HTML 不覆盖旧 worker 的完整离线页面', async () => {
  const { events, cache, fetch } = worker();
  const onlinePage = { ok: true, body: 'new page with new bundle', clone: vi.fn() };
  const offlinePage = { ok: true, body: 'old page with cached bundle' };
  fetch.mockResolvedValueOnce(onlinePage).mockRejectedValueOnce(new Error('offline'));
  cache.match.mockResolvedValue(offlinePage);
  const navigate = () => {
    let result;
    events.fetch({
      request: { url: 'https://test.example/tasks', method: 'GET', mode: 'navigate' },
      respondWith: (promise) => {
        result = promise;
      },
    });
    return result;
  };
  expect(await navigate()).toBe(onlinePage);
  expect(cache.put).not.toHaveBeenCalled();
  expect(await navigate()).toBe(offlinePage);
});

it('新版 worker 接管后，已打开的旧页面可以从上一版本加载资源', async () => {
  const { events, caches, fetch } = worker();
  const response = { status: 200, body: 'previous route bundle' };
  const oldCache = { match: vi.fn().mockResolvedValue(response) };
  caches.keys.mockResolvedValue([
    'other-app',
    'yanshi-static-previous',
    'yanshi-static-test-version',
  ]);
  caches.open.mockResolvedValueOnce(oldCache);
  const request = { url: 'https://test.example/assets/old-route.js', method: 'GET', mode: 'cors' };
  let result;
  events.fetch({
    request,
    respondWith: (promise) => {
      result = promise;
    },
  });
  expect(await result).toBe(response);
  expect(caches.open).toHaveBeenCalledExactlyOnceWith('yanshi-static-previous');
  expect(oldCache.match).toHaveBeenCalledWith(request);
  expect(fetch).not.toHaveBeenCalled();
});
