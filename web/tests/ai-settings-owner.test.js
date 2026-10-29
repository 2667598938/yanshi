// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {it,expect,vi} from 'vitest'
import AiSettingsView from '../src/views/AiSettingsView.vue'
import {aiApi} from '../src/api'
vi.mock('vue-router',()=>({useRouter:()=>({push:vi.fn(),back:vi.fn()})}))
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>({isVip:false})}))
vi.mock('../src/composables/useToast',()=>({useToast:()=>({toast:vi.fn()})}))
vi.mock('../src/api',()=>({aiApi:{enabled:vi.fn(),key:vi.fn(),usage:vi.fn(),deleteKey:vi.fn()}}))
it('权限到期时仍能查看本人Key掩码并确认删除',async()=>{
 aiApi.enabled.mockResolvedValue({access:false})
 aiApi.key.mockResolvedValue({configured:true,key_mask:'sk-***1234',model:'owner-model'})
 aiApi.deleteKey.mockResolvedValue({configured:false})
 vi.stubGlobal('confirm',vi.fn().mockReturnValue(true))
 const wrapper=mount(AiSettingsView)
 await flushPromises()
 expect(wrapper.text()).toContain('sk-***1234')
 expect(aiApi.usage).not.toHaveBeenCalled()
 expect(wrapper.find('input[type="password"]').exists()).toBe(false)
 await wrapper.findAll('button').find(b=>b.text()==='删除我的Key').trigger('click')
 await flushPromises()
 expect(aiApi.deleteKey).toHaveBeenCalledOnce()
 expect(wrapper.text()).not.toContain('sk-***1234')
 wrapper.unmount()
})
