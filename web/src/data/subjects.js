// 默认科目（内置，首次启动写入 Dexie，用户可增删改）
export const DEFAULT_SUBJECTS = [
  { id: 'math', name: '数学', color: '#2563eb', icon: 'Calculator' },
  { id: 'cs408', name: '408', color: '#7c3aed', icon: 'Cpu' },
  { id: 'english', name: '英语', color: '#059669', icon: 'BookOpen' },
  { id: 'politics', name: '政治', color: '#dc2626', icon: 'Flag' },
  { id: 'algo', name: '算法刷题', color: '#0891b2', icon: 'Code2' },
  { id: 'project', name: '项目开发', color: '#ea580c', icon: 'Hammer' },
  { id: 'recite', name: '八股背诵', color: '#d97706', icon: 'GraduationCap' },
  { id: 'other', name: '其他', color: '#64748b', icon: 'MoreHorizontal' },
]

// 自定义科目可选图标（lucide 名）
export const SUBJECT_ICONS = [
  'Calculator', 'Cpu', 'BookOpen', 'Flag', 'Code2', 'Hammer',
  'GraduationCap', 'MoreHorizontal', 'Brain', 'PenLine', 'Sigma',
  'Binary', 'Database', 'Globe', 'Beaker', 'Language', 'Palette',
  'Music', 'Briefcase', 'FlaskConical', 'Dumbbell', 'Camera',
]

// 自定义科目可选颜色
export const SUBJECT_COLORS = [
  '#2563eb', '#7c3aed', '#059669', '#dc2626', '#0891b2',
  '#ea580c', '#d97706', '#64748b', '#db2777', '#16a34a',
  '#0ea5e9', '#9333ea',
]

// 学习类型（用于区分听课 / 刷题 / 复盘 / 背诵，防止只听课不做题）
export const ACTIVITIES = [
  { id: 'listen', name: '听课', color: '#0ea5e9', icon: 'Headphones' },
  { id: 'practice', name: '刷题', color: '#f2705b', icon: 'PenLine' },
  { id: 'review', name: '复盘', color: '#f0a830', icon: 'RotateCcw' },
  { id: 'recite', name: '背诵', color: '#7c3aed', icon: 'BookMarked' },
]
export const ACTIVITY_MAP = Object.fromEntries(ACTIVITIES.map((a) => [a.id, a]))

// 可选倒计时时长（分钟）
export const DURATIONS = [25, 45, 50, 90]
export const MIN_DURATION = 5
export const MAX_DURATION = 180

// 复习阶段（艾宾浩斯，单位：天）
export const REVIEW_INTERVALS = [1, 2, 4, 7, 15, 30]

// 考研阶段（任务用）
export const PHASES = [
  { id: 'base', name: '基础', color: '#0ea5e9' },
  { id: 'intensive', name: '强化', color: '#7c3aed' },
  { id: 'pastpaper', name: '真题', color: '#f2705b' },
  { id: 'sprint', name: '冲刺', color: '#dc2626' },
  { id: 'custom', name: '日常', color: '#64748b' },
]
export const PHASE_MAP = Object.fromEntries(PHASES.map((p) => [p.id, p]))

// 错题错误原因
export const MISTAKE_REASONS = [
  { id: 'calc', name: '计算失误' },
  { id: 'concept', name: '概念不清' },
  { id: 'review', name: '审题错误' },
  { id: 'method', name: '思路/方法' },
  { id: 'careless', name: '粗心大意' },
  { id: 'other', name: '其他' },
]
export const REASON_MAP = Object.fromEntries(MISTAKE_REASONS.map((r) => [r.id, r]))
