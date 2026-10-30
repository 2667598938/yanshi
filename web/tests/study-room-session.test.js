// @vitest-environment happy-dom
import {mount} from '@vue/test-utils'
import {it,expect,vi} from 'vitest'
import StudyStatusBar from '../src/components/StudyStatusBar.vue'
import {useStudyRoomStore} from '../src/stores/studyRoom'
import {useTimerStore} from '../src/stores/timer'
vi.mock('vue-router',()=>({useRoute:()=>({name:'ai'})}))
it('跨页计时条展示有效专注；离开共学不会结束计时或保留旧账号位置',async()=>{
 sessionStorage.clear()
 const room=useStudyRoomStore(),timer=useTimerStore()
 room.enter({id:3,name:'数学共学'},2)
 timer.current={id:'focus-1',startedAt:1000000,paused:false,pauseAccum:1200000}
 timer.now=2800000
 const wrapper=mount(StudyStatusBar,{global:{stubs:{RouterLink:{props:['to'],template:'<a :href="to"><slot /></a>'}}}})
 try{
  expect(wrapper.text()).toContain('10:00')
  expect(wrapper.get('a[href="/rooms/3"]').text()).toContain('数学共学')
  expect(wrapper.find('button').exists()).toBe(false)
  expect(room.room.id).toBe(3);expect(timer.current.id).toBe('focus-1')
  room.leave();expect(room.room).toBeNull()
  room.enter({id:3,name:'数学共学'},2);room.load(9)
  expect(room.room).toBeNull();room.load(2);expect(room.room).toBeNull()
 }finally{wrapper.unmount();timer.current=null;room.leave()}
})
