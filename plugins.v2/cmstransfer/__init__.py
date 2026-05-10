from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.interval import IntervalTrigger

from app.core.event import eventmanager, Event
from app.core.meta import MetaVideo
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils


class CMSTransfer(_PluginBase):
    # Plugin metadata
    plugin_name = "CMS转存"
    plugin_desc = "搜索资源并通知CMS转存下载，转存完成后自动进行剧集识别和重命名，识别失败通知手动处理"
    plugin_icon = "https://raw.githubusercontent.com/imaliang/MoviePilot-Plugins/main/icons/cms.png"
    plugin_version = "1.0"
    plugin_author = "penYo22"
    author_url = "https://github.com/penYo22"
    plugin_config_prefix = "cmstransfer_"
    plugin_order = 10
    auth_level = 1

    # Private attributes
    _enabled: bool = False
    _cms_domain: str = "http://172.17.0.1:9527"
    _cms_api_token: str = "cloud_media_sync"
    _monitor_path: str = ""
    _transfer_type: str = "link"
    _poll_interval: int = 2
    _notify_enabled: bool = False
    _scheduler = None

    # Video file extensions to monitor
    _video_extensions = (".mkv", ".mp4", ".avi", ".ts", ".rmvb", ".wmv", ".flv", ".mov")

    def init_plugin(self, config: dict = None):
        """
        Initialize plugin with configuration.
        """
        if config:
            self._enabled = config.get("enabled", False)
            self._cms_domain = config.get("cms_domain", "http://172.17.0.1:9527").rstrip("/")
            self._cms_api_token = config.get("cms_api_token", "cloud_media_sync")
            self._monitor_path = config.get("monitor_path", "")
            self._transfer_type = config.get("transfer_type", "link")
            self._poll_interval = int(config.get("poll_interval", 2))
            self._notify_enabled = config.get("notify_enabled", False)

    def get_state(self) -> bool:
        """
        Return plugin enabled state.
        """
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        Register /cms_transfer command.
        """
        return [
            {
                "cmd": "/cms_transfer",
                "event": EventType.PluginAction,
                "desc": "CMS转存",
                "category": "",
                "data": {
                    "action": "cms_transfer"
                }
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        """
        Register API endpoints.
        """
        return [
            {
                "path": "/transfer",
                "endpoint": self.api_transfer,
                "methods": ["POST"],
                "summary": "CMS转存下载"
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        Plugin configuration form.
        """
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {
                                    "cols": 12,
                                    "md": 4
                                },
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
                                "props": {
                                    "cols": 12,
                                    "md": 4
                                },
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "notify_enabled",
                                            "label": "发送通知"
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
                                "props": {
                                    "cols": 12,
                                    "md": 6
                                },
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cms_domain",
                                            "label": "CMS服务地址",
                                            "placeholder": "http://172.17.0.1:9527"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {
                                    "cols": 12,
                                    "md": 6
                                },
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "cms_api_token",
                                            "label": "CMS API Token",
                                            "placeholder": "cloud_media_sync"
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
                                "props": {
                                    "cols": 12,
                                    "md": 6
                                },
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "monitor_path",
                                            "label": "监控目录",
                                            "placeholder": "CMS转存完成后文件所在目录"
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {
                                    "cols": 12,
                                    "md": 3
                                },
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "transfer_type",
                                            "label": "转移方式",
                                            "items": [
                                                {"title": "移动", "value": "move"},
                                                {"title": "复制", "value": "copy"},
                                                {"title": "硬链接", "value": "link"},
                                                {"title": "软链接", "value": "softlink"},
                                                {"title": "Rclone复制", "value": "rclone_copy"},
                                                {"title": "Rclone移动", "value": "rclone_move"}
                                            ]
                                        }
                                    }
                                ]
                            },
                            {
                                "component": "VCol",
                                "props": {
                                    "cols": 12,
                                    "md": 3
                                },
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "poll_interval",
                                            "label": "轮询间隔(分钟)",
                                            "placeholder": "2"
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
            "cms_domain": "http://172.17.0.1:9527",
            "cms_api_token": "cloud_media_sync",
            "monitor_path": "",
            "transfer_type": "link",
            "poll_interval": 2,
            "notify_enabled": False
        }

    def get_page(self) -> List[dict]:
        """
        No custom page needed.
        """
        return []

    def get_service(self) -> List[Dict[str, Any]]:
        """
        Register periodic service for monitoring completed transfers.
        """
        if self._enabled and self._monitor_path:
            return [
                {
                    "id": "CMSTransferMonitor",
                    "name": "CMS转存监控",
                    "trigger": IntervalTrigger(minutes=self._poll_interval),
                    "func": self.__check_transfers,
                    "kwargs": {}
                }
            ]
        return []

    def stop_service(self):
        """
        Stop plugin service.
        """
        pass

    @eventmanager.register(EventType.PluginAction)
    def handle_command(self, event: Event):
        """
        Handle /cms_transfer command via event.
        """
        if not self._enabled:
            return
        if not event:
            return
        event_data = event.event_data or {}
        if event_data.get("action") != "cms_transfer":
            return

        # Get the resource link from command arguments
        link = event_data.get("args")
        if not link:
            logger.warning("CMS转存: 未提供资源链接")
            return

        logger.info(f"CMS转存: 收到命令转存请求，链接: {link}")
        self.__send_to_cms(link)

    def api_transfer(self, url: str = None, **kwargs) -> dict:
        """
        API endpoint to trigger CMS transfer.
        """
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}

        if not url:
            return {"code": 1, "msg": "未提供资源链接"}

        logger.info(f"CMS转存: 收到API转存请求，链接: {url}")
        result = self.__send_to_cms(url)
        if result:
            return {"code": 0, "msg": "转存请求已发送"}
        return {"code": 1, "msg": "转存请求发送失败"}

    def __send_to_cms(self, link: str) -> bool:
        """
        Send resource link to CMS API for offline download/transfer.
        """
        if not self._cms_domain or not self._cms_api_token:
            logger.error("CMS转存: CMS服务地址或API Token未配置")
            return False

        # Validate URL scheme before sending to CMS
        valid_schemes = ("magnet:", "ed2k://", "http://", "https://")
        if not link or not link.lower().startswith(valid_schemes):
            logger.warning(f"CMS转存: 无效的资源链接格式，仅支持 magnet/ed2k/http/https 协议: {link}")
            return False

        # POST to CMS offline save endpoint
        # Note: Token is passed in query string as required by the CMS API protocol;
        # this is a CMS API requirement, not a design choice.
        api_url = f"{self._cms_domain}/api/offline/save?token={self._cms_api_token}"
        try:
            res = RequestUtils(content_type="application/json").post(
                url=api_url,
                json={"url": link}
            )
            if res and res.status_code == 200:
                logger.info(f"CMS转存: 转存请求发送成功，链接: {link}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Organize,
                        title="CMS转存",
                        text=f"转存请求已发送:\n{link}"
                    )
                return True
            else:
                status = res.status_code if res else "无响应"
                logger.error(f"CMS转存: 转存请求失败，状态码: {status}，链接: {link}")
                return False
        except Exception as e:
            logger.error(f"CMS转存: 转存请求异常: {str(e)}")
            return False

    def __check_transfers(self):
        """
        Periodically scan the monitor directory for newly completed media files.
        """
        if not self._monitor_path:
            return

        monitor_dir = Path(self._monitor_path)
        if not monitor_dir.exists():
            logger.warning(f"CMS转存: 监控目录不存在: {self._monitor_path}")
            return

        # Load previously processed files from data store
        processed_data = self.get_data("processed_files") or {}
        processed_files = set(processed_data.get("files", []))

        # Prune entries whose paths no longer exist on disk to prevent unbounded growth
        stale_entries = {f for f in processed_files if not Path(f).exists()}
        if stale_entries:
            processed_files -= stale_entries
            logger.debug(f"CMS转存: 清理了 {len(stale_entries)} 条已不存在的记录")
            self.save_data("processed_files", {"files": list(processed_files)})

        # Scan for video files
        new_files_found = False
        for file_path in monitor_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self._video_extensions:
                continue
            file_key = str(file_path)
            if file_key in processed_files:
                continue

            # New file found
            new_files_found = True
            logger.info(f"CMS转存: 发现新文件: {file_path.name}")
            processed_files.add(file_key)

            # Attempt recognition and rename
            self.__recognize_and_rename(file_path)

        if new_files_found:
            # Save updated processed files list
            self.save_data("processed_files", {"files": list(processed_files)})
            # Trigger CMS sync only when new files were discovered
            self.__trigger_cms_sync()

    def __recognize_and_rename(self, file_path: Path):
        """
        Recognize media from filename and transfer/rename using MoviePilot chain.
        """
        filename = file_path.stem
        logger.info(f"CMS转存: 开始识别文件: {filename}")

        try:
            # Create metadata from filename
            meta = MetaVideo(title=filename, isfile=True)

            # Recognize media via chain
            mediainfo = self.chain.recognize_media(meta=meta)

            if not mediainfo:
                # Recognition failed - notify for manual handling
                logger.warning(f"CMS转存: 识别失败: {filename}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="CMS转存 - 识别失败",
                        text=f"文件识别失败，请手动处理:\n{file_path.name}"
                    )
                return

            # Recognition succeeded - transfer/rename
            logger.info(f"CMS转存: 识别成功: {filename} -> {mediainfo.title}")
            transfer_result = self.chain.transfer(
                path=file_path,
                meta=meta,
                mediainfo=mediainfo,
                transfer_type=self._transfer_type
            )

            if transfer_result:
                logger.info(f"CMS转存: 转移成功: {filename}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Organize,
                        title="CMS转存 - 整理完成",
                        text=f"文件整理成功:\n{file_path.name}\n识别为: {mediainfo.title}"
                    )
            else:
                logger.warning(f"CMS转存: 转移失败: {filename}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="CMS转存 - 转移失败",
                        text=f"文件转移失败，请手动处理:\n{file_path.name}"
                    )

        except Exception as e:
            logger.error(f"CMS转存: 识别处理异常: {filename}, 错误: {str(e)}")
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Manual,
                    title="CMS转存 - 处理异常",
                    text=f"文件处理异常:\n{file_path.name}\n错误: {str(e)}"
                )

    def __trigger_cms_sync(self):
        """
        Trigger CMS sync after transfer check.
        """
        if not self._cms_domain or not self._cms_api_token:
            return

        # Note: Token is passed in query string as required by the CMS API protocol;
        # this is a CMS API requirement, not a design choice.
        sync_url = f"{self._cms_domain}/api/sync/lift_by_token?token={self._cms_api_token}&type=lift_sync"
        try:
            res = RequestUtils().get(url=sync_url)
            if res and res.status_code == 200:
                logger.debug("CMS转存: CMS同步触发成功")
            else:
                logger.debug("CMS转存: CMS同步触发失败")
        except Exception as e:
            logger.debug(f"CMS转存: CMS同步触发异常: {str(e)}")
