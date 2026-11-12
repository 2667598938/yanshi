let anchor = null;

export function calibrateClock(serverTime) {
  if (!Number.isFinite(serverTime) || serverTime <= 0) return;
  anchor = { serverTime, monotonic: performance.now() };
  localStorage.setItem('yanshi:clock-offset', String(serverTime - Date.now()));
}

export function clockNow() {
  if (anchor) return anchor.serverTime + performance.now() - anchor.monotonic;
  const offset = Number(localStorage.getItem('yanshi:clock-offset') || 0);
  return Date.now() + (Number.isFinite(offset) ? offset : 0);
}

export function resetClockAnchor() {
  anchor = null;
}
