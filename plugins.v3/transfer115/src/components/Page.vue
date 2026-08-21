<script setup>
import Transfer115Workbench from './Transfer115Workbench.vue'

defineProps({ api: { type: Object, default: () => ({}) } })
defineEmits(['action', 'close'])
</script>

<template>
  <Transfer115Workbench :api="api" plugin-id="Transfer115" show-close compact @action="$emit('action')" @close="$emit('close')" />
</template>
