# NOTE: This plugin runs inside the MoviePilot plugin framework, which has no test
# infrastructure (no pytest setup, no test directory, no test runner configured).
# Unit tests for this plugin cannot be written here; manual verification via the
# MoviePilot UI and the onlyonce trigger is the only available testing approach.
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.interval import IntervalTrigger

from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType


class Transfer115(_PluginBase):
    # 插件名称
    plugin_name = "115离线整理"
    # 插件描述
    plugin_desc = "⚠️ 未经测试，封号自理。使用MoviePilot已存储的115授权或自填Cookie，添加离线下载任务，完成后自动识别重命名，失败文件夹整体归档"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Frontend/refs/heads/v2/src/assets/images/misc/u115.png"
    # 插件版本
    plugin_version = "3.11"
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
    _fail_path: str = ""
    _poll_interval: int = 5
    _transfer_type: str = "move"
    _auth_mode: str = "mp_oauth"
    _cookie: str = ""
    _library_path: str = ""
    _api_interval: int = 0

    # 支持的视频文件扩展名
    _video_extensions = (".mkv", ".mp4", ".avi", ".ts", ".rmvb", ".wmv", ".flv", ".mov")

    def _get_u115_oper(self):
        """Get the live U115Pan singleton — already authenticated via MP's OAuth token."""
        try:
            from app.modules.filemanager.storages.u115 import U115Pan
            oper = U115Pan()
            if oper.check():  # check() returns True if access_token is present
                return oper
        except Exception as e:
            logger.warning(f"Transfer115: 获取115存储实例失败: {e}")
        return None

    def _get_cookie_oper(self):
        """Initialize P115Client with stored cookie."""
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
        """在两次115 API调用之间插入延迟，避免触发风控"""
        if self._api_interval > 0:
            import time
            time.sleep(self._api_interval)

    def init_plugin(self, config: dict = None):
        if not config:
            return

        self._enabled = config.get("enabled", False)
        self._notify_enabled = config.get("notify_enabled", False)
        self._auth_mode = config.get("auth_mode", "mp_oauth")
        self._cookie = config.get("cookie", "").strip()
        self._download_path = config.get("download_path", "").strip()
        self._fail_path = config.get("fail_path", "").strip()
        self._library_path = config.get("library_path", "").strip()
        self._poll_interval = int(config.get("poll_interval", 5) or 5)
        self._transfer_type = config.get("transfer_type", "move")
        self._api_interval = int(config.get("api_interval", 0) or 0)

        # 处理立即提交的链接
        link_input = config.get("link_input", "").strip()
        if link_input:
            lines = [l.strip() for l in link_input.splitlines() if l.strip()]
            if lines:
                if self._auth_mode == "cookie":
                    oper = self._get_cookie_oper()
                else:
                    oper = self._get_u115_oper()
                if oper:
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
                            # Resolve download_path to folder id
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
                        # 提交成功后立即查询任务列表，将属于下载目录的新任务写入记录
                        try:
                            if self._auth_mode == "cookie":
                                self._sleep_if_needed()
                                list_resp = oper.offline_list({"page": 1})
                            else:
                                self._sleep_if_needed()
                                list_resp = oper._request_api("GET", "/open/offline/get_task_list", params={"page": 1})
                            new_tasks = (list_resp or {}).get("data", {}).get("tasks", [])
                            processed = self.get_data("processed_tasks") or []
                            expected_prefix = self._download_path.strip("/") if self._download_path else None
                            recorded = 0
                            for t in new_tasks:
                                t_name = t.get("name", "")
                                t_id = t.get("info_hash") or t.get("hash", "")
                                t_file_path = t.get("file_path", "").strip("/")
                                if not t_name or not t_id or t_id in processed:
                                    continue
                                # 记录条件：
                                # 1. 任务路径已知且属于下载目录，或
                                # 2. 任务路径为空（刚提交尚未开始下载，路径未填充）且设置了下载目录
                                path_ok = (
                                    (expected_prefix and t_file_path and t_file_path.startswith(expected_prefix))
                                    or (expected_prefix and not t_file_path)
                                )
                                if path_ok:
                                    self.__upsert_task_record(t_name, "下载中")
                                    recorded += 1
                            logger.info(f"Transfer115: 已记录 {recorded} 个新任务为下载中")
                        except Exception as list_err:
                            logger.warning(f"Transfer115: 提交后查询任务列表失败: {list_err}")
                        if self._notify_enabled:
                            self.post_message(
                                mtype=NotificationType.Organize,
                                title="115离线任务已提交",
                                text=f"已提交 {len(lines)} 条离线下载任务"
                            )
                    except Exception as e:
                        logger.error(f"Transfer115: 添加离线任务失败: {e}")
                else:
                    logger.warning("Transfer115: 链接已填写但115未授权或Cookie无效")

        # 处理立即执行
        onlyonce = config.get("onlyonce", False)
        if onlyonce:
            self.__check_and_organize()

        # 清空 link_input 和 onlyonce
        if link_input or onlyonce:
            self.update_config({
                "enabled": self._enabled,
                "notify_enabled": self._notify_enabled,
                "auth_mode": self._auth_mode,
                "cookie": self._cookie,
                "download_path": self._download_path,
                "fail_path": self._fail_path,
                "library_path": self._library_path,
                "poll_interval": self._poll_interval,
                "transfer_type": self._transfer_type,
                "api_interval": self._api_interval,
                "onlyonce": False,
                "link_input": ""
            })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/refresh_tasks",
                "endpoint": self.api_refresh_tasks,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "手动触发115离线任务检查"
            },
            {
                "path": "/list_dirs",
                "endpoint": self.api_list_dirs,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "列出115目录"
            },
            {
                "path": "/set_path",
                "endpoint": self.api_set_path,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "设置目录配置"
            },
            {
                "path": "/nav_dir",
                "endpoint": self.api_nav_dir,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "导航到目录"
            },
            {
                "path": "/clear_logs",
                "endpoint": self.api_clear_logs,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "清空插件任务记录"
            }
        ]

    def api_refresh_tasks(self) -> dict:
        """手动触发任务检查"""
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}
        if self._auth_mode == "cookie":
            oper = self._get_cookie_oper()
        else:
            oper = self._get_u115_oper()
        if not oper:
            return {"code": 1, "msg": "115网盘未授权或Cookie无效"}
        self.__check_and_organize()
        return {"code": 0, "msg": "任务检查已触发"}

    def api_list_dirs(self, path: str = "/") -> dict:
        """列出115目录"""
        if self._auth_mode == "cookie":
            return {"code": 1, "msg": "Cookie模式下目录浏览不可用，请手动填写目录路径", "dirs": []}
        try:
            from app.chain.storage import StorageChain
            from app.schemas import FileItem
            if not path.endswith("/"):
                path = path + "/"
            fileitem = FileItem(storage="u115", path=path, type="dir")
            self._sleep_if_needed()
            items = StorageChain().list_files(fileitem) or []
            dirs = [{"name": i.name, "path": i.path} for i in items if i.type == "dir"]
            return {"code": 0, "dirs": dirs}
        except Exception as e:
            logger.warning(f"Transfer115: 列出目录失败: {e}")
            return {"code": 1, "msg": str(e), "dirs": []}

    def api_set_path(self, field: str = "", path: str = "/") -> dict:
        """设置目录配置"""
        if field not in ("download_path", "fail_path", "library_path"):
            return {"code": 1, "msg": "无效字段"}
        clean_path = path.rstrip("/") if path != "/" else "/"
        conf = {
            "enabled": self._enabled,
            "notify_enabled": self._notify_enabled,
            "auth_mode": self._auth_mode,
            "cookie": self._cookie,
            "download_path": self._download_path,
            "fail_path": self._fail_path,
            "library_path": self._library_path,
            "poll_interval": self._poll_interval,
            "transfer_type": self._transfer_type,
            "api_interval": self._api_interval,
            "onlyonce": False,
            "link_input": ""
        }
        conf[field] = clean_path
        self.update_config(conf)
        if field == "download_path":
            self._download_path = clean_path
        elif field == "fail_path":
            self._fail_path = clean_path
        else:
            self._library_path = clean_path
        return {"code": 0, "msg": f"已设置 {field} 为 {clean_path}"}

    def api_nav_dir(self, path: str = "/") -> dict:
        """导航到目录"""
        self.save_data("browse_path", path)
        return {"code": 0}

    def api_clear_logs(self) -> dict:
        """清空插件任务记录及处理状态"""
        self.del_data("task_records")
        self.del_data("processed_tasks")
        self.del_data("failed_tasks")
        self.del_data("download_done_tasks")
        logger.info("Transfer115: 插件任务记录已清空")
        return {"code": 0, "msg": "任务记录已清空"}

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
                    # 行2：Cookie输入（始终渲染，仅cookie模式需填写）
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 12},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cookie",
                                            "label": "Cookie",
                                            "type": "password",
                                            "hint": "仅选择「手动填写Cookie」模式时需要填写，MP OAuth模式请留空",
                                            "placeholder": "填写115网盘Cookie字符串（UID=xxx;CID=xxx;SEID=xxx 格式）",
                                            "persistent-hint": True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行3：授权状态提示
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 12},
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {
                                            "type": "info",
                                            "variant": "tonal",
                                            "density": "compact",
                                            "text": "115授权状态请在下方数据页查看"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行4：目录配置
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "download_path",
                                            "label": "离线下载保存目录",
                                            "placeholder": "如 /待整理 （115云盘内路径，可在数据页可视化选择）"
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
                                            "model": "library_path",
                                            "label": "媒体库存放路径",
                                            "placeholder": "如 /媒体库 （整理成功后存入此目录，留空则使用MP目录配置）"
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
                                            "model": "fail_path",
                                            "label": "整理失败目录",
                                            "placeholder": "如 /整理失败 （整理失败后整个文件夹移动到这里）"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行5：参数配置（含立即检查一次开关）
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "poll_interval",
                                            "label": "轮询间隔(分钟)",
                                            "placeholder": "5"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "transfer_type",
                                            "label": "整理方式",
                                            "items": [
                                                {"title": "移动", "value": "move"},
                                                {"title": "复制", "value": "copy"}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "onlyonce",
                                            "label": "立即检查一次",
                                            "hint": "保存后立即执行一次",
                                            "persistent-hint": True
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "api_interval",
                                            "label": "API请求间隔(秒)",
                                            "placeholder": "0",
                                            "hint": "每次115 API调用前等待的秒数，0表示不等待，建议1-3秒",
                                            "persistent-hint": True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行6：添加离线下载链接
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
                                            "placeholder": "支持磁力链接、115分享链接、ed2k链接，每行一个，保存后自动提交",
                                            "rows": 4,
                                            "clearable": True,
                                            "hint": "填写后点击保存即可提交，提交后自动清空"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行7：免责声明
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
                                            "text": (
                                                "⚠️ 免责声明：本插件未经充分测试，使用115网盘离线下载及API功能存在账号被封禁风险，后果自负，封号自理。"
                                                "建议在小号或测试账号上使用。"
                                            )
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行8：使用说明
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
                                            "text": (
                                                "【授权方式】支持两种授权：MP OAuth（共用MoviePilot的115授权，推荐）和手动Cookie（自行填写Cookie字符串）。"
                                                "MP OAuth请先前往 设置→存储→115网盘 完成扫码登录。"
                                                "【目录选择】可在数据页可视化浏览115目录并一键设置下载/失败目录。"
                                                "【工作流程】插件定时轮询115离线任务→发现完成任务→自动识别媒体信息并重命名→失败时将整个任务文件夹移入整理失败目录。"
                                            )
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
            "onlyonce": False,
            "download_path": "",
            "library_path": "",
            "fail_path": "",
            "poll_interval": 5,
            "transfer_type": "move",
            "api_interval": 0,
            "link_input": ""
        }

    def get_page(self) -> List[dict]:
        # SECTION A: Auth status — only shown when plugin is enabled
        if not self._enabled:
            status_component = None
        elif self._auth_mode == "cookie":
            if not self._cookie:
                status_component = {
                    "component": "VAlert",
                    "props": {
                        "type": "error",
                        "variant": "tonal",
                        "text": "❌ Cookie模式：未配置Cookie，请在设置页填写Cookie"
                    }
                }
            else:
                oper = self._get_cookie_oper()
                if oper:
                    status_component = {
                        "component": "VAlert",
                        "props": {
                            "type": "success",
                            "variant": "tonal",
                            "text": "✅ Cookie模式已配置（Cookie已填写）"
                        }
                    }
                else:
                    status_component = {
                        "component": "VAlert",
                        "props": {
                            "type": "error",
                            "variant": "tonal",
                            "text": "❌ Cookie模式：Cookie初始化失败，请检查p115client是否安装"
                        }
                    }
        else:  # mp_oauth
            oper = self._get_u115_oper()
            if oper:
                status_component = {
                    "component": "VAlert",
                    "props": {
                        "type": "success",
                        "variant": "tonal",
                        "text": "✅ MP OAuth模式已授权（使用MoviePilot存储配置）"
                    }
                }
            else:
                status_component = {
                    "component": "VAlert",
                    "props": {
                        "type": "error",
                        "variant": "tonal",
                        "text": "❌ MP OAuth模式：115网盘未授权，请前往 设置→存储→115网盘 完成扫码登录"
                    }
                }

        # SECTION B: Current config display
        config_section = {
            "component": "VList",
            "props": {"lines": "two", "density": "compact"},
            "content": [
                {
                    "component": "VListItem",
                    "props": {"density": "compact"},
                    "content": [
                        {
                            "component": "VListItemTitle",
                            "text": f"下载目录: {self._download_path or '（未设置）'}"
                        },
                        {
                            "component": "VListItemSubtitle",
                            "content": [
                                {
                                    "component": "VBtn",
                                    "props": {
                                        "size": "x-small",
                                        "variant": "tonal",
                                        "color": "warning"
                                    },
                                    "text": "清空",
                                    "events": {
                                        "click": {
                                            "api": "plugin/Transfer115/set_path",
                                            "method": "get",
                                            "params": {"field": "download_path", "path": "/"}
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                },
                {
                    "component": "VListItem",
                    "props": {"density": "compact"},
                    "content": [
                        {
                            "component": "VListItemTitle",
                            "text": f"失败目录: {self._fail_path or '（未设置）'}"
                        },
                        {
                            "component": "VListItemSubtitle",
                            "content": [
                                {
                                    "component": "VBtn",
                                    "props": {
                                        "size": "x-small",
                                        "variant": "tonal",
                                        "color": "warning"
                                    },
                                    "text": "清空",
                                    "events": {
                                        "click": {
                                            "api": "plugin/Transfer115/set_path",
                                            "method": "get",
                                            "params": {"field": "fail_path", "path": "/"}
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                },
                {
                    "component": "VListItem",
                    "props": {"density": "compact"},
                    "content": [
                        {
                            "component": "VListItemTitle",
                            "text": f"媒体库目录: {self._library_path or '（未设置，使用MP目录配置）'}"
                        },
                        {
                            "component": "VListItemSubtitle",
                            "content": [
                                {
                                    "component": "VBtn",
                                    "props": {
                                        "size": "x-small",
                                        "variant": "tonal",
                                        "color": "warning"
                                    },
                                    "text": "清空",
                                    "events": {
                                        "click": {
                                            "api": "plugin/Transfer115/set_path",
                                            "method": "get",
                                            "params": {"field": "library_path", "path": "/"}
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        # SECTION C: Directory browser
        browse_path = self.get_data("browse_path") or "/"

        # Compute parent path
        if browse_path == "/":
            parent_path = None
        else:
            parts = browse_path.rstrip("/").rsplit("/", 1)
            parent_path = parts[0] + "/" if parts[0] else "/"

        if self._auth_mode == "cookie" or not self._enabled:
            # Cookie mode or plugin disabled: hide the directory browser entirely.
            browser_section = None
        else:
            # MP OAuth mode: try to list dirs via StorageChain
            # Try to list dirs
            dir_items = []
            dir_error = None
            try:
                from app.chain.storage import StorageChain
                from app.schemas import FileItem
                bp = browse_path if browse_path.endswith("/") else browse_path + "/"
                fileitem = FileItem(storage="u115", path=bp, type="dir")
                listed = StorageChain().list_files(fileitem) or []
                dir_items = [i for i in listed if i.type == "dir"]
            except Exception as e:
                dir_error = str(e)

            # Build browser nav buttons
            browser_nav_content = []
            browser_nav_content.append({
                "component": "span",
                "text": f"当前路径: {browse_path}",
                "props": {"class": "text-body-2 mr-2"}
            })
            if parent_path is not None:
                browser_nav_content.append({
                    "component": "VBtn",
                    "props": {"size": "x-small", "variant": "tonal", "color": "secondary", "class": "mr-1"},
                    "text": "返回上级",
                    "events": {
                        "click": {
                            "api": "plugin/Transfer115/nav_dir",
                            "method": "get",
                            "params": {"path": parent_path}
                        }
                    }
                })
            browser_nav_content.append({
                "component": "VBtn",
                "props": {"size": "x-small", "variant": "tonal", "color": "secondary"},
                "text": "刷新",
                "events": {
                    "click": {
                        "api": "plugin/Transfer115/nav_dir",
                        "method": "get",
                        "params": {"path": browse_path}
                    }
                }
            })

            browser_header = {
                "component": "VRow",
                "props": {"class": "align-center mb-1"},
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": browser_nav_content
                    }
                ]
            }

            browser_items_content = []
            if dir_error:
                browser_items_content.append({
                    "component": "VAlert",
                    "props": {
                        "type": "warning",
                        "variant": "tonal",
                        "density": "compact",
                        "text": f"列出目录失败: {dir_error}"
                    }
                })
            elif not dir_items:
                browser_items_content.append({
                    "component": "div",
                    "text": "此目录下无子目录",
                    "props": {"class": "text-caption text-center pa-2"}
                })
            else:
                dir_rows = []
                for d in dir_items:
                    dir_rows.append({
                        "component": "VListItem",
                        "props": {"density": "compact"},
                        "content": [
                            {
                                "component": "VListItemTitle",
                                "props": {"class": "text-body-2"},
                                "text": d.name
                            },
                            {
                                "component": "VListItemSubtitle",
                                "content": [
                                    {
                                        "component": "VBtn",
                                        "props": {
                                            "size": "x-small",
                                            "variant": "tonal",
                                            "color": "primary",
                                            "class": "mr-1"
                                        },
                                        "text": "设为下载目录",
                                        "events": {
                                            "click": {
                                                "api": "plugin/Transfer115/set_path",
                                                "method": "get",
                                                "params": {"field": "download_path", "path": d.path}
                                            }
                                        }
                                    },
                                    {
                                        "component": "VBtn",
                                        "props": {
                                            "size": "x-small",
                                            "variant": "tonal",
                                            "color": "warning",
                                            "class": "mr-1"
                                        },
                                        "text": "设为失败目录",
                                        "events": {
                                            "click": {
                                                "api": "plugin/Transfer115/set_path",
                                                "method": "get",
                                                "params": {"field": "fail_path", "path": d.path}
                                            }
                                        }
                                    },
                                    {
                                        "component": "VBtn",
                                        "props": {
                                            "size": "x-small",
                                            "variant": "tonal",
                                            "color": "success",
                                            "class": "mr-1"
                                        },
                                        "text": "设为媒体库",
                                        "events": {
                                            "click": {
                                                "api": "plugin/Transfer115/set_path",
                                                "method": "get",
                                                "params": {"field": "library_path", "path": d.path}
                                            }
                                        }
                                    },
                                    {
                                        "component": "VBtn",
                                        "props": {
                                            "size": "x-small",
                                            "variant": "tonal",
                                            "color": "secondary"
                                        },
                                        "text": "进入",
                                        "events": {
                                            "click": {
                                                "api": "plugin/Transfer115/nav_dir",
                                                "method": "get",
                                                "params": {"path": d.path}
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    })
                browser_items_content.append({
                    "component": "VList",
                    "props": {"lines": "two", "density": "compact"},
                    "content": dir_rows
                })

            browser_section = {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mb-2"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "props": {"class": "text-body-1"},
                        "text": "目录浏览器"
                    },
                    {
                        "component": "VCardText",
                        "content": [browser_header] + browser_items_content
                    }
                ]
            }

        # SECTION D: Task records
        records = self.get_data("task_records") or []
        if not records:
            task_section = {
                "component": "div",
                "text": "暂无任务记录",
                "props": {"class": "text-center pa-4"}
            }
        else:
            records = list(reversed(records[-50:]))
            rows = []
            for entry in records:
                status = entry.get("status", "")
                if status == "整理完成":
                    status_text = "✅ 整理完成"
                elif status == "整理失败":
                    status_text = "❌ 整理失败"
                elif status == "下载完成":
                    status_text = "📥 下载完成"
                else:
                    status_text = "⏳ 下载中"
                rows.append({
                    "component": "VListItem",
                    "props": {"density": "compact"},
                    "content": [
                        {
                            "component": "VListItemTitle",
                            "props": {"class": "text-caption text-truncate"},
                            "text": entry.get("name", "")
                        },
                        {
                            "component": "VListItemSubtitle",
                            "text": f"{entry.get('time', '')}  {status_text}"
                        }
                    ]
                })
            task_section = {
                "component": "VList",
                "props": {"lines": "two"},
                "content": rows
            }

        # SECTION E: Refresh button
        refresh_section = {
            "component": "VRow",
            "props": {"class": "mt-2"},
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 12, "class": "text-center"},
                    "content": [
                        {
                            "component": "VBtn",
                            "props": {
                                "color": "primary",
                                "variant": "tonal",
                                "size": "small"
                            },
                            "text": "刷新任务状态",
                            "events": {
                                "click": {
                                    "api": "plugin/Transfer115/refresh_tasks",
                                    "method": "get"
                                }
                            }
                        },
                        {
                            "component": "VBtn",
                            "props": {"color": "error", "variant": "tonal", "size": "small", "class": "ml-2"},
                            "text": "清空任务记录",
                            "events": {
                                "click": {
                                    "api": "plugin/Transfer115/clear_logs",
                                    "method": "get"
                                }
                            }
                        }
                    ]
                }
            ]
        }

        return [c for c in [
            status_component,
            config_section,
            browser_section,
            task_section,
            refresh_section
        ] if c is not None]

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._download_path:
            return [
                {
                    "id": "Transfer115Monitor",
                    "name": "115离线整理监控",
                    "trigger": IntervalTrigger(minutes=self._poll_interval),
                    "func": self.__check_and_organize,
                    "kwargs": {}
                }
            ]
        return []

    def stop_service(self):
        pass

    def __check_and_organize(self):
        """轮询115离线任务，对已完成的任务执行整理"""
        if self._auth_mode == "cookie":
            oper = self._get_cookie_oper()
        else:
            oper = self._get_u115_oper()
        if not oper:
            logger.warning("Transfer115: 115未授权，跳过任务检查")
            return
        try:
            if self._auth_mode == "cookie":
                self._sleep_if_needed()
                resp = oper.offline_list({"page": 1})
            else:
                self._sleep_if_needed()
                resp = oper._request_api("GET", "/open/offline/get_task_list", params={"page": 1})
            tasks = (resp or {}).get("data", {}).get("tasks", [])
            # processed_tasks: list of task IDs that completed successfully and need no
            # further action.
            processed = self.get_data("processed_tasks") or []
            # failed_tasks: dict of {task_id: retry_count} tracking transient failures.
            # Tasks are retried up to _MAX_TASK_RETRIES times before being permanently
            # skipped, preventing a broken task from blocking the poll loop forever.
            _MAX_TASK_RETRIES = 3
            failed_tasks: dict = self.get_data("failed_tasks") or {}
            # download_done_tasks: set of task IDs that have been marked "下载完成" but
            # not yet organized. Organizing is deferred to the next poll cycle so that
            # the "下载完成" status is visible to the user for at least one interval.
            download_done: set = set(self.get_data("download_done_tasks") or [])
            changed = False

            for task in tasks:
                task_id = task.get("info_hash") or task.get("hash", "")
                if not task_id:
                    continue

                task_name = task.get("name", task_id)
                task_status = task.get("status", 0)

                # 已成功整理的任务优先跳过，避免状态被反向覆写为"下载中"
                if task_id in processed:
                    continue

                if task_status != 2:
                    # 未完成
                    self.__upsert_task_record(task_name, "下载中")
                    continue

                # Check if this task has exhausted its retries
                retry_count = failed_tasks.get(task_id, 0)
                if retry_count >= _MAX_TASK_RETRIES:
                    # Already logged on the run that hit the limit; silently skip.
                    continue

                # 仅处理保存在指定下载目录下的任务
                # 未设置下载目录，一律跳过
                if not self._download_path:
                    logger.debug(f"Transfer115: 跳过任务 '{task_name}'，未设置下载目录")
                    continue
                task_file_path = task.get("file_path", "").strip("/")
                expected_prefix = self._download_path.strip("/")
                if task_file_path and not task_file_path.startswith(expected_prefix):
                    logger.debug(
                        f"Transfer115: 跳过任务 '{task_name}'，"
                        f"保存路径 '/{task_file_path}' 不在下载目录 '{self._download_path}' 下"
                    )
                    continue
                # task_file_path 为空时，说明路径尚未填充，按下载目录+任务名构造路径，继续处理
                if not task_file_path:
                    logger.debug(f"Transfer115: 任务 '{task_name}' 路径为空，将使用下载目录+任务名构造路径")

                # 两阶段处理：
                # 第一次轮询到 status=2 时只写"下载完成"，等下次轮询再整理，
                # 确保用户至少能看到一个轮询周期的"下载完成"状态。
                if task_id not in download_done:
                    logger.info(f"Transfer115: 任务下载完成，等待下次轮询整理: {task_name}")
                    self.__upsert_task_record(task_name, "下载完成")
                    download_done.add(task_id)
                    self.save_data("download_done_tasks", list(download_done))
                    continue

                # 已经过一个轮询周期，现在执行整理
                logger.info(f"Transfer115: 开始整理任务: {task_name}")
                success = self.__organize_task(task, task_name, oper)
                changed = True

                # 整理完成后从 download_done 移除
                download_done.discard(task_id)

                if success:
                    # Full success: permanently mark as processed and remove from
                    # failed_tasks if it was there from an earlier partial attempt.
                    processed.append(task_id)
                    failed_tasks.pop(task_id, None)
                    self.__upsert_task_record(task_name, "整理完成")
                else:
                    # Failure: increment retry counter. Do NOT add to processed so the
                    # task will be retried on the next poll cycle.
                    new_count = retry_count + 1
                    failed_tasks[task_id] = new_count
                    self.__upsert_task_record(task_name, "整理失败")
                    if new_count >= _MAX_TASK_RETRIES:
                        logger.warning(
                            f"Transfer115: 任务 '{task_name}' 已失败 {new_count} 次，"
                            "不再重试，已归档"
                        )
                        # On exhaustion: attempt fail-path move and notify user
                        if self._fail_path and task.get("file_id"):
                            self.__move_folder_to_fail(task, task_name, oper)
                        elif self._notify_enabled:
                            self.post_message(
                                mtype=NotificationType.Manual,
                                title="115整理放弃",
                                text=f"❌ 任务: {task_name}\n已失败 {new_count} 次，不再重试，请手动处理"
                            )
                        # Mark as permanently processed so it doesn't re-enter the loop
                        processed.append(task_id)
                        failed_tasks.pop(task_id, None)

            if changed:
                self.save_data("processed_tasks", processed)
                self.save_data("failed_tasks", failed_tasks)
                self.save_data("download_done_tasks", list(download_done))

        except Exception as e:
            logger.error(f"Transfer115: 任务检查异常: {e}")

    def __organize_task(self, task: dict, task_name: str, oper) -> bool:
        """对已完成的离线任务进行媒体识别和整理（使用115云盘在线整理）"""
        try:
            from app.chain.transfer import TransferChain

            file_id = task.get("file_id", "")
            if not file_id:
                logger.warning(f"Transfer115: 任务 '{task_name}' 无 file_id，无法整理")
                return False

            # 构造任务文件夹的云盘路径
            task_file_path = task.get("file_path", "").strip("/")
            if task_file_path:
                cloud_folder_path = Path("/" + task_file_path)
            else:
                cloud_folder_path = Path(self._download_path.rstrip("/") + "/" + task_name)

            logger.info(f"Transfer115: 开始整理任务文件夹: {cloud_folder_path} (file_id={file_id})")

            transfer_kwargs = dict(
                storage="u115",
                in_path=cloud_folder_path,
                fileid=str(file_id),
                filetype="dir",
                transfer_type=self._transfer_type,
            )
            if self._library_path:
                transfer_kwargs["target"] = Path(self._library_path)

            state, errmsg = TransferChain().manual_transfer(**transfer_kwargs)

            if state:
                logger.info(f"Transfer115: 整理成功: {task_name}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Organize,
                        title="115离线整理完成",
                        text=f"✅ {task_name} 已整理入库"
                    )
                return True
            else:
                logger.warning(f"Transfer115: 整理失败: {task_name}，原因: {errmsg}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="115整理失败",
                        text=f"❌ 任务: {task_name}\n原因: {errmsg}\n将在下次检查时重试"
                    )
                return False

        except Exception as e:
            logger.error(f"Transfer115: 整理任务 '{task_name}' 异常: {e}")
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Manual,
                    title="115整理异常",
                    text=f"❌ 任务: {task_name}\n错误: {e}"
                )
            return False

    def _get_folder_id_by_path_cookie(self, path: str, oper) -> Optional[int]:
        """Walk path to get folder id for cookie mode.

        WARNING: Each level of the walk fetches at most 1000 items (p115client
        single-page limit). If a directory contains more than 1000 sub-folders,
        the target may not be found even when it exists.
        """
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
                    logger.warning(
                        f"Transfer115: cookie模式未找到目录 '{part}'，"
                        "可能路径不存在或该层目录下子文件夹超过1000个"
                    )
                    return None
                current_id = int(found)
            return current_id
        except Exception as e:
            logger.warning(f"Transfer115: cookie模式获取目录ID失败: {e}")
            return None

    def __move_folder_to_fail(self, task: dict, task_name: str, oper):
        """将整个任务文件夹移动到整理失败目录"""
        try:
            folder_id = task.get("file_id", "")
            if not folder_id:
                logger.warning(f"Transfer115: 无法获取任务文件夹ID，跳过移动: {task_name}")
                return

            if self._auth_mode == "cookie":
                # Cookie mode: use p115client fs_move
                fail_folder_id = self._get_folder_id_by_path_cookie(self._fail_path, oper)
                if fail_folder_id is None:
                    logger.warning(f"Transfer115: cookie模式无法找到失败目录: {self._fail_path}")
                    if self._notify_enabled:
                        self.post_message(
                            mtype=NotificationType.Manual,
                            title="115整理失败",
                            text=f"❌ 任务: {task_name}\n整理失败，请手动移至: {self._fail_path}"
                        )
                    return
                self._sleep_if_needed()
                oper.fs_move([int(folder_id)], pid=fail_folder_id)
                logger.info(f"Transfer115: 已将失败任务 '{task_name}' 的文件夹移至: {self._fail_path}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="115整理失败-已归档",
                        text=f"❌ 任务: {task_name}\n文件夹已移至失败目录: {self._fail_path}"
                    )
            else:
                # MP OAuth mode: use U115Pan helpers
                try:
                    fail_item = oper.get_folder(Path(self._fail_path))
                except Exception as e:
                    logger.warning(f"Transfer115: 获取失败目录失败: {e}")
                    fail_item = None

                if not fail_item:
                    logger.warning(f"Transfer115: 无法获取失败目录: {self._fail_path}")
                    if self._notify_enabled:
                        self.post_message(
                            mtype=NotificationType.Manual,
                            title="115整理失败",
                            text=f"❌ 任务: {task_name}\n整理失败，请手动移至: {self._fail_path}"
                        )
                    return

                # Try to get file_path from task first, else construct
                task_file_path = task.get("file_path", "").strip("/")
                if task_file_path:
                    task_folder_path = "/" + task_file_path
                else:
                    task_folder_path = self._download_path.rstrip("/") + "/" + task_name

                try:
                    task_item = oper.get_item(Path(task_folder_path))
                except Exception as e:
                    logger.warning(f"Transfer115: 获取任务文件夹失败: {e}")
                    task_item = None

                if not task_item:
                    logger.warning(f"Transfer115: 无法获取任务文件夹，跳过移动: {task_name}")
                    if self._notify_enabled:
                        self.post_message(
                            mtype=NotificationType.Manual,
                            title="115整理失败",
                            text=f"❌ 任务: {task_name}\n整理失败，请手动移至: {self._fail_path}"
                        )
                    return

                self._sleep_if_needed()
                oper.move(task_item, Path(self._fail_path), task_item.name)
                logger.info(f"Transfer115: 已将失败任务 '{task_name}' 的文件夹移至: {self._fail_path}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="115整理失败-已归档",
                        text=f"❌ 任务: {task_name}\n文件夹已移至失败目录: {self._fail_path}"
                    )

        except Exception as e:
            logger.error(f"Transfer115: 移动失败目录异常 ({task_name}): {e}")

    def __upsert_task_record(self, name: str, status: str):
        """更新或插入任务记录"""
        records = self.get_data("task_records") or []
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for rec in records:
            if rec.get("name") == name:
                rec["status"] = status
                rec["time"] = now
                self.save_data("task_records", records[-200:])
                return
        records.append({"name": name, "status": status, "time": now})
        self.save_data("task_records", records[-200:])
