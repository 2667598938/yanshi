import { beforeEach, afterEach, expect, it, vi } from 'vitest'
import { db } from '../src/db'
import { attachmentApi } from '../src/api'
import { flushMistakeImages } from '../src/sync/attachments'

vi.mock('../src/api', () => ({ attachmentApi: { uploadImage: vi.fn() } }))
beforeEach(async () => { await db.open() })
afterEach(async () => { await db.delete() })

it.each(['images', 'answerImages'])('%s 首张网络失败保留全部原图和顺序', async (field) => {
  const images = [new Blob(['first']), 'existing/key.jpg', new Blob(['last'])]
  await db.mistakes.add({ id: 'm', [field]: images })
  attachmentApi.uploadImage.mockRejectedValue(new Error('offline'))
  expect(await flushMistakeImages()).toEqual([])
  const saved = (await db.mistakes.get('m'))[field]
  expect(saved).toHaveLength(3)
  expect(await saved[0].text()).toBe('first')
  expect(saved[1]).toBe('existing/key.jpg')
  expect(await saved[2].text()).toBe('last')
})

it('中途 503 后重试只上传剩余图片，两组图片均保留', async () => {
  await db.mistakes.add({ id: 'm', images: [new Blob(['a']), new Blob(['b']), new Blob(['c'])],
    answerImages: [new Blob(['answer'])] })
  attachmentApi.uploadImage.mockResolvedValueOnce({ key: 'key/a' })
    .mockRejectedValueOnce(Object.assign(new Error('unavailable'), { status: 503 }))
    .mockResolvedValueOnce({ key: 'key/answer' })
  expect(await flushMistakeImages()).toEqual([])
  const partial = await db.mistakes.get('m')
  expect(partial.images).toHaveLength(3)
  expect(partial.images[0]).toBe('key/a')
  expect(await partial.images[1].text()).toBe('b')
  expect(await partial.images[2].text()).toBe('c')
  expect(partial.answerImages).toEqual(['key/answer'])
  attachmentApi.uploadImage.mockResolvedValueOnce({ key: 'key/b' }).mockResolvedValueOnce({ key: 'key/c' })
  const completed = await flushMistakeImages()
  expect(completed[0].images).toEqual(['key/a', 'key/b', 'key/c'])
  expect(attachmentApi.uploadImage).toHaveBeenCalledTimes(5)
})

it('4xx 失败保留该图，其他图片可成功补传', async () => {
  await db.mistakes.add({ id: 'm', images: [new Blob(['bad']), new Blob(['good'])] })
  attachmentApi.uploadImage.mockRejectedValueOnce(Object.assign(new Error('bad image'), { status: 400 }))
    .mockResolvedValueOnce({ key: 'key/good' })
  expect(await flushMistakeImages()).toEqual([])
  const saved = await db.mistakes.get('m')
  expect(await saved.images[0].text()).toBe('bad')
  expect(saved.images[1]).toBe('key/good')
})
