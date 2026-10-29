<script setup>
import { useRoute } from 'vue-router'
import { useTimerStore } from '../stores/timer'
import { useStudyRoomStore } from '../stores/studyRoom'
import { fmtClock } from '../utils/date'
const route=useRoute(),timer=useTimerStore(),studyRoom=useStudyRoomStore()
</script>
<template>
 <div v-if="(studyRoom.room || ((timer.current || timer.rest) && route.name!=='focus')) && route.name!=='login'" class="study-status-bar">
  <router-link v-if="(timer.current || timer.rest) && route.name!=='focus'" to="/focus">{{timer.rest?'休息':timer.isPaused?'已暂停':'本轮专注'}} <span class="tnum">{{fmtClock(timer.rest?timer.restRemainingSec:timer.elapsedSec)}}</span> · 返回计时</router-link>
  <router-link v-if="studyRoom.room" :to="`/rooms/${studyRoom.room.id}`">共学 · {{studyRoom.room.name}}</router-link>
  <button v-if="studyRoom.room" @click="studyRoom.leave()">离开共学</button>
 </div>
</template>
<style scoped>
.study-status-bar{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:6px 16px;padding:7px 12px;background:var(--card,#fff);border-bottom:1px solid var(--line);color:var(--ink);font-size:12px;line-height:1.5}
a{color:inherit;text-decoration:none;overflow-wrap:anywhere}button{border:0;background:transparent;color:var(--sub);text-decoration:underline;font:inherit;cursor:pointer}.tnum{font-weight:600}
</style>
