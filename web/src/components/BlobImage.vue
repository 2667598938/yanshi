<script setup>
import { ref, watch, onBeforeUnmount } from 'vue';
import { fetchBlob } from '../api/http';
import { attachmentApi } from '../api';
import { resolveCachedImage } from '../db/imageCache';
import { useAuthStore } from '../stores/auth';
const auth = useAuthStore();

const props = defineProps({
  // 本地 Blob（错题本地图片）
  blob: { type: [Blob, Object], default: null },
  // 来源：附件 key / http(s) URL / 相对路径 / dataURL
  src: { type: String, default: '' },
  alt: { type: String, default: '' },
  // 加载失败时的兜底图
  fallback: { type: String, default: '' },
});

const url = ref('');
const failed = ref(false);
let objectUrl = '';
let generation = 0;

function clearObject() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = '';
  }
}

function isKey(s) {
  return s && !/^(https?:|\/|data:|blob:)/.test(s);
}

async function resolve() {
  const current = ++generation;
  clearObject();
  failed.value = false;
  url.value = '';
  if (props.blob) {
    objectUrl = URL.createObjectURL(props.blob);
    url.value = objectUrl;
    return;
  }
  if (props.src) {
    if (isKey(props.src)) {
      // 附件对象 key，需要带鉴权头拉取
      try {
        const blob = await resolveCachedImage(props.src, () =>
          fetchBlob(attachmentApi.viewUrl(props.src)),
        );
        if (current !== generation || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        url.value = objectUrl;
      } catch {
        if (current !== generation) return;
        failed.value = true;
      }
    } else {
      url.value = props.src;
    }
    return;
  }
  if (props.fallback) {
    failed.value = true;
    url.value = props.fallback;
  }
}

watch([() => props.blob, () => props.src, () => auth.user?.id], resolve, { immediate: true });
onBeforeUnmount(() => {
  generation += 1;
  clearObject();
});

function onError() {
  if (props.fallback && url.value !== props.fallback) {
    url.value = props.fallback;
  }
}
</script>

<template>
  <img
    v-if="url || failed"
    :src="failed && fallback ? fallback : url"
    :alt="alt"
    @error="onError"
  />
</template>
