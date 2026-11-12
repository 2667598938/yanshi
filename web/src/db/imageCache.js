import { localAccountScope } from './index';
export const IMAGE_CACHE_LIMIT = 100 * 1024 * 1024;
const pending = new WeakMap();
let persistenceRequested = false;
export async function requestPersistentStorage() {
  if (persistenceRequested) return false;
  persistenceRequested = true;
  try {
    return (await navigator.storage?.persist?.()) || false;
  } catch {
    return false;
  }
}
export async function cacheImage(
  key,
  blob,
  scope = localAccountScope(),
  limit = IMAGE_CACHE_LIMIT,
) {
  if (!scope.isCurrent() || !key || !(blob instanceof Blob) || blob.size > limit) return;
  try {
    await scope.db.transaction('rw', scope.db.imageCache, async () => {
      if (!scope.isCurrent()) return;
      const rows = await scope.db.imageCache.orderBy('lastAccessedAt').toArray();
      let size =
        rows.filter((row) => row.key !== key).reduce((sum, row) => sum + row.size, 0) + blob.size;
      for (const row of rows) {
        if (size <= limit) break;
        if (row.key !== key) {
          await scope.db.imageCache.delete(row.key);
          size -= row.size;
        }
      }
      await scope.db.imageCache.put({ key, blob, size: blob.size, lastAccessedAt: Date.now() });
    });
    void requestPersistentStorage();
  } catch {
    /* Cache failure must not discard a successfully uploaded image. */
  }
}
export async function resolveCachedImage(key, download) {
  const scope = localAccountScope();
  try {
    const row = await scope.db.imageCache.get(key);
    if (!scope.isCurrent()) return null;
    if (row?.blob) {
      await scope.db.imageCache.update(key, { lastAccessedAt: Date.now() }).catch(() => {});
      return scope.isCurrent() ? row.blob : null;
    }
  } catch {
    /* Unavailable cache can fall back to the authenticated server. */
  }
  if (!scope.isCurrent()) return null;
  let requests = pending.get(scope.db);
  if (!requests) {
    requests = new Map();
    pending.set(scope.db, requests);
  }
  if (!requests.has(key))
    requests.set(
      key,
      (async () => {
        const blob = await download();
        if (!scope.isCurrent()) return null;
        await cacheImage(key, blob, scope);
        return scope.isCurrent() ? blob : null;
      })().finally(() => requests.delete(key)),
    );
  return requests.get(key);
}
