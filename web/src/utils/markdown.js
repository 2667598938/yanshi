// 轻量 Markdown 渲染：先全量转义，再生成受控标签，避免 XSS
import katex from 'katex'
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ESC[c])
}

/** 行内格式：代码、粗体、斜体、删除线、链接 */
function inline(text) {
  const codes = []
  let s = escapeHtml(text)
  // 行内代码先占位，避免内部再被格式化
  s = s.replace(/`([^`\n]+)`/g, (_, code) => {
    codes.push(code)
    return `\u0000${codes.length - 1}\u0000`
  })
  s = s
    .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
    .replace(/~~([^~\n]+)~~/g, '<del>$1</del>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (match, label, url) => {
      const safe = /^(https?:\/\/|mailto:)/i.test(url) ? url : ''
      return safe
        ? `<a href="${safe}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : label
    })
    .replace(/\n/g, '<br/>')
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[Number(i)]}</code>`)
}

function splitRow(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())
}

/** 把 AI 回复渲染为安全 HTML：段落/标题/列表/引用/代码块/表格 */
export function renderMarkdown(source = '') {
  const math = []
  // Protect code first. Math is rendered independently with untrusted commands
  // disabled, then restored AFTER Markdown escaping/formatting has finished.
  const prepared = String(source).replace(/\r\n/g, '\n')
    .split(/(```[\s\S]*?(?:```|$)|`[^`\n]+`)/g)
    .map(part => part.startsWith('`') ? part : part.replace(
      /\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$\$([\s\S]*?)\$\$|(?<!\\)\$([^$\n]+?)(?<!\\)\$/g,
      (whole, bracket, inline, display, dollar) => {
        const expression = bracket ?? inline ?? display ?? dollar
        if (expression.length > 12000) return whole
        try {
          const html = katex.renderToString(expression, { displayMode: bracket != null || display != null,
            trust: false, throwOnError: false, strict: 'ignore', maxSize: 12, maxExpand: 1000,
            errorColor: '#9b6666', macros: {} })
          math.push(html)
          return `\u0001MATH${math.length - 1}\u0001`
        } catch { return whole }
      }))
    .join('')
  const lines = prepared.split('\n')
  const out = []
  let list = null
  let i = 0
  const closeList = () => {
    if (list) {
      out.push(`</${list}>`)
      list = null
    }
  }

  while (i < lines.length) {
    const line = lines[i]

    // 代码块（流式输出时可能尚未闭合，按到文末处理）
    const fence = /^\s*```(\S*)\s*$/.exec(line)
    if (fence) {
      closeList()
      const lang = fence[1]
      const buf = []
      i++
      while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) {
        buf.push(lines[i])
        i++
      }
      i++
      out.push(
        `<pre><code${lang ? ` data-lang="${escapeHtml(lang)}"` : ''}>${escapeHtml(buf.join('\n'))}</code></pre>`
      )
      continue
    }

    // 表格：| 表头 | 下一行含 --- 分隔
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      closeList()
      const head = splitRow(line)
      i += 2
      const rows = []
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
        rows.push(splitRow(lines[i]))
        i++
      }
      out.push(
        '<div class="md-table"><table><thead><tr>' +
          head.map((c) => `<th>${inline(c)}</th>`).join('') +
          '</tr></thead><tbody>' +
          rows.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('') +
          '</tbody></table></div>'
      )
      continue
    }

    // 标题
    const heading = /^(#{1,4})\s+(.*)$/.exec(line)
    if (heading) {
      closeList()
      const level = Math.min(4, heading[1].length) + 2
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`)
      i++
      continue
    }

    // 分隔线
    if (/^\s*([-*_])\1{2,}\s*$/.test(line)) {
      closeList()
      out.push('<hr/>')
      i++
      continue
    }

    // 引用
    if (/^\s*>\s?/.test(line)) {
      closeList()
      const buf = []
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
        buf.push(lines[i].replace(/^\s*>\s?/, ''))
        i++
      }
      out.push(`<blockquote>${inline(buf.join('\n'))}</blockquote>`)
      continue
    }

    // 列表
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line)
    if (bullet) {
      if (list !== 'ul') {
        closeList()
        out.push('<ul>')
        list = 'ul'
      }
      out.push(`<li>${inline(bullet[1])}</li>`)
      i++
      continue
    }
    const ordered = /^\s*(\d+)[.)]\s+(.*)$/.exec(line)
    if (ordered) {
      if (list !== 'ol') {
        closeList()
        out.push('<ol>')
        list = 'ol'
      }
      out.push(`<li>${inline(ordered[2])}</li>`)
      i++
      continue
    }

    // 空行
    if (!line.trim()) {
      closeList()
      i++
      continue
    }

    // 普通段落：合并连续文本行
    closeList()
    const buf = [line]
    i++
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^\s*```/.test(lines[i]) &&
      !/^(#{1,4})\s+/.test(lines[i]) &&
      !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i]) &&
      !/^\s*>/.test(lines[i]) &&
      !/^\s*\|.*\|\s*$/.test(lines[i])
    ) {
      buf.push(lines[i])
      i++
    }
    out.push(`<p>${inline(buf.join('\n'))}</p>`)
  }
  closeList()
  return out.join('').replace(/\u0001MATH(\d+)\u0001/g, (_, i) => math[Number(i)] || '')
}
