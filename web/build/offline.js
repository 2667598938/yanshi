import { createHash } from 'node:crypto'

export function serviceWorkerSource(files, version) {
  return `const PREFIX = 'yanshi-static-';
const CACHE = PREFIX + ${JSON.stringify(version)};
const ASSETS = ${JSON.stringify([...new Set(['/index.html', ...files])])};
self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = (await caches.keys()).filter((name) => name.startsWith(PREFIX));
    for (const name of names.filter((name) => name !== CACHE).slice(0, -1)) await caches.delete(name);
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/') || url.pathname === '/health') return;
  if (request.mode !== 'navigate' && !ASSETS.includes(url.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const response = await fetch(request);
      if (response.ok) await cache.put(request.mode === 'navigate' ? '/index.html' : request, response.clone());
      return response;
    } catch (error) {
      const cached = await cache.match(request.mode === 'navigate' ? '/index.html' : request);
      if (cached) return cached;
      throw error;
    }
  })());
});`
}

export function offlinePlugin() {
  return {
    name: 'yanshi-offline-static-pages',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const files = Object.keys(bundle).filter((name) => !name.endsWith('.map')).map((name) => '/' + name)
      const version = createHash('sha256').update(files.join('|')).digest('hex').slice(0, 16)
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: serviceWorkerSource(files, version) })
    },
  }
}
