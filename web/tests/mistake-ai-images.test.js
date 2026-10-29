// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {it,expect,vi} from 'vitest'
import MistakesView from '../src/views/MistakesView.vue'
import {useMistakesStore} from '../src/stores/mistakes'
import {db} from '../src/db'
const mocks=vi.hoisted(()=>({push:vi.fn()}))
vi.mock('vue-router',()=>({useRouter:()=>({push:mocks.push,back:vi.fn()})}))
it('多于4张题图时先选择，可带上最后的解析图，不静默丢图或直接请求AI',async()=>{
 await db.open()
 const store=useMistakesStore()
 store.list=[{id:'image-question',subjectId:'math',content:'积分换序',reason:'knowledge',stage:0,mastered:0,
  nextReviewAt:Date.now()+3600000,images:['q1','q2','q3','q4'],answerImages:['analysis5'],tags:[]}]
 const wrapper=mount(MistakesView,{global:{stubs:{BlobImage:true}}})
 try{
  await wrapper.get('.mk-card').trigger('click')
  expect(wrapper.text()).not.toContain('答案解析')
  await wrapper.findAll('button').find(b=>b.text()==='让 AI 讲讲这道题').trigger('click')
  expect(wrapper.find('.ai-image-picker').exists()).toBe(true)
  expect(await db.kv.get('ai:draft')).toBeUndefined()
  const boxes=wrapper.findAll('.ai-image-picker input')
  await boxes[0].setValue(false);await boxes[4].setValue(true)
  await wrapper.findAll('button').find(b=>b.text()==='携带选中图片去 AI').trigger('click');await flushPromises()
  const draft=await db.kv.get('ai:draft')
  expect(draft.value.images).toEqual(['q2','q3','q4','analysis5'])
  expect(mocks.push).toHaveBeenCalledWith('/ai')
 }finally{wrapper.unmount();await db.delete()}
})
