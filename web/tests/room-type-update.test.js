// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import {defineComponent,onBeforeUnmount} from 'vue'
import RoomView from '../src/views/RoomView.vue'
import {roomApi} from '../src/api'
vi.mock('vue-router',()=>({useRoute:()=>({params:{id:'7'},name:'room-detail'}),useRouter:()=>({replace:vi.fn(),push:vi.fn(),back:vi.fn()})}))
vi.mock('../src/api',()=>({roomApi:{get:vi.fn(),applies:vi.fn(),update:vi.fn()}}))
vi.mock('../src/stores/auth',()=>({useAuthStore:()=>({user:{id:1},isAdmin:false})}))
vi.mock('../src/stores/timer',()=>({useTimerStore:()=>({current:null})}))
vi.mock('../src/stores/subjects',()=>({useSubjectsStore:()=>({byId:{}})}))
let wrapper,current
const closed=vi.fn()
const Media=defineComponent({setup(){onBeforeUnmount(closed)},template:'<section data-test="media">音视频</section>'})
function state(){return {room:{...current},joined:true,members:[],messages:[],ranking:{today:[],week:[],all:[]}}}
async function open(){wrapper=mount(RoomView,{global:{stubs:{BlobImage:true,RoomMedia:Media}}});await flushPromises();await wrapper.get('[aria-label="房间设置"]').trigger('click');await flushPromises()}
function field(label){return wrapper.findAll('.sheet label').find(row=>row.find('span').text()===label)}
async function save(){await wrapper.findAll('.sheet button').find(button=>button.text()==='保存').trigger('click');await flushPromises()}
beforeEach(()=>{
 vi.clearAllMocks();current={id:7,name:'原有房间',intro:'每天一起学',visibility:'private',my_role:'owner',code:'ABC123',room_type:'text_room',capacity:50,media_mode:''}
 roomApi.get.mockImplementation(async()=>state());roomApi.applies.mockResolvedValue({items:[]})
 roomApi.update.mockImplementation(async(id,body)=>{current={...current,...body};return {...current}})
})
afterEach(()=>wrapper?.unmount())
it('房主将原有文字房切成音视频，提交六人限制并出现媒体入口',async()=>{
 await open();expect(field('房间类型').get('select').element.value).toBe('text_room')
 await field('房间类型').get('select').setValue('av_room')
 expect(wrapper.text()).toContain('最多 6 人');expect(wrapper.text()).toContain('保留房间码、成员和留言')
 await save()
 expect(roomApi.update).toHaveBeenCalledExactlyOnceWith(7,{name:'原有房间',intro:'每天一起学',visibility:'private',room_type:'av_room',capacity:6,media_mode:'mesh'})
 expect(wrapper.find('[data-test="media"]').exists()).toBe(true);expect(wrapper.find('.sheet').exists()).toBe(false)
})
it('切回文字房可选容量，保存后销毁当前音视频组件',async()=>{
 current={...current,room_type:'av_room',capacity:6,media_mode:'mesh'}
 await open();expect(wrapper.find('[data-test="media"]').exists()).toBe(true)
 await field('房间类型').get('select').setValue('text_room')
 await field('成员上限').get('select').setValue('20');await save()
 expect(roomApi.update.mock.calls[0][1]).toMatchObject({room_type:'text_room',capacity:20})
 expect(wrapper.find('[data-test="media"]').exists()).toBe(false);expect(closed).toHaveBeenCalledOnce()
})
it('普通成员的设置中不提供类型修改',async()=>{
 current.my_role='member';await open()
 expect(wrapper.find('.sheet select').exists()).toBe(false);expect(wrapper.text()).toContain('退出房间并停止同步')
 expect(roomApi.update).not.toHaveBeenCalled()
})
it('超员保存失败时保留设置供调整，不显示成功后的音视频入口',async()=>{
 roomApi.update.mockRejectedValueOnce(Object.assign(new Error('当前已有7位成员'),{status:409}))
 await open();await field('房间类型').get('select').setValue('av_room');await save()
 expect(wrapper.find('.sheet').exists()).toBe(true);expect(wrapper.find('[data-test="media"]').exists()).toBe(false)
 expect(wrapper.findAll('.sheet button').find(button=>button.text()==='保存').attributes('disabled')).toBeUndefined()
})
it('只改名称不重设原有房间类型和容量',async()=>{
 current={...current,room_type:'av_room',capacity:6,media_mode:'mesh'}
 await open();await field('房间名').get('input').setValue('新的房名');await save()
 expect(roomApi.update.mock.calls[0][1]).toEqual({name:'新的房名',intro:'每天一起学',visibility:'private'})
})
