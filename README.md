# MoviePilot Plugins

免责声明：本插件未经充分测试，使用115网盘离线下载及API功能存在账号被封禁风险，后果自负，封号自理。建议在小号或测试账号上使用。

## MoviePilot V3

- V3 插件源码：`plugins.v3/transfer115/`
- V3 市场索引：`package.v3.json`
- 最低版本：MoviePilot `>=3.0.0`
- V2 插件保留在 `plugins.v2/`，并在 `package.v2.json` 标记为不由 V3 回退加载。

`Transfer115 5.0.0` 在原有离线任务、轮询和自动整理能力上增加了 115 媒体识别与改名功能：先使用 MoviePilot 媒体识别链及当前命名模板生成预览，再由用户确认执行批量改名。远端改名依赖 MoviePilot 内置 115 授权，预览计划有效期为 30 分钟。
