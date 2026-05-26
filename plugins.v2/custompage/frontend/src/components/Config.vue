<template>
  <v-container fluid class="pa-4">
    <v-card class="rounded-lg" variant="outlined">
      <v-card-title class="text-h6">
        <v-icon class="mr-2">mdi-cog</v-icon>
        插件配置
      </v-card-title>
      <v-card-text>
        <v-alert type="info" variant="tonal" class="mb-4">
          自定义美化页面插件配置。启用后将在侧栏添加「美化首页」导航入口。
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
