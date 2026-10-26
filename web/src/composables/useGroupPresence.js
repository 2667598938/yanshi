import { watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { groupApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
import { presenceDeviceId } from '../utils/presence'
export function useGroupPresence(){
 const auth=useAuthStore(),timer=useTimerStore(),subjects=useSubjectsStore(),route=useRoute()
 function payload(){
  const hidden=document.visibilityState!=='visible',c=timer.current
  const status=hidden?'offline':timer.isResting&&!timer.rest?.finished?'resting':c&&!c.paused?'focusing':'idle'
  const rid=route.name==='room-detail'?Number(route.params.id):null
  return {device_id:presenceDeviceId(),room_id:!hidden&&rid>0?rid:null,status,
   subject_client_id:c?.subjectId||'',subject_name:subjects.byId[c?.subjectId]?.name||'',
   mode:c?.mode||'',activity_type:c?.activityType||'',focus_started_at:status==='focusing'?c.startedAt:null}
 }
 function beat(){if(auth.isLoggedIn)groupApi.presence(payload()).catch(()=>{})}
 function leave(){if(auth.accessToken)fetch('/api/v1/group/presence',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json',Authorization:`Bearer ${auth.accessToken}`},body:JSON.stringify({device_id:presenceDeviceId(),status:'offline'})}).catch(()=>{})}
 watch(()=>[auth.user?.id,timer.current?.startedAt,timer.isPaused,timer.isResting,timer.rest?.finished,route.fullPath],beat,{immediate:true})
 const interval=setInterval(beat,30000)
 document.addEventListener('visibilitychange',beat);window.addEventListener('pagehide',leave);window.addEventListener('yanshi:presence',beat)
 onBeforeUnmount(()=>{clearInterval(interval);document.removeEventListener('visibilitychange',beat);window.removeEventListener('pagehide',leave);window.removeEventListener('yanshi:presence',beat)})
}
