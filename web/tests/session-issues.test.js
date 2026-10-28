// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {it,expect,vi} from 'vitest'
import SessionIssues from '../src/components/SessionIssues.vue'
import {timerApi} from '../src/api'
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>({isLoggedIn:true,user:{id:8}})}))
vi.mock('../src/api',()=>({timerApi:{conflicts:vi.fn(),resolve:vi.fn()},syncApi:{commands:vi.fn()}}))
vi.mock('../src/sync/engine',()=>({waitForSync:vi.fn().mockResolvedValue(),syncNow:vi.fn().mockResolvedValue()}))
const items=[
 {id:'a',revision:2,started_at:1000,ended_at:3000,seconds:1200},
 {id:'b',revision:1,started_at:2000,ended_at:4000,seconds:1200},
 {id:'c',revision:3,started_at:3500,ended_at:5500,seconds:1200},
]
it('链式重叠可保留互不重叠的两条，只删除勾选放弃的桥接记录',async()=>{
 const group={id:'overlap',items}
 timerApi.conflicts.mockResolvedValueOnce({groups:[group],invalid:[]}).mockResolvedValue({groups:[],invalid:[]})
 timerApi.resolve.mockResolvedValue({})
 const confirm=vi.fn().mockReturnValue(false);vi.stubGlobal('confirm',confirm)
 const wrapper=mount(SessionIssues);await flushPromises()
 // 默认全部不放弃，不能提交
 const button=()=>wrapper.findAll('button').find(b=>b.text().startsWith('确认放弃'))
 expect(button().attributes('disabled')).toBeDefined()
 // 只放弃 B，A+C 互不重叠
 await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
 await wrapper.vm.$nextTick()
 expect(button().text()).toContain('确认放弃 1 条，保留 2 条')
 await button().trigger('click');expect(timerApi.resolve).not.toHaveBeenCalled()
 confirm.mockReturnValue(true);await button().trigger('click');await flushPromises()
 expect(timerApi.resolve).toHaveBeenCalledExactlyOnceWith({
  group_id:'overlap',keep_ids:['a','c'],versions:{a:2,b:1,c:3},confirmed:true,
 })
 wrapper.unmount()
})
it('放弃 B 后若保留的 A+B 仍重叠则阻止提交',async()=>{
 const group={id:'overlap',items}
 timerApi.conflicts.mockResolvedValueOnce({groups:[group],invalid:[]}).mockResolvedValue({groups:[],invalid:[]})
 const wrapper=mount(SessionIssues);await flushPromises()
 await wrapper.findAll('input[type="checkbox"]')[2].setValue(true)
 await wrapper.vm.$nextTick()
 expect(wrapper.text()).toContain('仍互相重叠')
 expect(wrapper.findAll('button').find(b=>b.text().startsWith('确认放弃')).attributes('disabled')).toBeDefined()
 wrapper.unmount()
})
