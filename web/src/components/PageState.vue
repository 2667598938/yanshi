<script setup>
defineProps({ loading: Boolean, error: String, empty: Boolean, emptyLabel: String });
defineEmits(['retry']);
</script>

<template>
  <div v-if="loading" class="empty" role="status">读取中…</div>
  <div v-else-if="error" class="empty" role="alert">
    <p>{{ error }}</p>
    <button class="btn btn-outline btn-sm" type="button" @click="$emit('retry')">重试</button>
  </div>
  <div v-else-if="empty" class="empty">{{ emptyLabel }}</div>
  <slot v-else />
</template>
