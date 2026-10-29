<script setup>
import {ref,onBeforeUnmount} from 'vue'
import {useAuthStore} from '../stores/auth'
const props=defineProps({roomId:{type:Number,required:true}})
const auth=useAuthStore(),active=ref(false),connecting=ref(false),error=ref(''),videos=ref([]),selfVideo=ref(null),muted=ref(false),cameraOff=ref(false)
let socket,stream,heartbeat,alive=true,generation=0,iceServers=[],messageChain=Promise.resolve()
const peers=new Map(),candidates=new Map()
function send(type,to,payload){if(socket?.readyState===WebSocket.OPEN)socket.send(JSON.stringify({type,to,payload}))}
function closePeer(id){peers.get(id)?.close();peers.delete(id);candidates.delete(id);videos.value=videos.value.filter(row=>row.id!==id)}
function peerFor(id,nickname){
 if(peers.has(id))return peers.get(id)
 const peer=new RTCPeerConnection({iceServers});peers.set(id,peer)
 for(const track of stream.getTracks())peer.addTrack(track,stream)
 peer.onicecandidate=event=>{if(event.candidate)send('candidate',id,event.candidate.toJSON())}
 peer.ontrack=event=>{if(!videos.value.some(row=>row.id===id))videos.value.push({id,nickname,stream:event.streams[0]})}
 peer.onconnectionstatechange=()=>{if(['failed','closed'].includes(peer.connectionState))closePeer(id)}
 return peer
}
async function message(event){
 const data=JSON.parse(event.data)
 if(data.type==='welcome'){
  iceServers=data.iceServers;active.value=true;connecting.value=false
  for(const user of data.peers){const peer=peerFor(user.id,user.nickname);const offer=await peer.createOffer();await peer.setLocalDescription(offer);send('offer',user.id,peer.localDescription)}
 }else if(data.type==='left')closePeer(data.id)
 else if(['offer','answer','candidate'].includes(data.type)){
  const peer=peerFor(data.from,data.nickname)
  if(data.type==='candidate'){
   if(peer.remoteDescription)await peer.addIceCandidate(data.payload)
   else{const queue=candidates.get(data.from)||[];queue.push(data.payload);candidates.set(data.from,queue)}
  }else{
   await peer.setRemoteDescription(data.payload)
   for(const candidate of candidates.get(data.from)||[])await peer.addIceCandidate(candidate)
   candidates.delete(data.from)
   if(data.type==='offer'){await peer.setLocalDescription(await peer.createAnswer());send('answer',data.from,peer.localDescription)}
  }
 }
}
async function start(){
 if(connecting.value||active.value)return
 connecting.value=true;error.value='';const seq=++generation
 try{
  if(!navigator.mediaDevices?.getUserMedia)throw new Error('当前浏览器不支持音视频，请使用HTTPS和较新的浏览器')
  if(!auth.accessToken&&!await auth.tryRefresh())throw new Error('请重新登录')
  const captured=await navigator.mediaDevices.getUserMedia({audio:true,video:{width:{ideal:640},height:{ideal:360}}})
  if(!alive||seq!==generation){captured.getTracks().forEach(track=>track.stop());return}
  stream=captured;if(selfVideo.value)selfVideo.value.srcObject=stream
  socket=new WebSocket(`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/api/v1/rooms/${props.roomId}/media`)
  socket.onopen=()=>{socket.send(JSON.stringify({token:auth.accessToken}));heartbeat=setInterval(()=>send('ping'),25000)}
  socket.onmessage=event=>{messageChain=messageChain.then(()=>alive&&seq===generation?message(event):undefined).catch(()=>{if(seq===generation){error.value='音视频连接失败，可退出后重试';stop()}})}
  socket.onerror=()=>{error.value='无法连接音视频服务'}
  socket.onclose=()=>{if(active.value||connecting.value)error.value||='音视频连接已断开，请重新加入';stop()}
 }catch(e){error.value=e.message||'无法获取麦克风或摄像头权限';stop()}
}
function stop(){generation++;clearInterval(heartbeat);if(socket){socket.onclose=null;socket.close();socket=null}for(const id of peers.keys())closePeer(id);stream?.getTracks().forEach(track=>track.stop());stream=null;if(selfVideo.value)selfVideo.value.srcObject=null;active.value=false;connecting.value=false;muted.value=false;cameraOff.value=false}
function toggleAudio(){muted.value=!muted.value;stream?.getAudioTracks().forEach(track=>track.enabled=!muted.value)}
function toggleVideo(){cameraOff.value=!cameraOff.value;stream?.getVideoTracks().forEach(track=>track.enabled=!cameraOff.value)}
onBeforeUnmount(()=>{alive=false;stop()})
</script>
<template><section class="card room-media"><h2>音视频共学</h2><p>由你主动开启摄像头和麦克风，离开即停止采集。网络受限时可能需要 TURN 中继。</p><p v-if="error" role="alert">{{error}}</p><video ref="selfVideo" autoplay muted playsinline v-show="active||connecting" aria-label="本机画面"></video><div class="remote-videos"><figure v-for="user in videos" :key="user.id"><video :ref="el=>{if(el)el.srcObject=user.stream}" autoplay playsinline></video><figcaption>{{user.nickname}}</figcaption></figure></div><div class="media-actions"><button v-if="!active" class="btn btn-primary" :disabled="connecting" @click="start">{{connecting?'正在连接…':'开启音视频'}}</button><template v-else><button class="btn btn-outline" @click="toggleAudio">{{muted?'打开麦克风':'静音'}}</button><button class="btn btn-outline" @click="toggleVideo">{{cameraOff?'打开摄像头':'关闭摄像头'}}</button><button class="btn btn-danger" @click="stop">退出音视频</button></template></div></section></template>
<style scoped>h2{font-size:16px;margin:0}p,figcaption{font-size:12px;color:var(--sub)}video{max-width:100%;width:240px;background:#213a2c;border-radius:12px}.remote-videos,.media-actions{display:flex;flex-wrap:wrap;gap:8px}figure{margin:0}.media-actions{margin-top:12px}</style>
