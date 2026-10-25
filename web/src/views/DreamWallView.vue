<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, MapPin, Quote, ChevronRight } from 'lucide-vue-next'
import { SCHOOLS } from '../data/schools'

const router = useRouter()
const active = ref(null)
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">梦校墙</div>
    </div>

    <div class="page">
      <div class="wall-hero">
        <div class="wh-title">把想去的地方，贴在每天看得见的地方</div>
        <div class="wh-sub">七所梦校 · 总有一个名字让你坐直</div>
      </div>

      <div class="school-grid">
        <button
          v-for="s in SCHOOLS"
          :key="s.key"
          class="school-card"
          :style="{ '--sc': s.color }"
          @click="active = s"
        >
          <img class="sc-view" :src="s.view" :alt="s.name" />
          <div class="sc-body">
            <img class="sc-logo" :src="s.logo" :alt="s.name" />
            <div class="sc-main">
              <div class="sc-name">{{ s.name }}</div>
              <div class="sc-city"><MapPin :size="11" />{{ s.city }}</div>
            </div>
            <ChevronRight :size="16" class="sc-arrow" />
          </div>
        </button>
      </div>
    </div>

    <div v-if="active" class="mask" @click.self="active = null">
      <div class="sheet" :style="{ '--sc': active.color }">
        <img class="big-view" :src="active.view" :alt="active.name" />
        <div class="big-body">
          <img class="big-logo" :src="active.logo" :alt="active.name" />
          <div>
            <div class="big-name">{{ active.name }}</div>
            <div class="big-city"><MapPin :size="12" />{{ active.city }}</div>
          </div>
        </div>
        <div class="motto"><Quote :size="15" />{{ active.motto }}</div>
        <button class="btn btn-ghost btn-block" @click="active = null">收好，继续学</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back { border: none; background: #fff; width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: var(--sub); cursor: pointer; box-shadow: var(--shadow-soft); }
.wall-hero { border-radius: 16px; padding: 20px; background: linear-gradient(140deg, #0f1f3a, #31547f); color: #eef4ff; margin-bottom: 14px; }
.wh-title { font-size: 16.5px; font-weight: 700; line-height: 1.6; }
.wh-sub { font-size: 11.5px; color: rgba(238,244,255,.62); margin-top: 7px; }
.school-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.school-card { position: relative; border: none; padding: 0; border-radius: 14px; overflow: hidden; background: #fff; box-shadow: var(--shadow-soft); cursor: pointer; text-align: left; }
.sc-view { width: 100%; height: 88px; object-fit: cover; display: block; }
.sc-body { display: flex; align-items: center; gap: 8px; padding: 9px 10px; background: #fff; }
.sc-logo { width: 28px; height: 28px; border-radius: 50%; object-fit: cover; border: 1.5px solid var(--sc); }
.sc-main { flex: 1; min-width: 0; }
.sc-name { font-size: 12.5px; font-weight: 700; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sc-city { display: flex; align-items: center; gap: 2px; font-size: 10px; color: var(--faint); margin-top: 1px; }
.sc-arrow { color: #c9d2df; flex-shrink: 0; }
.mask { position: fixed; inset: 0; background: rgba(15,23,42,.5); display: flex; align-items: flex-end; justify-content: center; z-index: 150; }
.sheet { width: 100%; max-width: 520px; background: #fff; border-radius: 22px 22px 0 0; overflow: hidden; padding-bottom: calc(18px + env(safe-area-inset-bottom)); }
.big-view { width: 100%; height: 190px; object-fit: cover; display: block; }
.big-body { display: flex; align-items: center; gap: 11px; padding: 16px 18px 0; }
.big-logo { width: 46px; height: 46px; border-radius: 50%; object-fit: cover; border: 2px solid var(--sc); }
.big-name { font-size: 19px; font-weight: 800; }
.big-city { display: flex; align-items: center; gap: 3px; font-size: 11.5px; color: var(--faint); margin-top: 2px; }
.motto { display: flex; align-items: flex-start; gap: 6px; margin: 14px 18px; font-size: 14px; line-height: 1.7; color: var(--sc); font-weight: 600; }
.sheet .btn { width: calc(100% - 36px); margin: 0 18px; }
</style>
