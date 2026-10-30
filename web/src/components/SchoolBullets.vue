<script setup>
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useLearningSettingsStore } from '../stores/learningSettings'
import { inspirationApi } from '../api'
import { useToast } from '../composables/useToast'
import { useRouter } from 'vue-router'
import { PencilLine } from 'lucide-vue-next'
import { QUOTES } from '../data/quotes'
const { toast }=useToast()
const router=useRouter()
const saving=ref(false), ready=ref(false)
const auth=useAuthStore(), settings=useLearningSettingsStore()
const quotes=ref(QUOTES.slice(0,8)), index=ref(0), paused=ref(false), hidden=ref(document.visibilityState==='hidden')
const showEditor=ref(false), draft=ref('')
const reduced=ref(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false)
const media=window.matchMedia?.('(prefers-reduced-motion: reduce)')
const motionChanged=e=>{reduced.value=e.matches}
media?.addEventListener('change',motionChanged)
const visible=()=>{hidden.value=document.visibilityState==='hidden'}
document.addEventListener('visibilitychange',visible)
const customText=computed(()=>String(settings.value.bulletText||'').trim())
const text=computed(()=>customText.value || quotes.value[index.value%quotes.value.length])
function openEditor(){draft.value=settings.value.bulletText||'';showEditor.value=true}
async function saveBullet(){
 if(saving.value)return
 saving.value=true
 try{
  await settings.save({...settings.value,bulletText:draft.value})
  showEditor.value=false
  toast(draft.value.trim()?'弹幕已保存到本机，联网后自动同步':'已在本机恢复公共弹幕，联网后自动同步')
 }catch(e){toast(e.message||'弹幕保存失败，请重试')}
 finally{saving.value=false}
}
async function clearBullet(){
 if(saving.value)return
 saving.value=true
 try{
  await settings.save({...settings.value,bulletText:''})
  draft.value=''
  showEditor.value=false
  toast('已在本机恢复公共弹幕，联网后自动同步')
 }catch(e){toast(e.message||'弹幕保存失败，请重试')}
 finally{saving.value=false}
}
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
  <div class="bullet-actions">
    <button type="button" class="bullet-toggle" :disabled="saving||!ready" :aria-pressed="settings.value.bulletEnabled" @click="toggle">{{settings.value.bulletEnabled?'关闭梦校弹幕':'开启梦校弹幕'}}</button>
    <button type="button" class="bullet-edit" :disabled="!ready" @click="openEditor"><PencilLine :size="12" />编辑</button>
    <button type="button" class="bullet-link" title="在励志区投稿，或撤回自己的弹幕" @click="router.push('/inspirations')">投稿/管理</button>
  </div>
 </div>
 <Teleport to="body">
  <div v-if="showEditor" class="bullet-mask" @click.self="showEditor=false">
    <div class="bullet-sheet">
      <div class="bs-head">
        <strong>编辑我的梦校弹幕</strong>
        <button type="button" class="bs-close" aria-label="关闭弹幕编辑" @click="showEditor=false">×</button>
      </div>
      <p class="bs-hint">只在自己的账号与设备显示；留空或点“恢复公共弹幕”即可回到励志区公共文案。</p>
      <textarea v-model="draft" maxlength="80" rows="3" placeholder="写一句给自己的话…"></textarea>
      <div class="bs-count">{{ draft.length }} / 80</div>
      <button class="btn btn-primary btn-block" :disabled="saving" @click="saveBullet">保存</button>
      <button class="btn btn-ghost btn-block mt8" :disabled="saving" @click="showEditor=false">取消</button>
      <button v-if="settings.value.bulletText" class="btn btn-ghost btn-block mt8" :disabled="saving" @click="clearBullet">恢复公共弹幕</button>
    </div>
  </div>
 </Teleport>
</template>
<style scoped>
.school-bullets{margin:10px 0;display:flex;flex-direction:column;gap:4px;min-width:0}
.bullet-window{width:100%;min-width:0;overflow:hidden;contain:paint;height:30px;position:relative}
.bullet{display:inline-block;white-space:nowrap;font-size: 14px;line-height:30px;animation:school-bullet 14s linear both;text-shadow:0 1px 3px #0008}
.bullet.still{animation:none;white-space:normal;line-height:1.4}.bullet.paused{animation-play-state:paused}
.bullet-actions{display:flex;align-items:center;justify-content:flex-end;gap:6px;flex-wrap:wrap}
.bullet-toggle{flex-shrink:0;border:1px solid #ffffff60;border-radius:16px;background:rgba(30,27,75,.55);color:inherit;font-size: 12px;padding:6px 9px;cursor:pointer;transition:background-color .24s ease,border-color .24s ease}
.bullet-link{flex-shrink:0;border:none;background:transparent;color:rgba(255,255,255,.78);font-size: 12px;text-decoration:underline;text-underline-offset:2px;cursor:pointer;padding:6px 2px}
.bullet-edit{display:inline-flex;align-items:center;gap:3px;flex-shrink:0;border:1px solid #ffffff55;border-radius:14px;background:rgba(255,255,255,.12);color:#fff;font-size: 12px;padding:6px 8px;cursor:pointer}
.bullet-edit:disabled{opacity:.5;cursor:not-allowed}
.bullet-mask{position:fixed;inset:0;z-index:320;background:rgba(30,27,75,.45);display:flex;align-items:flex-end;justify-content:center;padding-top:max(8px,env(safe-area-inset-top))}
.bullet-sheet{width:100%;max-width:520px;background:#fff;color:var(--ink);border-radius:24px 24px 0 0;padding:22px 16px max(24px,env(safe-area-inset-bottom));max-height:calc(100dvh - 16px);overflow-y:auto}
.bs-head{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size: 16px}
.bs-close{width:32px;height:32px;border:1px solid var(--line);border-radius:50%;background:#fff;color:var(--sub);font-size: 20px;line-height:1;cursor:pointer}
.bs-hint{font-size: 14px;color:var(--sub);line-height:1.7;margin:10px 0}
.bullet-sheet textarea{width:100%;box-sizing:border-box;border:1px solid var(--line);border-radius:12px;padding:10px 12px;font-size: 14px;line-height:1.7;resize:vertical;min-height:88px;background:#fbfcff;color:var(--ink)}
.bs-count{text-align:right;font-size: 12px;color:var(--faint);margin:6px 0 12px}
@keyframes school-bullet{from{transform:translateX(240px)}to{transform:translateX(-100%)}}
@media(prefers-reduced-motion:reduce){.bullet{animation:none;white-space:normal;line-height:1.4}.bullet-window{height:auto}}
</style>
