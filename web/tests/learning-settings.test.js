// @vitest-environment happy-dom
import { expect, it, vi } from 'vitest';

vi.mock('../src/db', () => ({ localAccountScope: vi.fn() }));
vi.mock('../src/sync/engine', () => ({ writeRecord: vi.fn() }));

import {
  DEFAULT_LEARNING_SETTINGS,
  validateLearningSettings,
} from '../src/stores/learningSettings';

it('个人梦校弹幕最多 80 字，空白内容恢复公共弹幕', () => {
  expect(
    validateLearningSettings({ ...DEFAULT_LEARNING_SETTINGS, bulletText: '每天进步一点点' })
      .bulletText,
  ).toBe('每天进步一点点');
  expect(
    validateLearningSettings({ ...DEFAULT_LEARNING_SETTINGS, bulletText: '   ' }).bulletText,
  ).toBe('');
  expect(
    validateLearningSettings({ ...DEFAULT_LEARNING_SETTINGS, bulletText: '字'.repeat(80) })
      .bulletText,
  ).toHaveLength(80);
  expect(() =>
    validateLearningSettings({ ...DEFAULT_LEARNING_SETTINGS, bulletText: '字'.repeat(81) }),
  ).toThrow('弹幕最多 80 个字');
});
