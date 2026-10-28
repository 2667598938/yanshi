// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { expect, it, vi } from 'vitest'
import AiSettingsView from '../src/views/AiSettingsView.vue'
import { aiApi } from '../src/api'

vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn(), back: vi.fn() }) }))
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ isVip: true }) }))
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ toast: vi.fn() }) }))
vi.mock('../src/api', () => ({
  aiApi: {
    enabled: vi.fn(),
    key: vi.fn(),
    usage: vi.fn(),
    models: vi.fn(),
    deleteKey: vi.fn(),
  },
}))

it('模型目录可展示第13项以后并支持搜索，手填模型 ID 保留', async () => {
  aiApi.enabled.mockResolvedValue({ access: true })
  aiApi.key.mockResolvedValue({
    configured: true,
    key_mask: 'sk-***1234',
    provider: 'deepseek',
    base_url: 'https://api.deepseek.com/v1',
    model: 'model-01',
  })
  aiApi.usage.mockResolvedValue({ context_turns: 10 })
  aiApi.models.mockResolvedValue({
    models: Array.from({ length: 20 }, (_, i) => `model-${String(i + 1).padStart(2, '0')}`),
    details: [],
    fallback: false,
  })
  const wrapper = mount(AiSettingsView)
  await flushPromises()
  const fetchButton = wrapper.findAll('button').find((b) => b.text().includes('拉取列表'))
  await fetchButton.trigger('click')
  await flushPromises()

  expect(wrapper.findAll('.model-chip')).toHaveLength(20)
  expect(wrapper.text()).toContain('20 / 20')
  const search = wrapper.find('.model-filter input')
  await search.setValue('model-19')
  expect(wrapper.findAll('.model-chip')).toHaveLength(1)
  expect(wrapper.find('.model-chip').text()).toContain('model-19')
  expect(wrapper.find('.model-row input').exists()).toBe(true)
  wrapper.unmount()
})

it('用量接口失败仍显示保存的服务商和模型', async () => {
  aiApi.enabled.mockResolvedValue({ access: true })
  aiApi.key.mockResolvedValue({ configured: true, provider: 'custom', base_url: 'https://gateway.example/v1', model: 'my-model', key_mask: 'sk-***1234' })
  aiApi.usage.mockRejectedValueOnce(new Error('usage unavailable'))
  const wrapper = mount(AiSettingsView)
  await flushPromises()
  expect(wrapper.get('.model-row input').element.value).toBe('my-model')
  expect(wrapper.get('.form-card > input').element.value).toBe('https://gateway.example/v1')
  wrapper.unmount()
})

it('删除Key会清空模型目录，迟到的拉取结果不能重新填回', async () => {
  aiApi.enabled.mockResolvedValue({ access: true })
  aiApi.key.mockResolvedValue({ configured: true, provider: 'deepseek', base_url: 'https://api.deepseek.com/v1', model: 'saved-model' })
  aiApi.usage.mockResolvedValue({ context_turns: 10 })
  aiApi.deleteKey.mockResolvedValue({ configured: false })
  let finish
  aiApi.models.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
  vi.stubGlobal('confirm', () => true)
  const wrapper = mount(AiSettingsView)
  await flushPromises()
  await wrapper.findAll('button').find(b => b.text().includes('拉取列表')).trigger('click')
  await wrapper.findAll('button').find(b => b.text().includes('删除 Key')).trigger('click'); await flushPromises()
  finish({ models: ['old-key-only-model'] }); await flushPromises()
  expect(wrapper.findAll('.model-chip')).toHaveLength(0)
  expect(wrapper.get('.model-row input').element.value).toBe('')
  wrapper.unmount()
})
