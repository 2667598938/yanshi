<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: { type: Number, default: 0 }, // 0 ~ 1
  size: { type: Number, default: 268 },
  stroke: { type: Number, default: 16 },
  color: { type: String, default: '#f2705b' },
  startColor: { type: String, default: '#ff9d8a' },
  track: { type: String, default: 'rgba(255,255,255,0.14)' },
})

const center = computed(() => props.size / 2)
const r = computed(() => (props.size - props.stroke) / 2)
const circumference = computed(() => 2 * Math.PI * r.value)
const offset = computed(() => circumference.value * (1 - props.progress))
</script>

<template>
  <div class="ring" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size">
      <defs>
        <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" :stop-color="startColor" />
          <stop offset="100%" :stop-color="color" />
        </linearGradient>
      </defs>
      <circle
        :cx="center"
        :cy="center"
        :r="r"
        :stroke="track"
        :stroke-width="stroke"
        fill="none"
      />
      <circle
        class="prog"
        :cx="center"
        :cy="center"
        :r="r"
        stroke="url(#ringGrad)"
        :stroke-width="stroke"
        fill="none"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
        :style="{ transform: `rotate(-90deg)`, transformOrigin: 'center' }"
      />
    </svg>
    <div class="ring-center"><slot /></div>
  </div>
</template>

<style scoped>
.ring {
  position: relative;
  margin: 0 auto;
}
.ring svg {
  display: block;
}
.prog {
  transition: stroke-dashoffset 0.5s linear;
}
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
</style>
