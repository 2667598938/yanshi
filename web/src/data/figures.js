// 虚拟形象预设：一期用内置 emoji + 配色，不依赖图片资源。
export const FIGURES = [
  { id: 'figure-1', emoji: '🌱', name: '新芽', bg: '#e7f6f0' },
  { id: 'figure-2', emoji: '📖', name: '书虫', bg: '#e6f0fb' },
  { id: 'figure-3', emoji: '☕', name: '夜读', bg: '#f3ece2' },
  { id: 'figure-4', emoji: '🐱', name: '猫伴', bg: '#fff3df' },
  { id: 'figure-5', emoji: '🌙', name: '守夜', bg: '#eef0fe' },
  { id: 'figure-6', emoji: '🚀', name: '冲刺', bg: '#fdecec' },
  { id: 'figure-7', emoji: '🐧', name: '专注', bg: '#e6f7fb' },
  { id: 'figure-8', emoji: '🌲', name: '深埋', bg: '#eaf2e8' },
];

export const FIGURE_MAP = Object.fromEntries(FIGURES.map((f) => [f.id, f]));
