<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useLearningSettingsStore } from '../stores/learningSettings'
import { inspirationApi } from '../api'
import { useToast } from '../composables/useToast'
import { QUOTES } from '../data/quotes'
const { toast }=useToast()
const saving=ref(false), ready=ref(false)
const auth=useAuthStore(), settings=useLearningSettingsStore()
const quotes=ref(QUOTES.slice(0,8)), index=ref(0), paused=ref(false), hidden=ref(document.visibilityState==='hidden')
const reduced=ref(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
const media=window.matchMedia?.('(prefers-reduced-motion: reduce)')
const motionChanged=e=>{reduced.value=e.matches}
media?.addEventListener('change',motionChanged)
const visible=()=>{hidden.value=document.visibilityState==='hidden'}
document.addEventListener('visibilitychange',visible)
const text=computed(()=>quotes.value[index.value%quotes.value.length])
let timer, generation=0
watch(()=>auth.user?.id,async()=>{
  ready.value=false
  const seq=++generation;quotes.value=QUOTES.slice(0,8);index.value=0
  await settings.load(true).catch(()=>{})
  if(seq!==generation)return
  ready.value=true
  try{
    const rows=await inspirationApi.bullets()
    if(seq!==generation)return
    const clean=rows.map(row=>row.content?.trim()).filter(Boolean)
    if(clean.length)quotes.value=[...new Set(clean)]
  }catch{/* 离线或励志区关闭时使用内置固定文案 */}
},{immediate:true})
watch(()=>settings.value.bulletEnabled,enabled=>{
  clearInterval(timer)
  if(enabled)timer=setInterval(()=>{if(!hidden.value&&!paused.value&&!reduced.value)index.value++},14000)
},{immediate:true})
async function toggle(){
 if(saving.value||!ready.value)return
 saving.value=true
 try{await settings.save({...settings.value,bulletEnabled:!settings.value.bulletEnabled})}
 catch(e){toast(e.message||'弹幕设置未保存，请重试')}
 finally{saving.value=false}
}
onBeforeUnmount(()=>{generation++;clearInterval(timer);media?.removeEventListener('change',motionChanged);document.removeEventListener('visibilitychange',visible)})
</script>
<template>
 <div class="school-bullets" @mouseenter="paused=true" @mouseleave="paused=false" @focusin="paused=true" @focusout="paused=false">
  <div v-if="settings.value.bulletEnabled" class="bullet-window" aria-hidden="true" @mouseenter="paused=true" @mouseleave="paused=false">
   <span :key="index" class="bullet" :class="{still:reduced,paused:paused||hidden}">{{text}}</span>
  </div>
  <button type="button" class="bullet-toggle" :disabled="saving||!ready" :aria-pressed="settings.value.bulletEnabled" @click="toggle">{{settings.value.bulletEnabled?'关闭梦校弹幕':'开启梦校弹幕'}}</button>
 </div>
</template>
<style scoped>
.school-bullets{margin:12px 0;display:flex;align-items:center;gap:10px;min-width:0}
.bullet-window{flex:1;min-width:0;overflow:hidden;contain:paint;height:30px;position:relative}
.bullet{display:inline-block;white-space:nowrap;font-size:12px;line-height:30px;animation:school-bullet 14s linear both;text-shadow:0 1px 3px #0008}
.bullet.still{animation:none;white-space:normal;line-height:1.4}.bullet.paused{animation-play-state:paused}
.bullet-toggle{margin-left:auto;flex-shrink:0;border:1px solid #ffffff60;border-radius:16px;background:#18263e80;color:inherit;font-size:11px;padding:7px 10px;cursor:pointer}
@keyframes school-bullet{from{transform:translateX(240px)}to{transform:translateX(-100%)}}
@media(prefers-reduced-motion:reduce){.bullet{animation:none;white-space:normal;line-height:1.4}.bullet-window{height:auto}}
</style>
