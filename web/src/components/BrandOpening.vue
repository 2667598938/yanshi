<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { BRAND, brandColorVars } from '../config/brand'

const props = defineProps({ brand: { type: Object, default: () => BRAND }, siteName: { type: String, default: '' } })
const emit = defineEmits(['done'])
const visible = ref(true), leaving = ref(false), fallbackLogo = ref(false), skipButton = ref(null)
const media = window.matchMedia?.('(prefers-reduced-motion: reduce)')
const reduced = ref(media?.matches ?? false)
const settings = props.brand.opening
const totalMs = Math.max(500, settings.durationMs)
const regularFadeMs = Math.min(totalMs, settings.fadeOutMs)
const ratio = totalMs / 3800
const exitMs = ref(reduced.value ? settings.reducedFadeMs : regularFadeMs)
// 动画开始前冻结完整名称；所有字符从一开始占位，不改变行的居中位置。
const name = ref(props.siteName.trim() || props.brand.name || props.brand.fallbackName)
let nameLocked = false, nameTimer
watch(() => props.siteName, value => { if (!nameLocked && value.trim()) name.value = value.trim() })
const characters = computed(() => Array.from(name.value))
const characterStep = computed(() => Math.min(settings.characterStepMs, 450 / Math.max(1, characters.value.length - 1)))
const particles = Array.from({ length: settings.particleCount }, (_, index) => ({
  left: `${3 + (index * 37 + 9) % 94}%`, top: `${7 + (index * 29 + 11) % 87}%`,
  size: `${1 + index % 5 * .3}px`, duration: `${12 + index % 5 * 2}s`, delay: `${-(index % 7) * 1.7}s`,
  drift: `${index % 2 ? -4 : 5}px`, gold: index % 4 === 0, blurred: index % 3 === 0,
}))
const colors = computed(() => ({ ...brandColorVars({ colors: settings.colors || props.brand.colors }), '--opening-exit-ms': `${exitMs.value}ms`,
  '--opening-logo-delay': `${400 * ratio}ms`, '--opening-logo-ms': `${700 * ratio}ms`,
  '--opening-tagline-delay': `${1600 * ratio}ms`, '--opening-support-delay': `${1900 * ratio}ms`,
}))
let fadeTimer, finishTimer, completed = false, restored = false
let previousOverflow, previousFocus, pageRoot, previousHidden, previousInert

function restorePage() {
  if (restored) return
  restored = true
  document.documentElement.classList.remove('brand-opening-active', 'brand-opening-leaving')
  document.body.style.overflow = previousOverflow ?? ''
  if (pageRoot) {
    if (previousHidden === null) pageRoot.removeAttribute('aria-hidden')
    else pageRoot.setAttribute('aria-hidden', previousHidden)
    if (!previousInert) pageRoot.removeAttribute('inert')
  }
}
function complete() {
  if (completed) return
  completed = true
  clearTimeout(fadeTimer); clearTimeout(finishTimer); clearTimeout(nameTimer)
  restorePage()
  visible.value = false
  if (previousFocus?.isConnected && previousFocus !== document.body) previousFocus.focus?.({ preventScroll: true })
  else document.getElementById('main-content')?.focus({ preventScroll: true })
  emit('done')
}
function fade(duration = regularFadeMs) {
  if (completed) return
  if (leaving.value && exitMs.value <= duration) return
  clearTimeout(fadeTimer); clearTimeout(finishTimer)
  exitMs.value = duration
  leaving.value = true
  document.documentElement.style.setProperty('--brand-crossfade-ms', `${duration}ms`)
  document.documentElement.classList.add('brand-opening-leaving')
  finishTimer = setTimeout(complete, duration)
}
function skip() { fade(settings.skipFadeMs) }
function schedule() {
  clearTimeout(fadeTimer); clearTimeout(finishTimer)
  const duration = reduced.value ? settings.reducedDurationMs : totalMs
  const fadeDuration = reduced.value ? settings.reducedFadeMs : regularFadeMs
  exitMs.value = fadeDuration
  fadeTimer = setTimeout(() => fade(fadeDuration), Math.max(0, duration - fadeDuration))
}
function motionChanged(event) {
  if (event.matches) reduced.value = true
  if (reduced.value && !completed) {
    if (leaving.value) fade(settings.reducedFadeMs)
    else schedule()
  }
}
function onKey(event) {
  if (completed) return
  if (event.key === 'Escape') { event.preventDefault(); skip() }
  if (event.key === 'Tab') { event.preventDefault(); skipButton.value?.focus({ preventScroll: true }) }
}
function onVisibility() { if (document.visibilityState === 'hidden') complete() }
onMounted(async () => {
  previousOverflow = document.body.style.overflow
  previousFocus = document.activeElement
  pageRoot = document.getElementById('app')
  previousHidden = pageRoot?.getAttribute('aria-hidden') ?? null
  previousInert = pageRoot?.hasAttribute('inert') ?? false
  pageRoot?.setAttribute('inert', '')
  pageRoot?.setAttribute('aria-hidden', 'true')
  document.body.style.overflow = 'hidden'
  document.documentElement.style.setProperty('--brand-crossfade-ms', `${exitMs.value}ms`)
  document.documentElement.classList.add('brand-opening-active')
  media?.addEventListener('change', motionChanged)
  document.addEventListener('keydown', onKey)
  document.addEventListener('visibilitychange', onVisibility)
  schedule()
  nameTimer = setTimeout(() => { nameLocked = true }, 950 * ratio)
  await nextTick()
  if (!completed) skipButton.value?.focus({ preventScroll: true })
})
onBeforeUnmount(() => {
  clearTimeout(fadeTimer); clearTimeout(finishTimer); clearTimeout(nameTimer)
  media?.removeEventListener('change', motionChanged)
  document.removeEventListener('keydown', onKey)
  document.removeEventListener('visibilitychange', onVisibility)
  restorePage()
})
</script>

<template>
  <Teleport to="body">
    <section v-if="visible" class="brand-opening" :class="{ 'is-leaving': leaving, 'is-reduced': reduced }" :style="colors" role="dialog" aria-modal="true" aria-labelledby="opening-name">
      <div class="opening-backdrop" aria-hidden="true"><i class="soft-glow glow-a"></i><i class="soft-glow glow-b"></i><i class="soft-glow glow-c"></i></div>
      <div class="opening-particles" aria-hidden="true"><i v-for="(particle, index) in particles" :key="index" class="dust" :class="{ gold: particle.gold, blurred: particle.blurred }" :style="{ left: particle.left, top: particle.top, width: particle.size, height: particle.size, '--dust-duration': particle.duration, '--dust-delay': particle.delay, '--dust-drift': particle.drift }"></i></div>
      <svg class="campus-line" viewBox="0 0 1440 170" preserveAspectRatio="xMidYMax slice" fill="none" aria-hidden="true">
        <path d="M0 151H1440M170 151V108H330V151M212 108V86H290V108M1110 151V108H1270V151M1150 108V86H1230V108M510 151V77L720 20L930 77V151M510 77H930M565 151V92H875V151M680 151V98H760V151M660 43H780" />
        <path d="M196 122H217M242 122H263M288 122H309M1135 122H1156M1181 122H1202M1227 122H1248M592 105V136M620 105V136M648 105V136M792 105V136M820 105V136M848 105V136M693 98V151M720 98V151M747 98V151" />
      </svg>
      <button ref="skipButton" type="button" class="opening-skip" @click="skip">跳过<span aria-hidden="true">↗</span></button>
      <div class="opening-content">
        <div class="logo-stage"><div class="logo-glow" aria-hidden="true"></div><span class="logo-ring ring-blue" aria-hidden="true"></span><span class="logo-ring ring-gold" aria-hidden="true"></span><span class="logo-ring ring-outer" aria-hidden="true"></span>
          <div class="opening-logo"><img v-if="brand.logoSrc && !fallbackLogo" :src="brand.logoSrc" alt="" @error="fallbackLogo = true" /><svg v-else viewBox="0 0 96 96" fill="none" aria-label="书本标志"><path d="M48 26C37 19 24 19 13 23V70C25 66 37 68 48 75C59 68 71 66 83 70V23C72 19 59 19 48 26ZM48 26V75" /><path class="book-path" d="M25 36C31 35 36 36 41 39M25 47C31 46 36 47 41 50M57 39L65 32L71 36L79 28" /></svg></div>
        </div>
        <h1 id="opening-name" class="opening-name" :aria-label="name"><span v-for="(character, index) in characters" :key="index" aria-hidden="true" :style="{ animationDelay: `${(1000 + index * characterStep) * ratio}ms` }">{{ character }}</span></h1>
        <p class="opening-tagline">{{ brand.tagline }}</p>
        <p class="opening-support">{{ brand.supportingText }}</p>
      </div>
    </section>
  </Teleport>
</template>

<style scoped>
.brand-opening { position: fixed; inset: 0; z-index: 10000; isolation: isolate; display: grid; place-items: center; width: 100%; height: 100%; min-height: 100dvh; padding: max(72px,env(safe-area-inset-top)) max(24px,env(safe-area-inset-right)) max(56px,env(safe-area-inset-bottom)) max(24px,env(safe-area-inset-left)); overflow: hidden; background: var(--brand-background); color: var(--brand-title); opacity: 1; transition: opacity var(--opening-exit-ms) cubic-bezier(.22,.61,.36,1); }
.brand-opening.is-leaving { opacity: 0; }
.opening-backdrop { position: absolute; inset: 0; z-index: -2; overflow: hidden; background: radial-gradient(ellipse at 50% 38%,var(--brand-primary) 0,transparent 64%),linear-gradient(180deg,var(--brand-wash),var(--brand-background) 95%); animation: backdrop-arrive 500ms ease-out both; }
.soft-glow { position: absolute; width: min(24vw,420px); height: 130%; top: -15%; border-radius: 50%; filter: blur(100px); background: var(--brand-accent); opacity: .035; transform: rotate(12deg); animation: quiet-light 18s ease-in-out infinite alternate; }
.glow-a { left: 5%; }
.glow-b { right: 9%; animation-delay: -5s; opacity: .025; }
.glow-c { left: 43%; animation-delay: -9s; opacity: .018; }
.opening-particles { position: absolute; inset: 0; z-index: -1; pointer-events: none; animation: backdrop-arrive 500ms ease both; }
.dust { position: absolute; border-radius: 50%; background: var(--brand-accent); opacity: 0; animation: floating-dust var(--dust-duration) var(--dust-delay) ease-in-out infinite; }
.dust.gold { background: var(--brand-accent); }
.dust.blurred { filter: blur(.6px); }
.campus-line { position: absolute; bottom: max(8px,env(safe-area-inset-bottom)); width: 100%; height: clamp(60px,18svh,180px); z-index: -1; color: #200205; stroke: #d6b366; fill: currentColor; stroke-width: .6; opacity: .13; pointer-events: none; }
.opening-skip { position: absolute; top: max(18px,env(safe-area-inset-top)); right: max(22px,env(safe-area-inset-right)); display: inline-flex; align-items: center; justify-content: center; gap: 10px; min-height: 44px; padding: 7px 15px; border: 1px solid #d6b36638; border-radius: 24px; background: #30060940; color: #f3ebddc9; font-size: 14px; font-weight: 400; cursor: pointer; transition: background .2s ease; }
.opening-skip:hover { background: #d6b36614; border-color: #d6b36670; }
.opening-skip:focus-visible { outline: 2px solid var(--brand-primary); outline-offset: 4px; }
.opening-content { width: 100%; max-width: 800px; min-width: 0; text-align: center; transform: translateY(-4svh); }
.logo-stage { --logo-size: clamp(72px,20vw,88px); position: relative; width: var(--logo-size); height: var(--logo-size); margin: 0 auto 34px; }
.logo-glow { position: absolute; inset: -28%; border-radius: 50%; background: var(--brand-accent); filter: blur(36px); opacity: .12; }
.opening-logo { position: relative; z-index: 1; width: 100%; height: 100%; opacity: 0; animation: logo-arrive var(--opening-logo-ms) var(--opening-logo-delay) cubic-bezier(.22,.61,.36,1) both; }
.opening-logo img { display: block; width: 100%; height: 100%; object-fit: contain; }
.opening-logo svg { display: block; width: 100%; height: 100%; color: var(--brand-primary); stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.opening-logo .book-path { stroke: var(--brand-accent); stroke-width: 1.6; }
.logo-ring { position: absolute; inset: 0; border: 1px solid var(--brand-accent); border-radius: 50%; opacity: 0; pointer-events: none; animation: breathing-ring 2200ms 500ms ease-out infinite; }
.ring-gold { animation-delay: 1200ms; }
.ring-outer { animation-delay: 1900ms; }
.opening-name { margin: 0; width: 100%; min-height: 1.55em; color: var(--brand-title); font-family: 'Noto Serif SC','Songti SC','STSong','SimSun',serif; font-size: clamp(24px,3vw,40px); font-weight: 500; line-height: 1.55; letter-spacing: .16em; overflow-wrap: anywhere; }
.opening-name span { display: inline-block; white-space: pre-wrap; opacity: 0; animation: name-arrive 450ms cubic-bezier(.22,.61,.36,1) both; }
.opening-tagline { margin: 17px 0 0; color: var(--brand-accent); font-size: clamp(13px,1.3vw,17px); font-weight: 400; line-height: 1.9; letter-spacing: .08em; opacity: 0; animation: text-arrive 600ms var(--opening-tagline-delay) ease-out both; }
.opening-support { margin: 14px 0 0; color: var(--brand-secondary); font-size: clamp(10px,1vw,12px); font-weight: 400; line-height: 1.8; letter-spacing: .26em; opacity: 0; animation: text-arrive 400ms var(--opening-support-delay) ease-out both; }
@keyframes backdrop-arrive { from { opacity: 0; } to { opacity: 1; } }
@keyframes quiet-light { from { transform: translate3d(0,0,0) rotate(12deg); } to { transform: translate3d(10px,-8px,0) rotate(13deg); } }
@keyframes floating-dust { 0%,100% { opacity: 0; transform: translate3d(0,0,0); } 28% { opacity: .32; } 70% { opacity: .14; } 99% { opacity: 0; transform: translate3d(var(--dust-drift),-24px,0); } }
@keyframes logo-arrive { from { opacity: 0; transform: scale(.85); } to { opacity: 1; transform: scale(1); } }
@keyframes breathing-ring { from { transform: scale(.98); opacity: .2; } to { transform: scale(1.6); opacity: 0; } }
@keyframes name-arrive { from { opacity: 0; filter: blur(2px); transform: translateY(4px); } to { opacity: 1; filter: blur(0); transform: translateY(0); } }
@keyframes text-arrive { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }
@media (min-width: 960px) { .logo-stage { --logo-size: clamp(96px,12vmin,120px); margin-bottom: 38px; } .opening-name { font-size: clamp(32px,3vw,40px); } }
@media (max-width: 520px) { .opening-name { font-size: 27px; } .opening-content { transform: translateY(-3svh); } .opening-tagline { letter-spacing: .02em; } .dust:nth-child(n+13) { display: none; } .soft-glow { width: 80vw; filter: blur(42px); } }
@media (max-height: 520px) { .brand-opening { padding-top: 58px; padding-bottom: 22px; } .opening-content { transform: none; } .logo-stage { --logo-size: 64px; margin-bottom: 16px; } .opening-name { font-size: 25px; line-height: 1.4; } .opening-tagline { margin-top: 8px; font-size: 14px; } .opening-support { margin-top: 7px; font-size: 12px; } .campus-line { opacity: .05; } }
@media (max-height: 340px) { .brand-opening { padding-top: 48px; padding-bottom: 12px; } .logo-stage { --logo-size: 48px; margin-bottom: 10px; } .opening-name { font-size: 20px; } .opening-tagline { margin-top: 4px; font-size: 14px; } .opening-support { margin-top: 4px; } .opening-skip { min-height: 32px; top: 10px; right: 14px; } }
.is-reduced :is(.soft-glow,.opening-particles,.logo-ring) { display: none; }
.is-reduced :is(.opening-backdrop,.opening-logo,.opening-name span,.opening-tagline,.opening-support) { animation: none; opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) { .brand-opening { transition-duration: 160ms !important; } .soft-glow,.opening-particles,.logo-ring { display: none; } .opening-backdrop,.opening-logo,.opening-name span,.opening-tagline,.opening-support { animation: none !important; opacity: 1; transform: none; } }
</style>
