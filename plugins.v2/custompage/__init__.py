from typing import Any, Dict, List, Optional, Tuple

from app.plugins import _PluginBase


class CustomPage(_PluginBase):
    # 插件名称
    plugin_name = "自定义美化页面"
    # 插件描述
    plugin_desc = "通过侧栏全页入口展示美观的自定义仪表板页面，包含欢迎卡片、快捷导航、系统信息等美化元素"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Frontend/refs/heads/v2/public/logo.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "penYo22"
    # 作者主页
    author_url = "https://github.com/penYo22"
    # 插件配置项ID前缀
    plugin_config_prefix = "custompage_"
    # 加载顺序
    plugin_order = 1
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled: bool = False

    def init_plugin(self, config: dict = None):
        if not config:
            return
        self._enabled = config.get("enabled", False)

    def get_state(self) -> bool:
        return self._enabled

    def get_render_mode(self) -> Tuple[str, str]:
        return ("vue", "dist/assets")

    def get_sidebar_nav(self) -> List[dict]:
        return [
            {
                "nav_key": "CustomPageDashboard",
                "section": "start",
                "title": "美化首页",
                "icon": "mdi-view-dashboard",
                "permission": "admin"
            }
        ]

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "enabled",
                                            "label": "启用插件"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "text": "启用后将在侧栏添加「美化首页」入口，展示自定义仪表板页面。"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False
        }

    def get_page(self) -> List[dict]:
        return [{
            "component": "div",
            "text": "请通过侧栏「美化首页」入口访问自定义仪表板页面",
            "props": {"class": "text-center pa-4"}
        }]

    def get_service(self) -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        pass
