// @vitest-environment happy-dom
import { Blob as NativeBlob } from 'node:buffer';
import Dexie from 'dexie';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import { getActivePinia } from 'pinia';
import MistakeEditView from '../src/views/MistakeEditView.vue';
import { db, activateAccount } from '../src/db';
import { useSubjectsStore } from '../src/stores/subjects';
import { useMistakesStore } from '../src/stores/mistakes';
import { attachmentApi } from '../src/api';

const mocks = vi.hoisted(() => ({ push: vi.fn(), toast: vi.fn(), query: {} }));
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push, back: vi.fn() }),
  useRoute: () => ({ query: mocks.query }),
}));
vi.mock('../src/api', () => ({
  errorTypeApi: { list: vi.fn().mockResolvedValue({ custom: [] }) },
  attachmentApi: { uploadImage: vi.fn() },
}));
vi.mock('../src/composables/useToast', () => ({ useToast: () => ({ toast: mocks.toast }) }));
vi.mock('../src/utils/image', () => ({
  compressImage: vi.fn(async (file) => new Blob([file.name], { type: 'image/jpeg' })),
}));
vi.mock('../src/sync/engine', () => ({ enqueueRecord: vi.fn(), enqueueDelete: vi.fn() }));

let wrapper;
beforeEach(async () => {
  vi.stubGlobal('Blob', NativeBlob);
  await activateAccount(null);
  mocks.query = {};
  useSubjectsStore().list = [{ id: 'math', name: '数学', archived: 0, order: 0 }];
});
afterEach(async () => {
  wrapper?.unmount();
  db.close();
  for (const name of await Dexie.getDatabaseNames()) await Dexie.delete(name);
  await activateAccount(null);
});
function render() {
  wrapper = mount(MistakeEditView, {
    global: { plugins: [getActivePinia()], stubs: { BlobImage: true } },
  });
  return wrapper;
}
const saveButton = () => wrapper.get('button.btn-tomato');
const contentInput = () => wrapper.get('textarea[placeholder^="题目"]');
async function pick(index, names) {
  const input = wrapper.findAll('input[type="file"]')[index];
  Object.defineProperty(input.element, 'files', {
    configurable: true,
    value: names.map((name) => new File(['image'], name, { type: 'image/jpeg' })),
  });
  await input.trigger('change');
  await flushPromises();
}

it('点击收录实际保存响应式标签、两张题图和一张解析图，不等待网络上传', async () => {
  render();
  await contentInput().setValue('图片同步测试001');
  await wrapper
    .findAll('button')
    .find((button) => button.text() === '真题')
    .trigger('click');
  await pick(0, ['question1.jpg', 'question2.jpg']);
  await pick(1, ['answer.jpg']);
  await saveButton().trigger('click');
  await vi.waitFor(() => expect(mocks.push).toHaveBeenCalledWith('/mistakes'));
  const [saved] = await db.mistakes.toArray();
  expect(saved).toMatchObject({ content: '图片同步测试001', tags: ['真题'] });
  expect(saved.images).toHaveLength(2);
  expect(await saved.images[0].text()).toBe('question1.jpg');
  expect(await saved.images[1].text()).toBe('question2.jpg');
  expect(await saved.answerImages[0].text()).toBe('answer.jpg');
  expect(attachmentApi.uploadImage).not.toHaveBeenCalled();
});

it('保存中禁用按钮且重复点击只写一次', async () => {
  const store = useMistakesStore();
  let complete;
  const add = vi.spyOn(store, 'add').mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  render();
  await contentInput().setValue('防止重复');
  await saveButton().trigger('click');
  expect(saveButton().attributes('disabled')).toBeDefined();
  expect(saveButton().text()).toContain('保存中');
  await saveButton().trigger('click');
  expect(add).toHaveBeenCalledTimes(1);
  complete({ id: 'once' });
  await flushPromises();
  expect(mocks.push).toHaveBeenCalledTimes(1);
});

it('保存报错后明确提示、保留输入并允许重试', async () => {
  const store = useMistakesStore();
  const add = vi.spyOn(store, 'add').mockRejectedValueOnce(new Error('disk full'));
  vi.spyOn(console, 'error').mockImplementation(() => {});
  render();
  await contentInput().setValue('失败后仍保留');
  await saveButton().trigger('click');
  await flushPromises();
  expect(mocks.toast).toHaveBeenCalledWith(expect.stringContaining('保存失败'));
  expect(contentInput().element.value).toBe('失败后仍保留');
  expect(saveButton().attributes('disabled')).toBeUndefined();
  expect(mocks.push).not.toHaveBeenCalled();
  add.mockRestore();
  await saveButton().trigger('click');
  await vi.waitFor(() => expect(mocks.push).toHaveBeenCalledWith('/mistakes'));
  expect(await db.mistakes.count()).toBe(1);
});

it('空表单先校验，既不保存也不上传', async () => {
  const add = vi.spyOn(useMistakesStore(), 'add');
  render();
  await saveButton().trigger('click');
  expect(mocks.toast).toHaveBeenCalledWith('至少写点题干或上传一张题目截图');
  expect(add).not.toHaveBeenCalled();
  expect(attachmentApi.uploadImage).not.toHaveBeenCalled();
});

it('编辑保存修改原记录，保留原图片 key 并保存新解析图', async () => {
  const row = await useMistakesStore().add({ content: '原错题', images: ['mistake/existing-key'] });
  mocks.query = { id: row.id };
  render();
  await contentInput().setValue('修改后的错题');
  await pick(1, ['answer-new.jpg']);
  expect(saveButton().text()).toContain('保存修改');
  await saveButton().trigger('click');
  await vi.waitFor(() => expect(mocks.push).toHaveBeenCalledWith('/mistakes'));
  const saved = await db.mistakes.get(row.id);
  expect(saved.content).toBe('修改后的错题');
  expect(saved.images).toEqual(['mistake/existing-key']);
  expect(await saved.answerImages[0].text()).toBe('answer-new.jpg');
  expect(await db.mistakes.count()).toBe(1);
});
