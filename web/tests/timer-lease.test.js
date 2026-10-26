// @vitest-environment happy-dom
import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import {useTimerStore} from '../src/stores/timer'
import {timerApi} from '../src/api'
import {db,currentKey} from '../src/db'
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>({isLoggedIn:true,user:{id:7}})}))
vi.mock('../src/api',()=>({timerApi:{start:vi.fn(),release:vi.fn()}}))
vi.mock('../src/sync/engine',()=>({enqueueRecord:vi.fn(),enqueueDelete:vi.fn()}))
let timer
beforeEach(async()=>{await db.open();timer=useTimerStore();timerApi.start.mockReset()})
afterEach(async()=>{timer.current=null;timer.rest=null;timer.stopTicker();await db.delete()})
it('等待服务端取得全局主计时后才创建本机当前计时',async()=>{
 let done;timerApi.start.mockImplementation(()=>new Promise(resolve=>{done=resolve}))
 const request=timer.start({subjectId:'math'});expect(timer.current).toBeNull();expect(timer.claiming).toBe(true)
 done({session_id:'owned',device_id:'desktop'});expect(await request).toBe(true)
 expect(timer.current.startedAt).toBeGreaterThanOrEqual(1767225600000)
 expect(JSON.parse(localStorage.getItem(currentKey())).id).toBe(timer.current.id)
})
it('其他设备占用时不偷偷开始本地计时',async()=>{
 timerApi.start.mockRejectedValue({status:409,message:'其他设备正在计时',data:{current:{session_id:'peer',device_id:'phone'}}})
 expect(await timer.start({subjectId:'math'})).toBe(false)
 expect(timer.current).toBeNull();expect(timer.remoteLease.session_id).toBe('peer');expect(timer.startError).toContain('其他设备')
})
it('纯网络故障仍支持离线计时，后续重叠由同步冲突处理',async()=>{
 timerApi.start.mockRejectedValue(new Error('offline'))
 expect(await timer.start({subjectId:'math'})).toBe(true)
 expect(timer.current.onlineLease).not.toBe(true)
})
