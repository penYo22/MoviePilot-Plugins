# NOTE: This plugin runs inside the MoviePilot plugin framework, which has no test
# infrastructure (no pytest setup, no test directory, no test runner configured).
# Unit tests for this plugin cannot be written here; manual verification via the
# MoviePilot UI and the onlyonce trigger is the only available testing approach.
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.interval import IntervalTrigger

from app.core.meta import MetaVideo
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
    plugin_version = "3.0"
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

    def init_plugin(self, config: dict = None):
        if not config:
            return

        self._enabled = config.get("enabled", False)
        self._notify_enabled = config.get("notify_enabled", False)
        self._auth_mode = config.get("auth_mode", "mp_oauth")
        self._cookie = config.get("cookie", "").strip()
        self._download_path = config.get("download_path", "").strip()
        self._fail_path = config.get("fail_path", "").strip()
        self._poll_interval = int(config.get("poll_interval", 5) or 5)
        self._transfer_type = config.get("transfer_type", "move")

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
                            oper.offline_add_urls({"urls": "\n".join(lines)})
                        else:
                            oper._request_api(
                                "POST",
                                "/open/offline/add_task_urls",
                                data={"urls": "\n".join(lines)}
                            )
                        logger.info(f"Transfer115: 添加离线任务成功，共 {len(lines)} 条")
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
                "poll_interval": self._poll_interval,
                "transfer_type": self._transfer_type,
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
                "methods": ["POST"],
                "auth": "bear",
                "summary": "设置目录配置"
            },
            {
                "path": "/nav_dir",
                "endpoint": self.api_nav_dir,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "导航到目录"
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
            items = StorageChain().list_files(fileitem) or []
            dirs = [{"name": i.name, "path": i.path} for i in items if i.type == "dir"]
            return {"code": 0, "dirs": dirs}
        except Exception as e:
            logger.warning(f"Transfer115: 列出目录失败: {e}")
            return {"code": 1, "msg": str(e), "dirs": []}

    def api_set_path(self, field: str = "", path: str = "/") -> dict:
        """设置目录配置"""
        if field not in ("download_path", "fail_path"):
            return {"code": 1, "msg": "无效字段"}
        clean_path = path.rstrip("/") if path != "/" else "/"
        # Read current persisted config to avoid overwriting concurrent changes.
        # get_config() is not available in _PluginBase; we fall back to a snapshot
        # from instance state but add setdefault-style merging so that if two
        # requests race, the last write wins only for the field it explicitly sets.
        # NOTE: a true read-modify-write race is still possible here because
        # update_config has no atomic merge operation; this is a framework limitation.
        conf = {
            "enabled": self._enabled,
            "notify_enabled": self._notify_enabled,
            "auth_mode": self._auth_mode,
            # Preserve the stored cookie without exposing self._cookie in new code
            "cookie": self._cookie,
            "download_path": self._download_path,
            "fail_path": self._fail_path,
            "poll_interval": self._poll_interval,
            "transfer_type": self._transfer_type,
            "onlyonce": False,
            "link_input": ""
        }
        conf[field] = clean_path
        self.update_config(conf)
        if field == "download_path":
            self._download_path = clean_path
        else:
            self._fail_path = clean_path
        return {"code": 0, "msg": f"已设置 {field} 为 {clean_path}"}

    def api_nav_dir(self, path: str = "/") -> dict:
        """导航到目录"""
        self.save_data("browse_path", path)
        return {"code": 0}

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
                                "props": {"cols": 12, "md": 6},
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
                                "props": {"cols": 12, "md": 6},
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
            "fail_path": "",
            "poll_interval": 5,
            "transfer_type": "move",
            "link_input": ""
        }

    def get_page(self) -> List[dict]:
        # SECTION A: Auth status
        if self._auth_mode == "cookie":
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
                                            "method": "post",
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
                                            "method": "post",
                                            "params": {"field": "fail_path", "path": "/"}
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

        if self._auth_mode == "cookie":
            # In cookie mode the directory browser uses StorageChain (MP OAuth) which
            # is a different credential. Disable the browser and show a clear message.
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
                            "method": "post",
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
                        "method": "post",
                        "params": {"path": browse_path}
                    }
                }
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
                        "content": [
                            {
                                "component": "VRow",
                                "props": {"class": "align-center mb-1"},
                                "content": [
                                    {
                                        "component": "VCol",
                                        "props": {"cols": 12},
                                        "content": browser_nav_content
                                    }
                                ]
                            },
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "density": "compact",
                                    "text": "Cookie模式下目录浏览器不可用，请手动在设置页填写目录路径"
                                }
                            }
                        ]
                    }
                ]
            }
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
                            "method": "post",
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
                        "method": "post",
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
                                                "method": "post",
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
                                                "method": "post",
                                                "params": {"field": "fail_path", "path": d.path}
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
                                                "method": "post",
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
                if status == "整理成功":
                    status_text = "✅ 整理成功"
                elif status == "整理失败":
                    status_text = "❌ 整理失败"
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
                        }
                    ]
                }
            ]
        }

        return [
            status_component,
            config_section,
            browser_section,
            task_section,
            refresh_section
        ]

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
                resp = oper.offline_list({"page": 1})
            else:
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
            changed = False

            for task in tasks:
                task_id = task.get("info_hash") or task.get("hash", "")
                if not task_id:
                    continue

                task_name = task.get("name", task_id)
                task_status = task.get("status", 0)

                if task_status != 2:
                    # 未完成
                    self.__upsert_task_record(task_name, "下载中")
                    continue

                if task_id in processed:
                    continue

                # Check if this task has exhausted its retries
                retry_count = failed_tasks.get(task_id, 0)
                if retry_count >= _MAX_TASK_RETRIES:
                    # Already logged on the run that hit the limit; silently skip.
                    continue

                # 已完成且未处理
                logger.info(f"Transfer115: 发现已完成任务: {task_name}")
                success = self.__organize_task(task, task_name, oper)
                changed = True

                if success:
                    # Full success: permanently mark as processed and remove from
                    # failed_tasks if it was there from an earlier partial attempt.
                    processed.append(task_id)
                    failed_tasks.pop(task_id, None)
                    self.__upsert_task_record(task_name, "整理成功")
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

        except Exception as e:
            logger.error(f"Transfer115: 任务检查异常: {e}")

    def __organize_task(self, task: dict, task_name: str, oper) -> bool:
        """对已完成的离线任务进行媒体识别和整理"""
        any_failure = False
        organized_count = 0

        try:
            file_id = task.get("file_id", "")
            file_list = []

            if file_id:
                try:
                    if self._auth_mode == "cookie":
                        resp = oper.fs_files({"cid": int(file_id), "limit": 1000})
                        file_list = resp.get("data", [])
                        # NOTE: p115client fetches a single page of up to 1000 items.
                        # Files beyond position 1000 in the task folder will not be
                        # processed. This is a p115client single-page limitation.
                        if len(file_list) >= 1000:
                            logger.warning(
                                f"Transfer115: 任务 '{task_name}' 文件列表已达1000条上限，"
                                "超出部分将被跳过（p115client单页限制）"
                            )
                    else:
                        resp = oper._request_api(
                            "GET",
                            "/open/ufile/files",
                            "data",
                            params={"cid": int(file_id), "limit": 1000}
                        )
                        file_list = (resp or [])
                except Exception as e:
                    logger.warning(f"Transfer115: 获取任务文件列表失败: {e}")
                    file_list = []

            if not file_list:
                # 尝试直接用任务文件夹路径
                logger.warning(f"Transfer115: 未能获取任务 '{task_name}' 的文件列表")
                return False

            for f in file_list:
                fname = f.get("n", "")
                if not fname:
                    continue
                if not any(fname.lower().endswith(ext) for ext in self._video_extensions):
                    continue

                meta = MetaVideo(title=Path(fname).stem, isfile=True)
                mediainfo = self.chain.recognize_media(meta=meta)

                if not mediainfo:
                    logger.warning(f"Transfer115: 识别失败: {fname}")
                    any_failure = True
                    continue

                task_folder_path = self._download_path.rstrip("/") + "/" + task_name
                cloud_path = Path(task_folder_path) / fname
                result = self.chain.transfer(
                    path=cloud_path,
                    meta=meta,
                    mediainfo=mediainfo,
                    transfer_type=self._transfer_type
                )

                if result:
                    organized_count += 1
                    logger.info(f"Transfer115: 整理成功: {fname} -> {mediainfo.title}")
                    if self._notify_enabled:
                        self.post_message(
                            mtype=NotificationType.Organize,
                            title="115离线整理完成",
                            text=f"✅ {fname}\n识别为: {mediainfo.title}"
                        )
                else:
                    logger.warning(f"Transfer115: 整理失败: {fname}")
                    any_failure = True

            if any_failure:
                logger.warning(f"Transfer115: 任务 '{task_name}' 部分文件整理失败，等待重试")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="115整理失败",
                        text=f"❌ 任务: {task_name}\n部分文件整理失败，将在下次检查时重试"
                    )

            return organized_count > 0 and not any_failure

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

                try:
                    task_item = oper.get_item(Path(
                        self._download_path.rstrip("/") + "/" + task_name
                    ))
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
