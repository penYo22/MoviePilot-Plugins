<template>
  <v-container fluid class="pa-4">
    <!-- Welcome Banner -->
    <v-card
      class="mb-6 rounded-xl elevation-4"
      :style="{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white'
      }"
    >
      <v-card-text class="pa-8">
        <v-row align="center">
          <v-col cols="12" md="8">
            <h1 class="text-h4 font-weight-bold mb-2">{{ greeting }}</h1>
            <p class="text-subtitle-1 mb-0" style="opacity: 0.9">
              欢迎使用 MoviePilot，您的智能影音管理助手
            </p>
          </v-col>
          <v-col cols="12" md="4" class="text-right">
            <div class="text-h5 font-weight-medium">{{ currentTime }}</div>
            <div class="text-subtitle-2" style="opacity: 0.8">{{ currentDate }}</div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Quick Navigation -->
    <h2 class="text-h6 font-weight-bold mb-4">
      <v-icon class="mr-2">mdi-compass</v-icon>
      快捷导航
    </h2>
    <v-row class="mb-6">
      <v-col
        v-for="nav in navItems"
        :key="nav.title"
        cols="6"
        sm="4"
        md="2"
      >
        <v-card
          class="text-center pa-4 rounded-lg nav-card"
          variant="outlined"
          hover
        >
          <v-icon
            :color="nav.color"
            size="40"
            class="mb-2"
          >
            {{ nav.icon }}
          </v-icon>
          <div class="text-body-2 font-weight-medium">{{ nav.title }}</div>
          <div class="text-caption text-medium-emphasis">{{ nav.desc }}</div>
        </v-card>
      </v-col>
    </v-row>

    <!-- System Info -->
    <h2 class="text-h6 font-weight-bold mb-4">
      <v-icon class="mr-2">mdi-information-outline</v-icon>
      系统信息
    </h2>
    <v-row>
      <v-col cols="12" md="6">
        <v-card class="rounded-lg" variant="outlined">
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <template #prepend>
                  <v-icon color="primary">mdi-clock-outline</v-icon>
                </template>
                <v-list-item-title>当前时间</v-list-item-title>
                <v-list-item-subtitle>{{ currentTime }} {{ currentDate }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="success">mdi-check-circle</v-icon>
                </template>
                <v-list-item-title>运行状态</v-list-item-title>
                <v-list-item-subtitle>系统运行正常</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="info">mdi-puzzle</v-icon>
                </template>
                <v-list-item-title>插件版本</v-list-item-title>
                <v-list-item-subtitle>v1.0</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="12" md="6">
        <v-card class="rounded-lg" variant="outlined">
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <template #prepend>
                  <v-icon color="warning">mdi-star</v-icon>
                </template>
                <v-list-item-title>提示</v-list-item-title>
                <v-list-item-subtitle>使用侧栏导航快速访问各功能模块</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="purple">mdi-palette</v-icon>
                </template>
                <v-list-item-title>自定义</v-list-item-title>
                <v-list-item-subtitle>可修改前端源码自定义此页面内容</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <template #prepend>
                  <v-icon color="teal">mdi-github</v-icon>
                </template>
                <v-list-item-title>开源</v-list-item-title>
                <v-list-item-subtitle>前端源码位于 frontend/ 目录</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Footer -->
    <v-card class="mt-6 rounded-lg" variant="flat" color="surface-variant">
      <v-card-text class="text-center text-caption text-medium-emphasis pa-3">
        <v-icon size="small" class="mr-1">mdi-heart</v-icon>
        MoviePilot CustomPage Plugin v1.0 | Powered by Vue 3 + Vuetify + Module Federation
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'

const props = defineProps<{
  api?: any
  navKey?: string
  pluginId?: string
}>()

const currentTime = ref('')
const currentDate = ref('')
let timer: ReturnType<typeof setInterval> | null = null

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了，注意休息'
  if (hour < 9) return '早上好，美好的一天开始了'
  if (hour < 12) return '上午好，工作顺利'
  if (hour < 14) return '中午好，记得休息'
  if (hour < 18) return '下午好，继续加油'
  if (hour < 22) return '晚上好，享受影音时光'
  return '夜深了，注意休息'
})

const navItems = [
  { title: '探索发现', desc: '发现新影片', icon: 'mdi-compass-outline', color: 'blue' },
  { title: '我的订阅', desc: '管理订阅', icon: 'mdi-heart-outline', color: 'red' },
  { title: '下载管理', desc: '查看下载', icon: 'mdi-download', color: 'green' },
  { title: '媒体整理', desc: '整理文件', icon: 'mdi-folder-multiple', color: 'orange' },
  { title: '历史记录', desc: '浏览历史', icon: 'mdi-history', color: 'purple' },
  { title: '系统设置', desc: '配置系统', icon: 'mdi-cog-outline', color: 'grey' }
]

function updateTime() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
  currentDate.value = now.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long'
  })
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.nav-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.nav-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15) !important;
}
</style>
