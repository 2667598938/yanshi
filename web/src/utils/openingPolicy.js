function browserSessionStorage() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function createOpeningGate() {
  const memory = new Set();
  return (settings, storage = browserSessionStorage()) => {
    if (!settings.enabled || settings.policy === 'off') return false;
    if (settings.policy === 'always') return true;
    const key = settings.storageKey;
    if (memory.has(key)) return false;
    memory.add(key);
    try {
      if (storage?.getItem(key)) return false;
      storage?.setItem(key, 'seen');
    } catch {
      /* 存储受限时，同一页面生命周期仍只播放一次。 */
    }
    return true;
  };
}

export const claimBrandOpening = createOpeningGate();
