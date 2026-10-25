<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronLeft, Plus, Check, Trash2, Pencil, Brain, AlarmClock,
  RefreshCw, BookOpenCheck,
} from 'lucide-vue-next'
import BlobImage from '../components/BlobImage.vue'
import SubjectIcon from '../components/SubjectIcon.vue'
import { useMistakesStore } from '../stores/mistakes'
import { useSubjectsStore } from '../stores/subjects'
import { REASON_MAP, REVIEW_INTERVALS, intervalLabel } from '../data/subjects'
import { fmtShort } from '../utils/time'
import { useToast } from '../composables/useToast'

const router = useRouter()
const mistakes = useMistakesStore()
const subjects = useSubjectsStore()
const { toast } = useToast()

const filterSub = ref('')
const detail = ref(null)

const dueList = computed(() => {
  const arr = mistakes.dueReview
  return filterSub.value ? arr.filter((x) => x.subjectId === filterSub.value) : arr
})
const list = computed(() => {
  let arr = mistakes.sorted
  if (filterSub.value) arr = arr.filter((x) => x.subjectId === filterSub.value)
  return arr
})

function subjOf(id) {
  return subjects.byId[id] || subjects.byId.other
}
function isDue(m) {
  return !m.mastered && m.nextReviewAt && dueList.value.some((x) => x.id === m.id)
}
function nextLabel(m) {
  if (m.mastered) return null
  const stage = Math.min(m.stage || 0, REVIEW_INTERVALS.length - 1)
  return intervalLabel(REVIEW_INTERVALS[stage])
}
function dueLabel(ms) {
  if (!ms) return ''
  return fmtShort(new Date(ms).toISOString())
}

function open(m) {
  detail.value = m
}
async function remember() {
  if (!detail.value) return
  const m = detail.value
  const willMaster = m.stage + 1 >= REVIEW_INTERVALS.length
  const next = willMaster ? null : intervalLabel(REVIEW_INTERVALS[m.stage + 1])
  await mistakes.review(m.id, true)
  detail.value = mistakes.list.find((x) => x.id === m.id) || null
  toast(willMaster ? '已掌握，这道题过关了' : `${next}后再复习，加油`)
}
async function forget() {
  if (!detail.value) return
  const m = detail.value
  await mistakes.review(m.id, false)
  detail.value = mistakes.list.find((x) => x.id === m.id) || null
  const next = detail.value ? nextLabel(detail.value) : null
  toast(next ? `已回退一个节点，${next}后再复习` : '已回退一个复习节点')
}
async function remove() {
  if (!detail.value) return
  const id = detail.value.id
  detail.value = null
  await mistakes.remove(id)
  toast('已删除')
}
</script>

<template>
  <div class="nav">
    <button class="back-btn" @click="router.back()"><ChevronLeft :size="20" /></button>
    <div>
      <div class="nav-title">错题本</div>
      <div class="nav-sub">错题不是失败，是下次上岸的台阶</div>
    </div>
  </div>

  <div class="page">
    <!-- 待复习提醒 -->
    <div class="due-card" :class="{ hot: dueList.length }">
      <div class="due-ic"><AlarmClock :size="22" /></div>
      <div class="due-txt">
        <div class="due-num tnum">{{ dueList.length }} 道待复习</div>
        <div class="due-cap">
          {{ dueList.length ? '按艾宾浩斯节奏，今天该看这些' : '今天没有到期的复习，继续保持' }}
        </div>
      </div>
    </div>

    <!-- 科目筛选 -->
    <div class="filter-row">
      <button
        class="fpill"
        :class="{ on: !filterSub }"
        @click="filterSub = ''"
      >全部</button>
      <button
        v-for="s in subjects.active"
        :key="s.id"
        class="fpill"
        :class="{ on: filterSub === s.id }"
        :style="filterSub === s.id ? { background: s.color } : {}"
        @click="filterSub = filterSub === s.id ? '' : s.id"
      >
        <SubjectIcon :name="s.icon" :size="13" />{{ s.name }}
      </button>
    </div>

    <!-- 错题列表 -->
    <div v-if="!list.length" class="empty-card">
      <Brain :size="30" />
      <div>还没有错题，专注结束后可一键收录</div>
    </div>

    <div class="mk-list">
      <div
        v-for="m in list"
        :key="m.id"
        class="mk-card"
        :class="{ mastered: m.mastered }"
        @click="open(m)"
      >
        <div v-if="m.images?.length" class="mk-thumb">
          <BlobImage :blob="typeof m.images[0] === 'string' ? null : m.images[0]" :src="typeof m.images[0] === 'string' ? m.images[0] : ''" />
        </div>
        <div class="mk-body">
          <div class="mk-line1">
            <span class="mk-subj" :style="{ color: subjOf(m.subjectId)?.color }">
              <SubjectIcon :name="subjOf(m.subjectId)?.icon" :size="12" />
              {{ subjOf(m.subjectId)?.name }}
            </span>
            <span v-if="m.chapter" class="mk-chap">{{ m.chapter }}</span>
            <span v-if="isDue(m)" class="mk-due">复习</span>
            <span v-else-if="m.mastered" class="mk-ok">
              <BookOpenCheck :size="12" />已掌握
            </span>
            <span v-else class="mk-next">{{ dueLabel(m.nextReviewAt) }}</span>
          </div>
          <div v-if="m.content" class="mk-content">{{ m.content }}</div>
          <div class="mk-line2">
            <span class="mk-reason">{{ REASON_MAP[m.reason]?.name || m.reason }}</span>
            <span v-for="t in (m.tags || []).slice(0, 3)" :key="t" class="mk-tag">{{ t }}</span>
          </div>
        </div>
      </div>
    </div>

    <button class="fab-add" @click="router.push('/mistake/edit')">
      <Plus :size="24" />
    </button>
  </div>

  <!-- 详情 -->
  <div v-if="detail" class="mask" @click.self="detail = null">
    <div class="sheet">
      <div class="detail-head">
        <span class="mk-subj" :style="{ color: subjOf(detail.subjectId)?.color }">
          <SubjectIcon :name="subjOf(detail.subjectId)?.icon" :size="14" />
          {{ subjOf(detail.subjectId)?.name }}
        </span>
        <span v-if="detail.chapter" class="dk-chap">{{ detail.chapter }}</span>
        <button class="x-btn" @click="detail = null"><ChevronLeft :size="20" /></button>
      </div>

      <div class="stage-row">
        <span v-if="detail.mastered" class="master-badge">
          <Check :size="13" />已掌握
        </span>
        <template v-else>
          <span class="stage-text">第 {{ detail.stage + 1 }} / {{ REVIEW_INTERVALS.length }} 轮复习</span>
          <span class="stage-next">{{ isDue(detail) ? '现在该复习' : `${nextLabel(detail)}后复习` }}</span>
        </template>
      </div>
      <div class="stage-track">
        <div
          v-for="n in REVIEW_INTERVALS.length"
          :key="n"
          class="stage-seg"
          :class="{ on: detail.mastered || n - 1 < detail.stage }"
        ></div>
      </div>

      <div class="reason-line">
        {{ REASON_MAP[detail.reason]?.name || detail.reason }}
        <span v-for="t in detail.tags" :key="t" class="dk-tag">{{ t }}</span>
      </div>

      <div v-if="detail.content" class="dk-content">{{ detail.content }}</div>
      <div v-if="detail.idea" class="dk-block">
        <div class="dk-label">主要思路</div>
        <div class="dk-text">{{ detail.idea }}</div>
      </div>
      <div v-if="detail.analysis" class="dk-block">
        <div class="dk-label">答案解析</div>
        <div class="dk-text">{{ detail.analysis }}</div>
      </div>

      <div v-if="detail.images?.length" class="dk-imgs">
        <BlobImage v-for="(b, i) in detail.images" :key="`q${i}`" :blob="typeof b === 'string' ? null : b" :src="typeof b === 'string' ? b : ''" class="dk-img" />
      </div>
      <div v-if="detail.answerImages?.length" class="dk-imgs">
        <BlobImage v-for="(b, i) in detail.answerImages" :key="`a${i}`" :blob="typeof b === 'string' ? null : b" :src="typeof b === 'string' ? b : ''" class="dk-img" />
      </div>

      <div v-if="!detail.mastered" class="review-actions">
        <button class="btn btn-primary btn-block" @click="remember">
          <Check :size="18" />
          <span v-if="detail.stage + 1 >= REVIEW_INTERVALS.length">记住了，完成掌握</span>
          <span v-else>记住了，{{ intervalLabel(REVIEW_INTERVALS[detail.stage + 1]) }}后复习</span>
        </button>
        <button class="btn btn-ghost btn-block mt8" @click="forget">
          <RefreshCw :size="16" />还没记住，回退上一个节点
        </button>
      </div>

      <div class="row-actions">
        <button class="ra-btn" @click="router.push({ path: '/mistake/edit', query: { id: detail.id } }); detail = null">
          <Pencil :size="15" />编辑
        </button>
        <button class="ra-btn danger" @click="remove">
          <Trash2 :size="15" />删除
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid var(--line);
  background: #fff;
  color: var(--ink);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
}
.due-card {
  display: flex;
  align-items: center;
  gap: 13px;
  background: #fff;
  border-radius: 18px;
  padding: 16px 18px;
  box-shadow: var(--shadow-soft);
}
.due-card.hot {
  background: linear-gradient(135deg, #fff3e6, #ffe7d8);
}
.due-ic {
  width: 44px;
  height: 44px;
  border-radius: 13px;
  background: rgba(240, 168, 48, 0.18);
  color: var(--accent-deep);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.due-num {
  font-size: 17px;
  font-weight: 800;
}
.due-cap {
  font-size: 12px;
  color: var(--sub);
  margin-top: 2px;
}
.filter-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 14px 2px 4px;
  scrollbar-width: none;
}
.filter-row::-webkit-scrollbar {
  display: none;
}
.fpill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1.5px solid var(--line);
  background: #fff;
  color: var(--sub);
  font-size: 13px;
  font-weight: 600;
  padding: 7px 13px;
  border-radius: 999px;
  white-space: nowrap;
  cursor: pointer;
}
.fpill.on {
  color: #fff;
  border-color: transparent;
  background: var(--primary);
}
.empty-card {
  margin-top: 24px;
  text-align: center;
  color: var(--faint);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}
.mk-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.mk-card {
  display: flex;
  gap: 12px;
  background: #fff;
  border-radius: 16px;
  padding: 12px;
  box-shadow: var(--shadow-soft);
  cursor: pointer;
}
.mk-card.mastered {
  opacity: 0.62;
}
.mk-thumb {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f1f5f9;
}
.mk-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.mk-body {
  flex: 1;
  min-width: 0;
}
.mk-line1 {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.mk-subj {
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.mk-chap {
  font-size: 12px;
  color: var(--sub);
}
.mk-due {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: var(--tomato);
  padding: 2px 8px;
  border-radius: 999px;
}
.mk-ok {
  margin-left: auto;
  font-size: 11px;
  font-weight: 700;
  color: var(--green);
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.mk-next {
  margin-left: auto;
  font-size: 11px;
  color: var(--faint);
}
.mk-content {
  font-size: 13px;
  color: var(--sub);
  margin-top: 5px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.mk-line2 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  flex-wrap: wrap;
}
.mk-reason {
  font-size: 11px;
  color: var(--tomato-deep);
  background: #fdecec;
  padding: 2px 8px;
  border-radius: 999px;
}
.mk-tag {
  font-size: 11px;
  color: var(--purple);
  background: #f1eefd;
  padding: 2px 8px;
  border-radius: 999px;
}
.fab-add {
  position: fixed;
  right: calc(50% - 260px + 20px);
  bottom: 92px;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #ff8a72, var(--tomato-deep));
  color: #fff;
  box-shadow: 0 12px 24px rgba(224, 82, 63, 0.42);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
@media (max-width: 520px) {
  .fab-add {
    right: 20px;
  }
}

/* 详情弹层 */
.mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 150;
}
.sheet {
  width: 100%;
  max-width: 520px;
  background: #fff;
  border-radius: 22px 22px 0 0;
  padding: 20px 18px calc(22px + env(safe-area-inset-bottom));
  max-height: 88vh;
  overflow-y: auto;
}
.detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.dk-chap {
  font-size: 13px;
  font-weight: 600;
}
.x-btn {
  margin-left: auto;
  border: none;
  background: #f1f5f9;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.stage-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  font-size: 13px;
  font-weight: 600;
}
.stage-next {
  margin-left: auto;
  color: var(--tomato-deep);
  font-size: 12px;
}
.master-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--green);
  font-weight: 700;
}
.stage-track {
  display: flex;
  gap: 5px;
  margin: 10px 0 4px;
}
.stage-seg {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: var(--line);
}
.stage-seg.on {
  background: var(--green);
}
.reason-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
  font-size: 13px;
  font-weight: 700;
  color: var(--tomato-deep);
}
.dk-tag {
  font-size: 11px;
  font-weight: 600;
  color: var(--purple);
  background: #f1eefd;
  padding: 2px 8px;
  border-radius: 999px;
}
.dk-content {
  margin-top: 12px;
  font-size: 14px;
  color: var(--ink);
  line-height: 1.65;
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px 14px;
}
.dk-block { margin-top: 12px; background: #f8fafc; border-radius: 12px; padding: 12px 14px; }
.dk-label { font-size: 11.5px; color: var(--faint); margin-bottom: 4px; }
.dk-text { font-size: 14px; color: var(--ink); line-height: 1.65; white-space: pre-wrap; }
.dk-imgs {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dk-img {
  width: 100%;
  border-radius: 12px;
  border: 1px solid var(--line);
}
.review-actions {
  margin-top: 18px;
}
.row-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
}
.ra-btn {
  flex: 1;
  border: 1px solid var(--line);
  background: #fff;
  border-radius: 12px;
  padding: 11px;
  font-size: 13px;
  font-weight: 600;
  color: var(--sub);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
}
.ra-btn.danger {
  color: var(--red);
  border-color: #f3d1d1;
}
</style>
