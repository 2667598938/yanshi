// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { defineComponent, ref, onMounted } from 'vue';
import { createRouter, createMemoryHistory, useRoute } from 'vue-router';
import { it, expect, vi } from 'vitest';
import App from '../src/App.vue';
vi.mock('../src/composables/useGroupPresence', () => ({ useGroupPresence: vi.fn() }));
vi.mock('../src/composables/useTimerOwnership', () => ({ useTimerOwnership: vi.fn() }));
vi.mock('../src/stores/timer', () => ({ useTimerStore: () => ({}) }));
vi.mock('../src/stores/app', () => ({ useAppStore: () => ({}) }));
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 1 } }) }));
vi.mock('../src/stores/subjects', () => ({ useSubjectsStore: () => ({ byId: {} }) }));
vi.mock('../src/stores/notifications', () => ({
  useNotificationsStore: () => ({ start: vi.fn(), stop: vi.fn() }),
}));
it('相同页面组件切换资源ID时重新初始化，不带入上一份编辑内容', async () => {
  let mounts = 0;
  const Editor = defineComponent({
    setup() {
      const route = useRoute(),
        draft = ref('');
      onMounted(() => mounts++);
      return { route, draft };
    },
    template: '<div><input v-model="draft" />{{route.params.id}}</div>',
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/edit/:id', component: Editor, meta: { hideTabbar: true } }],
  });
  await router.push('/edit/1');
  await router.isReady();
  const wrapper = mount(App, {
    global: {
      plugins: [router],
      stubs: {
        SessionIssues: true,
        CommunityIssues: true,
        OfflineBanner: true,
        TabBar: true,
        ToastLayer: true,
        ConflictDialog: true,
      },
    },
  });
  await wrapper.get('input').setValue('上一个资源的内容');
  await router.push('/edit/2');
  expect(wrapper.get('input').element.value).toBe('');
  expect(mounts).toBe(2);
  wrapper.unmount();
});
