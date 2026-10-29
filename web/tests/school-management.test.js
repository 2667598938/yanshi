// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { it, expect, vi, afterEach } from 'vitest'
import SchoolAdminView from '../src/views/SchoolAdminView.vue'
import { db } from '../src/db'
import { schoolApi } from '../src/api'
const toast=vi.hoisted(()=>vi.fn())
vi.mock('vue-router',()=>({useRouter:()=>({back:vi.fn(),push:vi.fn()})}))
vi.mock('../src/composables/useToast',()=>({useToast:()=>({toast})}))
vi.mock('../src/stores/profile',()=>({useProfileStore:()=>({save:vi.fn()})}))
vi.mock('../src/api',()=>({schoolApi:{list:vi.fn(),update:vi.fn(),create:vi.fn()},attachmentApi:{},aiApi:{}}))
let wrapper
afterEach(async()=>{wrapper?.unmount();await db.delete()})
it('个人梦校保存后缓存可被克隆，回到我的页面即可选择新资料',async()=>{
 await db.open()
 schoolApi.list.mockResolvedValue([{key:'custom',name:'原名称',short:'自选',info:{},album_keys:[]}])
 schoolApi.update.mockResolvedValue({key:'custom',name:'新的梦校',short:'自选',info:{},album_keys:[]})
 wrapper=mount(SchoolAdminView,{global:{stubs:{BlobImage:true}}})
 await flushPromises()
 await vi.waitFor(()=>expect(wrapper.get('input[maxlength="80"]').element.value).toBe('原名称'))
 await wrapper.get('input[maxlength="80"]').setValue('新的梦校')
 await wrapper.findAll('button').find(b=>b.text()==='保存院校').trigger('click')
 await vi.waitFor(async()=>expect((await db.kv.get('schools:catalog'))?.value[0].name).toBe('新的梦校'))
 expect(toast).toHaveBeenCalledWith('已保存，返回首页即可看到新校徽与校园图轮播')
})
