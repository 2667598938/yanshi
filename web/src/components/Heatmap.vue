<script setup>
import { computed } from 'vue'
import { fmtMinutes } from '../utils/date'

const props = defineProps({
  view: { type: String, default: 'year' },
  yearWeeks: { type: Array, default: () => [] },
  monthWeeks: { type: Array, default: () => [] },
  monthLabs: { type: Array, default: () => [] },
  weekDays: { type: Array, default: () => [] },
  selected: { type: String, default: '' },
})
const emit = defineEmits(['select'])

const DOW = ['一', '二', '三', '四', '五', '六', '日']
const monthDays = computed(() => props.monthWeeks.flat())

function level(cell) {
  if (cell.future) return 'f'
  if (!cell.min) return 'l0'
  if (cell.min < 30) return 'l1'
  if (cell.min < 60) return 'l2'
  if (cell.min < 120) return 'l3'
  return 'l4'
}
function dowOf(key) {
  return DOW[((new Date(key + 'T00:00:00').getDay() + 6) % 7)]
}
function dayNum(key) {
  return Number(key.slice(8, 10))
}
</script>

<template>
  <div class="heatmap-root">
    <!-- 年视图 -->
    <div v-if="view === 'year'" class="hm-year">
      <div class="hm-months">
        <span
          v-for="ml in monthLabs"
          :key="ml.col"
          class="hm-ml"
          :style="{ left: (ml.col / Math.max(yearWeeks.length, 1)) * 100 + '%' }"
        >{{ ml.name }}</span>
      </div>
      <div class="hm-cols">
        <div v-for="(col, ci) in yearWeeks" :key="ci" class="hm-col">
          <div
            v-for="cell in col"
            :key="cell.key"
            class="hm-cell"
            :class="[level(cell), { dim: !cell.inYear, active: selected === cell.key }]"
            @click="emit('select', cell.key)"
            @mouseenter="emit('select', cell.key)"
          ></div>
        </div>
      </div>
    </div>

    <!-- 月视图 -->
    <div v-else-if="view === 'month'" class="hm-month">
      <div class="cal-dow">
        <span v-for="(d, i) in DOW" :key="i">{{ d }}</span>
      </div>
      <div class="cal-grid">
        <div
          v-for="cell in monthDays"
          :key="cell.key"
          class="cal-cell"
          :class="[level(cell), { dim: !cell.inMonth, active: selected === cell.key }]"
          @click="emit('select', cell.key)"
          @mouseenter="emit('select', cell.key)"
        >
          <span class="cal-num">{{ dayNum(cell.key) }}</span>
          <span v-if="cell.min" class="cal-min tnum">{{ cell.min >= 60 ? (cell.min / 60).toFixed(1).replace(/\.0$/, '') + 'h' : cell.min + 'm' }}</span>
        </div>
      </div>
    </div>

    <!-- 周视图 -->
    <div v-else class="hm-week">
      <div
        v-for="cell in weekDays"
        :key="cell.key"
        class="wk-cell"
        :class="{ active: selected === cell.key, future: cell.future }"
        @click="emit('select', cell.key)"
      >
        <span class="wk-dow">周{{ dowOf(cell.key) }}</span>
        <span class="wk-date">{{ cell.key.slice(5).replace('-', '/') }}</span>
        <span class="wk-min tnum">{{ cell.min ? fmtMinutes(cell.min) : '—' }}</span>
      </div>
    </div>
  </div>

  <div class="legend">
    <span>少</span>
    <i class="lg l0"></i>
    <i class="lg l1"></i>
    <i class="lg l2"></i>
    <i class="lg l3"></i>
    <i class="lg l4"></i>
    <span>多</span>
  </div>
</template>

<style scoped>
.heatmap-root {
  width: 100%;
}
/* 年视图 */
.hm-months {
  position: relative;
  height: 16px;
  margin-bottom: 4px;
}
.hm-ml {
  position: absolute;
  font-size: 10px;
  color: var(--faint);
  transform: translateX(0);
}
.hm-cols {
  display: flex;
  gap: 2px;
}
.hm-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.hm-cell {
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 2px;
  cursor: pointer;
  transition: transform 0.08s;
}
.hm-cell.dim {
  opacity: 0.28;
}
.hm-cell.active {
  outline: 2px solid var(--ink);
  outline-offset: 1px;
}

/* 月视图 */
.cal-dow,
.cal-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 5px;
}
.cal-dow {
  margin-bottom: 6px;
}
.cal-dow span {
  text-align: center;
  font-size: 11px;
  color: var(--faint);
}
.cal-cell {
  aspect-ratio: 1 / 1;
  border-radius: 9px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  cursor: pointer;
}
.cal-cell.dim {
  opacity: 0.3;
}
.cal-cell.active {
  outline: 2px solid var(--ink);
  outline-offset: 1px;
}
.cal-num {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink);
}
.cal-cell.f .cal-num {
  color: var(--faint);
}
.cal-cell:not(.l0):not(.f) .cal-num {
  color: #fff;
}
.cal-min {
  font-size: 9px;
  font-weight: 700;
  color: #fff;
}
.cal-cell.l1 .cal-min,
.cal-cell.l2 .cal-num,
.cal-cell.l2 .cal-min {
  color: #8a3a2c;
}
.cal-cell.l2 .cal-num,
.cal-cell.l2 .cal-min {
  color: #8a3a2c;
}

/* 周视图 */
.hm-week {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.wk-cell {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-radius: 12px;
  background: #f6f9fc;
  border: 1.5px solid transparent;
  cursor: pointer;
}
.wk-cell.future {
  opacity: 0.5;
}
.wk-cell.active {
  border-color: var(--primary);
  background: #eef5fb;
}
.wk-dow {
  font-size: 13px;
  font-weight: 700;
  width: 40px;
}
.wk-date {
  font-size: 12px;
  color: var(--faint);
  flex: 1;
}
.wk-min {
  font-size: 15px;
  font-weight: 800;
  color: var(--primary);
}

/* 色阶 */
.l0 {
  background: #eef0fa;
}
.l1 {
  background: #e0e7ff;
}
.l2 {
  background: #c7d2fe;
}
.l3 {
  background: #8b5cf6;
}
.l4 {
  background: #4f46e5;
}
.f {
  background: transparent;
}
.month .l0,
.hm-month .l0 {
  background: #eef0fa;
}
.legend {
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
  margin-top: 12px;
  font-size: 11px;
  color: var(--faint);
}
.lg {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  display: inline-block;
}
</style>
