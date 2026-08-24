<script setup>
import { computed, inject, nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'Transfer115' },
  initialTab: { type: String, default: 'offline' },
  showClose: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'action'])
const hostToast = inject('moviepilot:toast', null)
const pluginBase = computed(() => `plugin/${props.pluginId || 'Transfer115'}`)
const activeTab = ref(props.initialTab)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const state = ref({ enabled: false, rename_enabled: false, download_path: '', config: {} })
const directory = ref({ path: '/', parent: null, items: [] })
const directoryLoaded = ref(false)
const selectedPaths = ref([])
const samplePath = ref('')
const sampleElement = ref(null)
const selectedText = ref('')
const tokens = ref([])
const template = ref('{1} - {2}')
const keepExtension = ref(true)
const preview = ref(null)
const renameResult = ref(null)
const confirmOpen = ref(false)
const settings = ref({})
const offlineLinks = ref('')
const offlineTasks = ref([])
const offlineLoading = ref(false)

const files = computed(() => directory.value.items.filter(item => item.type !== 'dir'))
const folders = computed(() => directory.value.items.filter(item => item.type === 'dir'))
const selectedFiles = computed(() => files.value.filter(item => selectedPaths.value.includes(item.path)))
const sample = computed(() => files.value.find(item => item.path === samplePath.value) || selectedFiles.value[0] || files.value[0] || null)
const allFilesSelected = computed(() => files.value.length > 0 && files.value.every(item => selectedPaths.value.includes(item.path)))
const sampleExtension = computed(() => {
  const name = sample.value?.name || ''
  const index = name.lastIndexOf('.')
  return index > 0 ? name.slice(index) : ''
})
const sampleStem = computed(() => {
  const name = sample.value?.name || ''
  return sampleExtension.value ? name.slice(0, -sampleExtension.value.length) : name
})
const sampleParts = computed(() => {
  if (!sampleStem.value) return []
  if (!tokens.value.length) return [sampleStem.value]
  const escaped = [...tokens.value]
    .sort((left, right) => right.length - left.length)
    .map(token => token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  return sampleStem.value.split(new RegExp(escaped.join('|'), 'g')).map(part => part.trim()).filter(Boolean)
})

function unwrap(response) {
  if (response && Object.prototype.hasOwnProperty.call(response, 'success')) {
    if (response.success === false) throw new Error(response.message || '操作失败')
    return response.data
  }
  return response?.data ?? response
}

function assertResult(result) {
  if (!result || Number(result.code || 0) !== 0) throw new Error(result?.msg || '操作失败')
  return result
}

function notify(message, color = 'success') {
  const method = ['error', 'info', 'warning', 'success'].includes(color) ? color : 'success'
  if (typeof hostToast?.[method] === 'function') hostToast[method](message)
  else if (method === 'error') error.value = message
}

function formatBytes(value) {
  const size = Number(value || 0)
  if (!size) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1)
  return `${(size / 1024 ** index).toFixed(index > 1 ? 1 : 0)} ${units[index]}`
}

function taskColor(status) {
  return { completed: 'success', failed: 'error', downloading: 'info', unknown: 'secondary' }[status] || 'secondary'
}

function taskIcon(status) {
  return { completed: 'mdi-check-circle-outline', failed: 'mdi-alert-circle-outline', downloading: 'mdi-download-circle-outline', unknown: 'mdi-help-circle-outline' }[status] || 'mdi-help-circle-outline'
}

async function loadState() {
  const data = assertResult(unwrap(await props.api.get(`${pluginBase.value}/plugin_state`)))
  state.value = data
  settings.value = { ...(data.config || {}) }
  tokens.value = [...(data.split_tokens || [])]
  template.value = data.split_template || '{1} - {2}'
  keepExtension.value = data.split_keep_extension !== false
}

async function loadDirectory(path = '') {
  loading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams({ path: path || state.value.download_path || '/' })
    directory.value = assertResult(unwrap(await props.api.get(`${pluginBase.value}/file_manager?${query}`)))
    directoryLoaded.value = true
    selectedPaths.value = []
    samplePath.value = files.value[0]?.path || ''
    preview.value = null
  } catch (err) {
    error.value = err?.message || '读取115目录失败'
  } finally {
    loading.value = false
  }
}

async function ensureDirectoryLoaded() {
  if (
    !directoryLoaded.value
    && state.value.enabled
    && state.value.config?.auth_mode !== 'cookie'
  ) await loadDirectory(state.value.download_path || '/')
}

async function loadOfflineTasks({ quiet = false } = {}) {
  if (!state.value.enabled) return
  offlineLoading.value = true
  try {
    const result = assertResult(unwrap(await props.api.get(`${pluginBase.value}/offline_tasks`)))
    offlineTasks.value = result.tasks || []
    if (!quiet) notify(result.msg || '离线任务已刷新', 'info')
  } catch (err) {
    if (!quiet) notify(err?.message || '读取离线任务失败', 'error')
  } finally {
    offlineLoading.value = false
  }
}

async function submitOffline() {
  if (!offlineLinks.value.trim()) {
    notify('请先粘贴离线下载链接', 'warning')
    return
  }
  saving.value = true
  try {
    const result = assertResult(unwrap(await props.api.post(`${pluginBase.value}/submit_offline`, {
      links: offlineLinks.value,
    })))
    offlineLinks.value = ''
    await loadOfflineTasks({ quiet: true })
    notify(result.msg || '离线任务已提交')
    emit('action')
  } catch (err) {
    notify(err?.message || '提交离线任务失败', 'error')
  } finally {
    saving.value = false
  }
}

async function checkOfflineTasks() {
  offlineLoading.value = true
  try {
    const result = assertResult(unwrap(await props.api.get(`${pluginBase.value}/refresh_tasks`)))
    offlineTasks.value = result.tasks || []
    notify(result.msg || '任务检查完成')
  } catch (err) {
    notify(err?.message || '检查离线任务失败', 'error')
  } finally {
    offlineLoading.value = false
  }
}

async function organizeDownloads() {
  saving.value = true
  try {
    const result = assertResult(unwrap(await props.api.get(`${pluginBase.value}/organize_all`)))
    notify(result.msg || '整理完成')
    emit('action')
  } catch (err) {
    notify(err?.message || '整理下载目录失败', 'error')
  } finally {
    saving.value = false
  }
}

async function initialize() {
  loading.value = true
  try {
    await loadState()
    if (state.value.enabled) {
      await loadOfflineTasks({ quiet: true })
      if (activeTab.value === 'files') await ensureDirectoryLoaded()
    }
  } catch (err) {
    error.value = err?.message || '加载文件管理器失败'
  } finally {
    loading.value = false
  }
}

function toggleFile(path) {
  preview.value = null
  selectedPaths.value = selectedPaths.value.includes(path)
    ? selectedPaths.value.filter(item => item !== path)
    : [...selectedPaths.value, path]
  if (!samplePath.value || !selectedPaths.value.includes(samplePath.value)) samplePath.value = selectedPaths.value[0] || path
}

function toggleAllFiles() {
  preview.value = null
  selectedPaths.value = allFilesSelected.value ? [] : files.value.map(item => item.path)
  samplePath.value = selectedPaths.value[0] || files.value[0]?.path || ''
}

function captureSelection() {
  const selection = window.getSelection()
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed || !sampleElement.value) return
  const range = selection.getRangeAt(0)
  if (!sampleElement.value.contains(range.commonAncestorContainer)) return
  selectedText.value = selection.toString()
}

function addSelectedDelimiter() {
  const token = selectedText.value
  if (!token) {
    notify('请先用鼠标拖选样例文件名中的分隔文字', 'warning')
    return
  }
  if (!tokens.value.includes(token)) tokens.value.push(token)
  selectedText.value = ''
  window.getSelection()?.removeAllRanges()
  preview.value = null
}

function removeToken(token) {
  tokens.value = tokens.value.filter(item => item !== token)
  preview.value = null
}

function insertPart(index) {
  const part = `{${index}}`
  template.value = template.value.trim() ? `${template.value} ${part}` : part
  preview.value = null
}

async function testRename() {
  saving.value = true
  error.value = ''
  renameResult.value = null
  try {
    preview.value = assertResult(unwrap(await props.api.post(`${pluginBase.value}/preview_custom_rename`, {
      selected_paths: selectedPaths.value,
      split_tokens: tokens.value,
      template: template.value,
      keep_extension: keepExtension.value,
    })))
    notify(preview.value.msg || '测试完成')
  } catch (err) {
    notify(err?.message || '测试文件名拆分失败', 'error')
  } finally {
    saving.value = false
  }
}

async function applyRename() {
  if (!preview.value?.plan_id) return
  saving.value = true
  try {
    const result = assertResult(unwrap(await props.api.post(`${pluginBase.value}/apply_custom_rename`, {
      plan_id: preview.value.plan_id,
    })))
    confirmOpen.value = false
    preview.value = null
    renameResult.value = result
    await loadDirectory(directory.value.path)
    notify(result.msg || '改名完成')
    emit('action')
  } catch (err) {
    notify(err?.message || '执行改名失败', 'error')
  } finally {
    saving.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const payload = {
      ...settings.value,
      split_tokens: tokens.value,
      split_template: template.value,
      split_keep_extension: keepExtension.value,
    }
    const result = assertResult(unwrap(await props.api.post(`${pluginBase.value}/settings`, payload)))
    state.value = result
    settings.value = { ...(result.config || {}) }
    directoryLoaded.value = false
    notify(result.msg || '设置已保存')
  } catch (err) {
    notify(err?.message || '保存设置失败', 'error')
  } finally {
    saving.value = false
  }
}

watch(sample, async () => {
  selectedText.value = ''
  await nextTick()
})
watch([tokens, template, keepExtension], () => { preview.value = null }, { deep: true })
watch(activeTab, async (tab) => {
  if (tab === 'files') await ensureDirectoryLoaded()
})
onMounted(initialize)
</script>

<template>
  <div class="transfer115-shell" :class="{ 'transfer115-shell--compact': compact }">
    <header class="transfer115-header">
      <div>
        <h1>115 文件管理器</h1>
        <p>{{ directory.path || state.download_path || '/' }}</p>
      </div>
      <div class="transfer115-header__actions">
        <VTooltip v-if="activeTab === 'files'" text="刷新目录">
          <template #activator="{ props: tipProps }">
            <VBtn v-bind="tipProps" icon="mdi-refresh" variant="text" :loading="loading" @click="loadDirectory(directory.path)" />
          </template>
        </VTooltip>
        <VBtn v-if="showClose" icon="mdi-close" variant="text" @click="$emit('close')" />
      </div>
    </header>

    <VAlert v-if="error" type="error" variant="tonal" closable @click:close="error = ''">{{ error }}</VAlert>
    <VAlert v-if="!state.enabled" type="warning" variant="tonal">插件尚未启用，请先到设置页启用。</VAlert>

    <VTabs v-model="activeTab" color="primary" class="transfer115-tabs">
      <VTab value="offline">离线下载</VTab>
      <VTab value="files">文件改名</VTab>
      <VTab value="config">插件设置</VTab>
    </VTabs>
    <VDivider />

    <VWindow v-model="activeTab" :touch="false">
      <VWindowItem value="offline">
        <div class="transfer115-offline">
          <VSheet tag="section" class="transfer115-panel app-surface-static">
            <div class="transfer115-offline-head">
              <div>
                <div class="text-subtitle-1 font-weight-medium">添加离线下载</div>
                <div class="text-body-2 text-medium-emphasis">每行一个磁力、ed2k、HTTP 或 115 分享链接</div>
              </div>
              <VChip :color="state.config?.auth_mode === 'cookie' ? 'warning' : 'success'" size="small" variant="tonal" prepend-icon="mdi-shield-check-outline">
                {{ state.config?.auth_mode === 'cookie' ? 'Cookie授权' : 'MoviePilot 115授权' }}
              </VChip>
            </div>
            <VTextarea v-model="offlineLinks" label="离线下载链接" rows="7" auto-grow variant="outlined" placeholder="magnet:?xt=urn:btih:...&#10;ed2k://..." />
            <div class="transfer115-offline-target">
              <VIcon icon="mdi-folder-download-outline" color="primary" />
              <div><span>保存到</span><strong>{{ state.download_path || '115根目录' }}</strong></div>
              <VBtn size="small" variant="text" @click="activeTab = 'config'">修改目录</VBtn>
            </div>
            <div class="transfer115-actions">
              <VBtn color="primary" variant="flat" prepend-icon="mdi-download" :loading="saving" :disabled="!offlineLinks.trim() || !state.enabled" @click="submitOffline">提交离线任务</VBtn>
              <VBtn variant="tonal" prepend-icon="mdi-refresh" :loading="offlineLoading" :disabled="!state.enabled" @click="loadOfflineTasks()">刷新列表</VBtn>
              <VBtn color="info" variant="tonal" prepend-icon="mdi-progress-check" :loading="offlineLoading" :disabled="!state.enabled" @click="checkOfflineTasks">检查任务</VBtn>
              <VBtn color="success" variant="tonal" prepend-icon="mdi-folder-move-outline" :loading="saving" :disabled="!state.enabled || !state.download_path" @click="organizeDownloads">整理下载目录</VBtn>
            </div>
          </VSheet>

          <VSheet tag="section" class="transfer115-panel app-surface-static">
            <div class="transfer115-panel-head transfer115-panel-head--plain">
              <div><strong>离线任务</strong><span>最近 {{ offlineTasks.length }} 个任务</span></div>
              <VProgressCircular v-if="offlineLoading" indeterminate size="22" width="2" color="primary" />
            </div>
            <div v-if="offlineTasks.length" class="transfer115-task-list">
              <article v-for="task in offlineTasks" :key="task.id || `${task.name}-${task.created_at}`" class="transfer115-task-row">
                <VIcon :icon="taskIcon(task.status)" :color="taskColor(task.status)" />
                <div class="transfer115-task-main">
                  <div><strong>{{ task.name || '未命名任务' }}</strong><VChip :color="taskColor(task.status)" size="x-small" variant="tonal">{{ task.status_label }}</VChip></div>
                  <span>{{ task.save_path || state.download_path || '115根目录' }}<template v-if="task.size"> · {{ formatBytes(task.size) }}</template></span>
                  <VProgressLinear v-if="task.status === 'downloading'" :model-value="task.progress" height="4" color="info" rounded />
                  <small v-if="task.error">{{ task.error }}</small>
                </div>
                <span class="transfer115-task-progress">{{ task.status === 'downloading' ? `${task.progress}%` : '' }}</span>
              </article>
            </div>
            <div v-else class="transfer115-empty">暂无离线任务</div>
          </VSheet>
        </div>
      </VWindowItem>

      <VWindowItem value="files">
        <div class="transfer115-workspace">
          <VSheet tag="section" class="transfer115-browser app-surface-static">
            <div class="transfer115-panel-head">
              <div>
                <strong>选择文件</strong>
                <span>已选 {{ selectedPaths.length }} 个</span>
              </div>
              <VBtn size="small" variant="text" :disabled="!files.length" @click="toggleAllFiles">
                {{ allFilesSelected ? '取消全选' : '全选文件' }}
              </VBtn>
            </div>

            <div class="transfer115-breadcrumb">
              <VBtn v-if="directory.parent !== null" icon="mdi-arrow-up" size="small" variant="text" @click="loadDirectory(directory.parent)" />
              <VIcon v-else icon="mdi-cloud-outline" size="small" />
              <span>{{ directory.path }}</span>
            </div>

            <div v-if="loading" class="transfer115-loading"><VProgressCircular indeterminate color="primary" /></div>
            <div v-else class="transfer115-file-list">
              <button v-for="folder in folders" :key="folder.path" type="button" class="transfer115-file-row" @click="loadDirectory(folder.path)">
                <VIcon icon="mdi-folder-outline" color="warning" />
                <span class="transfer115-file-name">{{ folder.name }}</span>
                <VIcon icon="mdi-chevron-right" size="small" />
              </button>
              <div v-for="file in files" :key="file.path" class="transfer115-file-row transfer115-file-row--selectable" :class="{ 'transfer115-file-row--selected': selectedPaths.includes(file.path) }">
                <VCheckboxBtn :model-value="selectedPaths.includes(file.path)" @click.prevent="toggleFile(file.path)" />
                <button type="button" class="transfer115-file-main" @click.prevent="samplePath = file.path">
                  <span class="transfer115-file-name">{{ file.name }}</span>
                  <small>{{ formatBytes(file.size) }}</small>
                </button>
                <VTooltip text="设为拆分样例">
                  <template #activator="{ props: tipProps }">
                    <VBtn v-bind="tipProps" :icon="sample?.path === file.path ? 'mdi-text-box-check-outline' : 'mdi-text-box-outline'" size="small" variant="text" @click.prevent="samplePath = file.path" />
                  </template>
                </VTooltip>
              </div>
              <div v-if="!folders.length && !files.length" class="transfer115-empty">当前目录为空</div>
            </div>
          </VSheet>

          <main class="transfer115-editor">
            <VSheet tag="section" class="transfer115-panel app-surface-static">
              <div class="transfer115-step"><span>1</span><div><strong>拖选分隔文字</strong><small>像选择网页文字一样，在文件名里拖动鼠标</small></div></div>
              <div v-if="sample" class="transfer115-sample-wrap">
                <div ref="sampleElement" class="transfer115-sample" @mouseup="captureSelection" @keyup="captureSelection">{{ sampleStem }}</div>
                <VChip v-if="sampleExtension" size="small" variant="tonal">{{ sampleExtension }}</VChip>
              </div>
              <div v-else class="transfer115-empty">先在左侧选择一个文件</div>
              <div class="transfer115-selection-bar">
                <span>{{ selectedText ? `已选：${selectedText}` : '尚未选择分隔文字' }}</span>
                <VBtn color="primary" size="small" variant="tonal" :disabled="!selectedText" prepend-icon="mdi-content-cut" @click="addSelectedDelimiter">以此拆分</VBtn>
              </div>
              <div class="transfer115-token-row">
                <VChip v-for="token in tokens" :key="token" closable color="info" variant="tonal" @click:close="removeToken(token)">{{ token === ' ' ? '空格' : token }}</VChip>
                <span v-if="!tokens.length" class="text-body-2 text-medium-emphasis">拖选后，拆分符会显示在这里</span>
              </div>
            </VSheet>

            <VSheet tag="section" class="transfer115-panel app-surface-static">
              <div class="transfer115-step"><span>2</span><div><strong>组合新名称</strong><small>片段从 1 开始，扩展名可自动保留</small></div></div>
              <VTextField v-model="template" label="命名模板" variant="outlined" density="comfortable" hide-details placeholder="{1} - {2}" />
              <div class="transfer115-part-buttons">
                <VBtn v-for="(part, index) in sampleParts" :key="`${index}-${part}`" size="small" variant="tonal" @click="insertPart(index + 1)">{{ index + 1 }} · {{ part }}</VBtn>
              </div>
              <VSwitch v-model="keepExtension" label="自动保留原扩展名" color="primary" hide-details />
            </VSheet>

            <VSheet tag="section" class="transfer115-panel app-surface-static">
              <div class="transfer115-step"><span>3</span><div><strong>先测试，再改名</strong><small>测试不会修改115文件</small></div></div>
              <div class="transfer115-actions">
                <VBtn color="primary" variant="flat" prepend-icon="mdi-flask-outline" :loading="saving" :disabled="!selectedPaths.length || !tokens.length" @click="testRename">测试 {{ selectedPaths.length }} 个文件</VBtn>
                <VBtn color="warning" variant="tonal" prepend-icon="mdi-file-edit-outline" :disabled="!preview?.plan_id" @click="confirmOpen = true">确认改名</VBtn>
              </div>
              <VAlert v-if="preview" :type="preview.errors?.length ? 'warning' : 'success'" variant="tonal" density="compact">{{ preview.msg }}</VAlert>
              <div v-if="preview?.items?.length" class="transfer115-preview-list">
                <article v-for="item in preview.items" :key="item.path">
                  <span>{{ item.name }}</span><VIcon icon="mdi-arrow-right" size="small" /><strong>{{ item.new_name }}</strong>
                  <small>拆分：{{ item.parts.join(' | ') }}</small>
                  <div v-if="item.recognition" class="transfer115-preview-recognition" :class="item.recognition.matched ? 'is-matched' : 'is-unmatched'">
                    <VIcon :icon="item.recognition.matched ? (item.recognition.type === 'tv' ? 'mdi-television-play' : 'mdi-movie-open-outline') : 'mdi-help-circle-outline'" size="small" />
                    <span v-if="item.recognition.matched">{{ item.recognition.type_label }}<template v-if="item.recognition.episode_label"> · {{ item.recognition.episode_label }}</template><template v-if="item.recognition.title_year || item.recognition.title"> · {{ item.recognition.title_year || item.recognition.title }}</template><template v-if="item.recognition.tmdb_id"> · TMDB {{ item.recognition.tmdb_id }}</template></span>
                    <span v-else>{{ item.recognition.error || 'MoviePilot 未识别到电影或电视剧' }}</span>
                  </div>
                </article>
              </div>
              <VAlert v-if="renameResult" :type="renameResult.recognition_results?.some(item => item.matched) ? 'success' : 'warning'" variant="tonal" density="compact" class="transfer115-recognition-result">
                {{ renameResult.msg }}
              </VAlert>
              <div v-if="renameResult?.recognition_results?.length" class="transfer115-recognition-list">
                <article v-for="item in renameResult.recognition_results" :key="item.path" class="transfer115-recognition-row">
                  <VIcon :icon="item.matched ? (item.type === 'tv' ? 'mdi-television-play' : 'mdi-movie-open-outline') : 'mdi-help-circle-outline'" :color="item.matched ? 'success' : 'warning'" />
                  <div>
                    <strong>{{ item.name }}</strong>
                    <span v-if="item.matched">{{ item.type_label }}<template v-if="item.episode_label"> · {{ item.episode_label }}</template><template v-if="item.title_year || item.title"> · {{ item.title_year || item.title }}</template><template v-if="item.tmdb_id"> · TMDB {{ item.tmdb_id }}</template></span>
                    <span v-else>{{ item.error || 'TMDB 未命中电影或电视剧' }}</span>
                  </div>
                </article>
              </div>
            </VSheet>
          </main>
        </div>
      </VWindowItem>

      <VWindowItem value="config">
        <div class="transfer115-settings">
          <VSheet class="transfer115-panel app-surface-static">
            <div class="transfer115-settings-grid">
              <VSwitch v-model="settings.enabled" label="启用插件" color="primary" hide-details />
              <VSwitch v-model="settings.auto_organize" label="自动整理" color="primary" hide-details />
              <VSwitch v-model="settings.notify_enabled" label="发送通知" color="primary" hide-details />
              <VSwitch v-model="settings.rename_enabled" label="启用文件改名" color="primary" hide-details />
              <VSelect v-model="settings.auth_mode" label="115授权方式" :items="[{ title: 'MoviePilot授权', value: 'mp_oauth' }, { title: 'Cookie', value: 'cookie' }]" variant="outlined" hide-details />
              <VSelect v-model="settings.transfer_type" label="整理方式" :items="[{ title: '移动', value: 'move' }, { title: '复制', value: 'copy' }]" variant="outlined" hide-details />
              <VTextField v-model="settings.download_path" label="下载目录" variant="outlined" hide-details />
              <VTextField v-model="settings.library_path" label="媒体库目录" variant="outlined" hide-details />
              <VTextField v-model="settings.fail_path" label="失败目录" variant="outlined" hide-details />
              <VTextField v-if="settings.auth_mode === 'cookie'" v-model="settings.cookie" label="115 Cookie" type="password" variant="outlined" hide-details />
              <VTextField v-model.number="settings.poll_interval" label="轮询间隔（分钟）" type="number" variant="outlined" hide-details />
              <VTextField v-model.number="settings.rename_max_files" label="单次改名上限" type="number" variant="outlined" hide-details />
            </div>
            <div class="transfer115-settings-actions"><VBtn color="primary" prepend-icon="mdi-content-save-outline" :loading="saving" @click="saveSettings">保存设置</VBtn></div>
          </VSheet>
        </div>
      </VWindowItem>
    </VWindow>

    <VDialog v-model="confirmOpen" max-width="560">
      <VCard>
        <VCardTitle>确认修改 {{ preview?.items?.filter(item => !item.unchanged).length || 0 }} 个文件名？</VCardTitle>
        <VCardText>将按刚才的测试结果修改115远端文件。执行前仍会检查文件是否存在以及是否有同名冲突。</VCardText>
        <VCardActions>
          <VSpacer />
          <VBtn variant="text" @click="confirmOpen = false">取消</VBtn>
          <VBtn color="warning" variant="flat" :loading="saving" @click="applyRename">确认改名</VBtn>
        </VCardActions>
      </VCard>
    </VDialog>
  </div>
</template>

<style scoped>
.transfer115-shell { padding: 20px; color: rgb(var(--v-theme-on-surface)); }
.transfer115-shell--compact { padding: 4px; }
.transfer115-header, .transfer115-panel-head, .transfer115-selection-bar, .transfer115-actions, .transfer115-settings-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.transfer115-header { margin-block-end: 12px; }
.transfer115-header h1 { margin: 0; font-size: 1.45rem; font-weight: 650; letter-spacing: 0; }
.transfer115-header p { margin: 3px 0 0; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); overflow-wrap: anywhere; }
.transfer115-header__actions { display: flex; }
.transfer115-tabs { margin-block-start: 8px; }
.transfer115-workspace { display: grid; grid-template-columns: minmax(290px, 0.8fr) minmax(0, 1.2fr); gap: 16px; padding-block-start: 16px; }
.transfer115-browser, .transfer115-panel { border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 8px; }
.transfer115-browser { min-block-size: 620px; overflow: hidden; }
.transfer115-panel-head { min-block-size: 58px; padding: 12px 14px; border-block-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); }
.transfer115-panel-head > div { display: flex; flex-direction: column; }
.transfer115-panel-head span { font-size: .78rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-breadcrumb { display: flex; align-items: center; gap: 8px; min-block-size: 48px; padding: 8px 12px; background: rgba(var(--v-theme-surface-variant), .32); }
.transfer115-breadcrumb span { min-inline-size: 0; overflow-wrap: anywhere; font-size: .86rem; }
.transfer115-file-list { max-block-size: 590px; overflow: auto; }
.transfer115-file-row { display: flex; align-items: center; gap: 8px; inline-size: 100%; min-block-size: 48px; padding: 6px 12px; border: 0; border-block-end: 1px solid rgba(var(--v-border-color), .08); background: transparent; color: inherit; text-align: start; cursor: pointer; }
.transfer115-file-row:hover { background: rgba(var(--v-theme-primary), .05); }
.transfer115-file-row--selected { background: rgba(var(--v-theme-primary), .09); }
.transfer115-file-main { display: flex; flex: 1; min-inline-size: 0; align-items: center; justify-content: space-between; gap: 8px; border: 0; background: transparent; color: inherit; text-align: start; cursor: pointer; }
.transfer115-file-name { min-inline-size: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.transfer115-file-main small { flex: 0 0 auto; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-editor { display: grid; align-content: start; gap: 12px; min-inline-size: 0; }
.transfer115-panel { padding: 16px; }
.transfer115-step { display: flex; align-items: center; gap: 10px; margin-block-end: 14px; }
.transfer115-step > span { display: grid; place-items: center; inline-size: 28px; block-size: 28px; border-radius: 50%; background: rgb(var(--v-theme-primary)); color: rgb(var(--v-theme-on-primary)); font-weight: 700; }
.transfer115-step > div { display: flex; flex-direction: column; }
.transfer115-step small { color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-sample-wrap { display: flex; align-items: center; gap: 8px; }
.transfer115-sample { flex: 1; min-inline-size: 0; min-block-size: 70px; padding: 18px; border: 1px dashed rgba(var(--v-theme-primary), .55); border-radius: 6px; background: rgba(var(--v-theme-primary), .045); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 1rem; line-height: 1.8; overflow-wrap: anywhere; cursor: text; user-select: text; }
.transfer115-sample::selection { background: rgba(var(--v-theme-warning), .45); }
.transfer115-selection-bar { margin-block-start: 12px; }
.transfer115-selection-bar span { min-inline-size: 0; overflow-wrap: anywhere; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-token-row, .transfer115-part-buttons { display: flex; flex-wrap: wrap; gap: 8px; margin-block-start: 12px; }
.transfer115-actions { justify-content: flex-start; flex-wrap: wrap; margin-block-end: 12px; }
.transfer115-preview-list { display: grid; gap: 8px; max-block-size: 330px; margin-block-start: 12px; overflow: auto; }
.transfer115-preview-list article { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity)); border-radius: 6px; }
.transfer115-preview-list span, .transfer115-preview-list strong { min-inline-size: 0; overflow-wrap: anywhere; }
.transfer115-preview-list small { grid-column: 1 / -1; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-preview-recognition { grid-column: 1 / -1; display: flex; align-items: center; gap: 6px; min-inline-size: 0; font-size: .8rem; }
.transfer115-preview-recognition span { overflow-wrap: anywhere; }
.transfer115-preview-recognition.is-matched { color: rgb(var(--v-theme-success)); }
.transfer115-preview-recognition.is-unmatched { color: rgb(var(--v-theme-warning)); }
.transfer115-loading, .transfer115-empty { display: grid; place-items: center; min-block-size: 120px; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-settings { max-inline-size: 1080px; padding-block-start: 16px; }
.transfer115-settings-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.transfer115-settings-actions { justify-content: flex-end; margin-block-start: 18px; }
.transfer115-offline { display: grid; gap: 12px; padding-block-start: 16px; }
.transfer115-offline-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-block-end: 14px; }
.transfer115-offline-head > div { min-inline-size: 0; }
.transfer115-offline-target { display: flex; align-items: center; gap: 10px; min-block-size: 44px; padding: 8px 12px; border-radius: 6px; background: rgba(var(--v-theme-primary), .06); }
.transfer115-offline-target > div { display: flex; flex: 1; min-inline-size: 0; flex-direction: column; gap: 2px; }
.transfer115-offline-target span { font-size: .78rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-offline-target strong { overflow-wrap: anywhere; font-weight: 550; }
.transfer115-panel-head--plain { margin: -16px -16px 0; }
.transfer115-task-list { display: grid; gap: 0; }
.transfer115-task-row { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: start; gap: 10px; padding: 12px 0; border-block-end: 1px solid rgba(var(--v-border-color), .1); }
.transfer115-task-row:last-child { border-block-end: 0; }
.transfer115-task-main { min-inline-size: 0; }
.transfer115-task-main > div { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.transfer115-task-main strong { min-inline-size: 0; overflow-wrap: anywhere; }
.transfer115-task-main > span { display: block; margin-block: 4px 6px; overflow-wrap: anywhere; font-size: .8rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-task-main small { display: block; margin-block-start: 5px; overflow-wrap: anywhere; color: rgb(var(--v-theme-error)); }
.transfer115-task-progress { min-inline-size: 42px; text-align: end; font-size: .8rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
.transfer115-recognition-result { margin-block-start: 12px; }
.transfer115-recognition-list { display: grid; gap: 6px; max-block-size: 260px; margin-block-start: 10px; overflow: auto; }
.transfer115-recognition-row { display: flex; align-items: flex-start; gap: 8px; padding: 8px 10px; border-block-end: 1px solid rgba(var(--v-border-color), .1); }
.transfer115-recognition-row > div { display: flex; min-inline-size: 0; flex-direction: column; gap: 2px; }
.transfer115-recognition-row strong, .transfer115-recognition-row span { overflow-wrap: anywhere; }
.transfer115-recognition-row span { font-size: .8rem; color: rgba(var(--v-theme-on-surface), var(--v-medium-emphasis-opacity)); }
@media (max-width: 900px) {
  .transfer115-shell { padding: 12px; }
  .transfer115-workspace { grid-template-columns: 1fr; }
  .transfer115-browser { min-block-size: 420px; }
  .transfer115-file-list { max-block-size: 410px; }
  .transfer115-settings-grid { grid-template-columns: 1fr; }
}
@media (max-width: 520px) {
  .transfer115-header h1 { font-size: 1.2rem; }
  .transfer115-preview-list article { grid-template-columns: 1fr; }
  .transfer115-preview-list article :deep(.v-icon) { transform: rotate(90deg); }
  .transfer115-selection-bar { align-items: stretch; flex-direction: column; }
  .transfer115-offline-head { flex-direction: column; }
  .transfer115-offline-target { align-items: flex-start; }
  .transfer115-offline-target :deep(.v-btn) { margin-inline-start: auto; }
}
</style>
