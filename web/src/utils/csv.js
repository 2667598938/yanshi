// CSV 导出：统一转义逗号、双引号、换行，并把毫秒时间戳转成本地时间。
import { fmtClock } from './time'

export function csvCell(value) {
  let text = value == null ? '' : String(value)
  // 防止 Excel 把单元格当公式执行
  if (/^[=+@-]/.test(text)) text = "'" + text
  if (/[",\r\n]/.test(text) || text !== text.trim()) {
    return '"' + text.replace(/"/g, '""') + '"'
  }
  return text
}

export function buildSessionsCsv(rows, subjectName, activityName) {
  const head = ['日期', '开始时间', '模式', '科目', '学习类型', '时长(分钟)', '备注']
  const lines = rows.map((s) => {
    const start = s.startedAt == null ? '' : fmtClock(s.startedAt)
    const mode = s.mode === 'stopwatch' ? '正向计时' : '番茄钟'
    return [
      csvCell(s.date),
      csvCell(start),
      csvCell(mode),
      csvCell(subjectName(s)),
      csvCell(activityName(s)),
      csvCell(Math.round((s.actualSec || 0) / 60)),
      csvCell(s.note || ''),
    ].join(',')
  })
  return '\ufeff' + [head.map(csvCell).join(','), ...lines].join('\r\n')
}
