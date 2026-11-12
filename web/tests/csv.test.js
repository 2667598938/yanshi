import { expect, it } from 'vitest';
import { buildSessionsCsv, csvCell } from '../src/utils/csv';

it('毫秒开始时间能导出为时分，不再对数字调用 slice', () => {
  const ms = new Date(2026, 9, 26, 8, 5).getTime();
  const text = buildSessionsCsv(
    [{ date: '2026-10-26', startedAt: ms, mode: 'timer', actualSec: 1500, note: '' }],
    () => '数学',
    () => '刷题',
  );
  const row = text.split('\r\n')[1];
  expect(row).toContain('2026-10-26,08:05,番茄钟,数学,刷题,25,');
});

it('科目、备注里的逗号/引号/换行会被完整转义，列数不漂移', () => {
  const text = buildSessionsCsv(
    [
      {
        date: '2026-10-26',
        startedAt: new Date(2026, 9, 26, 9, 0).getTime(),
        mode: 'stopwatch',
        actualSec: 65,
        note: '第一行\n第二行 "引号"',
      },
    ],
    () => '数学,强化',
    () => '听课',
  );
  expect(text).toContain('"数学,强化"');
  expect(text).toContain('"第一行\n第二行 ""引号"""');
  expect(csvCell('=1+1')).toBe("'=1+1");
  // 每行应保持 7 列：用简单的 CSV 解析校验引号内换行不拆分记录
  const rows = [];
  let field = '';
  let row = [];
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else if (ch === '"') quoted = false;
      else field += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') {
      row.push(field);
      field = '';
    } else if (ch === '\n') {
      row.push(field);
      rows.push(row);
      row = [];
      field = '';
    } else if (ch !== '\r') field += ch;
  }
  row.push(field);
  rows.push(row);
  expect(rows.length).toBe(2);
  expect(rows.every((r) => r.length === 7)).toBe(true);
});
