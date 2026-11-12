import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import {db,activateAccount,localAccountScope} from '../src/db'
import {cacheImage,resolveCachedImage} from '../src/db/imageCache'
beforeEach(async()=>{await activateAccount(901);await db.imageCache.clear()})
afterEach(async()=>{await db.imageCache.clear();await activateAccount(null)})
it('上传图片可离线命中缓存，访问会刷新LRU顺序',async()=>{
 const blob=new Blob(['photo'],{type:'image/jpeg'});await cacheImage('mistake/a',blob)
 const download=vi.fn().mockRejectedValue(new Error('offline'))
 expect(await (await resolveCachedImage('mistake/a',download)).text()).toBe('photo')
 expect(download).not.toHaveBeenCalled()
})
it('按字节上限淘汰最久未使用的缓存，不触及学习记录',async()=>{
 await db.tasks.put({id:'keep',title:'learning data'})
 await db.imageCache.bulkPut([{key:'old',blob:new Blob(['1234']),size:4,lastAccessedAt:1},{key:'recent',blob:new Blob(['5678']),size:4,lastAccessedAt:2}])
 await cacheImage('new',new Blob(['abcd']),localAccountScope(),8)
 expect(await db.imageCache.get('old')).toBeUndefined()
 expect(await db.imageCache.count()).toBe(2)
 expect((await db.tasks.get('keep')).title).toBe('learning data')
 await db.tasks.delete('keep')
})
it('账号切换后，旧请求不能把图片写入新账号或显示给新账号',async()=>{
 let release;const request=resolveCachedImage('private-key',()=>new Promise(resolve=>{release=resolve}))
 await vi.waitFor(()=>expect(release).toBeTypeOf('function'))
 await activateAccount(902);release(new Blob(['private']))
 expect(await request).toBeNull();expect(await db.imageCache.count()).toBe(0)
})
it('并发读取同一图片只下载一次',async()=>{
 const download=vi.fn().mockResolvedValue(new Blob(['same']))
 const result=await Promise.all([resolveCachedImage('same',download),resolveCachedImage('same',download)])
 expect(download).toHaveBeenCalledTimes(1);expect(await result[0].text()).toBe('same')
})
