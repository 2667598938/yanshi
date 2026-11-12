// @vitest-environment happy-dom
import { mount } from '@vue/test-utils';
import { expect, it } from 'vitest';
import AiAnswer from '../src/components/AiAnswer.vue';
it('流式只为新文字标记淡入，完整内容保留可读Markdown', async () => {
  const wrapper = mount(AiAnswer, { props: { content: '先理解', streaming: true } });
  expect(wrapper.findAll('.stream-char')).toHaveLength(3);
  expect(wrapper.get('.md').attributes('aria-live')).toBe('polite');
  expect(wrapper.get('.md').attributes('aria-busy')).toBe('true');
  await wrapper.setProps({ content: '先理解，再练习' });
  expect(wrapper.text()).toBe('先理解，再练习');
  expect(
    wrapper
      .findAll('.stream-char')
      .map((span) => span.text())
      .join(''),
  ).toBe('，再练习');
  await wrapper.setProps({ content: '**先理解**，再练习', streaming: false });
  expect(wrapper.findAll('.stream-char')).toHaveLength(0);
  expect(wrapper.get('strong').text()).toBe('先理解');
  expect(wrapper.get('.md').attributes('aria-busy')).toBe('false');
  wrapper.unmount();
});

it('长回答只给最后 60 个新字符加淡入，避免生成长文本的数百个 span', () => {
  const wrapper = mount(AiAnswer, { props: { content: '字'.repeat(100), streaming: true } });
  expect(wrapper.findAll('.stream-char')).toHaveLength(60);
  wrapper.unmount();
});
it('历史及减少动态效果不播放，代码与危险HTML保持转义', () => {
  for (const props of [{ streaming: false }, { streaming: true, reduced: true }]) {
    const wrapper = mount(AiAnswer, {
      props: {
        ...props,
        content: '<img src=x onerror=alert(1)>\n\n```html\n<script>bad()</script>\n```',
      },
    });
    expect(wrapper.find('img').exists()).toBe(false);
    expect(wrapper.find('script').exists()).toBe(false);
    expect(wrapper.findAll('.stream-char')).toHaveLength(0);
    expect(wrapper.get('pre code').text()).toContain('<script>bad()</script>');
    wrapper.unmount();
  }
});
