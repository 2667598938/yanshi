<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ArrowLeft } from 'lucide-vue-next';
import { publicApi } from '../api';

const router = useRouter();
const text = ref('加载中…');

onMounted(async () => {
  try {
    const legal = await publicApi.legal();
    text.value = legal.disclaimer || '暂无内容';
  } catch {
    text.value = '加载失败，请稍后再试';
  }
});
</script>

<template>
  <div>
    <div class="nav">
      <button class="back" @click="router.back()"><ArrowLeft :size="20" /></button>
      <div class="nav-title">免责声明</div>
    </div>
    <div class="page">
      <div class="card">
        <pre class="doc">{{ text }}</pre>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back {
  border: none;
  background: #fff;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--sub);
  cursor: pointer;
  box-shadow: var(--shadow-soft);
}
.doc {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.9;
  color: var(--sub);
}
</style>
