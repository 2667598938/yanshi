// 优先使用现代剪贴板接口；局域网 HTTP 或权限拒绝时尝试选中文本复制。
// 两条路径都不可用时由调用方提供可手动选择的文本，不误报“已复制”。
export async function copyText(value) {
  const text = String(value ?? '');
  if (!text) return false;
  if (typeof globalThis.navigator?.clipboard?.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 浏览器权限或安全上下文限制，继续兼容路径。
    }
  }
  const doc = globalThis.document;
  if (!doc?.body || typeof doc.execCommand !== 'function') return false;
  const active = doc.activeElement;
  const start = active?.selectionStart;
  const end = active?.selectionEnd;
  const selection = doc.getSelection();
  const ranges = selection
    ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i).cloneRange())
    : [];
  const input = doc.createElement('textarea');
  input.value = text;
  input.readOnly = true;
  input.style.cssText =
    'position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;font-size:16px;';
  doc.body.appendChild(input);
  try {
    input.focus({ preventScroll: true });
    input.select();
    input.setSelectionRange(0, text.length);
    return doc.execCommand('copy') === true;
  } catch {
    return false;
  } finally {
    input.remove();
    try {
      active?.focus?.({ preventScroll: true });
      if (typeof start === 'number' && typeof end === 'number')
        active.setSelectionRange(start, end);
      if (selection && ranges.length) {
        selection.removeAllRanges();
        for (const range of ranges) selection.addRange(range);
      }
    } catch {
      // 原焦点已被移除时无需恢复。
    }
  }
}
