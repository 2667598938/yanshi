<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import BlobImage from './BlobImage.vue'
import { schoolApi } from '../api'
import { db } from '../db'
import { Check, Target, MapPin } from 'lucide-vue-next'
import { SCHOOLS, SCHOOL_MAP } from '../data/schools'
import { useAppStore } from '../stores/app'
import { useProfileStore } from '../stores/profile'
import { useToast } from '../composables/useToast'
import { daysUntil, weekLabel } from '../utils/date'
import TimeNodesHome from './TimeNodesHome.vue'

const schools = ref([])
const app = useAppStore()
const profile = useProfileStore()
const { toast } = useToast()
let carousel
let alive = true
let lastManual = 0
function mergeSchools(rows) {
  if (!Array.isArray(rows)) return
  schools.value = rows.map((row) => {
    const local = SCHOOL_MAP[row.key] || { color: '#526484', logo: '', view: '', motto: '', city: '' }
    return { ...local, ...row.info, key: row.key, name: row.name, short: row.short,
      logo: row.logo_key || local.logo, view: row.album_keys?.[0] || local.view,
      album: row.album_keys?.length ? row.album_keys : [local.view] }
  })
  const target = schools.value.findIndex(row => row.key === app.dreamSchool)
  if (!lastManual && target >= 0) browseIndex.value = target
  else if (browseIndex.value >= schools.value.length) browseIndex.value = 0
}
const albumIndex = ref(0)
const campusImage = computed(() => school.value.view)
onMounted(async () => {
  const cached = await db.kv.get('schools:catalog')
  if (!alive) return
  mergeSchools(cached?.value)
  carousel = setInterval(() => {
    if (document.visibilityState !== 'visible' || Date.now() - lastManual < 10000) return
    if (schools.value.length) browseIndex.value = (browseIndex.value + 1) % schools.value.length
  }, 6000)
  try {
    const rows = await schoolApi.list()
    if (!alive) return
    mergeSchools(rows)
    await db.kv.put({ key: 'schools:catalog', value: rows })
  } catch { /* 保留已缓存目录和内置七校素材 */ }
})
onBeforeUnmount(() => { alive = false; clearInterval(carousel) })
const dreamIndex = computed(() =>
  schools.value.findIndex((s) => s.key === app.dreamSchool)
)
const browseIndex = ref(dreamIndex.value >= 0 ? dreamIndex.value : 3)

const school = computed(() => schools.value[browseIndex.value] || schools.value[0] || { key:'',name:'我的梦校',color:'#526484',logo:'',view:'',motto:'自由添加你的目标院校',city:'' })
const isDream = computed(() => school.value.key === app.dreamSchool)
const days = computed(() => daysUntil(app.examDate))


const examDate = computed(() => {
  const d = new Date(app.examDate + 'T00:00:00')
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日 · ${weekLabel(d)}`
})

function pick(i) {
  browseIndex.value = i
  albumIndex.value = 0
  lastManual = Date.now()
}
async function setDream() {
  if (!isDream.value) {
    try { await profile.save({ target_school: school.value.key }) }
    catch (e) { toast(e.message) }
  }
}
</script>

<template>
  <div class="hero" :style="{ '--sc': school.color }">
    <BlobImage :key="school.key + campusImage" class="hero-bg" :src="campusImage" :alt="school.name" />
    <div class="hero-veil"></div>

    <div class="hero-inner">
      <div class="hero-top">
        <BlobImage class="seal" :src="school.logo" :alt="school.name + '校徽'" />
        <div class="school-meta">
          <button class="school-name" style="background:transparent;border:none;color:inherit" @click="$router.push({path:'/dream-wall',query:{school:school.key}})">{{ school.name }} · 查看相册</button>
          <div class="school-motto">{{ school.motto }}</div>
          <div class="school-city">
            <MapPin :size="11" :stroke-width="2.4" />
            <span>{{ school.city }}</span>
          </div>
        </div>
        <button
          class="dream-btn"
          :class="{ on: isDream }"
          @click="setDream"
        >
          <component :is="isDream ? Check : Target" :size="14" :stroke-width="2.6" />
          <span>{{ isDream ? '我的梦校' : '设为目标' }}</span>
        </button>
      </div>

      <TimeNodesHome />

      <div class="school-strip">
        <div
          v-for="(s, i) in schools"
          :key="s.key"
          class="strip-item"
          :class="{ active: i === browseIndex, dream: s.key === app.dreamSchool }"
          @click="pick(i)"
        >
          <BlobImage :src="s.logo" :alt="s.short" />
          <span v-if="s.key === app.dreamSchool" class="dream-mark">
            <Check :size="8" :stroke-width="3.5" />
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  min-height: 408px;
  color: #fff;
  overflow: hidden;
  background: var(--night);
}
.hero-bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  animation: bg-in 0.45s ease;
}
@keyframes bg-in {
  from {
    opacity: 0.3;
    transform: scale(1.04);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}
.hero-veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(15, 28, 54, 0.55) 0%,
    rgba(15, 28, 54, 0.28) 34%,
    rgba(15, 28, 54, 0.66) 78%,
    rgba(14, 24, 46, 0.94) 100%
  );
}
.hero-inner {
  position: relative;
  z-index: 2;
  padding: 20px 18px 16px;
  min-height: 408px;
  display: flex;
  flex-direction: column;
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 12px;
}
.seal {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  object-fit: cover;
  background: #fff;
  border: 2px solid rgba(255, 255, 255, 0.75);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}
.school-meta {
  flex: 1;
  min-width: 0;
}
.school-name {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.5px;
}
.school-motto {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.86);
  margin-top: 1px;
}
.school-city {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.72);
  margin-top: 2px;
}
.dream-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  backdrop-filter: blur(4px);
}
.dream-btn.on {
  background: var(--sc);
  border-color: transparent;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.22);
}

.countdown {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  margin-top: 18px;
}
.cd-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  letter-spacing: 1px;
}
.cd-num-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 2px;
}
.cd-num {
  font-size: 78px;
  font-weight: 900;
  line-height: 1;
  color: var(--accent);
  text-shadow: 0 4px 22px rgba(240, 168, 48, 0.4);
  letter-spacing: -2px;
}
.cd-unit {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
}
.cd-date {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.quote {
  text-align: center;
  font-size: 13.5px;
  color: #ffe9c4;
  margin: 12px 0 16px;
  letter-spacing: 0.5px;
}

.school-strip {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  padding: 4px 2px 2px;
}
.strip-item {
  position: relative;
  width: 38px;
  height: 38px;
  cursor: pointer;
  border-radius: 50%;
  opacity: 0.62;
  transition: all 0.18s ease;
}
.strip-item img {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  object-fit: cover;
  background: #fff;
  border: 1.5px solid rgba(255, 255, 255, 0.5);
}
.strip-item.active {
  opacity: 1;
  transform: scale(1.16);
}
.strip-item.active img {
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.25);
}
.dream-mark {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--accent);
  color: #3a2700;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #fff;
}
</style>
