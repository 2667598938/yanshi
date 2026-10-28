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
