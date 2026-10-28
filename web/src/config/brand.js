// 品牌入口：替换名称、Logo、文案、颜色、时长与播放策略只需改这里。
export const BRAND = Object.freeze({
  name: '研时',
  fallbackName: '考研学习平台',
  logoSrc: '/favicon.svg',
  tagline: '每一份坚持，都在靠近理想。',
  supportingText: '专注当下 · 稳步向前',
  colors: {
    background: '#F7F8FA', wash: '#E8EEF5', primary: '#647D9D',
    title: '#293241', secondary: '#7D8793', accent: '#B9A57D',
  },
  opening: {
    enabled: true,
    policy: 'session', // session：本次标签页访问一次；always：每次加载；off：关闭。
    storageKey: 'yanshi:brand-opening:v1',
    durationMs: 3000,
    fadeOutMs: 700,
    skipFadeMs: 160,
    reducedDurationMs: 500,
    reducedFadeMs: 160,
    characterStepMs: 50,
    particleCount: 20,
  },
})

export function brandColorVars(brand = BRAND) {
  return Object.fromEntries(Object.entries(brand.colors).map(([key, value]) => [`--brand-${key}`, value]))
}
