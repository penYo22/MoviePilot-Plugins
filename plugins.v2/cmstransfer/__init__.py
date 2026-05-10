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
    # 插件名称
    plugin_name = "转存"
    # 插件描述
    plugin_desc = "通知CMS转存下载，转存完成后自动识别剧集并在云盘内重命名，识别失败移入待处理目录并通知"
    # 插件图标
    plugin_icon = "QQ_A.png"
    # 插件版本
    plugin_version = "1.4"
    # 插件作者
    plugin_author = "penYo22"
    # 作者主页
    author_url = "https://github.com/penYo22"
    # 插件配置项ID前缀
    plugin_config_prefix = "cmstransfer_"
    # 加载顺序
    plugin_order = 10
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled: bool = False
    _cms_domain: str = "http://172.17.0.1:9527"
    _cms_api_token: str = "cloud_media_sync"
    _monitor_path: str = ""
    _fail_movie_path: str = ""
    _fail_tv_path: str = ""
    _auto_organize: bool = True
    _poll_interval: int = 2
    _notify_enabled: bool = False

    # 支持的视频文件扩展名
    _video_extensions = (".mkv", ".mp4", ".avi", ".ts", ".rmvb", ".wmv", ".flv", ".mov")

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled", False)
            self._cms_domain = config.get("cms_domain", "http://172.17.0.1:9527").rstrip("/")
            self._cms_api_token = config.get("cms_api_token", "cloud_media_sync")
            self._monitor_path = config.get("monitor_path", "")
            self._fail_movie_path = config.get("fail_movie_path", "")
            self._fail_tv_path = config.get("fail_tv_path", "")
            self._auto_organize = config.get("auto_organize", True)
            self._poll_interval = int(config.get("poll_interval", 2))
            self._notify_enabled = config.get("notify_enabled", False)

            # 处理立即提交的链接
            link_input = config.get("link_input", "").strip()
            if link_input:
                submitted = 0
                failed = 0
                for line in link_input.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if self.__send_to_cms(line):
                        submitted += 1
                    else:
                        failed += 1
                logger.info(f"CMS转存: 链接提交完成，成功 {submitted} 条，失败 {failed} 条")
                # 清空链接输入，避免重复提交
                self.update_config({
                    "enabled": self._enabled,
                    "auto_organize": self._auto_organize,
                    "notify_enabled": self._notify_enabled,
                    "cms_domain": self._cms_domain,
                    "cms_api_token": self._cms_api_token,
                    "monitor_path": self._monitor_path,
                    "fail_movie_path": self._fail_movie_path,
                    "fail_tv_path": self._fail_tv_path,
                    "poll_interval": self._poll_interval,
                    "link_input": ""  # 清空
                })

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
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
        return [
            {
                "path": "/transfer",
                "endpoint": self.api_transfer,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "CMS转存下载"
            }
        ]

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
                                "props": {"cols": 12, "md": 3},
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
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "auto_organize",
                                            "label": "自动整理"
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
                                            "model": "notify_enabled",
                                            "label": "发送通知"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行2：CMS连接配置
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
                                            "model": "cms_domain",
                                            "label": "CMS服务地址",
                                            "placeholder": "http://172.17.0.1:9527"
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
                                            "model": "cms_api_token",
                                            "label": "CMS API Token",
                                            "placeholder": "cloud_media_sync"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行3：监控目录 + 轮询间隔
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 9},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "monitor_path",
                                            "label": "监控目录",
                                            "placeholder": "在文件管理中复制目录路径，如 /115/待整理"
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
                                            "model": "poll_interval",
                                            "label": "轮询间隔(分钟)",
                                            "placeholder": "2"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行4：识别失败目录（电影 + 电视剧）
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
                                            "model": "fail_movie_path",
                                            "label": "识别失败-电影目录",
                                            "placeholder": "如 /115/识别失败/电影（可留空）"
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
                                            "model": "fail_tv_path",
                                            "label": "识别失败-电视剧目录",
                                            "placeholder": "如 /115/识别失败/电视剧（可留空）"
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    # 行5：添加转存链接
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
                                            "label": "添加转存链接",
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
                    # 行6：提示说明
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
                                            "text": "目录路径请在 MoviePilot 文件管理中浏览到目标目录后复制路径填入。"
                                                    "关闭【自动整理】时，仅转存到CMS，不进行识别和重命名。"
                                                    "识别失败目录留空则不移动文件，仅发通知。"
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
            "auto_organize": True,
            "notify_enabled": False,
            "cms_domain": "http://172.17.0.1:9527",
            "cms_api_token": "cloud_media_sync",
            "monitor_path": "",
            "fail_movie_path": "",
            "fail_tv_path": "",
            "poll_interval": 2,
            "link_input": ""
        }

    def get_page(self) -> List[dict]:
        logs = self.get_data("transfer_log") or []
        if not logs:
            return [
                {
                    "component": "div",
                    "text": "暂无转存记录",
                    "props": {"class": "text-center"}
                }
            ]
        # Show most recent 50 entries, newest first
        logs = list(reversed(logs[-50:]))
        rows = []
        for entry in logs:
            status_text = "✅ 成功" if entry.get("ok") else "❌ 失败"
            rows.append({
                "component": "VListItem",
                "props": {"density": "compact"},
                "content": [
                    {
                        "component": "VListItemTitle",
                        "props": {"class": "text-caption text-truncate"},
                        "text": entry.get("link", "")
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
            }
        ]

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._monitor_path and self._auto_organize:
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
        pass

    @eventmanager.register(EventType.PluginAction)
    def handle_command(self, event: Event):
        """
        处理 /cms_transfer 远程命令
        """
        if not self._enabled:
            return
        if not event:
            return
        event_data = event.event_data or {}
        if event_data.get("action") != "cms_transfer":
            return
        link = event_data.get("args")
        if not link:
            logger.warning("CMS转存: 未提供资源链接")
            return
        logger.info(f"CMS转存: 收到命令转存请求，链接: {link}")
        self.__send_to_cms(link)

    def api_transfer(self, url: str = None, **kwargs) -> dict:
        """
        API接口：触发CMS转存
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
        将资源链接发送到CMS进行离线下载
        """
        import datetime

        if not self._cms_domain or not self._cms_api_token:
            logger.error("CMS转存: CMS服务地址或API Token未配置")
            return False

        valid_schemes = ("magnet:", "ed2k://", "http://", "https://")
        if not link or not link.lower().startswith(valid_schemes):
            logger.warning(f"CMS转存: 无效链接格式，仅支持 magnet/ed2k/http/https: {link}")
            self.__append_transfer_log(link, ok=False)
            return False

        api_url = f"{self._cms_domain}/api/offline/save?token={self._cms_api_token}"
        try:
            res = RequestUtils(content_type="application/json").post(
                url=api_url,
                json={"url": link}
            )
            if res and res.status_code == 200:
                logger.info(f"CMS转存: 转存请求发送成功，链接: {link}")
                self.__append_transfer_log(link, ok=True)
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Organize,
                        title="CMS转存",
                        text=f"转存请求已发送:\n{link}"
                    )
                return True
            else:
                status = res.status_code if res else "无响应"
                logger.error(f"CMS转存: 转存请求失败，状态码: {status}")
                self.__append_transfer_log(link, ok=False)
                return False
        except Exception as e:
            logger.error(f"CMS转存: 转存请求异常: {e}")
            self.__append_transfer_log(link, ok=False)
            return False

    def __append_transfer_log(self, link: str, ok: bool):
        """
        追加转存记录到持久化日志
        """
        import datetime
        log_entry = {
            "link": link[:80] + ("..." if len(link) > 80 else ""),
            "ok": ok,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        existing_log = self.get_data("transfer_log") or []
        existing_log.append(log_entry)
        # Keep only last 200 entries
        if len(existing_log) > 200:
            existing_log = existing_log[-200:]
        self.save_data("transfer_log", existing_log)

    def __check_transfers(self):
        """
        定时扫描监控目录，处理新完成的转存文件
        """
        if not self._monitor_path:
            return

        monitor_dir = Path(self._monitor_path)
        if not monitor_dir.exists():
            logger.warning(f"CMS转存: 监控目录不存在: {self._monitor_path}")
            return

        processed_data = self.get_data("processed_files") or {}
        processed_files = set(processed_data.get("files", []))

        # 清理已不存在的记录
        stale = {f for f in processed_files if not Path(f).exists()}
        if stale:
            processed_files -= stale
            logger.debug(f"CMS转存: 清理 {len(stale)} 条过期记录")
            self.save_data("processed_files", {"files": list(processed_files)})

        new_files_found = False
        for file_path in monitor_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in self._video_extensions:
                continue
            file_key = str(file_path)
            if file_key in processed_files:
                continue

            new_files_found = True
            logger.info(f"CMS转存: 发现新文件: {file_path.name}")
            processed_files.add(file_key)
            self.__recognize_and_rename(file_path)

        if new_files_found:
            self.save_data("processed_files", {"files": list(processed_files)})
            self.__trigger_cms_sync()

    def __recognize_and_rename(self, file_path: Path):
        """
        识别媒体信息并重命名，识别失败则移入失败目录
        """
        filename = file_path.stem
        logger.info(f"CMS转存: 开始识别: {filename}")

        try:
            meta = MetaVideo(title=filename, isfile=True)
            mediainfo = self.chain.recognize_media(meta=meta)

            if not mediainfo:
                logger.warning(f"CMS转存: 识别失败: {filename}")
                self.__handle_recognize_failure(file_path, meta)
                return

            logger.info(f"CMS转存: 识别成功: {filename} -> {mediainfo.title} ({mediainfo.type})")
            transfer_result = self.chain.transfer(
                path=file_path,
                meta=meta,
                mediainfo=mediainfo,
                transfer_type="rename"
            )

            if transfer_result:
                logger.info(f"CMS转存: 重命名成功: {filename}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Organize,
                        title="转存整理完成",
                        text=f"✅ {file_path.name}\n识别为: {mediainfo.title}"
                    )
            else:
                logger.warning(f"CMS转存: 重命名失败: {filename}")
                if self._notify_enabled:
                    self.post_message(
                        mtype=NotificationType.Manual,
                        title="转存重命名失败",
                        text=f"⚠️ {file_path.name}\n识别为: {mediainfo.title}，但重命名失败，请手动处理"
                    )

        except Exception as e:
            logger.error(f"CMS转存: 处理异常: {filename}，错误: {e}")
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Manual,
                    title="转存处理异常",
                    text=f"❌ {file_path.name}\n错误: {e}"
                )

    def __handle_recognize_failure(self, file_path: Path, meta):
        """
        处理识别失败：移入对应失败目录，并发送通知
        """
        # 根据元数据判断是否为剧集，否则归类为电影
        is_tv = bool(meta.begin_episode)
        dest_dir = self._fail_tv_path if is_tv else self._fail_movie_path
        category = "电视剧" if is_tv else "电影"

        moved = False
        if dest_dir:
            dest_path = Path(dest_dir)
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
                target = dest_path / file_path.name
                file_path.rename(target)
                logger.info(f"CMS转存: 识别失败文件已移入{category}失败目录: {target}")
                moved = True
            except Exception as e:
                logger.error(f"CMS转存: 移动识别失败文件出错: {e}")

        if self._notify_enabled:
            location = f"已移入{category}失败目录" if moved else "未配置失败目录，请手动处理"
            self.post_message(
                mtype=NotificationType.Manual,
                title="转存识别失败",
                text=f"❌ {file_path.name}\n类型推断: {category}\n{location}"
            )

    def __trigger_cms_sync(self):
        """
        触发CMS增量同步
        """
        if not self._cms_domain or not self._cms_api_token:
            return
        sync_url = f"{self._cms_domain}/api/sync/lift_by_token?token={self._cms_api_token}&type=lift_sync"
        try:
            res = RequestUtils().get(url=sync_url)
            if res and res.status_code == 200:
                logger.debug("CMS转存: CMS同步触发成功")
            else:
                logger.debug("CMS转存: CMS同步触发失败")
        except Exception as e:
            logger.debug(f"CMS转存: CMS同步触发异常: {e}")
