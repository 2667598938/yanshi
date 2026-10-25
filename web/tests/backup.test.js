import { beforeEach, expect, it, vi } from 'vitest'
import { buildBackup } from '../src/utils/backup'

beforeEach(() => {
  vi.stubGlobal('FileReader', class {
    readAsDataURL(blob) {
      blob.arrayBuffer().then((buffer) => {
        this.result = `data:${blob.type};base64,${Buffer.from(buffer).toString('base64')}`
        this.onload()
      }, (error) => this.onerror(error))
    }
  })
})

const database = (rows) => Object.fromEntries(['subjects', 'sessions', 'tasks', 'mistakes']
  .map((table) => [table, { toArray: async () => table === 'mistakes' ? rows : [{ id: table }] }]))

it('导出的 JSON 中题图和解析图均可还原，云端引用和元数据保留', async () => {
  const rows = [{ id: 'm', analysis: '解析', history: [{ stage: 2 }],
    images: [new Blob(['question'], { type: 'image/png' }), 'mistake/cloud-key'],
    answerImages: [new Blob(['answer'], { type: 'image/jpeg' })] }]
  const result = JSON.parse(JSON.stringify(await buildBackup(database(rows), { dailyGoalMin: 120 })))
  const restored = (s) => Buffer.from(s.split(',')[1], 'base64').toString()
  expect(restored(result.mistakes[0].images[0])).toBe('question')
  expect(restored(result.mistakes[0].answerImages[0])).toBe('answer')
  expect(result.mistakes[0].images[1]).toBe('mistake/cloud-key')
  expect(result.mistakes[0]).toMatchObject({ analysis: '解析', history: [{ stage: 2 }] })
  expect(result.settings.dailyGoalMin).toBe(120)
  expect(result.sessions).toEqual([{ id: 'sessions' }])
  expect(rows[0].answerImages[0]).toBeInstanceOf(Blob)
})

it('空图片字段兼容旧记录', async () => {
  const result = await buildBackup(database([{ id: 'old' }]), {})
  expect(result.mistakes[0]).toMatchObject({ images: [], answerImages: [] })
})

it('图片读取失败使整个备份失败，不静默丢图', async () => {
  vi.stubGlobal('FileReader', class { readAsDataURL() { this.onerror(new Error('read failed')) } })
  await expect(buildBackup(database([{ id: 'm', answerImages: [new Blob(['bad'])] }]), {}))
    .rejects.toThrow('read failed')
})
