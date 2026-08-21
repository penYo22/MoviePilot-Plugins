<script setup>
import Transfer115Workbench from './Transfer115Workbench.vue'

defineProps({
  api: { type: Object, default: () => ({}) },
  navKey: { type: String, default: 'main' },
  pluginId: { type: String, default: 'Transfer115' },
})

defineEmits(['action'])
</script>

<template>
  <Transfer115Workbench :api="api" :plugin-id="pluginId" @action="$emit('action')" />
</template>
