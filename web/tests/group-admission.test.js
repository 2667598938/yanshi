// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {it,expect,vi} from 'vitest'
import GroupAdmissionView from '../src/views/GroupAdmissionView.vue'
import {groupAdmissionApi} from '../src/api'
vi.mock('vue-router',()=>({useRouter:()=>({back:vi.fn()})}))
vi.mock('../src/api',()=>({groupAdmissionApi:{mine:vi.fn(),apply:vi.fn()}}))
it('入组前说明默认共享，取消确认不提交申请',async()=>{
 groupAdmissionApi.mine.mockResolvedValue({is_member:false,applications:[]})
 groupAdmissionApi.apply.mockResolvedValue({status:'pending'})
 const confirm=vi.fn().mockReturnValue(false);vi.stubGlobal('confirm',confirm)
 const wrapper=mount(GroupAdmissionView,{global:{stubs:{RouterLink:true}}});await flushPromises()
 await wrapper.get('input').setValue('group-code')
 const button=wrapper.findAll('button').find(b=>b.text()==='提交入组申请')
 await button.trigger('click');expect(groupAdmissionApi.apply).not.toHaveBeenCalled()
 confirm.mockReturnValue(true);await button.trigger('click');await flushPromises()
 expect(groupAdmissionApi.apply).toHaveBeenCalledExactlyOnceWith({code:'group-code',reason:''})
 expect(confirm.mock.calls[0][0]).toContain('不授予VIP或房间准入')
 wrapper.unmount()
})
