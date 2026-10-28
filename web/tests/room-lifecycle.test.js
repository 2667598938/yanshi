// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { it, expect, vi } from 'vitest'
import RoomView from '../src/views/RoomView.vue'
import { roomApi } from '../src/api'
vi.mock('vue-router',()=>({useRoute:()=>({params:{id:'1'},name:'room-detail'}),useRouter:()=>({replace:vi.fn(),push:vi.fn(),back:vi.fn()})}))
vi.mock('../src/api',()=>({roomApi:{get:vi.fn(),postMessage:vi.fn(),deleteMessage:vi.fn()}}))
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
it('留言先本地出现，发送失败回滚并还原输入',async()=>{
 roomApi.get.mockResolvedValue({room:{id:1,capacity:4,my_role:'member'},joined:true,members:[],ranking:{today:[],week:[],all:[]},messages:[]})
 let rejectPost
 roomApi.postMessage.mockImplementation(()=>new Promise((_,reject)=>{rejectPost=reject}))
 const wrapper=mount(RoomView,{global:{stubs:{BlobImage:true}}})
 await flushPromises()
 const input=wrapper.find('.msg-input input')
 await input.setValue('今晚一起冲')
 await wrapper.find('.msg-input button').trigger('click')
 expect(wrapper.findAll('.msg')).toHaveLength(1)
 expect(wrapper.text()).toContain('发送中…')
 rejectPost(new Error('网络异常'))
 await flushPromises()
 expect(wrapper.findAll('.msg')).toHaveLength(0)
 expect(input.element.value).toBe('今晚一起冲')
 wrapper.unmount()
})
