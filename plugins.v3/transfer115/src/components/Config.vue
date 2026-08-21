<script setup>
import { onMounted } from 'vue'
import Transfer115Workbench from './Transfer115Workbench.vue'

defineProps({
  initialConfig: { type: Object, default: () => ({}) },
  api: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['layout', 'close'])
onMounted(() => emit('layout', { maxWidth: '82rem' }))
</script>

<template>
  <Transfer115Workbench :api="api" plugin-id="Transfer115" initial-tab="config" show-close compact @close="$emit('close')" />
</template>
