// @vitest-environment happy-dom
import { mount, flushPromises } from '@vue/test-utils';
import { reactive } from 'vue';
import { it, expect, vi } from 'vitest';
import BlobImage from '../src/components/BlobImage.vue';
const state = vi.hoisted(() => ({ auth: null, resolve: vi.fn() }));
vi.mock('../src/stores/auth', () => ({ useAuthStore: () => state.auth }));
vi.mock('../src/api', () => ({ attachmentApi: { viewUrl: (key) => key } }));
vi.mock('../src/api/http', () => ({ fetchBlob: vi.fn() }));
vi.mock('../src/db/imageCache', () => ({ resolveCachedImage: state.resolve }));
it('修改昵称不会重新加载或回退同一账号的已上传头像', async () => {
  state.auth = reactive({ user: { id: 8, nickname: '旧昵称' } });
  state.resolve.mockResolvedValue(new Blob(['avatar']));
  const create = vi.fn().mockReturnValue('blob:new-avatar'),
    revoke = vi.fn();
  vi.stubGlobal('URL', { createObjectURL: create, revokeObjectURL: revoke });
  const wrapper = mount(BlobImage, {
    props: { src: 'uploaded-avatar', fallback: '/old-school.jpg' },
  });
  await flushPromises();
  expect(wrapper.get('img').attributes('src')).toBe('blob:new-avatar');
  state.auth.user = { id: 8, nickname: '新昵称' };
  await flushPromises();
  expect(wrapper.get('img').attributes('src')).toBe('blob:new-avatar');
  expect(create).toHaveBeenCalledTimes(1);
  expect(revoke).not.toHaveBeenCalled();
  wrapper.unmount();
  expect(revoke).toHaveBeenCalledWith('blob:new-avatar');
});
