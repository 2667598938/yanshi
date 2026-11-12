// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import RoomsView from '../src/views/RoomsView.vue'
import { roomApi } from '../src/api'
const state=vi.hoisted(()=>({push:vi.fn()}))
vi.mock('vue-router',()=>({useRouter:()=>({push:state.push,back:vi.fn()})}))
vi.mock('../src/api',()=>({publicApi:{config:vi.fn().mockResolvedValue({features:['text_room']})},roomApi:{list:vi.fn(),create:vi.fn(),joinByCode:vi.fn()}}))
let wrapper
beforeEach(()=>{vi.clearAllMocks();vi.stubGlobal('confirm',vi.fn().mockReturnValue(false));roomApi.list.mockResolvedValue([]);roomApi.create.mockResolvedValue({id:7});roomApi.joinByCode.mockResolvedValue({room:{id:7}})})
afterEach(()=>{wrapper?.unmount();vi.unstubAllGlobals()})
it('默认私密创建好友房间，取消共享确认时不发送任何建房请求',async()=>{
 wrapper=mount(RoomsView);await flushPromises()
 await wrapper.get('.room-top-actions .btn-primary').trigger('click')
 await wrapper.get('input[placeholder="如：冲刺 408 小组"]').setValue('我的考研搭子')
 const create=wrapper.findAll('button').find(b=>b.text()==='创建并进入')
 await create.trigger('click');expect(roomApi.create).not.toHaveBeenCalled()
 confirm.mockReturnValue(true);await create.trigger('click');await flushPromises()
 expect(roomApi.create).toHaveBeenCalledExactlyOnceWith({name:'我的考研搭子',intro:'',visibility:'private',room_type:'text_room',capacity:50,accept_sharing:true})
 expect(confirm.mock.calls[0][0]).toContain('包含历史学习数据')
 expect(confirm.mock.calls[0][0]).toContain('AI 密钥和聊天')
})
it('凭码加入必须手动确认，取消时不会提交；列表不再显示四人限制',async()=>{
 roomApi.list.mockResolvedValue([{id:7,name:'朋友的房间',member_count:12,capacity:50,visibility:'public'}])
 wrapper=mount(RoomsView);await flushPromises()
 expect(wrapper.text()).toContain('50人上限');expect(wrapper.text()).not.toContain('/4')
 await wrapper.get('.room-top-actions .btn-outline').trigger('click')
 await wrapper.get('.code-input').setValue('ABC123')
 const join=wrapper.findAll('button').find(b=>b.text()==='加入')
 await join.trigger('click');expect(roomApi.joinByCode).not.toHaveBeenCalled()
 confirm.mockReturnValue(true);await join.trigger('click');await flushPromises()
 expect(roomApi.joinByCode).toHaveBeenCalledExactlyOnceWith('ABC123',true)
})
