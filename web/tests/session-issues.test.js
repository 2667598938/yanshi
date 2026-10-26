// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {it,expect,vi} from 'vitest'
import SessionIssues from '../src/components/SessionIssues.vue'
import {timerApi} from '../src/api'
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>({isLoggedIn:true,user:{id:8}})}))
vi.mock('../src/api',()=>({timerApi:{conflicts:vi.fn(),resolve:vi.fn()},syncApi:{commands:vi.fn()}}))
vi.mock('../src/sync/engine',()=>({waitForSync:vi.fn().mockResolvedValue(),syncNow:vi.fn().mockResolvedValue()}))
it('加载重叠记录不会删除；必须单选并确认后才裁决',async()=>{
 const group={id:'overlap',items:[{id:'a',revision:2,started_at:1767225600000,ended_at:1767227100000,seconds:1500},{id:'b',revision:1,started_at:1767225600000,ended_at:1767227100000,seconds:1500}]}
 timerApi.conflicts.mockResolvedValueOnce({groups:[group],invalid:[]}).mockResolvedValue({groups:[],invalid:[]})
 timerApi.resolve.mockResolvedValue({})
 const confirm=vi.fn().mockReturnValue(false);vi.stubGlobal('confirm',confirm)
 const wrapper=mount(SessionIssues);await flushPromises()
 expect(timerApi.resolve).not.toHaveBeenCalled()
 await wrapper.findAll('input[type="radio"]')[0].setValue(true)
 const button=wrapper.findAll('button').find(b=>b.text()==='确认仅保留所选，删除其余')
 await button.trigger('click');expect(timerApi.resolve).not.toHaveBeenCalled()
 confirm.mockReturnValue(true);await button.trigger('click');await flushPromises()
 expect(timerApi.resolve).toHaveBeenCalledExactlyOnceWith({group_id:'overlap',keep_id:'a',versions:{a:2,b:1},confirmed:true})
 wrapper.unmount()
})
