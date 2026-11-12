// 统一时间格式化：后端返回 UTC ISO（带 Z），这里统一转成浏览器本地时区展示。
function pad(n) {
  return String(n).padStart(2, '0');
}

function toDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** YYYY-MM-DD HH:mm */
export function fmtDateTime(value) {
  const d = toDate(value);
  if (!d) return '';
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

/** MM-DD HH:mm */
export function fmtShort(value) {
  const d = toDate(value);
  if (!d) return '';
  return (
    `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` + `${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

/** YYYY-MM-DD */
export function fmtDate(value) {
  const d = toDate(value);
  if (!d) return '';
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** HH:mm */
export function fmtClock(value) {
  const d = toDate(value);
  if (!d) return '';
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
