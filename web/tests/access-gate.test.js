// @vitest-environment happy-dom
import { createRouter, createMemoryHistory } from 'vue-router'
import { it, expect } from 'vitest'
import { routes } from '../src/router'
import { authorizeRoute } from '../src/router/access'
const stub = { template: '<div>页面</div>' }
function routerFor(auth) {
  const router = createRouter({ history: createMemoryHistory(), routes: routes.map(route => route.redirect ? route : { ...route, component: stub }) })
  router.beforeEach(to => authorizeRoute(to, auth))
  return router
}
const privateRoutes = routes.filter(route => !['/login', '/disclaimer'].includes(route.path) && !route.redirect)
it.each(privateRoutes.map(route => [route.path]))('未登录直接输入 %s 也必须回登录页', async path => {
  const router = routerFor({ isLoggedIn: false, isAdmin: false })
  const target = path.replace(':id', '1')
  await router.push(target)
  expect(router.currentRoute.value.path).toBe('/login')
  expect(router.currentRoute.value.query.redirect).toBe(target)
})
it.each(['/login', '/disclaimer'])('公共页面 %s 可在未登录时访问', async path => {
  const router = routerFor({ isLoggedIn: false })
  await router.push(path)
  expect(router.currentRoute.value.path).toBe(path)
})
it('已登录账号可进入学习页，普通成员仍不能进入管理页', async () => {
  const router = routerFor({ isLoggedIn: true, isAdmin: false })
  await router.push('/tasks'); expect(router.currentRoute.value.path).toBe('/tasks')
  await router.push('/admin'); expect(router.currentRoute.value.path).toBe('/me')
})
it('未登录保留完整目标与查询参数，不进入游客首页', async () => {
  const router = routerFor({ isLoggedIn: false })
  await router.push('/stats?view=month')
  expect(router.currentRoute.value.query.redirect).toBe('/stats?view=month')
})
