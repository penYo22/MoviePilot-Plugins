<template>
  <v-container fluid class="pa-4">
    <v-card class="rounded-lg" variant="outlined">
      <v-card-title class="text-h6">
        <v-icon class="mr-2">mdi-view-dashboard</v-icon>
        自定义美化页面
      </v-card-title>
      <v-card-text>
        <v-alert type="info" variant="tonal">
          此插件通过侧栏「美化首页」入口展示自定义仪表板页面。
          请通过侧栏导航访问完整的仪表板视图。
        </v-alert>
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
const props = defineProps<{
  api?: any
  pluginId?: string
}>()
</script>
