import { it, expect } from 'vitest';
import { authorizeRoute } from '../src/router/access';
it.each(['/', '/me', '/focus', '/tasks', '/rooms', '/ai', '/login'])(
  '主管理员访问%s时只进入后台',
  (path) => {
    expect(
      authorizeRoute(
        { path, fullPath: path, meta: {} },
        { isLoggedIn: true, isAdmin: true, isSuperAdmin: true },
      ),
    ).toEqual({ path: '/admin', replace: true });
  },
);
it('主管理员可使用后台和协议，普通管理员仍可使用学习页', () => {
  expect(
    authorizeRoute(
      { path: '/admin', meta: { requiresAdmin: true } },
      { isLoggedIn: true, isAdmin: true, isSuperAdmin: true },
    ),
  ).toBe(true);
  expect(
    authorizeRoute(
      { path: '/disclaimer', meta: {} },
      { isLoggedIn: true, isAdmin: true, isSuperAdmin: true },
    ),
  ).toBe(true);
  expect(
    authorizeRoute(
      { path: '/', meta: {} },
      { isLoggedIn: true, isAdmin: true, isSuperAdmin: false },
    ),
  ).toBe(true);
});
