// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import GroupLearningView from '../src/views/GroupLearningView.vue'
import SchoolBullets from '../src/components/SchoolBullets.vue'
import { groupApi, inspirationApi } from '../src/api'
const state=vi.hoisted(()=>({auth:null,settings:null}))
vi.mock('vue-router',()=>({useRouter:()=>({back:vi.fn()})}))
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>state.auth}))
vi.mock('../src/stores/learningSettings',()=>({useLearningSettingsStore:()=>state.settings}))
vi.mock('../src/api',()=>({roomApi:{list:vi.fn().mockResolvedValue([])},
 groupApi:{members:vi.fn(),learning:vi.fn(),changes:vi.fn()},
 inspirationApi:{bullets:vi.fn()}
}))
let wrapper
beforeEach(()=>{
 vi.useFakeTimers();vi.clearAllMocks()
 state.auth=reactive({user:{id:1}})
 state.settings=reactive({value:{bulletEnabled:true,focusMin:25},load:vi.fn().mockResolvedValue(),save:vi.fn(async value=>{state.settings.value=value})})
 groupApi.members.mockResolvedValue([{id:2,nickname:'组员',is_private_mode:false}])
 groupApi.learning.mockResolvedValue({items:[{id:'task',type:'task',title:'原任务'}],cursor:4,next:null})
 groupApi.changes.mockResolvedValue({items:[],cursor:4,has_more:false})
 inspirationApi.bullets.mockResolvedValue([{id:1,content:'管理员的寄语'}])
})
afterEach(()=>{wrapper?.unmount();wrapper=null;vi.useRealTimers()})
async function openGroup(){
 wrapper=mount(GroupLearningView,{global:{stubs:{RouterLink:true,BlobImage:true}}})
 await flushPromises()
 await wrapper.findAll('button').find(b=>b.text().includes('组员')).trigger('click')
 await flushPromises()
}
it('首次快照后只请求增量，删除不残留，隐私切换立即清空',async()=>{
 await openGroup();expect(wrapper.text()).toContain('原任务')
 groupApi.changes.mockResolvedValue({items:[{id:'task',record:null},{id:'new',record:{id:'new',type:'task',title:'新任务'}}],cursor:7,has_more:false})
 await vi.advanceTimersByTimeAsync(5000);await flushPromises()
 expect(groupApi.learning).toHaveBeenCalledTimes(1)
 expect(groupApi.changes).toHaveBeenLastCalledWith(2,4,null)
 expect(wrapper.text()).toContain('新任务');expect(wrapper.text()).not.toContain('原任务')
 groupApi.members.mockResolvedValue([{id:2,nickname:'组员',is_private_mode:true}])
 await vi.advanceTimersByTimeAsync(5000);await flushPromises()
 expect(wrapper.text()).not.toContain('新任务');expect(wrapper.text()).toContain('隐私中')
 groupApi.members.mockResolvedValue([{id:2,nickname:'组员',is_private_mode:false}])
 await vi.advanceTimersByTimeAsync(5000);await flushPromises()
 expect(groupApi.learning).toHaveBeenCalledTimes(2)
})
it('分页期间保留首页游标并补拉变更，含空的私人变更页',async()=>{
 groupApi.learning.mockResolvedValueOnce({items:[{id:'task',type:'task',title:'原任务'}],next:'task',cursor:10})
  .mockResolvedValueOnce({items:[],next:null,cursor:15})
 groupApi.changes.mockResolvedValueOnce({items:[],cursor:210,has_more:true})
  .mockResolvedValueOnce({items:[{id:'task',record:null}],cursor:211,has_more:false})
 await openGroup()
 expect(groupApi.changes.mock.calls).toEqual([[2,10,null],[2,210,null]])
 expect(wrapper.text()).not.toContain('原任务')
})
it('换账号后在途共享响应不能回填旧数据',async()=>{
 let resolve
 groupApi.learning.mockImplementation(()=>new Promise(r=>{resolve=r}))
 await openGroup()
 state.auth.user={id:3};await flushPromises()
 resolve({items:[{id:'old',type:'task',title:'旧账号秘密'}],next:null,cursor:1});await flushPromises()
 expect(wrapper.text()).not.toContain('旧账号秘密')
 expect(groupApi.changes).not.toHaveBeenCalled()
})
it('弹幕只读文案，关闭持久化到个人设置，切账号清掉旧文案',async()=>{
 wrapper=mount(SchoolBullets);await flushPromises()
 expect(wrapper.text()).toContain('管理员的寄语')
 await wrapper.get('button').trigger('click');await flushPromises()
 expect(state.settings.save).toHaveBeenCalledWith({bulletEnabled:false,focusMin:25})
 expect(wrapper.find('.bullet-window').exists()).toBe(false)
 inspirationApi.bullets.mockResolvedValue([])
 state.auth.user={id:2};state.settings.value.bulletEnabled=true;await flushPromises()
 expect(wrapper.text()).not.toContain('管理员的寄语')
 expect(wrapper.find('.bullet').exists()).toBe(true)
})
it('减少动态偏好下文案静态显示',async()=>{
 const original=window.matchMedia
 window.matchMedia=()=>({matches:true,addEventListener:vi.fn(),removeEventListener:vi.fn()})
 wrapper=mount(SchoolBullets);await flushPromises()
 expect(wrapper.get('.bullet').classes()).toContain('still')
 await vi.advanceTimersByTimeAsync(14000)
 expect(wrapper.get('.bullet').text()).toBe('管理员的寄语')
 window.matchMedia=original
})
