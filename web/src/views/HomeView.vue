<script setup>
import { computed, ref } from 'vue'
import SchoolHero from '../components/SchoolHero.vue'
import { useRouter } from 'vue-router'
import { Play, Pause, Square, Plus, ChevronRight, NotebookPen, Sparkles, BarChart3 } from 'lucide-vue-next'
import { useTimerStore } from '../stores/timer'
import { useTasksStore } from '../stores/tasks'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import { useClockStore } from '../stores/clock'
import { useToast } from '../composables/useToast'
import { fmtClock, diffDayKeys } from '../utils/date'
const router=useRouter(),timer=useTimerStore(),tasks=useTasksStore(),app=useAppStore(),auth=useAuthStore(),clock=useClockStore()
const {toast}=useToast()
const title=ref(''),saving=ref(false)
const days=computed(()=>diffDayKeys(clock.today,auth.user?.exam_date || app.examDate || '2027-12-25'))
const goal=computed(()=>Math.max(1,Number(auth.user?.daily_goal_min || app.dailyGoalMin || 300)))
const progress=computed(()=>Math.min(100,Math.round(timer.todayMin/goal.value*100)))
const todayTasks=computed(()=>[...tasks.todayAll].sort((a,b)=>a.done-b.done).slice(0,4))
async function add(){if(saving.value||!title.value.trim())return;saving.value=true;try{await tasks.add({title:title.value,dueDate:clock.today});title.value=''}catch(e){toast(e.message||'添加失败')}finally{saving.value=false}}
async function toggle(task){try{await tasks.toggle(task.id)}catch(e){toast(e.message||'更新失败')}}
function pause(){try{timer.isPaused?timer.resume():timer.pause()}catch(e){toast(e.message)}}
async function finish(){try{await timer.finish(false)}catch(e){toast(e.message||'保存失败，请重试')}}
</script>
<template>
 <div class="home-layout"><SchoolHero v-if="!app.heroCollapsed"/><div class="page home-dashboard"><header class="home-greeting"><div><small>今天也向梦校靠近一点</small><h1>{{auth.user?.nickname || app.nickname}}，欢迎回来</h1></div><button class="btn btn-outline" @click="app.setHeroCollapsed(!app.heroCollapsed)">{{app.heroCollapsed ? '展开梦校' : '收起梦校'}}</button></header>
  <router-link class="exam-strip" to="/settings/time-nodes"><span>考研初试{{days<0?'已过去':'还有'}} <strong>{{Math.abs(days)}}</strong> 天</span><ChevronRight :size="16"/></router-link>
  <section class="card today-overview" aria-label="今日概览">
   <div><strong class="tnum">{{Math.round(timer.todayMin)}}</strong><span>今日分钟</span></div>
   <div><strong class="tnum">{{timer.todayCount}}</strong><span>专注颗数</span></div>
   <div><strong class="tnum">{{timer.streak}}</strong><span>连续天数</span></div>
  </section>
  <section class="focus-card" aria-label="专注计时">
   <template v-if="timer.current">
    <router-link to="/focus" class="running-clock"><span>{{timer.isPaused?'已暂停':timer.isStopwatch?'正在专注 · 正向计时':'正在专注 · 倒计时'}}</span><strong class="tnum">{{fmtClock(timer.isStopwatch?timer.elapsedSec:timer.remainingSec)}}</strong></router-link>
    <div class="focus-actions"><button class="btn btn-outline" @click="pause"><component :is="timer.isPaused?Play:Pause" :size="18"/>{{timer.isPaused?'继续':'暂停'}}</button><button class="btn btn-primary" :disabled="timer.persisting" @click="finish"><Square :size="16"/>结束并保存</button></div>
   </template>
   <button v-else class="btn btn-primary start-focus" @click="router.push('/focus')"><Play :size="24"/><span>{{timer.isResting?'休息中 · 查看计时':'开始一次专注'}}</span><ChevronRight :size="20"/></button>
  </section>
  <section class="goal-card" aria-label="今日目标">
   <div><strong>今日目标</strong><span>{{(timer.todayMin/60).toFixed(1)}} / {{goal/60}} 小时</span></div>
   <div class="goal-track" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100" aria-label="今日目标完成进度"><span :style="{width:progress+'%'}"></span></div>
  </section>
  <section class="card today-tasks">
   <header><h1>今日任务</h1><router-link to="/tasks">全部 {{tasks.todayAll.length}} 项 <ChevronRight :size="16"/></router-link></header>
   <p v-if="!todayTasks.length" class="empty">写下一个小目标，开始今天的学习。</p>
   <label v-for="task in todayTasks" :key="task.id" class="task-row"><input type="checkbox" :checked="!!task.done" @change="toggle(task)"/><span :class="{done:task.done}">{{task.title}}</span></label>
   <form @submit.prevent="add"><input v-model="title" aria-label="新任务" maxlength="200" placeholder="添加今天要完成的事"/><button class="btn btn-primary" type="submit" :disabled="saving||!title.trim()" aria-label="添加任务"><Plus :size="20"/></button></form>
  </section>
  <nav class="home-shortcuts" aria-label="学习快捷入口"><router-link to="/mistakes"><NotebookPen :size="20"/>错题复习</router-link><router-link to="/ai"><Sparkles :size="20"/>AI 助教</router-link><router-link to="/stats"><BarChart3 :size="20"/>学习统计</router-link></nav>
 </div></div>
</template>
<style scoped>
.home-greeting{display:flex;align-items:center;justify-content:space-between;gap:12px}.home-greeting small{color:var(--sub);font-size:12px}.home-greeting h1{font-size:20px;line-height:28px;margin:4px 0}.home-greeting .btn{font-size:12px;flex-shrink:0}.home-dashboard{display:grid;gap:12px;max-width:900px;margin:auto;padding-top:12px}.exam-strip{display:flex;justify-content:space-between;align-items:center;padding:4px 12px;min-height:36px;border-radius:8px;background:var(--glass);color:var(--primary-deep);font-size: 14px;text-decoration:none}.exam-strip strong{font-size: 16px}
.today-overview{display:grid;grid-template-columns:repeat(3,1fr);padding:12px!important;margin:0!important;text-align:center}.today-overview>div+div{border-left:1px solid var(--line)}.today-overview strong{display:block;font-size: 24px;line-height:32px}.today-overview span{font-size: 14px;color:var(--sub)}
.focus-card{background:var(--primary);border-radius:16px;overflow:hidden}.start-focus{width:100%;min-height:76px!important;font-size: 20px!important;display:flex;gap:12px;padding:16px}.start-focus span{flex:1;text-align:left}.running-clock{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 16px;color:#fff;text-decoration:none}.running-clock span{font-size: 14px}.running-clock strong{font-size: 24px}.focus-actions{display:flex;gap:8px;padding:0 12px 12px}.focus-actions button{flex:1;display:flex;align-items:center;justify-content:center;gap:8px}.focus-actions .btn-primary{border-color:#fff}
.goal-card{padding:0 4px}.goal-card>div:first-child{display:flex;justify-content:space-between;font-size: 14px;line-height:24px}.goal-card span{color:var(--sub)}.goal-track{height:8px;background:var(--line);border-radius:8px;overflow:hidden;margin-top:8px}.goal-track span{display:block;height:100%;background:var(--primary);border-radius:8px}
.today-tasks{padding:12px!important;margin:0!important}.today-tasks header{display:flex;justify-content:space-between;align-items:center;gap:8px}.today-tasks h1{font-size: 16px;line-height:24px;margin:0}.today-tasks header a{display:flex;align-items:center;font-size: 14px;color:var(--sub);text-decoration:none}.empty{font-size: 14px;color:var(--sub);margin:12px 0}.task-row{display:flex;align-items:center;gap:8px;min-height:36px;font-size: 14px}.task-row input{width:18px;height:18px;accent-color:var(--primary)}.task-row span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.done{text-decoration:line-through;color:var(--sub)}form{display:flex;gap:8px;margin-top:8px}form>input{flex:1;min-width:0;border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size: 14px;background:var(--bg)}form .btn{padding:8px 12px}
.home-shortcuts{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.home-shortcuts a{display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;color:var(--primary);font-size: 14px;padding:8px 0}
@media(min-width:1024px){.home-dashboard{gap:16px;padding-top:24px}.start-focus{min-height:96px!important}.today-tasks{padding:16px!important}}
</style>
