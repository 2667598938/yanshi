import {beforeEach,it,expect,vi} from 'vitest'
import {http,fetchBlob} from '../src/api/http'
import {authApi} from '../src/api'
import {PENDING_LOGOUT_KEY} from '../src/utils/pendingLogout'
const auth=vi.hoisted(()=>({user:{id:1},accessToken:'old-token',canRefresh:true,tryRefresh:vi.fn()}))
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>auth}))
beforeEach(()=>{auth.user={id:1};auth.accessToken='old-token';auth.tryRefresh.mockReset()})
it('旧请求收到401前换号，不使用新账号身份重试写请求',async()=>{
 let done;const fetch=vi.fn().mockImplementation(()=>new Promise(resolve=>{done=resolve}));vi.stubGlobal('fetch',fetch)
 const pending=http.post('/timer/resolve',{keep_id:'old-record'})
 auth.user={id:2};auth.accessToken='new-token';done(new Response('{}',{status:401}))
 await expect(pending).rejects.toThrow('账号已切换')
 expect(fetch).toHaveBeenCalledOnce();expect(auth.tryRefresh).not.toHaveBeenCalled()
})
it('刷新等待期间换号，也不重放旧操作',async()=>{
 let done;auth.tryRefresh.mockImplementation(()=>new Promise(resolve=>{done=resolve}))
 const fetch=vi.fn().mockResolvedValue(new Response('{}',{status:401}));vi.stubGlobal('fetch',fetch)
 const pending=http.post('/timer/start',{session_id:'old-session'})
 for(let i=0;i<10&&!done;i++)await new Promise(resolve=>setTimeout(resolve,0))
 expect(done).toBeTypeOf('function');auth.user={id:2};done(true)
 await expect(pending).rejects.toThrow('账号已切换');expect(fetch).toHaveBeenCalledOnce()
})
it('私图请求不会把旧账号响应交给新账号页面',async()=>{
 let done;vi.stubGlobal('fetch',vi.fn().mockImplementation(()=>new Promise(resolve=>{done=resolve})))
 const pending=fetchBlob('/api/v1/attachments/view?key=private');auth.user={id:2};done(new Response('private-bytes'))
 await expect(pending).rejects.toThrow('账号已切换')
})
it('退出请求保留当前访问凭证，且失败时不在Cookie锁内重新续期',async()=>{
 const fetch=vi.fn().mockResolvedValue(new Response('{}',{status:401}));vi.stubGlobal('fetch',fetch)
 await expect(http.post('/auth/logout',{})).rejects.toMatchObject({status:401})
 expect(fetch).toHaveBeenCalledOnce();expect(auth.tryRefresh).not.toHaveBeenCalled()
 expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer old-token')
})

it('注销失败保留待办，重新登录成功后不发送过期的补注销请求', async () => {
  const fetch = vi.fn()
    .mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValueOnce(new Response(JSON.stringify({ code: 0, data: { access_token: 'new-token' } })))
  vi.stubGlobal('fetch', fetch)
  localStorage.setItem(PENDING_LOGOUT_KEY, '1')
  await expect(authApi.logout({ pendingOnly: true })).rejects.toThrow('offline')
  expect(localStorage.getItem(PENDING_LOGOUT_KEY)).toBe('1')
  await authApi.login('account@example.test', 'fixture-password')
  expect(localStorage.getItem(PENDING_LOGOUT_KEY)).toBeNull()
  await authApi.logout({ pendingOnly: true })
  expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/v1/auth/logout', '/api/v1/auth/login'])
})
