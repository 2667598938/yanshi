// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {it,expect,vi} from 'vitest'
import FocusView from '../src/views/FocusView.vue'
import {useAppStore} from '../src/stores/app'
import {useTimerStore} from '../src/stores/timer'
import {useTasksStore} from '../src/stores/tasks'
const mocks=vi.hoisted(()=>({save:vi.fn()}))
vi.mock('../src/stores/profile',()=>({useProfileStore:()=>({save:mocks.save})}))
vi.mock('vue-router',()=>({useRoute:()=>({query:{}}),useRouter:()=>({push:vi.fn()})}))
it('专注页通知开关使用账号资料保存；失败不显示已生效',async()=>{
 vi.stubGlobal('Notification',{permission:'granted'})
 const app=useAppStore();app.notifyEnabled=false
 mocks.save.mockResolvedValueOnce()
 const wrapper=mount(FocusView)
 try{
  await wrapper.get('.notify-btn').trigger('click');await flushPromises()
  expect(mocks.save).toHaveBeenCalledWith({notify_enabled:true});expect(app.notifyEnabled).toBe(true)
  mocks.save.mockRejectedValueOnce(new Error('保存失败'))
  await wrapper.get('.notify-btn').trigger('click');await flushPromises()
  expect(app.notifyEnabled).toBe(true)
 }finally{wrapper.unmount()}
})
it('计时完成只提供成果确认，必须用户点击后才完成关联任务',async()=>{
 const timer=useTimerStore(),tasks=useTasksStore()
 tasks.list=[{id:'task-a',title:'高数十题',done:0,acceptCriteria:'独立做完并订正'}]
 timer.lastFinished={at:Date.now(),session:{taskId:'task-a',actualSec:1500}}
 const toggle=vi.spyOn(tasks,'toggle').mockImplementation(async()=>{tasks.list[0].done=1})
 const wrapper=mount(FocusView)
 try{
  expect(toggle).not.toHaveBeenCalled()
  await wrapper.findAll('button').find(b=>b.text()==='已达到标准，标记任务完成').trigger('click');await flushPromises()
  expect(toggle).toHaveBeenCalledExactlyOnceWith('task-a')
  expect(wrapper.text()).toContain('此任务已完成')
 }finally{wrapper.unmount();timer.lastFinished=null}
})
