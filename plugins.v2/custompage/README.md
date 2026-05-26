# CustomPage - 自定义美化页面

通过侧栏全页入口展示美观的自定义仪表板页面，包含欢迎卡片、快捷导航、系统信息等美化元素。

## 功能特性

- 根据时间段动态显示问候语
- 实时时间和日期显示
- 快捷导航卡片（探索发现、我的订阅、下载管理、媒体整理、历史记录、系统设置）
- 系统信息展示
- 使用 Vuetify 组件构建，视觉效果美观

## 安装方式

1. 在 MoviePilot 插件管理中添加本仓库地址
2. 搜索并安装「自定义美化页面」插件
3. 在插件设置中启用
4. 侧栏将出现「美化首页」导航入口

## 前端开发

前端源码位于 `frontend/` 目录，使用 Vue 3 + TypeScript + Vite + Vuetify 构建。

### 重新构建前端

```bash
cd frontend
npm install
npm run build
```

构建完成后，将 `frontend/dist/assets/` 目录下生成的文件复制到 `../dist/assets/` 目录中：

```bash
cp dist/assets/*.js ../dist/assets/
```

### 项目结构

```
frontend/
  package.json          # 依赖声明
  vite.config.ts        # Vite + Module Federation 配置
  tsconfig.json         # TypeScript 配置
  src/
    main.ts             # 应用入口
    App.vue             # 根组件
    components/
      AppPage.vue       # 侧栏主页面组件 (props: api, navKey, pluginId)
      Page.vue          # 插件详情页组件
      Config.vue        # 插件配置页组件
```

### Module Federation 配置

本插件通过 `@originjs/vite-plugin-federation` 暴露三个组件：

- `./AppPage` - 侧栏导航页面（主仪表板）
- `./Page` - 插件详情页
- `./Config` - 插件配置页

共享依赖 `vue` 和 `vuetify` 由宿主应用提供，不需要打包。

## 自定义页面内容

编辑 `frontend/src/components/AppPage.vue` 文件可自定义仪表板内容。
修改后需要重新构建并替换 `dist/assets/` 中的文件。

## 版本历史

- v1.0: 初始版本，包含欢迎卡片、快捷导航、系统信息展示
