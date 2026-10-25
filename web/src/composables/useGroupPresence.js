import { watch, onBeforeUnmount } from 'vue'
import { groupApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
export function useGroupPresence() {
 const auth=useAuthStore(),timer=useTimerStore(),subjects=useSubjectsStore()
 function body(){
  if(document.visibilityState!=='visible')return {status:'offline'}
  if(timer.isResting)return {status:'resting'}
  const c=timer.current
  if(c&&!c.paused)return {status:'focusing',subject_client_id:c.subjectId||'',subject_name:subjects.byId[c.subjectId]?.name||'学习',mode:c.mode||'',activity_type:c.activityType||'',focus_started_at:c.startedAt}
  return {status:'idle'}
 }
 function beat(){if(auth.isLoggedIn)groupApi.presence(body()).catch(()=>{})}
 function leave(){if(auth.accessToken)fetch('/api/v1/group/presence',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json',Authorization:`Bearer ${auth.accessToken}`},body:JSON.stringify({status:'offline'})}).catch(()=>{})}
 watch(()=>[auth.user?.id,timer.current?.startedAt,timer.isPaused,timer.isResting],beat,{immediate:true})
 const interval=setInterval(beat,30000)
 document.addEventListener('visibilitychange',beat)
 window.addEventListener('pagehide',leave)
 onBeforeUnmount(()=>{clearInterval(interval);document.removeEventListener('visibilitychange',beat);window.removeEventListener('pagehide',leave)})
}
