<script setup>
import { computed, ref, onMounted } from 'vue';
import { Camera, Pencil, Crown } from 'lucide-vue-next';
import BlobImage from './BlobImage.vue';
import { useAuthStore } from '../stores/auth';
import { useAppStore } from '../stores/app';
import { useTimerStore } from '../stores/timer';
import { useSchoolsStore } from '../stores/schools';
import { SCHOOL_MAP } from '../data/schools';
import { FIGURES, FIGURE_MAP } from '../data/figures';
import { fmtMinutes } from '../utils/date';
import { attachmentApi } from '../api';
import { useToast } from '../composables/useToast';
defineEmits(['edit']);
const auth = useAuthStore(),
  app = useAppStore(),
  timer = useTimerStore(),
  catalog = useSchoolsStore(),
  { toast } = useToast();
const fileInput = ref(null),
  uploading = ref(false);
const school = computed(() => {
  const key = auth.user?.target_school || app.dreamSchool;
  const saved = catalog.rows.find((row) => row.key === key);
  return {
    ...(SCHOOL_MAP[key] || {}),
    ...saved?.info,
    ...saved,
    logo: saved?.logo_key || SCHOOL_MAP[key]?.logo || '',
  };
});
const figure = computed(() => FIGURE_MAP[auth.user?.figure_id || 'figure-1'] || FIGURES[0]);
async function upload(event) {
  const file = event.target.files?.[0],
    owner = auth.user?.id;
  if (!file || uploading.value) return;
  uploading.value = true;
  try {
    const result = await attachmentApi.uploadAvatar(file);
    if (auth.user?.id !== owner) return;
    auth.updateAvatar(result.key);
    await auth.fetchMe();
    toast('头像已更新');
  } catch (error) {
    toast(error.message || '头像上传失败，请重试');
  } finally {
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = '';
  }
}
onMounted(() => catalog.load().catch(() => {}));
</script>
<template>
  <section class="profile-card" aria-label="个人名片">
    <BlobImage v-if="school.logo" class="watermark" :src="school.logo" alt="" />
    <div class="profile-main">
      <button
        class="avatar-button"
        :disabled="uploading"
        aria-label="上传新头像"
        @click="fileInput?.click()"
      >
        <BlobImage
          class="profile-avatar"
          :src="auth.user?.avatar_key || ''"
          :fallback="school.logo"
          :alt="auth.user?.nickname || '我的头像'"
        />
        <span class="figure-chip" :style="{ background: figure.bg }">{{ figure.emoji }}</span><span
          class="camera"
          ><Camera :size="15"
        /></span>
      </button>
      <div class="profile-meta">
        <button class="profile-edit" aria-label="编辑昵称、签名与形象" @click="$emit('edit')">
          <strong>{{ auth.user?.nickname || app.nickname }}</strong><span
            v-if="auth.isVip"
            class="vip"
            ><Crown :size="12" />VIP</span
          ><Pencil :size="16" />
        </button>
        <p class="signature">
          {{ uploading ? '头像上传中…' : auth.user?.signature || '点此编辑昵称、签名与形象' }}
        </p>
        <p>{{ auth.user?.email }}</p>
        <p class="school">
          {{ school.name || '选择你的梦校'
          }}<template v-if="school.motto"> · {{ school.motto }}</template>
        </p>
      </div>
    </div>
    <div class="profile-stats">
      <div>
        <strong>{{ fmtMinutes(timer.totalMin) }}</strong><span>累计</span>
      </div>
      <div>
        <strong>{{ timer.streak }}</strong><span>连续（天）</span>
      </div>
      <div>
        <strong>{{ timer.totalCount }}</strong><span>番茄（颗）</span>
      </div>
    </div>
    <input ref="fileInput" type="file" accept="image/*" hidden @change="upload" />
  </section>
</template>
<style scoped>
.profile-card {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  color: #fff;
  background: linear-gradient(140deg, var(--primary), var(--night) 85%);
  border: 1px solid rgba(255, 255, 255, 0.36);
  border-radius: 24px;
  padding: 24px 20px 20px;
  box-shadow:
    0 12px 32px rgba(49, 46, 129, 0.17),
    inset 0 1px 0 rgba(255, 255, 255, 0.3);
}
.watermark {
  position: absolute;
  z-index: -1;
  right: -26px;
  top: -20px;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  opacity: 0.08;
}
.profile-main {
  display: flex;
  align-items: center;
  gap: 16px;
}
.avatar-button {
  position: relative;
  flex-shrink: 0;
  background: transparent;
  border: 0;
  padding: 0;
  cursor: pointer;
}
.profile-avatar {
  display: block;
  width: 68px;
  height: 68px;
  border-radius: 50%;
  object-fit: cover;
  background: rgba(255, 255, 255, 0.8);
  border: 2px solid rgba(255, 255, 255, 0.85);
}
.figure-chip,
.camera {
  position: absolute;
  bottom: -3px;
  width: 25px;
  height: 25px;
  border: 2px solid #fff;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 16px;
}
.figure-chip {
  left: -3px;
}
.camera {
  right: -4px;
  background: var(--primary);
}
.profile-meta {
  min-width: 0;
  flex: 1;
}
.profile-edit {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
  flex-wrap: wrap;
}
.profile-edit strong {
  font-size: 20px;
  line-height: 28px;
  overflow-wrap: anywhere;
}
.vip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 18px;
  background: #fbbf24;
  color: #713f12;
  font-size: 12px;
  font-weight: 700;
  padding: 4px 8px;
}
.profile-meta p {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.8);
  margin: 6px 0 0;
  overflow-wrap: anywhere;
}
.signature {
  font-style: italic;
}
.profile-meta .school {
  font-size: 12px;
}
.profile-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  text-align: center;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.2);
}
.profile-stats strong {
  display: block;
  font-size: 20px;
  line-height: 28px;
  font-variant-numeric: tabular-nums;
}
.profile-stats span {
  display: block;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
  margin-top: 4px;
}
</style>
