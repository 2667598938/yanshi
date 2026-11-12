<script setup>
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ChevronLeft, Plus, Pencil, Archive, Check, ArchiveRestore } from 'lucide-vue-next';
import SubjectIcon from '../components/SubjectIcon.vue';
import { useSubjectsStore } from '../stores/subjects';
import { SUBJECT_COLORS, SUBJECT_ICONS, DEFAULT_SUBJECTS } from '../data/subjects';
import { useToast } from '../composables/useToast';

const router = useRouter();
const subjects = useSubjectsStore();
const { toast } = useToast();

const sheet = ref(false);
const editingId = ref(null);
const formName = ref('');
const formColor = ref(SUBJECT_COLORS[0]);
const formIcon = ref('BookOpen');

const archived = computed(() =>
  subjects.list.filter((x) => x.archived).sort((a, b) => a.order - b.order),
);

function openAdd() {
  editingId.value = null;
  formName.value = '';
  formColor.value = SUBJECT_COLORS[subjects.list.length % SUBJECT_COLORS.length];
  formIcon.value = 'BookOpen';
  sheet.value = true;
}
function openEdit(s) {
  editingId.value = s.id;
  formName.value = s.name;
  formColor.value = s.color;
  formIcon.value = s.icon;
  sheet.value = true;
}
async function save() {
  const name = formName.value.trim();
  if (!name) {
    toast('请填写科目名称');
    return;
  }
  if (editingId.value) {
    await subjects.update(editingId.value, {
      name,
      color: formColor.value,
      icon: formIcon.value,
    });
    toast('已保存');
  } else {
    await subjects.add({ name, color: formColor.value, icon: formIcon.value });
    toast('已添加科目');
  }
  sheet.value = false;
}
async function setArchived(s, archived) {
  await subjects.setArchived(s.id, archived);
  if (archived) toast(`已归档「${s.name}」`);
  else toast(`已恢复「${s.name}」`);
}
</script>

<template>
  <div class="nav">
    <button class="back-btn" @click="router.back()"><ChevronLeft :size="20" /></button>
    <div>
      <div class="nav-title">科目管理</div>
      <div class="nav-sub">自定义学习科目，归档后历史统计仍保留</div>
    </div>
  </div>

  <div class="page">
    <div class="card">
      <div v-for="s in subjects.active" :key="s.id" class="subj-row">
        <span class="subj-ic" :style="{ background: s.color }">
          <SubjectIcon :name="s.icon" :size="17" />
        </span>
        <span class="subj-name">{{ s.name }}</span>
        <button class="row-ic" @click="openEdit(s)"><Pencil :size="16" /></button>
        <button class="row-ic" @click="setArchived(s, 1)"><Archive :size="16" /></button>
      </div>
      <div v-if="!subjects.active.length" class="empty">还没有科目，点下方添加</div>
    </div>

    <div v-if="archived.length" class="card">
      <div class="arch-head">已归档（{{ archived.length }}）</div>
      <div v-for="s in archived" :key="s.id" class="subj-row is-off">
        <span class="subj-ic" :style="{ background: s.color }">
          <SubjectIcon :name="s.icon" :size="17" />
        </span>
        <span class="subj-name">{{ s.name }}</span>
        <button class="row-ic" @click="setArchived(s, 0)"><ArchiveRestore :size="16" /></button>
      </div>
    </div>

    <button class="btn btn-primary btn-block mt12" @click="openAdd">
      <Plus :size="18" />新增科目
    </button>
    <div class="tip">
      内置 {{ DEFAULT_SUBJECTS.length }} 科也可以改名、换色；归档只是隐藏，不会删除历史记录。
    </div>
  </div>

  <!-- 编辑弹层 -->
  <div v-if="sheet" class="mask" @click.self="sheet = false">
    <div class="sheet">
      <div class="sheet-title">{{ editingId ? '编辑科目' : '新增科目' }}</div>
      <div class="f-label">名称</div>
      <input v-model="formName" class="input" placeholder="如：数一、复试点、竞赛" maxlength="12" />

      <div class="f-label">颜色</div>
      <div class="pick-grid">
        <button
          v-for="c in SUBJECT_COLORS"
          :key="c"
          class="color-dot"
          :class="{ on: formColor === c }"
          :style="{ background: c }"
          @click="formColor = c"
        ></button>
      </div>

      <div class="f-label">图标</div>
      <div class="pick-grid icon-grid">
        <button
          v-for="ic in SUBJECT_ICONS"
          :key="ic"
          class="icon-cell"
          :class="{ on: formIcon === ic }"
          :style="formIcon === ic ? { background: formColor, borderColor: formColor } : {}"
          @click="formIcon = ic"
        >
          <SubjectIcon :name="ic" :size="17" :stroke-width="2.2" />
        </button>
      </div>

      <button class="btn btn-primary btn-block mt16" @click="save"><Check :size="18" />保存</button>
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
.subj-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 0;
}
.subj-row + .subj-row {
  border-top: 1px solid var(--line);
}
.subj-ic {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.subj-name {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
}
.row-ic {
  width: 34px;
  height: 34px;
  border: none;
  background: #f4f7fb;
  border-radius: 10px;
  color: var(--sub);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.is-off .subj-name {
  color: var(--faint);
}
.arch-head {
  font-size: 14px;
  font-weight: 700;
  color: var(--faint);
  margin-bottom: 4px;
}
.tip {
  font-size: 14px;
  color: var(--faint);
  line-height: 1.6;
  margin-top: 12px;
  padding: 0 4px;
}
.f-label {
  font-size: 14px;
  font-weight: 700;
  margin: 14px 0 8px;
}
.pick-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 10px;
}
.color-dot {
  height: 34px;
  border-radius: 10px;
  border: 2px solid transparent;
  cursor: pointer;
  position: relative;
}
.color-dot.on::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 8px;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.25);
}
.icon-grid {
  grid-template-columns: repeat(6, 1fr);
}
.icon-cell {
  height: 40px;
  border-radius: 10px;
  border: 1.5px solid var(--line);
  background: #fff;
  color: var(--sub);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.icon-cell.on {
  color: #fff;
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
  max-height: 82vh;
  overflow-y: auto;
}
.sheet-title {
  font-size: 16px;
  font-weight: 800;
  text-align: center;
  margin-bottom: 6px;
}
</style>
