// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {ref,reactive,nextTick} from 'vue'
import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import {useGroupPresence} from '../src/composables/useGroupPresence'
import GroupLearningView from '../src/views/GroupLearningView.vue'
const mocks=vi.hoisted(()=>({auth:null,timer:null,route:null,presence:vi.fn(),members:vi.fn()}))
vi.mock('vue-router',()=>({useRoute:()=>mocks.route,useRouter:()=>({back:vi.fn()})}))
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>mocks.auth}))
vi.mock('../src/stores/timer',()=>({useTimerStore:()=>mocks.timer}))
vi.mock('../src/stores/subjects',()=>({useSubjectsStore:()=>({byId:{math:{name:'数学'}}})}))
vi.mock('../src/api',()=>({groupApi:{presence:mocks.presence,members:mocks.members}}))
let wrapper
beforeEach(()=>{
 mocks.auth=reactive({user:{id:2},isLoggedIn:true,accessToken:'test'})
 mocks.timer=reactive({current:{subjectId:'math',startedAt:1000,mode:'timer'},isResting:false,isPaused:false})
 mocks.route=reactive({name:'room-detail',params:{id:2},fullPath:'/rooms/2'})
 mocks.presence.mockResolvedValue({});mocks.presence.mockClear()
 vi.spyOn(document,'visibilityState','get').mockReturnValue('visible')
})
afterEach(()=>{wrapper?.unmount();vi.restoreAllMocks()})
it('前台按设备上报实际房间，离开房间页面继续在线但清除位置',async()=>{
 wrapper=mount({setup(){useGroupPresence();return{}},template:'<div />'})
 await flushPromises()
 expect(mocks.presence).toHaveBeenLastCalledWith(expect.objectContaining({device_id:expect.any(String),room_id:2,status:'focusing'}))
 mocks.route.name='tasks';mocks.route.fullPath='/tasks';await nextTick();await flushPromises()
 expect(mocks.presence).toHaveBeenLastCalledWith(expect.objectContaining({room_id:null,status:'focusing'}))
 vi.spyOn(document,'visibilityState','get').mockReturnValue('hidden');document.dispatchEvent(new Event('visibilitychange'));await flushPromises()
 expect(mocks.presence).toHaveBeenLastCalledWith(expect.objectContaining({room_id:null,status:'offline'}))
})
it('组员卡片展示状态及房间，隐私成员只显示隐藏位置',async()=>{
 mocks.members.mockResolvedValue([{id:3,nickname:'好友甲',status:'focusing',statusText:'专注中',isOnline:true,roomName:'数学自习室'},
 {id:4,nickname:'好友乙',status:'private',statusText:'隐私中',is_private_mode:true,isOnline:null,roomName:null}])
 wrapper=mount(GroupLearningView,{global:{stubs:{BlobImage:true}}});await flushPromises()
 expect(wrapper.text()).toContain('专注中');expect(wrapper.text()).toContain('房间：数学自习室');expect(wrapper.text()).toContain('隐私中');expect(wrapper.text()).toContain('位置已隐藏')
})
