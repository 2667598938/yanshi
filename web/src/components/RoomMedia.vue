<script setup>
import { ref, onBeforeUnmount, nextTick } from 'vue';
import { useAuthStore } from '../stores/auth';
const props = defineProps({ roomId: { type: Number, required: true } });
const auth = useAuthStore(),
  active = ref(false),
  connecting = ref(false),
  error = ref(''),
  videos = ref([]),
  selfVideo = ref(null),
  muted = ref(false),
  cameraOff = ref(false),
  needsAudio = ref(false);
let socket,
  stream,
  heartbeat,
  alive = true,
  generation = 0,
  iceServers = [],
  messageChain = Promise.resolve(),
  socketToken = '',
  lastRefresh = 0;
const peers = new Map(),
  candidates = new Map(),
  remoteElements = new Map();
function remoteVideo(element, user) {
  if (!element) return;
  remoteElements.set(user.id, element);
  element.srcObject = user.stream;
  element.play?.().catch(() => {
    needsAudio.value = true;
  });
}
async function playAudio() {
  for (const element of remoteElements.values()) await element.play?.().catch(() => {});
  needsAudio.value = false;
}
function send(type, to, payload) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type, to, payload }));
}
function closePeer(id) {
  peers.get(id)?.close();
  peers.delete(id);
  candidates.delete(id);
  remoteElements.delete(id);
  videos.value = videos.value.filter((row) => row.id !== id);
}
function peerFor(id, nickname) {
  if (peers.has(id)) return peers.get(id);
  const peer = new RTCPeerConnection({ iceServers });
  peers.set(id, peer);
  for (const track of stream.getTracks()) {
    const sender = peer.addTrack(track, stream);
    if (track.kind === 'video' && sender.getParameters && sender.setParameters) {
      const parameters = sender.getParameters();
      parameters.encodings = parameters.encodings?.length ? parameters.encodings : [{}];
      for (const encoding of parameters.encodings) {
        encoding.maxBitrate = 300000;
        encoding.maxFramerate = 15;
      }
      sender.setParameters(parameters).catch(() => {});
    }
  }
  peer.onicecandidate = (event) => {
    if (event.candidate) send('candidate', id, event.candidate.toJSON());
  };
  peer.ontrack = (event) => {
    if (!videos.value.some((row) => row.id === id))
      videos.value.push({
        id,
        nickname,
        stream: event.streams[0] || new MediaStream([event.track]),
      });
  };
  peer.onconnectionstatechange = () => {
    if (['failed', 'closed'].includes(peer.connectionState)) closePeer(id);
  };
  return peer;
}
async function message(event) {
  const data = JSON.parse(event.data);
  if (data.type === 'welcome') {
    iceServers = data.iceServers;
    active.value = true;
    connecting.value = false;
    for (const user of data.peers) {
      const peer = peerFor(user.id, user.nickname);
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      send('offer', user.id, peer.localDescription);
    }
  } else if (data.type === 'left') closePeer(data.id);
  else if (['offer', 'answer', 'candidate'].includes(data.type)) {
    const peer = peerFor(data.from, data.nickname);
    if (data.type === 'candidate') {
      if (peer.remoteDescription) await peer.addIceCandidate(data.payload);
      else {
        const queue = candidates.get(data.from) || [];
        queue.push(data.payload);
        candidates.set(data.from, queue);
      }
    } else {
      await peer.setRemoteDescription(data.payload);
      for (const candidate of candidates.get(data.from) || [])
        await peer.addIceCandidate(candidate);
      candidates.delete(data.from);
      if (data.type === 'offer') {
        await peer.setLocalDescription(await peer.createAnswer());
        send('answer', data.from, peer.localDescription);
      }
    }
  }
}
async function start(withCamera = true) {
  if (connecting.value || active.value) return;
  connecting.value = true;
  error.value = '';
  const seq = ++generation;
  try {
    if (!navigator.mediaDevices?.getUserMedia)
      throw new Error('当前浏览器不支持音视频，请使用HTTPS和较新的浏览器');
    if (!auth.accessToken && !(await auth.tryRefresh())) throw new Error('请重新登录');
    const captured = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
      video: withCamera
        ? { width: { ideal: 640 }, height: { ideal: 360 }, frameRate: { ideal: 15, max: 20 } }
        : false,
    });
    if (!alive || seq !== generation) {
      captured.getTracks().forEach((track) => track.stop());
      return;
    }
    stream = captured;
    cameraOff.value = !withCamera;
    await nextTick();
    if (selfVideo.value) selfVideo.value.srcObject = stream;
    socket = new WebSocket(
      `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/v1/rooms/${props.roomId}/media`,
    );
    socketToken = auth.accessToken;
    lastRefresh = Date.now();
    const connection = socket;
    connection.onopen = () => {
      if (seq !== generation) {
        connection.close();
        return;
      }
      connection.send(JSON.stringify({ token: socketToken }));
      heartbeat = setInterval(async () => {
        if (Date.now() - lastRefresh > 15 * 60000) {
          await auth.tryRefresh();
          lastRefresh = Date.now();
        }
        if (seq !== generation) return;
        if (
          auth.accessToken &&
          auth.accessToken !== socketToken &&
          connection.readyState === WebSocket.OPEN
        ) {
          socketToken = auth.accessToken;
          connection.send(JSON.stringify({ type: 'auth', token: socketToken }));
        }
        send('ping');
      }, 25000);
    };
    socket.onmessage = (event) => {
      messageChain = messageChain
        .then(() => (alive && seq === generation ? message(event) : undefined))
        .catch(() => {
          if (seq === generation) {
            error.value = '音视频连接失败，可退出后重试';
            stop();
          }
        });
    };
    socket.onerror = () => {
      if (seq === generation) error.value = '暂时无法连接，请检查网络后重试';
    };
    socket.onclose = () => {
      if (seq !== generation) return;
      if (active.value || connecting.value) error.value ||= '音视频连接已断开，请重新加入';
      stop();
    };
  } catch (e) {
    if (seq === generation) {
      error.value =
        e.name === 'NotAllowedError'
          ? '未获得设备权限，请在浏览器的网站设置中允许后重试'
          : e.message || '无法开启音视频';
      stop();
    }
  }
}
function stop() {
  generation++;
  clearInterval(heartbeat);
  if (socket) {
    socket.onclose = null;
    socket.onopen = null;
    socket.close();
    socket = null;
  }
  for (const id of [...peers.keys()]) closePeer(id);
  stream?.getTracks().forEach((track) => track.stop());
  stream = null;
  if (selfVideo.value) selfVideo.value.srcObject = null;
  active.value = false;
  connecting.value = false;
  muted.value = false;
  cameraOff.value = false;
  needsAudio.value = false;
  messageChain = Promise.resolve();
}
function toggleAudio() {
  muted.value = !muted.value;
  stream?.getAudioTracks().forEach((track) => (track.enabled = !muted.value));
}
function toggleVideo() {
  cameraOff.value = !cameraOff.value;
  stream?.getVideoTracks().forEach((track) => (track.enabled = !cameraOff.value));
}
onBeforeUnmount(() => {
  alive = false;
  stop();
});
</script>
<template>
  <section class="card room-media" aria-label="音视频共学">
    <header>
      <h2>和同桌一起学</h2>
      <span>{{ active ? videos.length + 1 : 0 }} / 6 在线</span>
    </header>
    <p v-if="!active">按需开启摄像头或仅开麦，离开房间页面时自动关闭设备。</p>
    <p v-if="error" role="alert" class="media-error">{{ error }}</p>
    <div v-show="active || connecting" class="media-grid">
      <figure class="self-video">
        <video ref="selfVideo" autoplay muted playsinline aria-label="我的画面"></video
        ><span v-if="cameraOff" class="camera-placeholder">摄像头已关闭</span>
        <figcaption>我{{ muted ? ' · 已静音' : '' }}</figcaption>
      </figure>
      <figure v-for="user in videos" :key="user.id">
        <video
          :ref="(element) => remoteVideo(element, user)"
          autoplay
          playsinline
          :aria-label="user.nickname + '的画面'"
        ></video>
        <figcaption>{{ user.nickname }}</figcaption>
      </figure>
    </div>
    <button v-if="needsAudio" class="btn btn-outline btn-block" @click="playAudio">
      点击播放研友声音
    </button>
    <div class="media-actions">
      <template v-if="!active"
        ><button class="btn btn-primary" :disabled="connecting" @click="start(true)">
          {{ connecting ? '正在连接…' : '开启摄像头共学' }}</button
        ><button class="btn btn-outline" :disabled="connecting" @click="start(false)">
          仅开麦
        </button></template
      >
      <template v-else
        ><button class="btn btn-outline" @click="toggleAudio">
          {{ muted ? '取消静音' : '静音' }}</button
        ><button
          v-if="stream?.getVideoTracks().length"
          class="btn btn-outline"
          @click="toggleVideo"
        >
          {{ cameraOff ? '打开画面' : '关闭画面' }}</button
        ><button class="btn btn-danger" @click="stop">关闭音视频</button></template
      >
    </div>
  </section>
</template>
<style scoped>
.room-media {
  margin-top: 16px;
  grid-column: 1/-1;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
h2 {
  font-size: 16px;
  margin: 0;
}
header span,
p {
  font-size: 12px;
  color: var(--sub);
}
.media-error {
  color: #b42318;
}
.media-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 12px 0;
}
figure {
  position: relative;
  aspect-ratio: 4/3;
  border-radius: 16px;
  overflow: hidden;
  margin: 0;
  background: #1d2038;
}
video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.self-video video {
  transform: scaleX(-1);
}
figcaption {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 6px 8px;
  font-size: 12px;
  color: white;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
}
.camera-placeholder {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #d9def5;
  font-size: 12px;
}
.media-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.media-actions .btn {
  flex: 1;
  gap: 6px;
  white-space: nowrap;
  font-size: 12px;
}
@media (min-width: 900px) {
  .media-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
