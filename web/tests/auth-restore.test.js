import { it, expect, vi } from 'vitest'
import { useAuthStore } from '../src/stores/auth'
import { authApi } from '../src/api'
vi.mock('../src/api', () => ({ authApi: { refresh: vi.fn() } }))
it('会话明确过期时清除缓存身份，不能以昵称缓存绕过登录页', async () => {
  const auth = useAuthStore()
  auth.user = { id: 7, nickname: '缓存账号' }; auth.persist()
  authApi.refresh.mockRejectedValueOnce({ status: 401 })
  expect(await auth.restore()).toBe(false)
  expect(auth.isLoggedIn).toBe(false)
  expect(localStorage.getItem('yanshi:session')).toBeNull()
})
it('已登录账号断网时保留本人离线身份及学习能力', async () => {
  const auth = useAuthStore(); auth.user = { id: 7 }
  authApi.refresh.mockRejectedValueOnce(new TypeError('offline'))
  expect(await auth.restore()).toBe(false)
  expect(auth.user.id).toBe(7)
})
it('没有本机用户缓存但Cookie有效时，先恢复真实账号再判断路由', async () => {
  const auth = useAuthStore(); auth.user = null
  authApi.refresh.mockResolvedValueOnce({ access_token: 'test-access', user: { id: 9, nickname: '恢复账号' } })
  expect(await auth.restore()).toBe(true)
  expect(auth.isLoggedIn).toBe(true)
  expect(auth.user.id).toBe(9)
})
