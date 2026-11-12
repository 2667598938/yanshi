<script setup>
import { computed } from 'vue';
import {
  Calculator,
  Cpu,
  BookOpen,
  Flag,
  Code2,
  Hammer,
  GraduationCap,
  MoreHorizontal,
  Brain,
  PenLine,
  Sigma,
  Binary,
  Database,
  Globe,
  Beaker,
  Languages,
  Palette,
  Music,
  Briefcase,
  FlaskConical,
  Dumbbell,
  Camera,
} from 'lucide-vue-next';

const ICONS = {
  Calculator,
  Cpu,
  BookOpen,
  Flag,
  Code2,
  Hammer,
  GraduationCap,
  MoreHorizontal,
  Brain,
  PenLine,
  Sigma,
  Binary,
  Database,
  Globe,
  Beaker,
  Language: Languages,
  Palette,
  Music,
  Briefcase,
  FlaskConical,
  Dumbbell,
  Camera,
};

const props = defineProps({
  name: { type: String, default: 'MoreHorizontal' },
  size: { type: Number, default: 16 },
  strokeWidth: { type: Number, default: 2.2 },
});

const Cmp = computed(() => ICONS[props.name] || MoreHorizontal);
</script>

<template>
  <component :is="Cmp" :size="size" :stroke-width="strokeWidth" />
</template>
