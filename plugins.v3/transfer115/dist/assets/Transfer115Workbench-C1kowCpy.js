import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,resolveComponent:_resolveComponent,mergeProps:_mergeProps,createVNode:_createVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "transfer115-header" };
const _hoisted_2 = { class: "transfer115-header__actions" };
const _hoisted_3 = { class: "transfer115-workspace" };
const _hoisted_4 = { class: "transfer115-panel-head" };
const _hoisted_5 = { class: "transfer115-browser-actions" };
const _hoisted_6 = ["src"];
const _hoisted_7 = { class: "transfer115-editor" };
const _hoisted_8 = {
  key: 0,
  class: "transfer115-sample-wrap"
};
const _hoisted_9 = {
  key: 1,
  class: "transfer115-empty"
};
const _hoisted_10 = { class: "transfer115-selection-bar" };
const _hoisted_11 = { class: "transfer115-token-row" };
const _hoisted_12 = {
  key: 0,
  class: "text-body-2 text-medium-emphasis"
};
const _hoisted_13 = { class: "transfer115-part-buttons" };
const _hoisted_14 = { class: "transfer115-actions" };
const _hoisted_15 = {
  key: 1,
  class: "transfer115-preview-list"
};
const _hoisted_16 = { key: 0 };
const _hoisted_17 = { key: 1 };
const _hoisted_18 = {
  key: 3,
  class: "transfer115-recognition-list"
};
const _hoisted_19 = { key: 0 };
const _hoisted_20 = { key: 1 };
const _hoisted_21 = { class: "transfer115-offline" };
const _hoisted_22 = { class: "transfer115-offline-head" };
const _hoisted_23 = { class: "transfer115-offline-target" };
const _hoisted_24 = { class: "transfer115-actions" };
const _hoisted_25 = { class: "transfer115-panel-head transfer115-panel-head--plain" };
const _hoisted_26 = {
  key: 0,
  class: "transfer115-task-list"
};
const _hoisted_27 = { class: "transfer115-task-main" };
const _hoisted_28 = { key: 1 };
const _hoisted_29 = { class: "transfer115-task-progress" };
const _hoisted_30 = {
  key: 1,
  class: "transfer115-empty"
};
const _hoisted_31 = { class: "transfer115-settings" };
const _hoisted_32 = { class: "transfer115-settings-grid" };
const _hoisted_33 = { class: "transfer115-settings-actions" };

const {computed,inject,nextTick,onMounted,ref,watch} = await importShared('vue');



const _sfc_main = {
  __name: 'Transfer115Workbench',
  props: {
  api: { type: Object, default: () => ({}) },
  pluginId: { type: String, default: 'Transfer115' },
  initialTab: { type: String, default: 'files' },
  showClose: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
},
  emits: ['close', 'action'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;
const hostToast = inject('moviepilot:toast', null);
const pluginBase = computed(() => `plugin/${props.pluginId || 'Transfer115'}`);
const activeTab = ref(props.initialTab);
const loading = ref(false);
const saving = ref(false);
const error = ref('');
const state = ref({ enabled: false, rename_enabled: false, download_path: '', config: {} });
const directory = ref({ path: '/', parent: null, items: [] });
const selectedPaths = ref([]);
const samplePath = ref('');
const sampleElement = ref(null);
const selectedText = ref('');
const tokens = ref([]);
const template = ref('{1} - {2}');
const keepExtension = ref(true);
const preview = ref(null);
const renameResult = ref(null);
const confirmOpen = ref(false);
const settings = ref({});
const offlineLinks = ref('');
const offlineTasks = ref([]);
const offlineLoading = ref(false);
const fileBrowserRef = ref(null);
const builtinPath = ref('/');
const builtinReady = ref(false);
const builtinFrameKey = ref(0);

const files = computed(() => directory.value.items.filter(item => item.type !== 'dir'));
const selectedFiles = computed(() => files.value.filter(item => selectedPaths.value.includes(item.path)));
const selectedFileItems = computed(() => selectedPaths.value.map(path => ({ path, name: baseName(path), size: 0, type: 'file' })));
const sample = computed(() => files.value.find(item => item.path === samplePath.value) || selectedFiles.value[0] || selectedFileItems.value[0] || files.value[0] || null);
const builtinFileManagerUrl = computed(() => {
  const base = window.location.href.split('#')[0] || '/';
  return `${base}#/filemanager`
});
const sampleExtension = computed(() => {
  const name = sample.value?.name || '';
  const index = name.lastIndexOf('.');
  return index > 0 ? name.slice(index) : ''
});
const sampleStem = computed(() => {
  const name = sample.value?.name || '';
  return sampleExtension.value ? name.slice(0, -sampleExtension.value.length) : name
});
const sampleParts = computed(() => {
  if (!sampleStem.value) return []
  if (!tokens.value.length) return [sampleStem.value]
  const escaped = [...tokens.value]
    .sort((left, right) => right.length - left.length)
    .map(token => token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  return sampleStem.value.split(new RegExp(escaped.join('|'), 'g')).map(part => part.trim()).filter(Boolean)
});

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
  const method = ['error', 'info', 'warning', 'success'].includes(color) ? color : 'success';
  if (typeof hostToast?.[method] === 'function') hostToast[method](message);
  else if (method === 'error') error.value = message;
}

function baseName(path) {
  const clean = String(path || '').replace(/\/+$/, '');
  return clean.split('/').pop() || ''
}

function joinPath(path, name) {
  const base = String(path).replace(/\/+$/, '') || '';
  return `${base}/${name}`
}

function readBuiltinPath(doc) {
  const toolbar = doc.querySelector('.file-browser-toolbar');
  if (!toolbar) return null
  const segments = Array.from(toolbar.querySelectorAll('button.v-btn'))
    .map(button => (button.textContent || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
    .slice(1);
  return segments.length ? `/${segments.join('/')}/` : '/'
}

function readBuiltinCheckedNames(doc) {
  const names = [];
  const inputs = Array.from(doc.querySelectorAll('.file-list-container input[type="checkbox"]'));
  for (const input of inputs) {
    if (!input.checked) continue
    const title = input.closest('.v-list-item')?.querySelector('.v-list-item-title');
    const name = title?.textContent?.trim();
    if (name && !names.includes(name)) names.push(name);
  }
  return names
}

function onBuiltinLoaded() {
  builtinReady.value = true;
}

function reloadBuiltinFileManager() {
  builtinFrameKey.value += 1;
  builtinReady.value = false;
}

function openBuiltinInNewTab() {
  window.open(builtinFileManagerUrl.value, '_blank');
}

async function syncSelectedFromBuiltin() {
  const frame = fileBrowserRef.value;
  const doc = frame?.contentDocument || frame?.contentWindow?.document;
  if (!doc) {
    notify('无法读取MoviePilot自带文件管理器', 'error');
    return
  }

  const names = readBuiltinCheckedNames(doc);
  if (!names.length) {
    notify('请先在自带文件管理器中勾选要改名的文件', 'warning');
    return
  }

  const path = readBuiltinPath(doc) || directory.value.path || state.value.download_path || '/';
  builtinPath.value = path;
  try {
    const loaded = await loadDirectory(path, { clearSelection: false });
    if (!loaded) throw new Error('读取115目录失败')
    const byName = new Map(files.value.map(item => [item.name, item]));
    const matched = names
      .map(name => byName.get(name)?.path || joinPath(path, name))
      .filter(Boolean);
    selectedPaths.value = [...new Set(matched)];
    samplePath.value = selectedPaths.value[0] || files.value[0]?.path || '';
    preview.value = null;
    notify(`已同步 ${selectedPaths.value.length} 个勾选文件`);
  } catch (err) {
    selectedPaths.value = [...new Set(names.map(name => joinPath(path, name)))];
    samplePath.value = selectedPaths.value[0] || '';
    builtinPath.value = path;
    directory.value.path = path;
    preview.value = null;
    notify(`已同步 ${selectedPaths.value.length} 个勾选文件`);
  }
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (!size) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
  return `${(size / 1024 ** index).toFixed(index > 1 ? 1 : 0)} ${units[index]}`
}

function taskColor(status) {
  return { completed: 'success', failed: 'error', downloading: 'info', unknown: 'secondary' }[status] || 'secondary'
}

function taskIcon(status) {
  return { completed: 'mdi-check-circle-outline', failed: 'mdi-alert-circle-outline', downloading: 'mdi-download-circle-outline', unknown: 'mdi-help-circle-outline' }[status] || 'mdi-help-circle-outline'
}

async function loadState() {
  const data = assertResult(unwrap(await props.api.get(`${pluginBase.value}/plugin_state`)));
  state.value = data;
  settings.value = { ...(data.config || {}) };
  directory.value.path = data.download_path || '/';
  tokens.value = [...(data.split_tokens || [])];
  template.value = data.split_template || '{1} - {2}';
  keepExtension.value = data.split_keep_extension !== false;
}

async function loadDirectory(path = '', { clearSelection = true } = {}) {
  loading.value = true;
  error.value = '';
  const target = path || state.value.download_path || '/';
  try {
    directory.value = { path: target, parent: null, items: [] };
    const query = new URLSearchParams({ path: target });
    directory.value = assertResult(unwrap(await props.api.get(`${pluginBase.value}/file_manager?${query}`)));
    if (clearSelection) {
      selectedPaths.value = [];
      samplePath.value = files.value[0]?.path || '';
    }
    preview.value = null;
    return true
  } catch (err) {
    error.value = err?.message || '读取115目录失败';
    return false
  } finally {
    loading.value = false;
  }
}

async function loadOfflineTasks({ quiet = false } = {}) {
  if (!state.value.enabled) return
  offlineLoading.value = true;
  try {
    const result = assertResult(unwrap(await props.api.get(`${pluginBase.value}/offline_tasks`)));
    offlineTasks.value = result.tasks || [];
    if (!quiet) notify(result.msg || '离线任务已刷新', 'info');
  } catch (err) {
    if (!quiet) notify(err?.message || '读取离线任务失败', 'error');
  } finally {
    offlineLoading.value = false;
  }
}

async function submitOffline() {
  if (!offlineLinks.value.trim()) {
    notify('请先粘贴离线下载链接', 'warning');
    return
  }
  saving.value = true;
  try {
    const result = assertResult(unwrap(await props.api.post(`${pluginBase.value}/submit_offline`, {
      links: offlineLinks.value,
    })));
    offlineLinks.value = '';
    await loadOfflineTasks({ quiet: true });
    notify(result.msg || '离线任务已提交');
    emit('action');
  } catch (err) {
    notify(err?.message || '提交离线任务失败', 'error');
  } finally {
    saving.value = false;
  }
}

async function checkOfflineTasks() {
  offlineLoading.value = true;
  try {
    const result = assertResult(unwrap(await props.api.get(`${pluginBase.value}/refresh_tasks`)));
    offlineTasks.value = result.tasks || [];
    notify(result.msg || '任务检查完成');
  } catch (err) {
    notify(err?.message || '检查离线任务失败', 'error');
  } finally {
    offlineLoading.value = false;
  }
}

async function organizeDownloads() {
  saving.value = true;
  try {
    const result = assertResult(unwrap(await props.api.get(`${pluginBase.value}/organize_all`)));
    notify(result.msg || '整理完成');
    emit('action');
  } catch (err) {
    notify(err?.message || '整理下载目录失败', 'error');
  } finally {
    saving.value = false;
  }
}

async function initialize() {
  loading.value = true;
  try {
    await loadState();
    if (state.value.enabled && activeTab.value === 'offline') {
      await loadOfflineTasks({ quiet: true });
    }
  } catch (err) {
    error.value = err?.message || '加载文件管理器失败';
  } finally {
    loading.value = false;
  }
}

function captureSelection() {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed || !sampleElement.value) return
  const range = selection.getRangeAt(0);
  if (!sampleElement.value.contains(range.commonAncestorContainer)) return
  selectedText.value = selection.toString();
}

function addSelectedDelimiter() {
  const token = selectedText.value;
  if (!token) {
    notify('请先用鼠标拖选样例文件名中的分隔文字', 'warning');
    return
  }
  if (!tokens.value.includes(token)) tokens.value.push(token);
  selectedText.value = '';
  window.getSelection()?.removeAllRanges();
  preview.value = null;
}

function removeToken(token) {
  tokens.value = tokens.value.filter(item => item !== token);
  preview.value = null;
}

function insertPart(index) {
  const part = `{${index}}`;
  template.value = template.value.trim() ? `${template.value} ${part}` : part;
  preview.value = null;
}

async function testRename() {
  saving.value = true;
  error.value = '';
  renameResult.value = null;
  try {
    preview.value = assertResult(unwrap(await props.api.post(`${pluginBase.value}/preview_custom_rename`, {
      selected_paths: selectedPaths.value,
      split_tokens: tokens.value,
      template: template.value,
      keep_extension: keepExtension.value,
    })));
    notify(preview.value.msg || '测试完成');
  } catch (err) {
    notify(err?.message || '测试文件名拆分失败', 'error');
  } finally {
    saving.value = false;
  }
}

async function applyRename() {
  if (!preview.value?.plan_id) return
  saving.value = true;
  try {
    const result = assertResult(unwrap(await props.api.post(`${pluginBase.value}/apply_custom_rename`, {
      plan_id: preview.value.plan_id,
    })));
    confirmOpen.value = false;
    preview.value = null;
    renameResult.value = result;
    await loadDirectory(directory.value.path);
    reloadBuiltinFileManager();
    notify(result.msg || '改名完成');
    emit('action');
  } catch (err) {
    notify(err?.message || '执行改名失败', 'error');
  } finally {
    saving.value = false;
  }
}

async function saveSettings() {
  saving.value = true;
  try {
    const payload = {
      ...settings.value,
      split_tokens: tokens.value,
      split_template: template.value,
      split_keep_extension: keepExtension.value,
    };
    const result = assertResult(unwrap(await props.api.post(`${pluginBase.value}/settings`, payload)));
    state.value = result;
    settings.value = { ...(result.config || {}) };
    directory.value.path = result.download_path || result.config?.download_path || directory.value.path || '/';
    builtinPath.value = directory.value.path;
    reloadBuiltinFileManager();
    notify(result.msg || '设置已保存');
  } catch (err) {
    notify(err?.message || '保存设置失败', 'error');
  } finally {
    saving.value = false;
  }
}

watch(sample, async () => {
  selectedText.value = '';
  await nextTick();
});
watch([tokens, template, keepExtension], () => { preview.value = null; }, { deep: true });
watch(activeTab, async (tab) => {
  if (tab === 'offline' && state.value.enabled) await loadOfflineTasks({ quiet: true });
});
onMounted(initialize);

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSheet = _resolveComponent("VSheet");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
  const _component_VTextarea = _resolveComponent("VTextarea");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VProgressLinear = _resolveComponent("VProgressLinear");
  const _component_VSelect = _resolveComponent("VSelect");
  const _component_VWindow = _resolveComponent("VWindow");
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VDialog = _resolveComponent("VDialog");

  return (_openBlock(), _createElementBlock("div", {
    class: _normalizeClass(["transfer115-shell", { 'transfer115-shell--compact': __props.compact }])
  }, [
    _createElementVNode("header", _hoisted_1, [
      _createElementVNode("div", null, [
        _cache[24] || (_cache[24] = _createElementVNode("h1", null, "115 文件管理器", -1)),
        _createElementVNode("p", null, _toDisplayString(directory.value.path || state.value.download_path || '/'), 1)
      ]),
      _createElementVNode("div", _hoisted_2, [
        (activeTab.value === 'files')
          ? (_openBlock(), _createBlock(_component_VTooltip, {
              key: 0,
              text: "刷新文件管理器"
            }, {
              activator: _withCtx(({ props: tipProps }) => [
                _createVNode(_component_VBtn, _mergeProps(tipProps, {
                  icon: "mdi-refresh",
                  variant: "text",
                  disabled: !builtinReady.value,
                  onClick: reloadBuiltinFileManager
                }), null, 16, ["disabled"])
              ]),
              _: 1
            }))
          : _createCommentVNode("", true),
        (__props.showClose)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 1,
              icon: "mdi-close",
              variant: "text",
              onClick: _cache[0] || (_cache[0] = $event => (_ctx.$emit('close')))
            }))
          : _createCommentVNode("", true)
      ])
    ]),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 0,
          type: "error",
          variant: "tonal",
          closable: "",
          "onClick:close": _cache[1] || (_cache[1] = $event => (error.value = ''))
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    (!state.value.enabled)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "warning",
          variant: "tonal"
        }, {
          default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
            _createTextVNode("插件尚未启用，请先到设置页启用。", -1)
          ]))]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createVNode(_component_VTabs, {
      modelValue: activeTab.value,
      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((activeTab).value = $event)),
      color: "primary",
      class: "transfer115-tabs"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VTab, { value: "files" }, {
          default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
            _createTextVNode("文件改名", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VTab, { value: "offline" }, {
          default: _withCtx(() => [...(_cache[27] || (_cache[27] = [
            _createTextVNode("离线下载", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VTab, { value: "config" }, {
          default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
            _createTextVNode("插件设置", -1)
          ]))]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDivider),
    _createVNode(_component_VWindow, {
      modelValue: activeTab.value,
      "onUpdate:modelValue": _cache[21] || (_cache[21] = $event => ((activeTab).value = $event)),
      touch: false
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VWindowItem, { value: "files" }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_3, [
              _createVNode(_component_VSheet, {
                tag: "section",
                class: "transfer115-browser app-surface-static"
              }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_4, [
                    _createElementVNode("div", null, [
                      _cache[29] || (_cache[29] = _createElementVNode("strong", null, "MoviePilot 文件管理器", -1)),
                      _createElementVNode("span", null, _toDisplayString(builtinPath.value || directory.value.path || state.value.download_path || '/'), 1)
                    ]),
                    _createElementVNode("div", _hoisted_5, [
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "tonal",
                        "prepend-icon": "mdi-checkbox-multiple-marked-outline",
                        loading: loading.value,
                        disabled: !builtinReady.value,
                        onClick: syncSelectedFromBuiltin
                      }, {
                        default: _withCtx(() => [...(_cache[30] || (_cache[30] = [
                          _createTextVNode("读取勾选", -1)
                        ]))]),
                        _: 1
                      }, 8, ["loading", "disabled"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "text",
                        icon: "mdi-refresh",
                        disabled: !builtinReady.value,
                        onClick: reloadBuiltinFileManager
                      }, null, 8, ["disabled"]),
                      _createVNode(_component_VBtn, {
                        size: "small",
                        variant: "text",
                        icon: "mdi-open-in-new",
                        disabled: !builtinReady.value,
                        onClick: openBuiltinInNewTab
                      }, null, 8, ["disabled"])
                    ])
                  ]),
                  (_openBlock(), _createElementBlock("iframe", {
                    key: builtinFrameKey.value,
                    ref_key: "fileBrowserRef",
                    ref: fileBrowserRef,
                    class: "transfer115-builtin-frame",
                    src: builtinFileManagerUrl.value,
                    title: "MoviePilot 文件管理器",
                    onLoad: onBuiltinLoaded
                  }, null, 40, _hoisted_6))
                ]),
                _: 1
              }),
              _createElementVNode("main", _hoisted_7, [
                _createVNode(_component_VSheet, {
                  tag: "section",
                  class: "transfer115-panel app-surface-static"
                }, {
                  default: _withCtx(() => [
                    _cache[32] || (_cache[32] = _createElementVNode("div", { class: "transfer115-step" }, [
                      _createElementVNode("span", null, "1"),
                      _createElementVNode("div", null, [
                        _createElementVNode("strong", null, "拖选分隔文字"),
                        _createElementVNode("small", null, "像选择网页文字一样，在文件名里拖动鼠标")
                      ])
                    ], -1)),
                    (sample.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_8, [
                          _createElementVNode("div", {
                            ref_key: "sampleElement",
                            ref: sampleElement,
                            class: "transfer115-sample",
                            onMouseup: captureSelection,
                            onKeyup: captureSelection
                          }, _toDisplayString(sampleStem.value), 545),
                          (sampleExtension.value)
                            ? (_openBlock(), _createBlock(_component_VChip, {
                                key: 0,
                                size: "small",
                                variant: "tonal"
                              }, {
                                default: _withCtx(() => [
                                  _createTextVNode(_toDisplayString(sampleExtension.value), 1)
                                ]),
                                _: 1
                              }))
                            : _createCommentVNode("", true)
                        ]))
                      : (_openBlock(), _createElementBlock("div", _hoisted_9, "先在左侧选择一个文件")),
                    _createElementVNode("div", _hoisted_10, [
                      _createElementVNode("span", null, _toDisplayString(selectedText.value ? `已选：${selectedText.value}` : '尚未选择分隔文字'), 1),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        size: "small",
                        variant: "tonal",
                        disabled: !selectedText.value,
                        "prepend-icon": "mdi-content-cut",
                        onClick: addSelectedDelimiter
                      }, {
                        default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
                          _createTextVNode("以此拆分", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled"])
                    ]),
                    _createElementVNode("div", _hoisted_11, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(tokens.value, (token) => {
                        return (_openBlock(), _createBlock(_component_VChip, {
                          key: token,
                          closable: "",
                          color: "info",
                          variant: "tonal",
                          "onClick:close": $event => (removeToken(token))
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(token === ' ' ? '空格' : token), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick:close"]))
                      }), 128)),
                      (!tokens.value.length)
                        ? (_openBlock(), _createElementBlock("span", _hoisted_12, "拖选后，拆分符会显示在这里"))
                        : _createCommentVNode("", true)
                    ])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VSheet, {
                  tag: "section",
                  class: "transfer115-panel app-surface-static"
                }, {
                  default: _withCtx(() => [
                    _cache[33] || (_cache[33] = _createElementVNode("div", { class: "transfer115-step" }, [
                      _createElementVNode("span", null, "2"),
                      _createElementVNode("div", null, [
                        _createElementVNode("strong", null, "组合新名称"),
                        _createElementVNode("small", null, "片段从 1 开始，扩展名可自动保留")
                      ])
                    ], -1)),
                    _createVNode(_component_VTextField, {
                      modelValue: template.value,
                      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((template).value = $event)),
                      label: "命名模板",
                      variant: "outlined",
                      density: "comfortable",
                      "hide-details": "",
                      placeholder: "{1} - {2}"
                    }, null, 8, ["modelValue"]),
                    _createElementVNode("div", _hoisted_13, [
                      (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sampleParts.value, (part, index) => {
                        return (_openBlock(), _createBlock(_component_VBtn, {
                          key: `${index}-${part}`,
                          size: "small",
                          variant: "tonal",
                          onClick: $event => (insertPart(index + 1))
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(index + 1) + " · " + _toDisplayString(part), 1)
                          ]),
                          _: 2
                        }, 1032, ["onClick"]))
                      }), 128))
                    ]),
                    _createVNode(_component_VSwitch, {
                      modelValue: keepExtension.value,
                      "onUpdate:modelValue": _cache[4] || (_cache[4] = $event => ((keepExtension).value = $event)),
                      label: "自动保留原扩展名",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VSheet, {
                  tag: "section",
                  class: "transfer115-panel app-surface-static"
                }, {
                  default: _withCtx(() => [
                    _cache[35] || (_cache[35] = _createElementVNode("div", { class: "transfer115-step" }, [
                      _createElementVNode("span", null, "3"),
                      _createElementVNode("div", null, [
                        _createElementVNode("strong", null, "先测试，再改名"),
                        _createElementVNode("small", null, "测试不会修改115文件")
                      ])
                    ], -1)),
                    _createElementVNode("div", _hoisted_14, [
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        variant: "flat",
                        "prepend-icon": "mdi-flask-outline",
                        loading: saving.value,
                        disabled: !selectedPaths.value.length || !tokens.value.length,
                        onClick: testRename
                      }, {
                        default: _withCtx(() => [
                          _createTextVNode("测试 " + _toDisplayString(selectedPaths.value.length) + " 个文件", 1)
                        ]),
                        _: 1
                      }, 8, ["loading", "disabled"]),
                      _createVNode(_component_VBtn, {
                        color: "warning",
                        variant: "tonal",
                        "prepend-icon": "mdi-file-edit-outline",
                        disabled: !preview.value?.plan_id,
                        onClick: _cache[5] || (_cache[5] = $event => (confirmOpen.value = true))
                      }, {
                        default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                          _createTextVNode("确认改名", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled"])
                    ]),
                    (preview.value)
                      ? (_openBlock(), _createBlock(_component_VAlert, {
                          key: 0,
                          type: preview.value.errors?.length ? 'warning' : 'success',
                          variant: "tonal",
                          density: "compact"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(preview.value.msg), 1)
                          ]),
                          _: 1
                        }, 8, ["type"]))
                      : _createCommentVNode("", true),
                    (preview.value?.items?.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_15, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(preview.value.items, (item) => {
                            return (_openBlock(), _createElementBlock("article", {
                              key: item.path
                            }, [
                              _createElementVNode("span", null, _toDisplayString(item.name), 1),
                              _createVNode(_component_VIcon, {
                                icon: "mdi-arrow-right",
                                size: "small"
                              }),
                              _createElementVNode("strong", null, _toDisplayString(item.new_name), 1),
                              _createElementVNode("small", null, "拆分：" + _toDisplayString(item.parts.join(' | ')), 1),
                              (item.recognition)
                                ? (_openBlock(), _createElementBlock("div", {
                                    key: 0,
                                    class: _normalizeClass(["transfer115-preview-recognition", item.recognition.matched ? 'is-matched' : 'is-unmatched'])
                                  }, [
                                    _createVNode(_component_VIcon, {
                                      icon: item.recognition.matched ? (item.recognition.type === 'tv' ? 'mdi-television-play' : 'mdi-movie-open-outline') : 'mdi-help-circle-outline',
                                      size: "small"
                                    }, null, 8, ["icon"]),
                                    (item.recognition.matched)
                                      ? (_openBlock(), _createElementBlock("span", _hoisted_16, [
                                          _createTextVNode(_toDisplayString(item.recognition.type_label), 1),
                                          (item.recognition.episode_label)
                                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                                _createTextVNode(" · " + _toDisplayString(item.recognition.episode_label), 1)
                                              ], 64))
                                            : _createCommentVNode("", true),
                                          (item.recognition.title_year || item.recognition.title)
                                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                                _createTextVNode(" · " + _toDisplayString(item.recognition.title_year || item.recognition.title), 1)
                                              ], 64))
                                            : _createCommentVNode("", true),
                                          (item.recognition.tmdb_id)
                                            ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                                                _createTextVNode(" · TMDB " + _toDisplayString(item.recognition.tmdb_id), 1)
                                              ], 64))
                                            : _createCommentVNode("", true)
                                        ]))
                                      : (_openBlock(), _createElementBlock("span", _hoisted_17, _toDisplayString(item.recognition.error || 'MoviePilot 未识别到电影或电视剧'), 1))
                                  ], 2))
                                : _createCommentVNode("", true)
                            ]))
                          }), 128))
                        ]))
                      : _createCommentVNode("", true),
                    (renameResult.value)
                      ? (_openBlock(), _createBlock(_component_VAlert, {
                          key: 2,
                          type: renameResult.value.recognition_results?.some(item => item.matched) ? 'success' : 'warning',
                          variant: "tonal",
                          density: "compact",
                          class: "transfer115-recognition-result"
                        }, {
                          default: _withCtx(() => [
                            _createTextVNode(_toDisplayString(renameResult.value.msg), 1)
                          ]),
                          _: 1
                        }, 8, ["type"]))
                      : _createCommentVNode("", true),
                    (renameResult.value?.recognition_results?.length)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_18, [
                          (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(renameResult.value.recognition_results, (item) => {
                            return (_openBlock(), _createElementBlock("article", {
                              key: item.path,
                              class: "transfer115-recognition-row"
                            }, [
                              _createVNode(_component_VIcon, {
                                icon: item.matched ? (item.type === 'tv' ? 'mdi-television-play' : 'mdi-movie-open-outline') : 'mdi-help-circle-outline',
                                color: item.matched ? 'success' : 'warning'
                              }, null, 8, ["icon", "color"]),
                              _createElementVNode("div", null, [
                                _createElementVNode("strong", null, _toDisplayString(item.name), 1),
                                (item.matched)
                                  ? (_openBlock(), _createElementBlock("span", _hoisted_19, [
                                      _createTextVNode(_toDisplayString(item.type_label), 1),
                                      (item.episode_label)
                                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                            _createTextVNode(" · " + _toDisplayString(item.episode_label), 1)
                                          ], 64))
                                        : _createCommentVNode("", true),
                                      (item.title_year || item.title)
                                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 1 }, [
                                            _createTextVNode(" · " + _toDisplayString(item.title_year || item.title), 1)
                                          ], 64))
                                        : _createCommentVNode("", true),
                                      (item.tmdb_id)
                                        ? (_openBlock(), _createElementBlock(_Fragment, { key: 2 }, [
                                            _createTextVNode(" · TMDB " + _toDisplayString(item.tmdb_id), 1)
                                          ], 64))
                                        : _createCommentVNode("", true)
                                    ]))
                                  : (_openBlock(), _createElementBlock("span", _hoisted_20, _toDisplayString(item.error || 'TMDB 未命中电影或电视剧'), 1))
                              ])
                            ]))
                          }), 128))
                        ]))
                      : _createCommentVNode("", true)
                  ]),
                  _: 1
                })
              ])
            ])
          ]),
          _: 1
        }),
        _createVNode(_component_VWindowItem, { value: "offline" }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_21, [
              _createVNode(_component_VSheet, {
                tag: "section",
                class: "transfer115-panel app-surface-static"
              }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_22, [
                    _cache[36] || (_cache[36] = _createElementVNode("div", null, [
                      _createElementVNode("div", { class: "text-subtitle-1 font-weight-medium" }, "添加离线下载"),
                      _createElementVNode("div", { class: "text-body-2 text-medium-emphasis" }, "每行一个磁力、ed2k、HTTP 或 115 分享链接")
                    ], -1)),
                    _createVNode(_component_VChip, {
                      color: state.value.config?.auth_mode === 'cookie' ? 'warning' : 'success',
                      size: "small",
                      variant: "tonal",
                      "prepend-icon": "mdi-shield-check-outline"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(state.value.config?.auth_mode === 'cookie' ? 'Cookie授权' : 'MoviePilot 115授权'), 1)
                      ]),
                      _: 1
                    }, 8, ["color"])
                  ]),
                  _createVNode(_component_VTextarea, {
                    modelValue: offlineLinks.value,
                    "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((offlineLinks).value = $event)),
                    label: "离线下载链接",
                    rows: "7",
                    "auto-grow": "",
                    variant: "outlined",
                    placeholder: "magnet:?xt=urn:btih:...\ned2k://..."
                  }, null, 8, ["modelValue"]),
                  _createElementVNode("div", _hoisted_23, [
                    _createVNode(_component_VIcon, {
                      icon: "mdi-folder-download-outline",
                      color: "primary"
                    }),
                    _createElementVNode("div", null, [
                      _cache[37] || (_cache[37] = _createElementVNode("span", null, "保存到", -1)),
                      _createElementVNode("strong", null, _toDisplayString(state.value.download_path || '115根目录'), 1)
                    ]),
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      onClick: _cache[7] || (_cache[7] = $event => (activeTab.value = 'config'))
                    }, {
                      default: _withCtx(() => [...(_cache[38] || (_cache[38] = [
                        _createTextVNode("修改目录", -1)
                      ]))]),
                      _: 1
                    })
                  ]),
                  _createElementVNode("div", _hoisted_24, [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      variant: "flat",
                      "prepend-icon": "mdi-download",
                      loading: saving.value,
                      disabled: !offlineLinks.value.trim() || !state.value.enabled,
                      onClick: submitOffline
                    }, {
                      default: _withCtx(() => [...(_cache[39] || (_cache[39] = [
                        _createTextVNode("提交离线任务", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode(_component_VBtn, {
                      variant: "tonal",
                      "prepend-icon": "mdi-refresh",
                      loading: offlineLoading.value,
                      disabled: !state.value.enabled,
                      onClick: _cache[8] || (_cache[8] = $event => (loadOfflineTasks()))
                    }, {
                      default: _withCtx(() => [...(_cache[40] || (_cache[40] = [
                        _createTextVNode("刷新列表", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode(_component_VBtn, {
                      color: "info",
                      variant: "tonal",
                      "prepend-icon": "mdi-progress-check",
                      loading: offlineLoading.value,
                      disabled: !state.value.enabled,
                      onClick: checkOfflineTasks
                    }, {
                      default: _withCtx(() => [...(_cache[41] || (_cache[41] = [
                        _createTextVNode("检查任务", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"]),
                    _createVNode(_component_VBtn, {
                      color: "success",
                      variant: "tonal",
                      "prepend-icon": "mdi-folder-move-outline",
                      loading: saving.value,
                      disabled: !state.value.enabled || !state.value.download_path,
                      onClick: organizeDownloads
                    }, {
                      default: _withCtx(() => [...(_cache[42] || (_cache[42] = [
                        _createTextVNode("整理下载目录", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading", "disabled"])
                  ])
                ]),
                _: 1
              }),
              _createVNode(_component_VSheet, {
                tag: "section",
                class: "transfer115-panel app-surface-static"
              }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_25, [
                    _createElementVNode("div", null, [
                      _cache[43] || (_cache[43] = _createElementVNode("strong", null, "离线任务", -1)),
                      _createElementVNode("span", null, "最近 " + _toDisplayString(offlineTasks.value.length) + " 个任务", 1)
                    ]),
                    (offlineLoading.value)
                      ? (_openBlock(), _createBlock(_component_VProgressCircular, {
                          key: 0,
                          indeterminate: "",
                          size: "22",
                          width: "2",
                          color: "primary"
                        }))
                      : _createCommentVNode("", true)
                  ]),
                  (offlineTasks.value.length)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_26, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(offlineTasks.value, (task) => {
                          return (_openBlock(), _createElementBlock("article", {
                            key: task.id || `${task.name}-${task.created_at}`,
                            class: "transfer115-task-row"
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: taskIcon(task.status),
                              color: taskColor(task.status)
                            }, null, 8, ["icon", "color"]),
                            _createElementVNode("div", _hoisted_27, [
                              _createElementVNode("div", null, [
                                _createElementVNode("strong", null, _toDisplayString(task.name || '未命名任务'), 1),
                                _createVNode(_component_VChip, {
                                  color: taskColor(task.status),
                                  size: "x-small",
                                  variant: "tonal"
                                }, {
                                  default: _withCtx(() => [
                                    _createTextVNode(_toDisplayString(task.status_label), 1)
                                  ]),
                                  _: 2
                                }, 1032, ["color"])
                              ]),
                              _createElementVNode("span", null, [
                                _createTextVNode(_toDisplayString(task.save_path || state.value.download_path || '115根目录'), 1),
                                (task.size)
                                  ? (_openBlock(), _createElementBlock(_Fragment, { key: 0 }, [
                                      _createTextVNode(" · " + _toDisplayString(formatBytes(task.size)), 1)
                                    ], 64))
                                  : _createCommentVNode("", true)
                              ]),
                              (task.status === 'downloading')
                                ? (_openBlock(), _createBlock(_component_VProgressLinear, {
                                    key: 0,
                                    "model-value": task.progress,
                                    height: "4",
                                    color: "info",
                                    rounded: ""
                                  }, null, 8, ["model-value"]))
                                : _createCommentVNode("", true),
                              (task.error)
                                ? (_openBlock(), _createElementBlock("small", _hoisted_28, _toDisplayString(task.error), 1))
                                : _createCommentVNode("", true)
                            ]),
                            _createElementVNode("span", _hoisted_29, _toDisplayString(task.status === 'downloading' ? `${task.progress}%` : ''), 1)
                          ]))
                        }), 128))
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_30, "暂无离线任务"))
                ]),
                _: 1
              })
            ])
          ]),
          _: 1
        }),
        _createVNode(_component_VWindowItem, { value: "config" }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_31, [
              _createVNode(_component_VSheet, { class: "transfer115-panel app-surface-static" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_32, [
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.enabled,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((settings.value.enabled) = $event)),
                      label: "启用插件",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.auto_organize,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((settings.value.auto_organize) = $event)),
                      label: "自动整理",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.notify_enabled,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((settings.value.notify_enabled) = $event)),
                      label: "发送通知",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.rename_enabled,
                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((settings.value.rename_enabled) = $event)),
                      label: "启用文件改名",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSelect, {
                      modelValue: settings.value.auth_mode,
                      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((settings.value.auth_mode) = $event)),
                      label: "115授权方式",
                      items: [{ title: 'MoviePilot授权', value: 'mp_oauth' }, { title: 'Cookie', value: 'cookie' }],
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSelect, {
                      modelValue: settings.value.transfer_type,
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((settings.value.transfer_type) = $event)),
                      label: "整理方式",
                      items: [{ title: '移动', value: 'move' }, { title: '复制', value: 'copy' }],
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.download_path,
                      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((settings.value.download_path) = $event)),
                      label: "下载目录",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.library_path,
                      "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((settings.value.library_path) = $event)),
                      label: "媒体库目录",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.fail_path,
                      "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((settings.value.fail_path) = $event)),
                      label: "失败目录",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    (settings.value.auth_mode === 'cookie')
                      ? (_openBlock(), _createBlock(_component_VTextField, {
                          key: 0,
                          modelValue: settings.value.cookie,
                          "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((settings.value.cookie) = $event)),
                          label: "115 Cookie",
                          type: "password",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]))
                      : _createCommentVNode("", true),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.poll_interval,
                      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((settings.value.poll_interval) = $event)),
                      modelModifiers: { number: true },
                      label: "轮询间隔（分钟）",
                      type: "number",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.rename_max_files,
                      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((settings.value.rename_max_files) = $event)),
                      modelModifiers: { number: true },
                      label: "单次改名上限",
                      type: "number",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _createElementVNode("div", _hoisted_33, [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      "prepend-icon": "mdi-content-save-outline",
                      loading: saving.value,
                      onClick: saveSettings
                    }, {
                      default: _withCtx(() => [...(_cache[44] || (_cache[44] = [
                        _createTextVNode("保存设置", -1)
                      ]))]),
                      _: 1
                    }, 8, ["loading"])
                  ])
                ]),
                _: 1
              })
            ])
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"]),
    _createVNode(_component_VDialog, {
      modelValue: confirmOpen.value,
      "onUpdate:modelValue": _cache[23] || (_cache[23] = $event => ((confirmOpen).value = $event)),
      "max-width": "560"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VCard, null, {
          default: _withCtx(() => [
            _createVNode(_component_VCardTitle, null, {
              default: _withCtx(() => [
                _createTextVNode("确认修改 " + _toDisplayString(preview.value?.items?.filter(item => !item.unchanged).length || 0) + " 个文件名？", 1)
              ]),
              _: 1
            }),
            _createVNode(_component_VCardText, null, {
              default: _withCtx(() => [...(_cache[45] || (_cache[45] = [
                _createTextVNode("将按刚才的测试结果修改115远端文件。执行前仍会检查文件是否存在以及是否有同名冲突。", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[22] || (_cache[22] = $event => (confirmOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[46] || (_cache[46] = [
                    _createTextVNode("取消", -1)
                  ]))]),
                  _: 1
                }),
                _createVNode(_component_VBtn, {
                  color: "warning",
                  variant: "flat",
                  loading: saving.value,
                  onClick: applyRename
                }, {
                  default: _withCtx(() => [...(_cache[47] || (_cache[47] = [
                    _createTextVNode("确认改名", -1)
                  ]))]),
                  _: 1
                }, 8, ["loading"])
              ]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    }, 8, ["modelValue"])
  ], 2))
}
}

};
const Transfer115Workbench = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-75b1e338"]]);

export { Transfer115Workbench as T };
