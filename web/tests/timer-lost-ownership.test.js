// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'
import { expect, it, vi } from 'vitest'
import { useTimerOwnership } from '../src/composables/useTimerOwnership'
import { timerApi } from '../src/api'
const state=vi.hoisted(()=>({timer:null}))
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>({isLoggedIn:true,user:{id:1}})}))
vi.mock('../src/stores/timer',()=>({useTimerStore:()=>state.timer}))
vi.mock('../src/api',()=>({timerApi:{start:vi.fn(),heartbeat:vi.fn(),current:vi.fn().mockResolvedValue(null)}}))
it('已失权的旧设备只读取主设备状态，不自动重新抢占租约',async()=>{
 state.timer=reactive({leaseLost:true,current:{id:'old-round',startedAt:Date.now(),deviceId:'desktop',paused:true,leaseLost:true},saveCurrent:vi.fn()})
 const Host=defineComponent({setup(){useTimerOwnership();return()=>null}})
 const wrapper=mount(Host)
 try{
  await flushPromises()
  expect(timerApi.heartbeat).not.toHaveBeenCalled()
  expect(timerApi.start).not.toHaveBeenCalled()
  expect(timerApi.current).toHaveBeenCalled()
  expect(state.timer.leaseLost).toBe(true)
 }finally{wrapper.unmount()}
})
