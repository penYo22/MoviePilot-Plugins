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
    plugin_desc = "通过Cookie登录115网盘，添加离线下载任务，完成后自动识别重命名，失败文件夹整体归档"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Frontend/refs/heads/v2/src/assets/images/misc/u115.png"
    # 插件版本
    plugin_version = "1.0"
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
    _cookie: str = ""
    _download_path: str = ""
    _fail_path: str = ""
    _poll_interval: int = 5
    _transfer_type: str = "move"
    _client = None

    # 支持的视频文件扩展名
    _video_extensions = (".mkv", ".mp4", ".avi", ".ts", ".rmvb", ".wmv", ".flv", ".mov")

    def init_plugin(self, config: dict = None):
        if not config:
            return

        self._enabled = config.get("enabled", False)
        self._notify_enabled = config.get("notify_enabled", False)
        self._cookie = config.get("cookie", "").strip()
        self._download_path = config.get("download_path", "").strip()
        self._fail_path = config.get("fail_path", "").strip()
        self._poll_interval = int(config.get("poll_interval", 5) or 5)
        self._transfer_type = config.get("transfer_type", "move")

        # 初始化 P115Client
        self._client = None
        if self._cookie:
            try:
                from p115client import P115Client
                self._client = P115Client(cookies=self._cookie)
                logger.info("Transfer115: 115客户端初始化成功")
            except Exception as e:
                logger.error(f"Transfer115: 初始化115客户端失败: {e}")
                self._client = None

        # 处理立即提交的链接
        link_input = config.get("link_input", "").strip()
        if link_input and self._client:
            lines = [l.strip() for l in link_input.splitlines() if l.strip()]
            if lines:
                try:
                    self._client.offline_add_urls(lines)
                    logger.info(f"Transfer115: 添加离线任务成功，共 {len(lines)} 条")
                    if self._notify_enabled:
                        self.post_message(
                            mtype=NotificationType.Organize,
                            title="115离线任务已提交",
                            text=f"已提交 {len(lines)} 条离线下载任务"
                        )
                except Exception as e:
                    logger.error(f"Transfer115: 添加离线任务失败: {e}")
        elif link_input and not self._client:
            logger.warning("Transfer115: 链接已填写但115客户端未初始化（请检查Cookie配置）")

        # 处理立即执行
        onlyonce = config.get("onlyonce", False)
        if onlyonce:
            self.__check_and_organize()

        # 清空 link_input 和 onlyonce
        if link_input or onlyonce:
            self.update_config({
                "enabled": self._enabled,
                "notify_enabled": self._notify_enabled,
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
            }
        ]

    def api_refresh_tasks(self) -> dict:
        """手动触发任务检查"""
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}
        if not self._client:
            return {"code": 1, "msg": "115客户端未初始化，请检查Cookie配置"}
        self.__check_and_organize()
        return {"code": 0, "msg": "任务检查已触发"}

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    # 行1：开关区
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
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "onlyonce",
                                            "label": "立即检查一次",
                                            "hint": "保存后立即执行一次任务检查，执行后自动关闭",
                                            "persistent-hint": True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行2：115 Cookie
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
                                            "label": "115 Cookie",
                                            "placeholder": "UID=...;CID=...;SEID=...",
                                            "hint": "在115网盘网页版按F12打开开发者工具，Application > Cookies中复制所有cookie值",
                                            "persistent-hint": True
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行3：目录配置
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
                                            "placeholder": "如 /待整理 （115云盘内路径）"
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
                    # 行4：参数配置
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
                            }
                        ]
                    },
                    # 行5：添加离线下载链接
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
                    # 行6：说明
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
                                                "【Cookie获取】在115网盘网页版（115.com）按F12打开开发者工具，"
                                                "切换到Application标签，展开Cookies，复制所有cookie拼接为 key=value; 格式填入。"
                                                "【目录填写】填写115云盘内的绝对路径，如 /待整理 或 /离线下载/待处理。"
                                                "【工作流程】插件定时轮询115离线任务 → 发现完成任务 → "
                                                "自动识别媒体信息并重命名 → 失败时将整个任务文件夹移入整理失败目录（保持文件完整）。"
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
            "onlyonce": False,
            "cookie": "",
            "download_path": "",
            "fail_path": "",
            "poll_interval": 5,
            "transfer_type": "move",
            "link_input": ""
        }

    def get_page(self) -> List[dict]:
        records = self.get_data("task_records") or []
        if not records:
            return [
                {
                    "component": "div",
                    "text": "暂无任务记录",
                    "props": {"class": "text-center pa-4"}
                }
            ]

        # Show most recent 50 entries, newest first
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

        return [
            {
                "component": "VList",
                "props": {"lines": "two"},
                "content": rows
            },
            {
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
        if not self._client:
            logger.warning("Transfer115: 115客户端未初始化，跳过任务检查")
            return
        try:
            resp = self._client.offline_list()
            tasks = resp.get("tasks", [])
            processed = self.get_data("processed_tasks") or []
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

                # 已完成且未处理
                logger.info(f"Transfer115: 发现已完成任务: {task_name}")
                success = self.__organize_task(task, task_name)
                processed.append(task_id)
                changed = True
                self.__upsert_task_record(task_name, "整理成功" if success else "整理失败")

            if changed:
                self.save_data("processed_tasks", processed)

        except Exception as e:
            logger.error(f"Transfer115: 任务检查异常: {e}")

    def __organize_task(self, task: dict, task_name: str) -> bool:
        """对已完成的离线任务进行媒体识别和整理"""
        any_failure = False
        organized_count = 0

        try:
            file_id = task.get("file_id", "")
            file_list = []

            if file_id:
                try:
                    resp = self._client.fs_files({"cid": file_id, "limit": 1000})
                    file_list = resp.get("data", [])
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
                if self._fail_path and file_id:
                    self.__move_folder_to_fail(task, task_name)
                else:
                    logger.warning(f"Transfer115: 任务 '{task_name}' 部分文件整理失败")
                    if self._notify_enabled:
                        self.post_message(
                            mtype=NotificationType.Manual,
                            title="115整理失败",
                            text=f"❌ 任务: {task_name}\n部分文件整理失败，请手动处理"
                        )

            return not any_failure

        except Exception as e:
            logger.error(f"Transfer115: 整理任务 '{task_name}' 异常: {e}")
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Manual,
                    title="115整理异常",
                    text=f"❌ 任务: {task_name}\n错误: {e}"
                )
            return False

    def __move_folder_to_fail(self, task: dict, task_name: str):
        """将整个任务文件夹移动到整理失败目录"""
        try:
            folder_id = task.get("file_id", "")
            if not folder_id:
                logger.warning(f"Transfer115: 无法获取任务文件夹ID，跳过移动: {task_name}")
                return

            # 确保失败目录存在并获取其ID
            try:
                fail_resp = self._client.fs_makedirs(self._fail_path, exist_ok=True)
                fail_folder_id = (
                    fail_resp.get("id") or
                    fail_resp.get("cid") or
                    fail_resp.get("file_id", "")
                )
            except Exception as e:
                logger.warning(f"Transfer115: fs_makedirs不可用，尝试其他方式: {e}")
                fail_folder_id = ""

            if not fail_folder_id:
                logger.warning(f"Transfer115: 无法获取失败目录ID: {self._fail_path}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="115整理失败",
                        text=f"❌ 任务: {task_name}\n整理失败，请手动移至: {self._fail_path}"
                    )
                return

            # 移动文件夹
            self._client.fs_move([folder_id], pid=fail_folder_id)
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
