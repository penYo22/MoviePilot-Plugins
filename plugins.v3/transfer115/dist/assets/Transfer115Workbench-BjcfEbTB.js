import { importShared } from './__federation_fn_import-JrT3xvdd.js';

const _export_sfc = (sfc, props) => {
  const target = sfc.__vccOpts || sfc;
  for (const [key, val] of props) {
    target[key] = val;
  }
  return target;
};

const {createElementVNode:_createElementVNode,toDisplayString:_toDisplayString,resolveComponent:_resolveComponent,mergeProps:_mergeProps,createVNode:_createVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createTextVNode:_createTextVNode,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,withModifiers:_withModifiers,normalizeClass:_normalizeClass} = await importShared('vue');


const _hoisted_1 = { class: "transfer115-header" };
const _hoisted_2 = { class: "transfer115-header__actions" };
const _hoisted_3 = { class: "transfer115-workspace" };
const _hoisted_4 = { class: "transfer115-panel-head" };
const _hoisted_5 = { class: "transfer115-breadcrumb" };
const _hoisted_6 = {
  key: 0,
  class: "transfer115-loading"
};
const _hoisted_7 = {
  key: 1,
  class: "transfer115-file-list"
};
const _hoisted_8 = ["onClick"];
const _hoisted_9 = { class: "transfer115-file-name" };
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "transfer115-file-name" };
const _hoisted_12 = {
  key: 0,
  class: "transfer115-empty"
};
const _hoisted_13 = { class: "transfer115-editor" };
const _hoisted_14 = {
  key: 0,
  class: "transfer115-sample-wrap"
};
const _hoisted_15 = {
  key: 1,
  class: "transfer115-empty"
};
const _hoisted_16 = { class: "transfer115-selection-bar" };
const _hoisted_17 = { class: "transfer115-token-row" };
const _hoisted_18 = {
  key: 0,
  class: "text-body-2 text-medium-emphasis"
};
const _hoisted_19 = { class: "transfer115-part-buttons" };
const _hoisted_20 = { class: "transfer115-actions" };
const _hoisted_21 = {
  key: 1,
  class: "transfer115-preview-list"
};
const _hoisted_22 = { class: "transfer115-settings" };
const _hoisted_23 = { class: "transfer115-settings-grid" };
const _hoisted_24 = { class: "transfer115-settings-actions" };

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
const confirmOpen = ref(false);
const settings = ref({});

const files = computed(() => directory.value.items.filter(item => item.type !== 'dir'));
const folders = computed(() => directory.value.items.filter(item => item.type === 'dir'));
const selectedFiles = computed(() => files.value.filter(item => selectedPaths.value.includes(item.path)));
const sample = computed(() => files.value.find(item => item.path === samplePath.value) || selectedFiles.value[0] || files.value[0] || null);
const allFilesSelected = computed(() => files.value.length > 0 && files.value.every(item => selectedPaths.value.includes(item.path)));
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

function formatBytes(value) {
  const size = Number(value || 0);
  if (!size) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const index = Math.min(Math.floor(Math.log(size) / Math.log(1024)), units.length - 1);
  return `${(size / 1024 ** index).toFixed(index > 1 ? 1 : 0)} ${units[index]}`
}

async function loadState() {
  const data = assertResult(unwrap(await props.api.get(`${pluginBase.value}/plugin_state`)));
  state.value = data;
  settings.value = { ...(data.config || {}) };
  tokens.value = [...(data.split_tokens || [])];
  template.value = data.split_template || '{1} - {2}';
  keepExtension.value = data.split_keep_extension !== false;
}

async function loadDirectory(path = '') {
  loading.value = true;
  error.value = '';
  try {
    const query = new URLSearchParams({ path: path || state.value.download_path || '/' });
    directory.value = assertResult(unwrap(await props.api.get(`${pluginBase.value}/file_manager?${query}`)));
    selectedPaths.value = [];
    samplePath.value = files.value[0]?.path || '';
    preview.value = null;
  } catch (err) {
    error.value = err?.message || '读取115目录失败';
  } finally {
    loading.value = false;
  }
}

async function initialize() {
  loading.value = true;
  try {
    await loadState();
    await loadDirectory(state.value.download_path || '/');
  } catch (err) {
    error.value = err?.message || '加载文件管理器失败';
  } finally {
    loading.value = false;
  }
}

function toggleFile(path) {
  preview.value = null;
  selectedPaths.value = selectedPaths.value.includes(path)
    ? selectedPaths.value.filter(item => item !== path)
    : [...selectedPaths.value, path];
  if (!samplePath.value || !selectedPaths.value.includes(samplePath.value)) samplePath.value = selectedPaths.value[0] || path;
}

function toggleAllFiles() {
  preview.value = null;
  selectedPaths.value = allFilesSelected.value ? [] : files.value.map(item => item.path);
  samplePath.value = selectedPaths.value[0] || files.value[0]?.path || '';
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
    await loadDirectory(directory.value.path);
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
onMounted(initialize);

return (_ctx, _cache) => {
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VTooltip = _resolveComponent("VTooltip");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VTab = _resolveComponent("VTab");
  const _component_VTabs = _resolveComponent("VTabs");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VProgressCircular = _resolveComponent("VProgressCircular");
  const _component_VCheckboxBtn = _resolveComponent("VCheckboxBtn");
  const _component_VSheet = _resolveComponent("VSheet");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VWindowItem = _resolveComponent("VWindowItem");
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
        _cache[23] || (_cache[23] = _createElementVNode("h1", null, "115 文件管理器", -1)),
        _createElementVNode("p", null, _toDisplayString(directory.value.path || state.value.download_path || '/'), 1)
      ]),
      _createElementVNode("div", _hoisted_2, [
        _createVNode(_component_VTooltip, { text: "刷新目录" }, {
          activator: _withCtx(({ props: tipProps }) => [
            _createVNode(_component_VBtn, _mergeProps(tipProps, {
              icon: "mdi-refresh",
              variant: "text",
              loading: loading.value,
              onClick: _cache[0] || (_cache[0] = $event => (loadDirectory(directory.value.path)))
            }), null, 16, ["loading"])
          ]),
          _: 1
        }),
        (__props.showClose)
          ? (_openBlock(), _createBlock(_component_VBtn, {
              key: 0,
              icon: "mdi-close",
              variant: "text",
              onClick: _cache[1] || (_cache[1] = $event => (_ctx.$emit('close')))
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
          "onClick:close": _cache[2] || (_cache[2] = $event => (error.value = ''))
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
          default: _withCtx(() => [...(_cache[24] || (_cache[24] = [
            _createTextVNode("插件尚未启用，请先到设置页启用。", -1)
          ]))]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createVNode(_component_VTabs, {
      modelValue: activeTab.value,
      "onUpdate:modelValue": _cache[3] || (_cache[3] = $event => ((activeTab).value = $event)),
      color: "primary",
      class: "transfer115-tabs"
    }, {
      default: _withCtx(() => [
        _createVNode(_component_VTab, { value: "files" }, {
          default: _withCtx(() => [...(_cache[25] || (_cache[25] = [
            _createTextVNode("文件改名", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VTab, { value: "config" }, {
          default: _withCtx(() => [...(_cache[26] || (_cache[26] = [
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
      "onUpdate:modelValue": _cache[20] || (_cache[20] = $event => ((activeTab).value = $event)),
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
                      _cache[27] || (_cache[27] = _createElementVNode("strong", null, "选择文件", -1)),
                      _createElementVNode("span", null, "已选 " + _toDisplayString(selectedPaths.value.length) + " 个", 1)
                    ]),
                    _createVNode(_component_VBtn, {
                      size: "small",
                      variant: "text",
                      disabled: !files.value.length,
                      onClick: toggleAllFiles
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(allFilesSelected.value ? '取消全选' : '全选文件'), 1)
                      ]),
                      _: 1
                    }, 8, ["disabled"])
                  ]),
                  _createElementVNode("div", _hoisted_5, [
                    (directory.value.parent !== null)
                      ? (_openBlock(), _createBlock(_component_VBtn, {
                          key: 0,
                          icon: "mdi-arrow-up",
                          size: "small",
                          variant: "text",
                          onClick: _cache[4] || (_cache[4] = $event => (loadDirectory(directory.value.parent)))
                        }))
                      : (_openBlock(), _createBlock(_component_VIcon, {
                          key: 1,
                          icon: "mdi-cloud-outline",
                          size: "small"
                        })),
                    _createElementVNode("span", null, _toDisplayString(directory.value.path), 1)
                  ]),
                  (loading.value)
                    ? (_openBlock(), _createElementBlock("div", _hoisted_6, [
                        _createVNode(_component_VProgressCircular, {
                          indeterminate: "",
                          color: "primary"
                        })
                      ]))
                    : (_openBlock(), _createElementBlock("div", _hoisted_7, [
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(folders.value, (folder) => {
                          return (_openBlock(), _createElementBlock("button", {
                            key: folder.path,
                            type: "button",
                            class: "transfer115-file-row",
                            onClick: $event => (loadDirectory(folder.path))
                          }, [
                            _createVNode(_component_VIcon, {
                              icon: "mdi-folder-outline",
                              color: "warning"
                            }),
                            _createElementVNode("span", _hoisted_9, _toDisplayString(folder.name), 1),
                            _createVNode(_component_VIcon, {
                              icon: "mdi-chevron-right",
                              size: "small"
                            })
                          ], 8, _hoisted_8))
                        }), 128)),
                        (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(files.value, (file) => {
                          return (_openBlock(), _createElementBlock("div", {
                            key: file.path,
                            class: _normalizeClass(["transfer115-file-row transfer115-file-row--selectable", { 'transfer115-file-row--selected': selectedPaths.value.includes(file.path) }])
                          }, [
                            _createVNode(_component_VCheckboxBtn, {
                              "model-value": selectedPaths.value.includes(file.path),
                              onClick: _withModifiers($event => (toggleFile(file.path)), ["prevent"])
                            }, null, 8, ["model-value", "onClick"]),
                            _createElementVNode("button", {
                              type: "button",
                              class: "transfer115-file-main",
                              onClick: _withModifiers($event => (samplePath.value = file.path), ["prevent"])
                            }, [
                              _createElementVNode("span", _hoisted_11, _toDisplayString(file.name), 1),
                              _createElementVNode("small", null, _toDisplayString(formatBytes(file.size)), 1)
                            ], 8, _hoisted_10),
                            _createVNode(_component_VTooltip, { text: "设为拆分样例" }, {
                              activator: _withCtx(({ props: tipProps }) => [
                                _createVNode(_component_VBtn, _mergeProps({ ref_for: true }, tipProps, {
                                  icon: sample.value?.path === file.path ? 'mdi-text-box-check-outline' : 'mdi-text-box-outline',
                                  size: "small",
                                  variant: "text",
                                  onClick: _withModifiers($event => (samplePath.value = file.path), ["prevent"])
                                }), null, 16, ["icon", "onClick"])
                              ]),
                              _: 2
                            }, 1024)
                          ], 2))
                        }), 128)),
                        (!folders.value.length && !files.value.length)
                          ? (_openBlock(), _createElementBlock("div", _hoisted_12, "当前目录为空"))
                          : _createCommentVNode("", true)
                      ]))
                ]),
                _: 1
              }),
              _createElementVNode("main", _hoisted_13, [
                _createVNode(_component_VSheet, {
                  tag: "section",
                  class: "transfer115-panel app-surface-static"
                }, {
                  default: _withCtx(() => [
                    _cache[29] || (_cache[29] = _createElementVNode("div", { class: "transfer115-step" }, [
                      _createElementVNode("span", null, "1"),
                      _createElementVNode("div", null, [
                        _createElementVNode("strong", null, "拖选分隔文字"),
                        _createElementVNode("small", null, "像选择网页文字一样，在文件名里拖动鼠标")
                      ])
                    ], -1)),
                    (sample.value)
                      ? (_openBlock(), _createElementBlock("div", _hoisted_14, [
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
                      : (_openBlock(), _createElementBlock("div", _hoisted_15, "先在左侧选择一个文件")),
                    _createElementVNode("div", _hoisted_16, [
                      _createElementVNode("span", null, _toDisplayString(selectedText.value ? `已选：${selectedText.value}` : '尚未选择分隔文字'), 1),
                      _createVNode(_component_VBtn, {
                        color: "primary",
                        size: "small",
                        variant: "tonal",
                        disabled: !selectedText.value,
                        "prepend-icon": "mdi-content-cut",
                        onClick: addSelectedDelimiter
                      }, {
                        default: _withCtx(() => [...(_cache[28] || (_cache[28] = [
                          _createTextVNode("以此拆分", -1)
                        ]))]),
                        _: 1
                      }, 8, ["disabled"])
                    ]),
                    _createElementVNode("div", _hoisted_17, [
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
                        ? (_openBlock(), _createElementBlock("span", _hoisted_18, "拖选后，拆分符会显示在这里"))
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
                    _cache[30] || (_cache[30] = _createElementVNode("div", { class: "transfer115-step" }, [
                      _createElementVNode("span", null, "2"),
                      _createElementVNode("div", null, [
                        _createElementVNode("strong", null, "组合新名称"),
                        _createElementVNode("small", null, "片段从 1 开始，扩展名可自动保留")
                      ])
                    ], -1)),
                    _createVNode(_component_VTextField, {
                      modelValue: template.value,
                      "onUpdate:modelValue": _cache[5] || (_cache[5] = $event => ((template).value = $event)),
                      label: "命名模板",
                      variant: "outlined",
                      density: "comfortable",
                      "hide-details": "",
                      placeholder: "{1} - {2}"
                    }, null, 8, ["modelValue"]),
                    _createElementVNode("div", _hoisted_19, [
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
                      "onUpdate:modelValue": _cache[6] || (_cache[6] = $event => ((keepExtension).value = $event)),
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
                    _cache[32] || (_cache[32] = _createElementVNode("div", { class: "transfer115-step" }, [
                      _createElementVNode("span", null, "3"),
                      _createElementVNode("div", null, [
                        _createElementVNode("strong", null, "先测试，再改名"),
                        _createElementVNode("small", null, "测试不会修改115文件")
                      ])
                    ], -1)),
                    _createElementVNode("div", _hoisted_20, [
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
                        onClick: _cache[7] || (_cache[7] = $event => (confirmOpen.value = true))
                      }, {
                        default: _withCtx(() => [...(_cache[31] || (_cache[31] = [
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
                      ? (_openBlock(), _createElementBlock("div", _hoisted_21, [
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
                              _createElementVNode("small", null, "拆分：" + _toDisplayString(item.parts.join(' | ')), 1)
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
        _createVNode(_component_VWindowItem, { value: "config" }, {
          default: _withCtx(() => [
            _createElementVNode("div", _hoisted_22, [
              _createVNode(_component_VSheet, { class: "transfer115-panel app-surface-static" }, {
                default: _withCtx(() => [
                  _createElementVNode("div", _hoisted_23, [
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.enabled,
                      "onUpdate:modelValue": _cache[8] || (_cache[8] = $event => ((settings.value.enabled) = $event)),
                      label: "启用插件",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.auto_organize,
                      "onUpdate:modelValue": _cache[9] || (_cache[9] = $event => ((settings.value.auto_organize) = $event)),
                      label: "自动整理",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.notify_enabled,
                      "onUpdate:modelValue": _cache[10] || (_cache[10] = $event => ((settings.value.notify_enabled) = $event)),
                      label: "发送通知",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSwitch, {
                      modelValue: settings.value.rename_enabled,
                      "onUpdate:modelValue": _cache[11] || (_cache[11] = $event => ((settings.value.rename_enabled) = $event)),
                      label: "启用文件改名",
                      color: "primary",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSelect, {
                      modelValue: settings.value.auth_mode,
                      "onUpdate:modelValue": _cache[12] || (_cache[12] = $event => ((settings.value.auth_mode) = $event)),
                      label: "115授权方式",
                      items: [{ title: 'MoviePilot授权', value: 'mp_oauth' }, { title: 'Cookie', value: 'cookie' }],
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VSelect, {
                      modelValue: settings.value.transfer_type,
                      "onUpdate:modelValue": _cache[13] || (_cache[13] = $event => ((settings.value.transfer_type) = $event)),
                      label: "整理方式",
                      items: [{ title: '移动', value: 'move' }, { title: '复制', value: 'copy' }],
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.download_path,
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = $event => ((settings.value.download_path) = $event)),
                      label: "下载目录",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.library_path,
                      "onUpdate:modelValue": _cache[15] || (_cache[15] = $event => ((settings.value.library_path) = $event)),
                      label: "媒体库目录",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.fail_path,
                      "onUpdate:modelValue": _cache[16] || (_cache[16] = $event => ((settings.value.fail_path) = $event)),
                      label: "失败目录",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    (settings.value.auth_mode === 'cookie')
                      ? (_openBlock(), _createBlock(_component_VTextField, {
                          key: 0,
                          modelValue: settings.value.cookie,
                          "onUpdate:modelValue": _cache[17] || (_cache[17] = $event => ((settings.value.cookie) = $event)),
                          label: "115 Cookie",
                          type: "password",
                          variant: "outlined",
                          "hide-details": ""
                        }, null, 8, ["modelValue"]))
                      : _createCommentVNode("", true),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.poll_interval,
                      "onUpdate:modelValue": _cache[18] || (_cache[18] = $event => ((settings.value.poll_interval) = $event)),
                      modelModifiers: { number: true },
                      label: "轮询间隔（分钟）",
                      type: "number",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"]),
                    _createVNode(_component_VTextField, {
                      modelValue: settings.value.rename_max_files,
                      "onUpdate:modelValue": _cache[19] || (_cache[19] = $event => ((settings.value.rename_max_files) = $event)),
                      modelModifiers: { number: true },
                      label: "单次改名上限",
                      type: "number",
                      variant: "outlined",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _createElementVNode("div", _hoisted_24, [
                    _createVNode(_component_VBtn, {
                      color: "primary",
                      "prepend-icon": "mdi-content-save-outline",
                      loading: saving.value,
                      onClick: saveSettings
                    }, {
                      default: _withCtx(() => [...(_cache[33] || (_cache[33] = [
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
      "onUpdate:modelValue": _cache[22] || (_cache[22] = $event => ((confirmOpen).value = $event)),
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
              default: _withCtx(() => [...(_cache[34] || (_cache[34] = [
                _createTextVNode("将按刚才的测试结果修改115远端文件。执行前仍会检查文件是否存在以及是否有同名冲突。", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VCardActions, null, {
              default: _withCtx(() => [
                _createVNode(_component_VSpacer),
                _createVNode(_component_VBtn, {
                  variant: "text",
                  onClick: _cache[21] || (_cache[21] = $event => (confirmOpen.value = false))
                }, {
                  default: _withCtx(() => [...(_cache[35] || (_cache[35] = [
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
                  default: _withCtx(() => [...(_cache[36] || (_cache[36] = [
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
const Transfer115Workbench = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-48d6e44f"]]);

export { Transfer115Workbench as T };
