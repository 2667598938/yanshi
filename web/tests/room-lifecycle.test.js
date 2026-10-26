// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { it, expect, vi } from 'vitest'
import RoomView from '../src/views/RoomView.vue'
import { roomApi } from '../src/api'
vi.mock('vue-router',()=>({useRoute:()=>({params:{id:'1'},name:'room-detail'}),useRouter:()=>({replace:vi.fn(),push:vi.fn(),back:vi.fn()})}))
vi.mock('../src/api',()=>({roomApi:{get:vi.fn()}}))
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>({user:{id:1},isAdmin:false})}))
vi.mock('../src/stores/timer',()=>({useTimerStore:()=>({current:null})}))
vi.mock('../src/stores/subjects',()=>({useSubjectsStore:()=>({byId:{}})}))
it('房间首屏请求在离开页面后返回，不重建轮询和心跳',async()=>{
 vi.useFakeTimers();let resolve
 roomApi.get.mockImplementation(()=>new Promise(r=>{resolve=r}))
 const spy=vi.spyOn(window,'addEventListener')
 const wrapper=mount(RoomView,{global:{stubs:{BlobImage:true}}})
 wrapper.unmount();const timers=vi.getTimerCount()
 resolve({room:{id:1,capacity:4},joined:true,members:[],messages:[]});await flushPromises()
 expect(vi.getTimerCount()).toBe(timers)
 expect(spy.mock.calls.filter(([name])=>name==='beforeunload')).toHaveLength(0)
 vi.restoreAllMocks();vi.useRealTimers()
})
