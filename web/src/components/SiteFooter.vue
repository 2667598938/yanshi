<script setup>
// ICP 备案号与工信部查询地址
const MIIT_URL = 'https://beian.miit.gov.cn/';
const ICP_NUMBER = '豫ICP备2026056816号';

// 公安联网备案：审核通过后把号码填入 MPS_NUMBER（留空则不显示）
const MPS_URL = 'https://beian.mps.gov.cn/';
const MPS_NUMBER = '';
</script>

<template>
  <footer class="site-footer">
    <a class="footer-link" :href="MIIT_URL" target="_blank" rel="noopener noreferrer">
      {{ ICP_NUMBER }}
    </a>
    <a
      v-if="MPS_NUMBER"
      class="footer-link"
      :href="MPS_URL"
      target="_blank"
      rel="noopener noreferrer"
    >
      {{ MPS_NUMBER }}
    </a>
  </footer>
</template>

<style scoped>
.site-footer {
  padding: 24px 16px 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.footer-link {
  font-size: 11px;
  line-height: 1.5;
  color: var(--faint);
  text-decoration: none;
}
.footer-link:active {
  opacity: 0.7;
}
</style>
