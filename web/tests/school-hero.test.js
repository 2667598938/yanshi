// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.mock('../src/api', () => ({ schoolApi: { list: vi.fn() } }))
vi.mock('../src/db', () => {
  const db = { kv: { get: vi.fn(), put: vi.fn() } }
  return { db, activeAccountId: () => null, localAccountScope: () => ({ db, isCurrent: () => true, assertCurrent() {} }) }
})
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ toast: vi.fn() }) }))
vi.mock('../src/stores/profile', () => ({ useProfileStore: () => ({ save: vi.fn() }) }))
vi.mock('../src/components/TimeNodesHome.vue', () => ({ default: { template: '<div />' } }))
vi.mock('../src/components/SchoolBullets.vue', () => ({ default: { template: '<div />' } }))
vi.mock('../src/components/BlobImage.vue', () => ({
  default: {
    props: ['src'],
    template: '<img class="blob-image" :src="src" />',
  },
}))

import { schoolApi } from '../src/api'
import { db } from '../src/db'
import SchoolHero from '../src/components/SchoolHero.vue'

let wrapper

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-27T12:00:00'))
  schoolApi.list.mockResolvedValue([
    { key: 'custom', name: '南京理工大学', short: '南理工', logo_key: 'logo-key', album_keys: ['campus-1', 'logo-key', 'campus-2'], info: {} },
  ])
  db.kv.get.mockResolvedValue(undefined)
  db.kv.put.mockResolvedValue(undefined)
})

afterEach(() => {
  wrapper?.unmount()
  vi.useRealTimers()
})

it('首页使用上传校徽，并在多张校园图之间自动轮播', async () => {
  wrapper = mount(SchoolHero, { global: { plugins: [createPinia()] } })
  await flushPromises()
  await flushPromises()

  expect(wrapper.get('.seal').attributes('src')).toBe('logo-key')
  expect(wrapper.get('.hero-bg').attributes('src')).toBe('campus-1')
  expect(wrapper.findAll('.album-dot')).toHaveLength(2)
  expect(wrapper.get('.album-count').text()).toBe('校园图 1 / 2')

  await vi.advanceTimersByTimeAsync(5000)
  await flushPromises()

  expect(wrapper.get('.hero-bg').attributes('src')).toBe('campus-2')
  expect(wrapper.get('.album-count').text()).toBe('校园图 2 / 2')
})

it('点击相册圆点可手动切换，并暂停自动轮播', async () => {
  wrapper = mount(SchoolHero, { global: { plugins: [createPinia()] } })
  await flushPromises()
  await flushPromises()

  await wrapper.findAll('.album-dot')[1].trigger('click')
  expect(wrapper.get('.hero-bg').attributes('src')).toBe('campus-2')

  await vi.advanceTimersByTimeAsync(5000)
  expect(wrapper.get('.hero-bg').attributes('src')).toBe('campus-2')
})
