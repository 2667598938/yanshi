import vm from 'node:vm'
import { expect, it, vi } from 'vitest'
import { serviceWorkerSource } from '../build/offline'

function worker() {
  const events = {}
  const cache = { addAll: vi.fn().mockResolvedValue(undefined), put: vi.fn(), match: vi.fn() }
  const caches = { open: vi.fn().mockResolvedValue(cache), keys: vi.fn().mockResolvedValue([]), delete: vi.fn() }
  const fetch = vi.fn()
  const self = { addEventListener: (name, handler) => { events[name] = handler },
    location: { origin: 'https://test.example' }, skipWaiting: vi.fn(), clients: { claim: vi.fn() } }
  vm.runInNewContext(serviceWorkerSource(['/assets/app.js'], 'test-version'), { self, caches, fetch, URL })
  return { events, cache, caches, fetch }
}

it('API、上传请求和外部附件从不进入离线静态缓存', () => {
  const { events, caches } = worker()
  for (const request of [
    { url: 'https://test.example/api/v1/sync/records', method: 'GET' },
    { url: 'https://test.example/api/v1/attachments/image', method: 'POST' },
    { url: 'https://storage.example/private.jpg', method: 'GET' },
    { url: 'https://test.example/health', method: 'GET' },
  ]) {
    const respondWith = vi.fn()
    events.fetch({ request, respondWith })
    expect(respondWith).not.toHaveBeenCalled()
  }
  expect(caches.open).not.toHaveBeenCalled()
})

it('断网导航使用已预缓存的应用壳，JS资源可独立从缓存恢复', async () => {
  const { events, cache, fetch } = worker()
  fetch.mockRejectedValue(new Error('offline'))
  const response = { status: 200, body: 'cached page' }
  cache.match.mockResolvedValue(response)
  let result
  events.fetch({ request: { method: 'GET', url: 'https://test.example/tasks', mode: 'navigate' },
    respondWith: (promise) => { result = promise } })
  expect(await result).toBe(response)
  expect(cache.match).toHaveBeenCalledWith('/index.html')
  events.fetch({ request: { method: 'GET', url: 'https://test.example/assets/app.js', mode: 'cors' },
    respondWith: (promise) => { result = promise } })
  expect(await result).toBe(response)
})

it('安装预缓存静态资源；激活只清理自己的旧缓存，保留上一版本', async () => {
  const { events, cache, caches } = worker()
  let job
  events.install({ waitUntil: (promise) => { job = promise } })
  await job
  expect(cache.addAll).toHaveBeenCalledWith(['/index.html', '/assets/app.js'])
  caches.keys.mockResolvedValue(['other-app', 'yanshi-static-old1', 'yanshi-static-old2', 'yanshi-static-test-version'])
  events.activate({ waitUntil: (promise) => { job = promise } })
  await job
  expect(caches.delete).toHaveBeenCalledWith('yanshi-static-old1')
  expect(caches.delete).not.toHaveBeenCalledWith('other-app')
  expect(caches.delete).not.toHaveBeenCalledWith('yanshi-static-old2')
})
