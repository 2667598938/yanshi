// @vitest-environment happy-dom
import { it, expect } from 'vitest';
import { presenceDeviceId } from '../src/utils/presence';
it('复制标签页的sessionStorage不应让两个页面共用在场ID', () => {
  const key = Symbol.for('yanshi.documentPresenceId');
  sessionStorage.setItem('yanshi:device', 'copied-from-opener');
  delete globalThis[key];
  const first = presenceDeviceId();
  expect(presenceDeviceId()).toBe(first);
  // A separate document has a separate global object but may inherit sessionStorage.
  delete globalThis[key];
  const second = presenceDeviceId();
  expect(second).not.toBe(first);
  expect(second).not.toBe('copied-from-opener');
  delete globalThis[key];
});
