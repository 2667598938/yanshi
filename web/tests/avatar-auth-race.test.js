import {it,expect,vi} from 'vitest'
import {useAuthStore} from '../src/stores/auth'
import {authApi} from '../src/api'
vi.mock('../src/api',()=>({authApi:{me:vi.fn(),refresh:vi.fn()}}))
it.each(['fetchMe','tryRefresh'])('%s 的旧响应不能覆盖刚上传的新头像',async action=>{
 const auth=useAuthStore();auth.user={id:8,nickname:'同学',avatar_key:'old'}
 let resolve
 authApi[action==='fetchMe'?'me':'refresh'].mockImplementationOnce(()=>new Promise(done=>{resolve=done}))
 const request=auth[action]()
 auth.updateAvatar('new-upload')
 const user={id:8,nickname:'同学',avatar_key:'old'}
 resolve(action==='fetchMe'?user:{access_token:'refreshed',user})
 await request
 expect(auth.user.avatar_key).toBe('new-upload')
})
