import { createHash } from 'node:crypto'

export function serviceWorkerSource(files, version, offlineShell = '/index.html') {
  return `const PREFIX = 'yanshi-static-';
const CACHE = PREFIX + ${JSON.stringify(version)};
const OFFLINE_SHELL = ${JSON.stringify(offlineShell)};
const ASSETS = ${JSON.stringify([...new Set([offlineShell, ...files])])};
async function matchPreviousAsset(request) {
  const names = await caches.keys();
  for (const name of names.reverse()) {
    if (!name.startsWith(PREFIX) || name === CACHE) continue;
    const match = await (await caches.open(name)).match(request);
    if (match) return match;
  }
}
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
  const navigate = request.mode === 'navigate';
  const currentAsset = ASSETS.includes(url.pathname);
  if (!navigate && !currentAsset && !url.pathname.startsWith('/assets/')) return;
  event.respondWith((async () => {
    if (!navigate && !currentAsset) {
      const previous = await matchPreviousAsset(request);
      return previous || fetch(request);
    }
    const cache = await caches.open(CACHE);
    try {
      const response = await fetch(request);
      if (response.ok && !navigate) await cache.put(request, response.clone());
      return response;
    } catch (error) {
      const cached = await cache.match(navigate ? OFFLINE_SHELL : request);
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
      const html = bundle['index.html']
      if (html?.type !== 'asset') this.error('Offline build requires index.html')
      const files = Object.keys(bundle).filter((name) => name !== 'index.html' && !name.endsWith('.map')).map((name) => '/' + name)
      const version = createHash('sha256').update(files.join('|')).update(html.source).digest('hex').slice(0, 16)
      const shellName = `assets/offline-${version}.html`
      this.emitFile({ type: 'asset', fileName: shellName, source: html.source })
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: serviceWorkerSource(files, version, '/' + shellName) })
    },
  }
}
