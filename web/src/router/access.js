// 账号准入与页面离线能力分开：仅已登录账号可进入学习工作台。
export const PUBLIC_PAGES = new Set(['/login', '/disclaimer'])

export function authorizeRoute(to, auth) {
  const adminOnly = auth.isLoggedIn && (auth.isSuperAdmin ?? auth.isAdmin)
  if (adminOnly && to.path !== '/disclaimer' && !to.meta.requiresAdmin) return { path: '/admin', replace: true }
  if (PUBLIC_PAGES.has(to.path)) return true
  if (!auth.isLoggedIn) return { path: '/login', query: { redirect: to.fullPath }, replace: true }
  if (to.meta.requiresAdmin && !auth.isAdmin) return { path: '/me', replace: true }
  return true
}
