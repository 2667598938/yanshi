import { watch, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import { groupApi, roomApi } from '../api'
import { useAuthStore } from '../stores/auth'
import { useTimerStore } from '../stores/timer'
import { useSubjectsStore } from '../stores/subjects'
import { presenceDeviceId } from '../utils/presence'
import { useStudyRoomStore } from '../stores/studyRoom'
export function useGroupPresence(){
 const auth=useAuthStore(),timer=useTimerStore(),subjects=useSubjectsStore(),route=useRoute()
 const studyRoom=useStudyRoomStore()
 watch(()=>auth.user?.id,async id=>{
  studyRoom.load(id)
  if(!id||auth.isSuperAdmin||studyRoom.room)return
  const revision=studyRoom.revision
  try{
   const rooms=await roomApi.list()
   if(auth.user?.id!==id||studyRoom.revision!==revision||studyRoom.room)return
   const joined=rooms.find(room=>room.joined||room.my_role==='owner')
   if(joined)studyRoom.enter(joined,id)
  }catch{/* Keep the last confirmed membership when offline. */}
 },{immediate:true})
 function payload(){
  const hidden=document.visibilityState!=='visible',c=timer.current
  const status=hidden?'away':timer.isResting&&!timer.rest?.finished?'resting':c&&!c.paused?'focusing':'idle'
  const rid=studyRoom.room?.id || null
  return {device_id:presenceDeviceId(),room_id:rid,status,
   subject_client_id:c?.subjectId||'',subject_name:subjects.byId[c?.subjectId]?.name||'',
   mode:c?.mode||'',activity_type:c?.activityType||'',focus_started_at:status==='focusing'?c.startedAt:null,
   focus_elapsed_sec:status==='focusing'?Math.min(10800,Math.max(0,Math.floor(timer.elapsedSec||0))):null}
 }
 async function beat(){
  if(!auth.isLoggedIn||auth.isSuperAdmin)return
  const body=payload(),owner=auth.user?.id
  try{
   const result=await groupApi.presence(body)
   if(owner===auth.user?.id && studyRoom.room?.id===body.room_id && result && Object.hasOwn(result,'roomId') && result.roomId===null)studyRoom.leave()
  }catch{/* Next heartbeat retries; expiry handles disconnected devices. */}
 }
 function leave(){if(auth.accessToken)fetch('/api/v1/group/presence',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json',Authorization:`Bearer ${auth.accessToken}`},body:JSON.stringify({device_id:presenceDeviceId(),status:'offline'})}).catch(()=>{})}
 watch(()=>[auth.user?.id,timer.current?.startedAt,timer.isPaused,timer.isResting,timer.rest?.finished,route.fullPath,studyRoom.room?.id],beat,{immediate:true})
 const interval=setInterval(beat,10000)
 document.addEventListener('visibilitychange',beat);window.addEventListener('pagehide',leave);window.addEventListener('yanshi:presence',beat)
 onBeforeUnmount(()=>{clearInterval(interval);document.removeEventListener('visibilitychange',beat);window.removeEventListener('pagehide',leave);window.removeEventListener('yanshi:presence',beat)})
}
