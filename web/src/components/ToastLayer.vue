<script setup>
import { toastState } from '../composables/useToast';
</script>

<template>
  <div class="toast-layer">
    <div v-for="t in toastState.list" :key="t.id" class="toast">{{ t.msg }}</div>
  </div>
</template>
