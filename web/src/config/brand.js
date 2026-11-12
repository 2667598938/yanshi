// 品牌入口：替换名称、Logo、文案、颜色、时长与播放策略只需改这里。
export const BRAND = Object.freeze({
  name: '研时',
  fallbackName: '考研学习平台',
  logoSrc: '/brand/yanshi-symbol.svg',
  iconSrc: '/favicon.svg',
  tagline: '每一份坚持，都在靠近理想。',
  supportingText: '专注当下 · 稳步向前',
  colors: {
    background: '#F7F8FA',
    wash: '#F2E9E8',
    primary: '#7B2632',
    title: '#293241',
    secondary: '#7D8793',
    accent: '#D6B366',
  },
  opening: {
    enabled: true,
    policy: 'session', // session：本次标签页访问一次；always：每次加载；off：关闭。
    storageKey: 'yanshi:brand-opening:v2',
    colors: {
      background: '#300609',
      wash: '#650E16',
      primary: '#921C24',
      title: '#F3EBDD',
      secondary: '#BDAE9C',
      accent: '#D6B366',
    },
    durationMs: 3800,
    fadeOutMs: 700,
    skipFadeMs: 160,
    reducedDurationMs: 500,
    reducedFadeMs: 160,
    characterStepMs: 60,
    particleCount: 18,
  },
});

export function brandColorVars(brand = BRAND) {
  return Object.fromEntries(
    Object.entries(brand.colors).map(([key, value]) => [`--brand-${key}`, value]),
  );
}
