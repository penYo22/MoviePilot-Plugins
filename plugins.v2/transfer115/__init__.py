# NOTE: This plugin runs inside the MoviePilot plugin framework, which has no test
# infrastructure (no pytest setup, no test directory, no test runner configured).
# Unit tests for this plugin cannot be written here; manual verification via the
# MoviePilot UI is the only available testing approach.
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
    plugin_version = "3.14"
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

        # 清空 link_input
        if link_input:
            self.update_config({
                "enabled": self._enabled,
                "notify_enabled": self._notify_enabled,
                "auth_mode": self._auth_mode,
                "cookie": self._cookie,
                "download_path": self._download_path,
                "fail_path": self._fail_path,
                "library_path": self._library_path,
                "transfer_type": self._transfer_type,
                "api_interval": self._api_interval,
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
            },
            {
                "path": "/list_download_folders",
                "endpoint": self.api_list_download_folders,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "列出下载目录中的子文件夹"
            },
            {
                "path": "/organize_folder",
                "endpoint": self.api_organize_folder,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "整理单个文件夹"
            },
            {
                "path": "/organize_all",
                "endpoint": self.api_organize_all,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "一键整理所有文件夹"
            }
        ]

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
            "transfer_type": self._transfer_type,
            "api_interval": self._api_interval,
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

    def api_list_download_folders(self) -> dict:
        """列出下载目录中的子文件夹"""
        if not self._download_path:
            return {"code": 1, "msg": "未设置下载目录", "folders": []}
        try:
            truncated = False
            if self._auth_mode == "mp_oauth":
                from app.chain.storage import StorageChain
                from app.schemas import FileItem
                path = self._download_path if self._download_path.endswith("/") else self._download_path + "/"
                fileitem = FileItem(storage="u115", path=path, type="dir")
                self._sleep_if_needed()
                items = StorageChain().list_files(fileitem) or []
                folders = [
                    {"name": i.name, "path": i.path, "fileid": i.fileid if i.fileid else None}
                    for i in items if i.type == "dir"
                ]
            else:  # cookie
                oper = self._get_cookie_oper()
                if not oper:
                    return {"code": 1, "msg": "Cookie客户端初始化失败", "folders": []}
                folder_id = self._get_folder_id_by_path_cookie(self._download_path, oper)
                if folder_id is None:
                    return {"code": 1, "msg": "无法找到下载目录", "folders": []}
                self._sleep_if_needed()
                resp = oper.fs_files({"cid": folder_id, "limit": 200})
                items = resp.get("data", [])
                folders = [
                    {"name": i.get("n", ""), "path": self._download_path.rstrip("/") + "/" + i.get("n", ""), "fileid": str(i.get("cid", ""))}
                    for i in items if i.get("fid") is None and i.get("n")
                ]
                if len(folders) >= 200:
                    truncated = True
                    logger.warning(f"Transfer115: Cookie模式子文件夹列表已达上限200个，可能不完整")
            result = {"code": 0, "folders": folders}
            if truncated:
                result["warning"] = "Cookie模式仅显示前200个子文件夹，列表可能不完整"
            return result
        except Exception as e:
            logger.warning(f"Transfer115: 列出下载目录失败: {e}")
            return {"code": 1, "msg": str(e), "folders": []}

    def api_organize_folder(self, folder_path: str = "", fileid: str = "") -> dict:
        """整理单个文件夹"""
        if not folder_path:
            return {"code": 1, "msg": "缺少参数: folder_path"}
        if not fileid:
            return {"code": 1, "msg": f"无法整理 {Path(folder_path).name}：文件夹ID不可用，请检查115授权状态"}
        try:
            from app.chain.transfer import TransferChain
            from app.schemas import FileItem

            folder_name = Path(folder_path).name
            # 构造 FileItem 对象，path 需要以 / 结尾表示目录
            file_path = folder_path if folder_path.endswith("/") else folder_path + "/"
            fileitem = FileItem(
                storage="u115",
                type="dir",
                path=file_path,
                name=folder_name,
                fileid=fileid,
            )

            transfer_kwargs = dict(
                fileitem=fileitem,
                transfer_type=self._transfer_type,
            )
            if self._library_path:
                transfer_kwargs["target_path"] = Path(self._library_path)

            logger.info(f"Transfer115: 开始整理: {folder_path} (fileid={fileid})")
            state, errmsg = TransferChain().manual_transfer(**transfer_kwargs)

            if state:
                self.__upsert_task_record(folder_name, "整理完成")
                logger.info(f"Transfer115: 手动整理成功: {folder_path}")
                return {"code": 0, "msg": f"整理成功: {folder_name}"}
            else:
                self.__upsert_task_record(folder_name, "整理失败")
                logger.warning(f"Transfer115: 手动整理失败: {folder_path}，原因: {errmsg}")
                return {"code": 1, "msg": f"整理失败: {errmsg}"}
        except Exception as e:
            logger.error(f"Transfer115: 手动整理异常: {e}")
            return {"code": 1, "msg": str(e)}

    def api_organize_all(self) -> dict:
        """一键整理下载目录中的所有文件夹"""
        result = self.api_list_download_folders()
        if result.get("code") != 0:
            return result
        folders = result.get("folders", [])
        if not folders:
            return {"code": 0, "msg": "下载目录中没有子文件夹"}
        success_count = 0
        fail_count = 0
        for folder in folders:
            r = self.api_organize_folder(folder_path=folder["path"], fileid=folder["fileid"])
            if r.get("code") == 0:
                success_count += 1
            else:
                fail_count += 1
            self._sleep_if_needed()
        code = 1 if success_count == 0 and fail_count > 0 else 0
        return {"code": code, "msg": f"整理完成：成功 {success_count} 个，失败 {fail_count} 个"}

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
                    # 行5：参数配置
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
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
                                "props": {"cols": 12, "md": 6},
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
            "download_path": "",
            "library_path": "",
            "fail_path": "",
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

        # SECTION B2: Download folder list for manual organize
        if self._enabled and self._download_path:
            folder_result = self.api_list_download_folders()
            folder_list = folder_result.get("folders", [])
            folder_error = folder_result.get("msg") if folder_result.get("code") != 0 else None

            folder_rows = []
            if folder_error:
                folder_rows.append({
                    "component": "VAlert",
                    "props": {"type": "warning", "variant": "tonal", "density": "compact",
                              "text": f"获取文件夹列表失败: {folder_error}"}
                })
            elif not folder_list:
                folder_rows.append({
                    "component": "div",
                    "text": "下载目录中暂无子文件夹",
                    "props": {"class": "text-caption text-center pa-2"}
                })
            else:
                for folder in folder_list:
                    folder_rows.append({
                        "component": "VListItem",
                        "props": {"density": "compact"},
                        "content": [
                            {
                                "component": "VListItemTitle",
                                "props": {"class": "text-body-2 text-truncate"},
                                "text": folder["name"]
                            },
                            {
                                "component": "VListItemSubtitle",
                                "content": [
                                    {
                                        "component": "VBtn",
                                        "props": {"size": "x-small", "variant": "tonal", "color": "primary"},
                                        "text": "整理",
                                        "events": {
                                            "click": {
                                                "api": "plugin/Transfer115/organize_folder",
                                                "method": "get",
                                                "params": {"folder_path": folder["path"], "fileid": folder.get("fileid") or ""}
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    })

            folder_list_content = [{
                "component": "VList",
                "props": {"lines": "two", "density": "compact"},
                "content": folder_rows
            }] if folder_list else folder_rows

            download_folders_section = {
                "component": "VCard",
                "props": {"variant": "outlined", "class": "mb-2"},
                "content": [
                    {
                        "component": "VCardTitle",
                        "props": {"class": "text-body-1"},
                        "text": f"待整理文件夹（{self._download_path}）"
                    },
                    {
                        "component": "VCardText",
                        "content": [
                            {
                                "component": "VRow",
                                "props": {"class": "mb-1"},
                                "content": [
                                    {
                                        "component": "VCol",
                                        "props": {"cols": 12, "class": "d-flex ga-2 justify-end"},
                                        "content": [
                                            {
                                                "component": "VBtn",
                                                "props": {"size": "x-small", "variant": "tonal", "color": "success"},
                                                "text": "一键全部整理",
                                                "events": {
                                                    "click": {
                                                        "api": "plugin/Transfer115/organize_all",
                                                        "method": "get"
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                ]
                            }
                        ] + folder_list_content
                    }
                ]
            }
        else:
            download_folders_section = None

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
                            "props": {"color": "error", "variant": "tonal", "size": "small"},
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
            download_folders_section,
            browser_section,
            task_section,
            refresh_section
        ] if c is not None]

    def get_service(self) -> List[Dict[str, Any]]:
        return []

    def stop_service(self):
        pass

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
