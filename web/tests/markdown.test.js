import { describe, it, expect } from 'vitest';
import { renderMarkdown } from '../src/utils/markdown';

it('排版分式、积分与矩阵；代码中的美元符保持原文', () => {
  const html = renderMarkdown(
    String.raw`行内 $\frac{\sin x}{x}$，块级：
$$\begin{pmatrix}1&2\\3&4\end{pmatrix}$$
\[\int_0^1 x^2\,dx\]
` + '\n`$not_math$`',
  );
  expect(html).toContain('class="katex"');
  expect(html).toContain('katex-display');
  expect(html).toContain('<code>$not_math$</code>');
});

it('不执行公式中的链接、图片或HTML扩展，流式未闭合公式可安全显示', () => {
  const html = renderMarkdown(
    String.raw`$\href{javascript:alert(1)}{x}$ $\includegraphics{https://evil.test/a}$`,
  );
  expect(html).not.toContain('href="javascript:');
  expect(html).not.toContain('<img');
  expect(renderMarkdown('未结束：$\\frac{1}{')).toContain('$\\frac{1}{');
});

describe('AI 回复 Markdown 渲染', () => {
  it('转义 HTML，避免注入', () => {
    const html = renderMarkdown('<script>alert(1)</script>');
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('渲染粗体、行内代码与段落', () => {
    const html = renderMarkdown('先看 **极限**，再算 `f(0)`。\n换行继续');
    expect(html).toContain('<strong>极限</strong>');
    expect(html).toContain('<code>f(0)</code>');
    expect(html).toContain('<br/>');
  });

  it('代码块单独成块并保留语言标记', () => {
    const html = renderMarkdown('示例：\n```python\nprint("<x>")\n```');
    expect(html).toContain('<pre><code data-lang="python">');
    expect(html).toContain('print(&quot;&lt;x&gt;&quot;)');
    expect(html).toContain('</code></pre>');
  });

  it('流式输出中未闭合的代码块也能安全渲染', () => {
    const html = renderMarkdown('```js\nconst a = 1');
    expect(html).toContain('<pre><code data-lang="js">');
    expect(html).toContain('const a = 1');
  });

  it('有序与无序列表', () => {
    expect(renderMarkdown('- 第一点\n- 第二点')).toContain(
      '<ul><li>第一点</li><li>第二点</li></ul>',
    );
    expect(renderMarkdown('1. 第一步\n2. 第二步')).toContain(
      '<ol><li>第一步</li><li>第二步</li></ol>',
    );
  });

  it('渲染表格', () => {
    const html = renderMarkdown('| 科目 | 分数 |\n| --- | --- |\n| 数学 | 130 |');
    expect(html).toContain('<table>');
    expect(html).toContain('<th>科目</th>');
    expect(html).toContain('<td>130</td>');
  });

  it('只放行 http/https 链接', () => {
    expect(renderMarkdown('[资料](https://example.com)')).toContain('href="https://example.com"');
    expect(renderMarkdown('[危险](javascript:alert(1))')).not.toContain('javascript:');
  });

  it('标题、引用与分隔线', () => {
    const html = renderMarkdown('## 解题步骤\n> 注意定义域\n---');
    expect(html).toContain('<h4>解题步骤</h4>');
    expect(html).toContain('<blockquote>注意定义域</blockquote>');
    expect(html).toContain('<hr/>');
  });
});
