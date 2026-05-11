import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType


class Transfer115(_PluginBase):
    # 插件名称
    plugin_name = "115离线下载"
    # 插件描述
    plugin_desc = "⚠️ 未经测试，封号自理。添加115离线下载任务，支持磁力/ed2k/115分享链接"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Frontend/refs/heads/v2/src/assets/images/misc/u115.png"
    # 插件版本
    plugin_version = "4.0"
    # 插件作者
    plugin_author = "penYo22"
    # 作者主页
    author_url = "https://github.com/penYo22"
    # 插件配置项ID前缀
    plugin_config_prefix = "transfer115_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled: bool = False
    _notify_enabled: bool = False
    _download_path: str = ""
    _auth_mode: str = "mp_oauth"
    _cookie: str = ""
    _api_interval: int = 0

    def _get_u115_oper(self):
        """获取115 OAuth存储实例"""
        try:
            from app.modules.filemanager.storages.u115 import U115Pan
            oper = U115Pan()
            if oper.check():
                return oper
        except Exception as e:
            logger.warning(f"Transfer115: 获取115存储实例失败: {e}")
        return None

    def _get_cookie_oper(self):
        """初始化Cookie客户端"""
        if not self._cookie:
            return None
        try:
            from p115client import P115Client
            client = P115Client(cookies=self._cookie)
            return client
        except Exception as e:
            logger.warning(f"Transfer115: 初始化Cookie客户端失败: {e}")
            return None

    def _sleep_if_needed(self):
        """API调用间隔"""
        if self._api_interval > 0:
            import time
            time.sleep(self._api_interval)

    def _get_folder_id_by_path_cookie(self, path: str, oper) -> Optional[int]:
        """Cookie模式下通过路径获取文件夹ID"""
        try:
            parts = [p for p in path.strip("/").split("/") if p]
            current_id = 0
            for part in parts:
                self._sleep_if_needed()
                resp = oper.fs_files({"cid": current_id, "limit": 1000})
                items = resp.get("data", [])
                found = None
                for item in items:
                    if item.get("n") == part and item.get("fid") is None:
                        found = item.get("cid") or item.get("fid")
                        break
                if found is None:
                    return None
                current_id = int(found)
            return current_id
        except Exception as e:
            logger.warning(f"Transfer115: cookie模式获取目录ID失败: {e}")
            return None

    def init_plugin(self, config: dict = None):
        if not config:
            return

        self._enabled = config.get("enabled", False)
        self._notify_enabled = config.get("notify_enabled", False)
        self._auth_mode = config.get("auth_mode", "mp_oauth")
        self._cookie = config.get("cookie", "").strip()
        self._download_path = config.get("download_path", "").strip()
        self._api_interval = int(config.get("api_interval", 0) or 0)

        # 处理立即提交的链接
        link_input = config.get("link_input", "").strip()
        if link_input:
            lines = [l.strip() for l in link_input.splitlines() if l.strip()]
            if lines:
                self._submit_links(lines)

            # 清空 link_input
            self.update_config({
                "enabled": self._enabled,
                "notify_enabled": self._notify_enabled,
                "auth_mode": self._auth_mode,
                "cookie": self._cookie,
                "download_path": self._download_path,
                "api_interval": self._api_interval,
                "link_input": ""
            })

    def _submit_links(self, lines: List[str]):
        """提交离线下载链接"""
        if self._auth_mode == "cookie":
            oper = self._get_cookie_oper()
        else:
            oper = self._get_u115_oper()

        if not oper:
            logger.warning("Transfer115: 115未授权或Cookie无效，无法提交链接")
            return

        try:
            if self._auth_mode == "cookie":
                wp_path_id = None
                if self._download_path:
                    wp_path_id = self._get_folder_id_by_path_cookie(self._download_path, oper)
                payload = {"urls": "\n".join(lines)}
                if wp_path_id is not None:
                    payload["wp_path_id"] = wp_path_id
                self._sleep_if_needed()
                oper.offline_add_urls(payload)
            else:
                wp_path_id = None
                if self._download_path:
                    try:
                        folder_item = oper.get_folder(Path(self._download_path))
                        if folder_item:
                            wp_path_id = int(folder_item.fileid)
                    except Exception as e:
                        logger.warning(f"Transfer115: 无法解析下载目录ID，将使用根目录: {e}")
                data = {"urls": "\n".join(lines)}
                if wp_path_id is not None:
                    data["wp_path_id"] = wp_path_id
                self._sleep_if_needed()
                oper._request_api("POST", "/open/offline/add_task_urls", data=data)

            logger.info(f"Transfer115: 添加离线任务成功，共 {len(lines)} 条")
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Organize,
                    title="115离线任务已提交",
                    text=f"已提交 {len(lines)} 条离线下载任务"
                )
        except Exception as e:
            logger.error(f"Transfer115: 添加离线任务失败: {e}")

    def get_state(self) -> bool:
        return self._enabled

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
                    # 行1：启用插件 | 发送通知 | 授权方式
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
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify_enabled",
                                            "label": "发送通知"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "auth_mode",
                                            "label": "授权方式",
                                            "items": [
                                                {"title": "共用MP授权", "value": "mp_oauth"},
                                                {"title": "手动填写Cookie", "value": "cookie"}
                                            ]
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行2：Cookie
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cookie",
                                            "label": "Cookie",
                                            "type": "password",
                                            "placeholder": "仅Cookie模式需要填写（UID=xxx;CID=xxx;SEID=xxx）"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行3：下载目录 | API间隔
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 8},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "download_path",
                                            "label": "离线下载保存目录",
                                            "placeholder": "115云盘路径，如 /下载 或 /待整理"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "api_interval",
                                            "label": "API间隔(秒)",
                                            "placeholder": "0",
                                            "hint": "建议1-3秒，避免风控",
                                            "persistent-hint": True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行4：添加离线下载链接
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "link_input",
                                            "label": "添加离线下载链接",
                                            "placeholder": "支持磁力链接、ed2k链接、115分享链接，每行一个，保存后自动提交",
                                            "rows": 5,
                                            "clearable": True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行5：免责声明
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
                                            "type": "warning",
                                            "variant": "tonal",
                                            "text": "⚠️ 未经测试，封号自理。使用115离线下载API存在封号风险，建议小号使用。"
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "notify_enabled": False,
            "auth_mode": "mp_oauth",
            "cookie": "",
            "download_path": "",
            "api_interval": 0,
            "link_input": ""
        }

    def get_page(self) -> List[dict]:
        # 简单的状态显示
        if not self._enabled:
            return [{
                "component": "div",
                "text": "插件未启用",
                "props": {"class": "text-center pa-4"}
            }]

        # 授权状态
        if self._auth_mode == "cookie":
            if self._cookie:
                auth_text = "✅ Cookie模式已配置"
                auth_type = "success"
            else:
                auth_text = "❌ Cookie未填写"
                auth_type = "error"
        else:
            oper = self._get_u115_oper()
            if oper:
                auth_text = "✅ MP OAuth已授权"
                auth_type = "success"
            else:
                auth_text = "❌ 115未授权，请前往 设置→存储→115网盘 登录"
                auth_type = "error"

        return [
            {
                "component": "VAlert",
                "props": {
                    "type": auth_type,
                    "variant": "tonal",
                    "text": auth_text
                }
            },
            {
                "component": "div",
                "props": {"class": "pa-2"},
                "text": f"下载目录: {self._download_path or '（未设置，将保存到根目录）'}"
            }
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        pass
