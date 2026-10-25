<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronLeft, Plus, Check, Trash2, Pencil, AlertTriangle, Play,
} from 'lucide-vue-next'
import SubjectIcon from '../components/SubjectIcon.vue'
import { useTasksStore } from '../stores/tasks'
import { useSubjectsStore } from '../stores/subjects'
import { PHASES, PHASE_MAP } from '../data/subjects'
import { todayKey, mdWeekLabel } from '../utils/date'
import { useToast } from '../composables/useToast'

const router = useRouter()
const tasks = useTasksStore()
const subjects = useSubjectsStore()
const { toast } = useToast()

const sheet = ref(false)
const editingId = ref(null)
const fTitle = ref('')
const fSubject = ref('')
const fPhase = ref('custom')
const fCriteria = ref('')
const fDue = ref(todayKey())

const today = todayKey()
const overdue = computed(() =>
  tasks.open.filter((t) => t.dueDate && t.dueDate < today))
const todayTasks = computed(() =>
  tasks.open.filter((t) => t.dueDate === today))
const future = computed(() =>
  tasks.open
    .filter((t) => t.dueDate && t.dueDate > today)
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate)))
const doneList = computed(() =>
  tasks.sorted.filter((t) => t.done).slice(-30).reverse())

const todayRate = computed(() => {
  const all = tasks.todayAll
  if (!all.length) return null
  return Math.round((all.filter((t) => t.done).length / all.length) * 100)
})

function subjOf(id) {
  return subjects.byId[id] || subjects.byId.other
}
function dateLabel(key) {
  if (key === today) return '今天'
  return mdWeekLabel(key)
}

function openAdd() {
  editingId.value = null
  fTitle.value = ''
  fSubject.value = subjects.active[0]?.id || 'other'
  fPhase.value = 'custom'
  fCriteria.value = ''
  fDue.value = today
  sheet.value = true
}
function openEdit(t) {
  editingId.value = t.id
  fTitle.value = t.title
  fSubject.value = t.subjectId
  fPhase.value = t.phase
  fCriteria.value = t.acceptCriteria || ''
  fDue.value = t.dueDate || today
  sheet.value = true
}
function focusTask(task) {
  router.push({ path: '/focus', query: { taskId: task.id, subjectId: task.subjectId,
    content: task.title.slice(0, 100) } })
}
async function save() {
  if (!fTitle.value.trim()) {
    toast('请填写任务标题')
    return
  }
  const payload = {
    title: fTitle.value,
    subjectId: fSubject.value,
    phase: fPhase.value,
    acceptCriteria: fCriteria.value,
    dueDate: fDue.value,
  }
  if (editingId.value) {
    await tasks.update(editingId.value, payload)
    toast('已更新任务')
  } else {
    await tasks.add(payload)
    toast('已添加任务')
  }
  sheet.value = false
}
async function remove(id) {
  await tasks.remove(id)
  toast('已删除任务')
}
</script>

<template>
  <div class="nav">
    <button class="back-btn" @click="router.back()"><ChevronLeft :size="20" /></button>
    <div>
      <div class="nav-title">任务计划</div>
      <div class="nav-sub">用验收标准检验，不只看时长</div>
    </div>
  </div>

  <div class="page">
    <!-- 今日完成率 -->
    <div class="rate-card">
      <div class="rate-l">
        <div class="rate-num tnum">{{ todayRate === null ? '—' : todayRate + '%' }}</div>
        <div class="rate-cap">今日任务完成</div>
      </div>
      <div class="rate-r">
        <div>今天 {{ todayTasks.filter((t) => t.done).length }}/{{ todayTasks.length }} 项</div>
        <div v-if="overdue.length" class="overdue">
          <AlertTriangle :size="13" /> {{ overdue.length }} 项已逾期
        </div>
      </div>
    </div>

    <button class="btn btn-primary btn-block mt12" @click="openAdd">
      <Plus :size="18" />新建任务
    </button>

    <!-- 逾期 -->
    <template v-if="overdue.length">
      <div class="section-title">已逾期</div>
      <div class="card">
        <div v-for="t in overdue" :key="t.id" class="task-row">
          <button class="check" @click="tasks.toggle(t.id)"><Check :size="15" :stroke-width="3" /></button>
          <div class="task-body" @click="openEdit(t)">
            <div class="task-title danger">{{ t.title }}</div>
            <div v-if="t.acceptCriteria" class="task-crit">{{ t.acceptCriteria }}</div>
            <div class="task-meta">
              <span class="meta-subj" :style="{ color: subjOf(t.subjectId)?.color }">
                <SubjectIcon :name="subjOf(t.subjectId)?.icon" :size="12" />
                {{ subjOf(t.subjectId)?.name }}
              </span>
              <span class="phase-tag" :style="{ background: (PHASE_MAP[t.phase]?.color || '#999') + '1a', color: PHASE_MAP[t.phase]?.color }">
                {{ PHASE_MAP[t.phase]?.name }}
              </span>
              <span class="due overdue-text">{{ dateLabel(t.dueDate) }}</span>
            </div>
          </div>
          <button class="del" @click="remove(t.id)"><Trash2 :size="15" /></button>
        </div>
      </div>
    </template>

    <!-- 今日 -->
    <div class="section-title">今天</div>
    <div class="card">
      <div v-if="!todayTasks.length" class="empty">今天没有任务，新建一个吧</div>
      <div v-for="t in todayTasks" :key="t.id" class="task-row">
        <button class="check" @click="tasks.toggle(t.id)"><Check :size="15" :stroke-width="3" /></button>
        <div class="task-body" @click="openEdit(t)">
          <div class="task-title">{{ t.title }}</div>
          <div v-if="t.acceptCriteria" class="task-crit">{{ t.acceptCriteria }}</div>
          <div class="task-meta">
            <span class="meta-subj" :style="{ color: subjOf(t.subjectId)?.color }">
              <SubjectIcon :name="subjOf(t.subjectId)?.icon" :size="12" />
              {{ subjOf(t.subjectId)?.name }}
            </span>
            <span class="phase-tag" :style="{ background: (PHASE_MAP[t.phase]?.color || '#999') + '1a', color: PHASE_MAP[t.phase]?.color }">
              {{ PHASE_MAP[t.phase]?.name }}
            </span>
          </div>
        </div>
        <button class="edit" title="为此任务专注" @click="focusTask(t)"><Play :size="15" /></button>
        <button class="edit" @click="openEdit(t)"><Pencil :size="15" /></button>
      </div>
    </div>

    <!-- 未来 -->
    <template v-if="future.length">
      <div class="section-title">即将到期</div>
      <div class="card">
        <div v-for="t in future" :key="t.id" class="task-row">
          <button class="check" @click="tasks.toggle(t.id)"><Check :size="15" :stroke-width="3" /></button>
          <div class="task-body" @click="openEdit(t)">
            <div class="task-title">{{ t.title }}</div>
            <div v-if="t.acceptCriteria" class="task-crit">{{ t.acceptCriteria }}</div>
            <div class="task-meta">
              <span class="meta-subj" :style="{ color: subjOf(t.subjectId)?.color }">
                <SubjectIcon :name="subjOf(t.subjectId)?.icon" :size="12" />
                {{ subjOf(t.subjectId)?.name }}
              </span>
              <span class="phase-tag" :style="{ background: (PHASE_MAP[t.phase]?.color || '#999') + '1a', color: PHASE_MAP[t.phase]?.color }">
                {{ PHASE_MAP[t.phase]?.name }}
              </span>
              <span class="due">{{ dateLabel(t.dueDate) }}</span>
            </div>
          </div>
          <button class="edit" title="为此任务专注" @click="focusTask(t)"><Play :size="15" /></button>
          <button class="edit" @click="openEdit(t)"><Pencil :size="15" /></button>
        </div>
      </div>
    </template>

    <!-- 已完成 -->
    <template v-if="doneList.length">
      <div class="section-title">已完成</div>
      <div class="card">
        <div v-for="t in doneList" :key="t.id" class="task-row done">
          <button class="check on" @click="tasks.toggle(t.id)"><Check :size="15" :stroke-width="3" /></button>
          <div class="task-body">
            <div class="task-title">{{ t.title }}</div>
          </div>
          <button class="del" @click="remove(t.id)"><Trash2 :size="15" /></button>
        </div>
      </div>
    </template>
  </div>

  <!-- 新建/编辑 -->
  <div v-if="sheet" class="mask" @click.self="sheet = false">
    <div class="sheet">
      <div class="sheet-title">{{ editingId ? '编辑任务' : '新建任务' }}</div>

      <div class="f-label">任务标题</div>
      <input v-model="fTitle" class="input" placeholder="如：高数极限章节习题做完" maxlength="40" />

      <div class="f-label">所属科目</div>
      <select v-model="fSubject" class="select">
        <option v-for="s in subjects.active" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>

      <div class="f-label">考研阶段</div>
      <div class="pill-row">
        <button
          v-for="p in PHASES"
          :key="p.id"
          class="pill"
          :class="{ active: fPhase === p.id }"
          :style="fPhase === p.id ? { background: p.color } : {}"
          @click="fPhase = p.id"
        >{{ p.name }}</button>
      </div>

      <div class="f-label">验收标准（做完的标准是什么）</div>
      <textarea
        v-model="fCriteria"
        class="criteria-input"
        rows="2"
        placeholder="如：极限章节课后习题全做完、错题能独立讲清"
      ></textarea>

      <div class="f-label">截止日期</div>
      <input v-model="fDue" type="date" class="input" />

      <button class="btn btn-primary btn-block mt16" @click="save">
        <Check :size="18" />保存
      </button>
      <button class="btn btn-ghost btn-block mt8" @click="sheet = false">取消</button>
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
.rate-card {
  background: linear-gradient(135deg, var(--night2), var(--night));
  border-radius: 18px;
  padding: 18px 20px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.rate-num {
  font-size: 32px;
  font-weight: 800;
  line-height: 1;
}
.rate-cap {
  font-size: 12px;
  opacity: 0.75;
  margin-top: 5px;
}
.rate-r {
  font-size: 13px;
  text-align: right;
  opacity: 0.9;
}
.overdue {
  margin-top: 6px;
  color: #ffb4ab;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.task-row {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 11px 0;
}
.task-row + .task-row {
  border-top: 1px solid var(--line);
}
.check {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid var(--faint);
  background: #fff;
  color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  margin-top: 1px;
}
.check.on {
  background: var(--green);
  border-color: var(--green);
  color: #fff;
}
.task-body {
  flex: 1;
  min-width: 0;
  cursor: pointer;
}
.task-title {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.4;
}
.task-title.danger {
  color: var(--red);
}
.task-crit {
  font-size: 12.5px;
  color: var(--sub);
  margin-top: 3px;
  line-height: 1.5;
}
.task-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 6px;
}
.meta-subj {
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.phase-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}
.due {
  font-size: 12px;
  color: var(--faint);
}
.due.overdue-text {
  color: var(--red);
  font-weight: 600;
}
.edit,
.del {
  border: none;
  background: none;
  color: var(--faint);
  width: 30px;
  height: 30px;
  border-radius: 9px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.del {
  color: #d98b8b;
}
.task-row.done .task-title {
  color: var(--faint);
  text-decoration: line-through;
}

.f-label {
  font-size: 13px;
  font-weight: 700;
  margin: 14px 0 8px;
}
.criteria-input {
  width: 100%;
  border: 1.5px solid var(--line);
  border-radius: 12px;
  padding: 11px 14px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  background: #f8fafc;
}
.criteria-input:focus {
  border-color: var(--primary);
}
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
  padding: 22px 18px calc(22px + env(safe-area-inset-bottom));
  max-height: 86vh;
  overflow-y: auto;
}
.sheet-title {
  font-size: 17px;
  font-weight: 800;
  text-align: center;
  margin-bottom: 4px;
}
.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
