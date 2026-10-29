// @vitest-environment happy-dom
import {mount,flushPromises} from '@vue/test-utils'
import {afterEach,it,expect,vi} from 'vitest'
import ResourceReviewView from '../src/views/ResourceReviewView.vue'
import {adminApi} from '../src/api'
const toast=vi.hoisted(()=>vi.fn())
vi.mock('vue-router',()=>({useRouter:()=>({back:vi.fn()})}))
vi.mock('../src/api',()=>({adminApi:{resourceQueue:vi.fn(),reviewResource:vi.fn()},resourceApi:{}}))
vi.mock('../src/composables/useToast',()=>({useToast:()=>({toast})}))
let wrapper
afterEach(()=>wrapper?.unmount())
it('审核提交当前版本，驳回需要原因，成功后刷新队列',async()=>{
 adminApi.resourceQueue.mockResolvedValue({items:[{id:4,title:'待审资料',url:'https://example.com/share',review_status:'pending',revision:2}],next:null})
 adminApi.reviewResource.mockResolvedValue({})
 wrapper=mount(ResourceReviewView);await flushPromises()
 const reject=()=>wrapper.findAll('button').find(b=>b.text()==='驳回')
 await reject().trigger('click');expect(adminApi.reviewResource).not.toHaveBeenCalled()
 await wrapper.get('textarea').setValue('链接需要核实');await reject().trigger('click');await flushPromises()
 expect(adminApi.reviewResource).toHaveBeenCalledWith(4,{action:'reject',expected_revision:2,note:'链接需要核实'})
 expect(adminApi.resourceQueue).toHaveBeenCalledTimes(2)
})
