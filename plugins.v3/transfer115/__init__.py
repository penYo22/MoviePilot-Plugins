import datetime
import json
import re
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import Body

from app.sdk.config import settings
from app.sdk.logging import logger
from app.sdk.media import MetaInfoPath
from app.plugins import _PluginBase
from app.schemas.types import MediaSource, MediaType, NotificationType


class Transfer115(_PluginBase):
    # 插件名称
    plugin_name = "115离线下载"
    # 插件描述
    plugin_desc = "使用MoviePilot内置115授权提交离线任务，支持文件管理、批量改名和改名后TMDB复核。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Frontend/refs/heads/v2/src/assets/images/misc/u115.png"
    # 插件版本
    plugin_version = "5.2.0"
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
    _auto_organize: bool = True
    _download_path: str = ""
    _library_path: str = ""
    _fail_path: str = ""
    _auth_mode: str = "mp_oauth"
    _cookie: str = ""
    _transfer_type: str = "move"
    _poll_interval: int = 5
    _api_interval: int = 1
    _max_retries: int = 3
    _stabilize_cycles: int = 1
    _max_tasks_per_poll: int = 20
    _cleanup_empty_folder: bool = True
    _history_retention_days: int = 30
    _rename_enabled: bool = True
    _rename_directories: bool = True
    _rename_max_files: int = 200
    _split_delimiters: str = ""
    _split_template: str = "{1} - {2}"
    _split_keep_extension: bool = True
    _checking: bool = False

    _max_records = 200

    def init_plugin(self, config: dict = None):
        config = config or {}

        self._enabled = bool(config.get("enabled", False))
        self._notify_enabled = bool(config.get("notify_enabled", False))
        self._auto_organize = bool(config.get("auto_organize", True))
        self._auth_mode = config.get("auth_mode", "mp_oauth") or "mp_oauth"
        self._cookie = (config.get("cookie") or "").strip()
        self._download_path = self.__clean_path(config.get("download_path") or "")
        self._library_path = self.__clean_path(config.get("library_path") or "")
        self._fail_path = self.__clean_path(config.get("fail_path") or "")
        self._transfer_type = config.get("transfer_type", "move") or "move"
        self._poll_interval = self.__safe_int(config.get("poll_interval"), 5, 1, 1440)
        self._api_interval = self.__safe_int(config.get("api_interval"), 1, 0, 3600)
        self._max_retries = self.__safe_int(config.get("max_retries"), 3, 1, 20)
        self._stabilize_cycles = self.__safe_int(config.get("stabilize_cycles"), 1, 0, 10)
        self._max_tasks_per_poll = self.__safe_int(config.get("max_tasks_per_poll"), 20, 1, 200)
        self._cleanup_empty_folder = bool(config.get("cleanup_empty_folder", True))
        self._history_retention_days = self.__safe_int(config.get("history_retention_days"), 30, 0, 3650)
        self._rename_enabled = bool(config.get("rename_enabled", True))
        self._rename_directories = bool(config.get("rename_directories", True))
        self._rename_max_files = self.__safe_int(config.get("rename_max_files"), 200, 1, 1000)
        self._split_delimiters = str(config.get("split_delimiters") or "")[:1000]
        self._split_template = str(config.get("split_template") or "{1} - {2}")[:255]
        self._split_keep_extension = bool(config.get("split_keep_extension", True))

        self.__cleanup_history()

        link_input = (config.get("link_input") or "").strip()
        if link_input:
            lines = self.__parse_links(link_input)
            if lines:
                self.__submit_links(lines)

        onlyonce = bool(config.get("onlyonce", False))
        if onlyonce:
            self.__check_and_organize()

        if link_input or onlyonce:
            self.__save_config(link_input="", onlyonce=False)

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        if not self.get_state():
            return []
        return [
            {
                "nav_key": "main",
                "title": "115文件管理器",
                "icon": "mdi-folder-edit-outline",
                "section": "organize",
                "permission": "manage",
                "order": 48,
            }
        ]

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/refresh_tasks",
                "endpoint": self.api_refresh_tasks,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "手动检查115离线任务",
            },
            {
                "path": "/submit_offline",
                "endpoint": self.api_submit_offline,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "提交115离线下载链接",
            },
            {
                "path": "/offline_tasks",
                "endpoint": self.api_offline_tasks,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "查询115离线下载任务",
            },
            {
                "path": "/nav_dir",
                "endpoint": self.api_nav_dir,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "导航到目录",
            },
            {
                "path": "/set_download_path",
                "endpoint": self.api_set_download_path,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "设置下载目录",
            },
            {
                "path": "/set_path",
                "endpoint": self.api_set_path,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "设置目录配置",
            },
            {
                "path": "/clear_logs",
                "endpoint": self.api_clear_logs,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "清空任务记录",
            },
            {
                "path": "/list_download_folders",
                "endpoint": self.api_list_download_folders,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "列出下载目录子文件夹",
            },
            {
                "path": "/organize_folder",
                "endpoint": self.api_organize_folder,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "整理单个115文件夹",
            },
            {
                "path": "/organize_all",
                "endpoint": self.api_organize_all,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "整理下载目录下所有文件夹",
            },
            {
                "path": "/scan_rename",
                "endpoint": self.api_scan_rename,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "扫描115目录并生成改名预览",
            },
            {
                "path": "/apply_rename",
                "endpoint": self.api_apply_rename,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "确认执行115批量改名",
            },
            {
                "path": "/file_manager",
                "endpoint": self.api_file_manager,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "浏览115文件管理器",
            },
            {
                "path": "/plugin_state",
                "endpoint": self.api_plugin_state,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "读取115插件状态与配置",
            },
            {
                "path": "/settings",
                "endpoint": self.api_update_settings,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "更新115插件配置",
            },
            {
                "path": "/preview_custom_rename",
                "endpoint": self.api_preview_custom_rename,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "校验并预览勾选文件改名",
            },
            {
                "path": "/apply_custom_rename",
                "endpoint": self.api_apply_custom_rename,
                "methods": ["POST"],
                "auth": "bear",
                "summary": "执行勾选文件改名",
            },
        ]

    def api_refresh_tasks(self) -> dict:
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}
        self.__check_and_organize(force=True)
        result = self.api_offline_tasks()
        result["msg"] = "任务检查完成"
        return result

    def api_submit_offline(self, payload: Optional[dict] = Body(default=None)) -> dict:
        """通过MoviePilot内置115授权或Cookie客户端提交离线下载任务。"""
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}
        payload = payload or {}
        raw_links = payload.get("links") or payload.get("urls") or ""
        if isinstance(raw_links, list):
            raw_links = "\n".join(str(link) for link in raw_links)
        lines = self.__parse_links(str(raw_links))[:100]
        if not lines:
            return {"code": 1, "msg": "请填写磁力、ed2k、HTTP或115分享链接"}
        return self.__submit_links(lines)

    def api_offline_tasks(self) -> dict:
        """返回适合工作台展示的115离线任务列表。"""
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用", "tasks": []}
        oper = self._get_cookie_oper() if self._auth_mode == "cookie" else self._get_u115_oper()
        if not oper:
            mode = "Cookie" if self._auth_mode == "cookie" else "MoviePilot内置115"
            return {"code": 1, "msg": f"{mode}未授权或不可用", "tasks": []}
        try:
            tasks = [self.__offline_task_view(task) for task in self.__list_offline_tasks(oper)]
            return {
                "code": 0,
                "msg": f"已读取 {len(tasks)} 个离线任务",
                "tasks": tasks,
                "download_path": self._download_path,
                "auth_mode": self._auth_mode,
            }
        except Exception as e:
            logger.warning(f"Transfer115: 查询离线任务失败: {e}")
            return {"code": 1, "msg": str(e), "tasks": []}

    def api_nav_dir(self, path: str = "/") -> dict:
        self.save_data("browse_path", self.__clean_path(path, default="/"))
        return {"code": 0}

    def api_plugin_state(self) -> dict:
        """提供 Vue 文件管理器使用的轻量状态。"""
        return {
            "code": 0,
            "enabled": self._enabled,
            "rename_enabled": self._rename_enabled,
            "download_path": self._download_path,
            "split_tokens": self.__split_tokens(self._split_delimiters),
            "split_template": self._split_template,
            "split_keep_extension": self._split_keep_extension,
            "config": {
                "enabled": self._enabled,
                "notify_enabled": self._notify_enabled,
                "auto_organize": self._auto_organize,
                "auth_mode": self._auth_mode,
                "has_cookie": bool(self._cookie),
                "download_path": self._download_path,
                "library_path": self._library_path,
                "fail_path": self._fail_path,
                "transfer_type": self._transfer_type,
                "poll_interval": self._poll_interval,
                "api_interval": self._api_interval,
                "max_retries": self._max_retries,
                "stabilize_cycles": self._stabilize_cycles,
                "max_tasks_per_poll": self._max_tasks_per_poll,
                "cleanup_empty_folder": self._cleanup_empty_folder,
                "history_retention_days": self._history_retention_days,
                "rename_enabled": self._rename_enabled,
                "rename_directories": self._rename_directories,
                "rename_max_files": self._rename_max_files,
                "split_delimiters": self._split_delimiters,
                "split_template": self._split_template,
                "split_keep_extension": self._split_keep_extension,
            },
        }

    def api_update_settings(self, payload: Optional[dict] = Body(default=None)) -> dict:
        """更新插件设置，不触碰115文件。"""
        payload = payload or {}
        self._enabled = bool(payload.get("enabled", self._enabled))
        self._notify_enabled = bool(payload.get("notify_enabled", self._notify_enabled))
        self._auto_organize = bool(payload.get("auto_organize", self._auto_organize))
        auth_mode = str(payload.get("auth_mode") or self._auth_mode)
        self._auth_mode = auth_mode if auth_mode in {"mp_oauth", "cookie"} else "mp_oauth"
        if str(payload.get("cookie") or "").strip():
            self._cookie = str(payload.get("cookie") or "").strip()
        self._download_path = self.__clean_path(payload.get("download_path", self._download_path))
        self._library_path = self.__clean_path(payload.get("library_path", self._library_path))
        self._fail_path = self.__clean_path(payload.get("fail_path", self._fail_path))
        transfer_type = str(payload.get("transfer_type") or self._transfer_type)
        self._transfer_type = transfer_type if transfer_type in {"move", "copy"} else "move"
        self._poll_interval = self.__safe_int(payload.get("poll_interval"), self._poll_interval, 1, 1440)
        self._api_interval = self.__safe_int(payload.get("api_interval"), self._api_interval, 0, 3600)
        self._max_retries = self.__safe_int(payload.get("max_retries"), self._max_retries, 1, 20)
        self._stabilize_cycles = self.__safe_int(payload.get("stabilize_cycles"), self._stabilize_cycles, 0, 10)
        self._max_tasks_per_poll = self.__safe_int(payload.get("max_tasks_per_poll"), self._max_tasks_per_poll, 1, 200)
        self._cleanup_empty_folder = bool(payload.get("cleanup_empty_folder", self._cleanup_empty_folder))
        self._history_retention_days = self.__safe_int(payload.get("history_retention_days"), self._history_retention_days, 0, 3650)
        self._rename_enabled = bool(payload.get("rename_enabled", self._rename_enabled))
        self._rename_directories = bool(payload.get("rename_directories", self._rename_directories))
        self._rename_max_files = self.__safe_int(payload.get("rename_max_files"), self._rename_max_files, 1, 1000)
        split_tokens = payload.get("split_tokens")
        if isinstance(split_tokens, list):
            self._split_delimiters = json.dumps(
                [str(token)[:50] for token in split_tokens if str(token)],
                ensure_ascii=False,
            )[:1000]
        elif "split_delimiters" in payload:
            self._split_delimiters = str(payload.get("split_delimiters") or "")[:1000]
        self._split_template = str(payload.get("split_template") or self._split_template)[:255]
        self._split_keep_extension = bool(payload.get("split_keep_extension", self._split_keep_extension))
        self.__save_config()
        state = self.api_plugin_state()
        state["msg"] = "设置已保存；定时服务相关变更将在插件重新加载后生效"
        return state

    def api_file_manager(self, path: str = "") -> dict:
        """列出当前115目录的文件和子目录，供 Vue 文件管理器浏览。"""
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用", "items": []}
        if self._auth_mode == "cookie":
            return {"code": 1, "msg": "文件管理器需要使用MoviePilot内置115授权", "items": []}

        browse_path = self.__clean_path(path or self._download_path, default="/")
        try:
            from app.chain.storage import StorageChain
            from app.schemas import FileItem

            root = FileItem(storage="u115", path=self.__dir_path(browse_path), type="dir")
            self._sleep_if_needed()
            items = StorageChain().list_files(root) or []
            result = []
            for item in items:
                item_path = self.__clean_path(str(item.path or ""))
                if not item_path:
                    continue
                item_type = self.__display_value(getattr(item, "type", "file"))
                result.append(
                    {
                        "name": str(item.name or PurePosixPath(item_path).name),
                        "path": item_path,
                        "type": "dir" if item_type == "dir" else "file",
                        "fileid": str(item.fileid or ""),
                        "size": int(getattr(item, "size", 0) or 0),
                    }
                )
            result.sort(key=lambda item: (item["type"] != "dir", item["name"].casefold()))
            parent = None
            if browse_path != "/":
                parent = PurePosixPath(browse_path).parent.as_posix()
                if parent == ".":
                    parent = "/"
            return {
                "code": 0,
                "path": browse_path,
                "parent": parent,
                "items": result,
                "selected_count": 0,
            }
        except Exception as e:
            logger.warning(f"Transfer115: 文件管理器读取目录失败: {e}")
            return {"code": 1, "msg": str(e), "path": browse_path, "items": []}

    def api_preview_custom_rename(self, payload: Optional[dict] = Body(default=None)) -> dict:
        """根据鼠标选取的拆分字符串，预览勾选文件的新名称。"""
        if not self._enabled or not self._rename_enabled:
            return {"code": 1, "msg": "改名功能未启用"}
        payload = payload or {}
        paths = [self.__clean_path(str(path)) for path in (payload.get("selected_paths") or [])]
        paths = list(dict.fromkeys(path for path in paths if path))[: self._rename_max_files]
        tokens = [str(token)[:50] for token in (payload.get("split_tokens") or []) if str(token)]
        template = str(payload.get("template") or self._split_template)[:255]
        keep_extension = bool(payload.get("keep_extension", self._split_keep_extension))
        if not paths:
            return {"code": 1, "msg": "请先勾选要改名的文件", "items": []}
        if not tokens:
            return {"code": 1, "msg": "请先在样例文件名中拖选要拆分的文字", "items": []}
        if not re.search(r"\{\d+\}", template):
            return {"code": 1, "msg": "命名模板至少需要一个片段占位符，例如 {1} {2}", "items": []}

        try:
            from app.chain.storage import StorageChain
            from app.schemas import FileItem

            storage_chain = StorageChain()
            preview_items = []
            errors = []
            target_keys = set()
            for path in paths:
                old_name = PurePosixPath(path).name
                current = storage_chain.get_item(
                    FileItem(storage="u115", type="file", path=path, name=old_name)
                )
                if not current:
                    errors.append({"path": path, "msg": "远端文件不存在或路径已变化"})
                    continue
                parts, new_name = self.__split_filename(old_name, tokens, template, keep_extension)
                if not new_name:
                    errors.append({"path": path, "msg": "模板生成了空文件名"})
                    continue
                target_key = (PurePosixPath(path).parent.as_posix(), new_name.casefold())
                if target_key in target_keys:
                    errors.append({"path": path, "msg": f"生成了重复名称: {new_name}"})
                    continue
                target_keys.add(target_key)
                preview_items.append(
                    {
                        "type": "file",
                        "path": path,
                        "fileid": str(current.fileid or ""),
                        "name": old_name,
                        "parts": parts,
                        "new_name": new_name,
                        "unchanged": old_name == new_name,
                    }
                )
            plan = {
                "code": 0 if preview_items else 1,
                "msg": f"已测试 {len(preview_items)} 个文件，可改名 {sum(not item['unchanged'] for item in preview_items)} 个",
                "plan_id": uuid.uuid4().hex,
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "tokens": tokens,
                "template": template,
                "keep_extension": keep_extension,
                "items": preview_items,
                "errors": errors,
            }
            self.save_data("split_rename_plan", plan)
            return plan
        except Exception as e:
            logger.error(f"Transfer115: 自定义拆分预览失败: {e}")
            return {"code": 1, "msg": str(e), "items": []}

    def api_apply_custom_rename(self, payload: Optional[dict] = Body(default=None)) -> dict:
        """执行最近一次自定义拆分测试计划中的文件。"""
        if not self._enabled or not self._rename_enabled:
            return {"code": 1, "msg": "改名功能未启用"}
        payload = payload or {}
        plan = self.get_data("split_rename_plan") or {}
        if not plan.get("plan_id") or str(payload.get("plan_id") or "") != str(plan.get("plan_id")):
            return {"code": 1, "msg": "测试计划已变化，请重新测试"}
        if self.__rename_plan_expired(plan):
            self.del_data("split_rename_plan")
            return {"code": 1, "msg": "测试计划已过期，请重新测试"}

        try:
            from app.chain.storage import StorageChain
            from app.schemas import FileItem

            storage_chain = StorageChain()
            success, failed = [], []
            recognition_results = []
            for item in plan.get("items") or []:
                old_name = str(item.get("name") or "")
                new_name = self.__safe_name(item.get("new_name"))
                path = self.__clean_path(item.get("path"))
                if not old_name or not new_name or not path:
                    failed.append({"name": old_name, "msg": "改名计划条目不完整"})
                    continue
                if old_name == new_name:
                    success.append({"old_name": old_name, "new_name": new_name, "skipped": True})
                    continue
                current = storage_chain.get_item(
                    FileItem(storage="u115", type="file", path=path, name=old_name, fileid=str(item.get("fileid") or "") or None)
                )
                if not current:
                    failed.append({"name": old_name, "msg": "远端文件已不存在或路径已变化"})
                    continue
                sibling = FileItem(storage="u115", type="dir", path=self.__dir_path(PurePosixPath(path).parent.as_posix()))
                siblings = storage_chain.list_files(sibling) or []
                if any(str(s.name or "").casefold() == new_name.casefold() and s.path != current.path for s in siblings):
                    failed.append({"name": old_name, "msg": f"目标名称已存在: {new_name}"})
                    continue
                self._sleep_if_needed()
                if storage_chain.rename_file(current, new_name):
                    result = {"old_name": old_name, "new_name": new_name}
                    if item.get("type", "file") == "file":
                        result["recognition"] = self.__recognize_renamed_file(path, new_name)
                        recognition_results.append(result["recognition"])
                    success.append(result)
                else:
                    failed.append({"name": old_name, "msg": "115重命名接口返回失败"})
            self.del_data("split_rename_plan")
            self.__upsert_task_record("自定义拆分改名", f"完成 {len(success)} 个，失败 {len(failed)} 个")
            matched = sum(1 for item in recognition_results if item.get("matched"))
            return {
                "code": 0 if success or not failed else 1,
                "msg": f"改名完成：成功 {len(success)} 个，失败 {len(failed)} 个；识别命中 {matched} 个",
                "success": success,
                "failed": failed,
                "recognition_results": recognition_results,
            }
        except Exception as e:
            logger.error(f"Transfer115: 执行自定义改名失败: {e}")
            return {"code": 1, "msg": str(e)}

    def __recognize_renamed_file(self, old_path: str, new_name: str) -> dict:
        """用改名后的文件名调用MoviePilot内置TMDB识别链。"""
        parent = PurePosixPath(self.__clean_path(old_path)).parent.as_posix()
        new_path = f"{parent.rstrip('/')}/{new_name}" if parent != "/" else f"/{new_name}"
        result = {
            "path": new_path,
            "name": new_name,
            "matched": False,
            "type": "unknown",
            "type_label": "未命中",
            "season": None,
            "episodes": [],
            "episode_label": "",
            "title": "",
            "title_year": "",
            "tmdb_id": "",
            "media_source": "",
            "error": "",
        }
        try:
            from app.chain.media import MediaChain

            # 复用 MoviePilot 文件识别入口，保持识别结果与内置文件管理器一致。
            context = MediaChain().recognize_by_path(
                new_path,
                media_source=MediaSource.TMDB,
                obtain_images=False,
            )
            meta = getattr(context, "meta_info", None) if context else None
            mediainfo = getattr(context, "media_info", None) if context else None
            if not mediainfo or getattr(mediainfo, "type", None) not in (MediaType.MOVIE, MediaType.TV):
                return result
            media_type = getattr(mediainfo, "type", None)
            media_type_value = self.__display_value(media_type)
            if media_type == MediaType.MOVIE or media_type_value in {"电影", "movie", "movies"}:
                type_key = "movie"
                type_label = "电影"
            elif media_type == MediaType.TV or media_type_value in {"电视剧", "tv", "television"}:
                type_key = "tv"
                type_label = "电视剧"
            else:
                return result
            season = getattr(mediainfo, "season", None)
            if season is None:
                season = getattr(meta, "begin_season", None)
            episodes = list(getattr(meta, "episode_list", None) or [])
            if not episodes:
                episode = getattr(mediainfo, "episode", None)
                if episode is not None:
                    episodes = [episode]
            normalized_episodes = []
            for episode in episodes:
                try:
                    normalized_episodes.append(int(episode))
                except (TypeError, ValueError):
                    continue
            normalized_episodes = list(dict.fromkeys(normalized_episodes))
            try:
                season = int(season) if season is not None else None
            except (TypeError, ValueError):
                season = None
            result.update(
                {
                    "matched": True,
                    "type": type_key,
                    "type_label": type_label,
                    "season": season,
                    "episodes": normalized_episodes,
                    "episode_label": self.__format_episode_label(type_key, season, normalized_episodes),
                    "title": str(getattr(mediainfo, "title", "") or ""),
                    "title_year": str(getattr(mediainfo, "title_year", "") or ""),
                    "tmdb_id": str(getattr(mediainfo, "tmdb_id", None) or getattr(mediainfo, "media_id", "") or ""),
                    "media_source": self.__display_value(getattr(mediainfo, "media_source", None)),
                }
            )
        except Exception as e:
            logger.warning(f"Transfer115: 改名后TMDB识别失败 {new_path}: {e}")
            result["error"] = str(e)
        return result

    @staticmethod
    def __format_episode_label(type_key: str, season: Optional[int], episodes: List[int]) -> str:
        """将识别出的季集整理成简洁的中文展示文本。"""
        if type_key != "tv":
            return ""
        labels = []
        if season is not None:
            labels.append(f"第 {season} 季")
        if episodes:
            if len(episodes) == 1:
                episode_text = str(episodes[0])
            elif episodes == list(range(episodes[0], episodes[-1] + 1)):
                episode_text = f"{episodes[0]}-{episodes[-1]}"
            else:
                episode_text = "、".join(str(episode) for episode in episodes)
            labels.append(f"第 {episode_text} 集")
        return " · ".join(labels)

    def api_set_download_path(self, path: str = "/") -> dict:
        return self.api_set_path(field="download_path", path=path)

    def api_set_path(self, field: str = "", path: str = "/") -> dict:
        if field not in ("download_path", "library_path", "fail_path"):
            return {"code": 1, "msg": "无效字段"}

        clean_path = self.__clean_path(path, default="/")
        if field == "download_path":
            self._download_path = clean_path
            label = "下载目录"
        elif field == "library_path":
            self._library_path = clean_path
            label = "媒体库目录"
        else:
            self._fail_path = clean_path
            label = "失败目录"

        self.__save_config()
        logger.info(f"Transfer115: {label}已设置为: {clean_path}")
        return {"code": 0, "msg": f"{label}已设置为: {clean_path}"}

    def api_clear_logs(self) -> dict:
        for key in (
            "task_records",
            "processed_tasks",
            "failed_tasks",
            "download_done_tasks",
            "last_poll_summary",
            "rename_plan",
            "split_rename_plan",
        ):
            self.del_data(key)
        logger.info("Transfer115: 插件任务记录已清空")
        return {"code": 0, "msg": "任务记录已清空"}

    def api_list_download_folders(self) -> dict:
        if not self._download_path:
            return {"code": 1, "msg": "未设置下载目录", "folders": []}

        try:
            if self._auth_mode == "cookie":
                oper = self._get_cookie_oper()
                if not oper:
                    return {"code": 1, "msg": "Cookie客户端初始化失败", "folders": []}
                folder_id = self._get_folder_id_by_path_cookie(self._download_path, oper)
                if folder_id is None:
                    return {"code": 1, "msg": "无法找到下载目录", "folders": []}
                self._sleep_if_needed()
                resp = oper.fs_files({"cid": int(folder_id), "limit": 200})
                items = resp.get("data", []) if isinstance(resp, dict) else []
                folders = [
                    {
                        "name": item.get("n", ""),
                        "path": f"{self._download_path.rstrip('/')}/{item.get('n', '')}",
                        "fileid": str(item.get("cid") or ""),
                    }
                    for item in items
                    if item.get("n") and item.get("fid") is None
                ]
                result = {"code": 0, "folders": folders}
                if len(folders) >= 200:
                    result["warning"] = "Cookie模式仅显示前200个子文件夹，列表可能不完整"
                return result

            from app.chain.storage import StorageChain
            from app.schemas import FileItem

            path = self.__dir_path(self._download_path)
            fileitem = FileItem(storage="u115", path=path, type="dir")
            self._sleep_if_needed()
            items = StorageChain().list_files(fileitem) or []
            folders = [
                {"name": item.name, "path": item.path, "fileid": item.fileid or ""}
                for item in items
                if item.type == "dir"
            ]
            return {"code": 0, "folders": folders}
        except Exception as e:
            logger.warning(f"Transfer115: 列出下载目录失败: {e}")
            return {"code": 1, "msg": str(e), "folders": []}

    def api_organize_folder(self, folder_path: str = "", fileid: str = "") -> dict:
        folder_path = self.__clean_path(folder_path)
        if not folder_path:
            return {"code": 1, "msg": "缺少参数: folder_path"}

        fileitem = self.__build_folder_fileitem(folder_path=folder_path, fileid=fileid)
        if not fileitem:
            return {"code": 1, "msg": f"无法获取文件夹信息: {folder_path}"}

        state, errmsg = self.__manual_transfer_fileitem(fileitem=fileitem)
        folder_name = fileitem.name or Path(folder_path).name
        if state:
            self.__upsert_task_record(folder_name, "整理完成")
            self.__cleanup_source_folder(fileitem)
            return {"code": 0, "msg": f"整理成功: {folder_name}"}

        self.__upsert_task_record(folder_name, "整理失败")
        return {"code": 1, "msg": f"整理失败: {errmsg}"}

    def api_organize_all(self) -> dict:
        result = self.api_list_download_folders()
        if result.get("code") != 0:
            return result

        folders = result.get("folders") or []
        if not folders:
            return {"code": 0, "msg": "下载目录中没有子文件夹"}

        success_count = 0
        fail_count = 0
        for folder in folders:
            ret = self.api_organize_folder(
                folder_path=folder.get("path") or "",
                fileid=folder.get("fileid") or "",
            )
            if ret.get("code") == 0:
                success_count += 1
            else:
                fail_count += 1
            self._sleep_if_needed()

        code = 0 if success_count else 1
        return {"code": code, "msg": f"整理完成：成功 {success_count} 个，失败 {fail_count} 个"}

    def api_scan_rename(self, folder_path: str = "") -> dict:
        """扫描115目录，保存识别后的改名预览，不修改远端文件。"""
        if not self._enabled or not self._rename_enabled:
            return {"code": 1, "msg": "改名功能未启用"}
        folder_path = self.__clean_path(folder_path or self._download_path)
        if not folder_path:
            return {"code": 1, "msg": "未设置下载目录"}

        plan = self.__build_rename_plan(folder_path)
        if plan.get("code") != 0:
            return plan
        self.save_data("rename_plan", plan)
        return plan

    def api_apply_rename(self, payload: Optional[dict] = Body(default=None)) -> dict:
        """执行最近一次已保存的改名预览计划。"""
        if not self._enabled or not self._rename_enabled:
            return {"code": 1, "msg": "改名功能未启用"}

        plan_id = str((payload or {}).get("plan_id") or "")
        plan = self.get_data("rename_plan") or {}
        saved_plan_id = str(plan.get("plan_id") or "")
        if not saved_plan_id:
            return {"code": 1, "msg": "没有可执行的改名预览，请先扫描"}
        if not plan_id or plan_id != saved_plan_id:
            return {"code": 1, "msg": "改名预览已变化，请重新扫描"}
        if self.__rename_plan_expired(plan):
            self.del_data("rename_plan")
            return {"code": 1, "msg": "改名预览已过期，请重新扫描"}

        try:
            from app.chain.storage import StorageChain
            from app.schemas import FileItem

            storage_chain = StorageChain()
            success = []
            failed = []
            recognition_results = []
            # 文件先改名，目录后改名，避免目录改名影响后续路径校验。
            items = sorted(
                plan.get("items") or [],
                key=lambda item: 0 if item.get("type") == "file" else 1,
            )
            for item in items:
                old_name = str(item.get("name") or "")
                new_name = self.__safe_name(item.get("new_name"))
                path = self.__clean_path(item.get("path"))
                if not old_name or not new_name or not path:
                    failed.append({"name": old_name, "msg": "改名计划条目不完整"})
                    continue
                if old_name == new_name:
                    success.append({"old_name": old_name, "new_name": new_name, "skipped": True})
                    continue

                fileitem = FileItem(
                    storage="u115",
                    type=item.get("type") or "file",
                    path=self.__dir_path(path) if item.get("type") == "dir" else path,
                    name=old_name,
                    fileid=str(item.get("fileid") or "") or None,
                )
                current = storage_chain.get_item(fileitem)
                if not current:
                    failed.append({"name": old_name, "msg": "远端文件已不存在或路径已变化"})
                    continue
                sibling = FileItem(
                    storage="u115",
                    type="dir",
                    path=self.__dir_path(PurePosixPath(path).parent.as_posix()),
                )
                siblings = storage_chain.list_files(sibling) or []
                if any(
                    str(s.name or "").casefold() == new_name.casefold()
                    and s.path != current.path
                    for s in siblings
                ):
                    failed.append({"name": old_name, "msg": f"目标名称已存在: {new_name}"})
                    continue
                self._sleep_if_needed()
                renamed = storage_chain.rename_file(current, new_name)
                if renamed:
                    result = {"old_name": old_name, "new_name": new_name}
                    if item.get("type", "file") == "file":
                        result["recognition"] = self.__recognize_renamed_file(path, new_name)
                        recognition_results.append(result["recognition"])
                    success.append(result)
                else:
                    failed.append({"name": old_name, "msg": "115重命名接口返回失败"})

            self.del_data("rename_plan")
            self.__upsert_task_record("批量改名", f"完成 {len(success)} 个，失败 {len(failed)} 个")
            matched = sum(1 for item in recognition_results if item.get("matched"))
            return {
                "code": 0 if success or not failed else 1,
                "msg": f"改名完成：成功 {len(success)} 个，失败 {len(failed)} 个；识别命中 {matched} 个",
                "success": success,
                "failed": failed,
                "recognition_results": recognition_results,
            }
        except Exception as e:
            logger.error(f"Transfer115: 执行批量改名失败: {e}")
            return {"code": 1, "msg": str(e)}

    def __build_rename_plan(self, folder_path: str) -> dict:
        """使用MoviePilot识别链和当前命名模板生成115远端改名计划。"""
        try:
            from app.chain.media import MediaChain
            from app.chain.storage import StorageChain
            from app.chain.transfer import TransferChain
            from app.schemas import FileItem

            root = self.__build_folder_fileitem(folder_path=folder_path)
            if not root:
                return {"code": 1, "msg": f"无法读取目录: {folder_path}", "items": []}

            storage_chain = StorageChain()
            files = storage_chain.list_files(root, recursion=True) or []
            media_exts = {str(ext).lower() for ext in settings.RMT_MEDIAEXT}
            media_files = [
                item
                for item in files
                if item.type == "file"
                and PurePosixPath(item.path or item.name or "").suffix.lower() in media_exts
            ]
            truncated = len(media_files) > self._rename_max_files
            media_files = media_files[: self._rename_max_files]

            media_chain = MediaChain()
            transfer_chain = TransferChain()
            plan_items = []
            errors = []
            unchanged = 0
            target_keys = set()
            directory_targets: Dict[str, dict] = {}
            root_path = PurePosixPath(folder_path)

            for fileitem in media_files:
                try:
                    file_path = PurePosixPath(fileitem.path)
                    meta = MetaInfoPath(Path(file_path.as_posix()))
                    mediainfo = media_chain.recognize_media(meta=meta)
                    if not mediainfo:
                        errors.append({"path": file_path.as_posix(), "msg": "MoviePilot未识别到媒体"})
                        continue

                    recommended = transfer_chain.recommend_name(meta=meta, mediainfo=mediainfo)
                    recommended_name = self.__safe_name(PurePosixPath(str(recommended or "")).name)
                    if not recommended_name:
                        errors.append({"path": file_path.as_posix(), "msg": "未生成有效的推荐名称"})
                        continue
                    if not PurePosixPath(recommended_name).suffix and file_path.suffix:
                        recommended_name = f"{recommended_name}{file_path.suffix}"

                    target_key = (file_path.parent.as_posix(), recommended_name.casefold())
                    if target_key in target_keys:
                        errors.append({"path": file_path.as_posix(), "msg": f"推荐名称重复: {recommended_name}"})
                        continue
                    target_keys.add(target_key)

                    if fileitem.name == recommended_name:
                        unchanged += 1
                    else:
                        plan_items.append(
                            {
                                "type": "file",
                                "path": file_path.as_posix(),
                                "fileid": fileitem.fileid or "",
                                "name": fileitem.name or file_path.name,
                                "new_name": recommended_name,
                                "media_source": self.__display_value(getattr(mediainfo, "media_source", None)),
                                "media_id": str(getattr(mediainfo, "media_id", None) or ""),
                                "title": getattr(mediainfo, "title_year", None) or getattr(mediainfo, "title", ""),
                            }
                        )

                    if not self._rename_directories:
                        continue
                    try:
                        relative = file_path.relative_to(root_path)
                    except ValueError:
                        continue
                    if len(relative.parts) < 2:
                        continue
                    top_dir_path = root_path / relative.parts[0]
                    directory_name = self.__safe_name(
                        getattr(mediainfo, "title_year", None) or getattr(mediainfo, "title", "")
                    )
                    if not directory_name:
                        continue
                    entry = directory_targets.setdefault(
                        top_dir_path.as_posix(),
                        {"names": set(), "title": getattr(mediainfo, "title_year", None) or ""},
                    )
                    entry["names"].add(directory_name)
                except Exception as e:
                    errors.append({"path": str(getattr(fileitem, "path", "")), "msg": str(e)})

            if self._rename_directories:
                directory_target_keys = set()
                for dir_path, target in directory_targets.items():
                    names = target.get("names") or set()
                    if len(names) != 1:
                        errors.append({"path": dir_path, "msg": "同一目录识别到多个媒体，已跳过目录改名"})
                        continue
                    new_name = next(iter(names))
                    old_name = PurePosixPath(dir_path).name
                    if old_name == new_name:
                        unchanged += 1
                        continue
                    target_key = (PurePosixPath(dir_path).parent.as_posix(), new_name.casefold())
                    if target_key in directory_target_keys:
                        errors.append({"path": dir_path, "msg": f"目录推荐名称重复: {new_name}"})
                        continue
                    directory_target_keys.add(target_key)
                    dir_item = storage_chain.get_item(
                        FileItem(storage="u115", type="dir", path=self.__dir_path(dir_path))
                    )
                    if not dir_item:
                        errors.append({"path": dir_path, "msg": "无法获取待改名目录"})
                        continue
                    plan_items.append(
                        {
                            "type": "dir",
                            "path": dir_path,
                            "fileid": dir_item.fileid or "",
                            "name": old_name,
                            "new_name": new_name,
                            "title": target.get("title") or new_name,
                        }
                    )

            message = f"识别 {len(media_files)} 个媒体文件，可改名 {len(plan_items)} 项"
            if truncated:
                message += f"；已按上限截取前 {self._rename_max_files} 个文件"
            return {
                "code": 0,
                "msg": message,
                "plan_id": uuid.uuid4().hex,
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "folder_path": folder_path,
                "scanned": len(media_files),
                "unchanged": unchanged,
                "items": plan_items,
                "errors": errors,
                "truncated": truncated,
            }
        except Exception as e:
            logger.error(f"Transfer115: 生成改名预览失败: {e}")
            return {"code": 1, "msg": str(e), "items": []}

    @staticmethod
    def __rename_plan_expired(plan: dict) -> bool:
        """限制预览计划有效期，降低远端目录变化后的误改风险。"""
        try:
            created_at = datetime.datetime.fromisoformat(str(plan.get("created_at") or ""))
            return datetime.datetime.now() - created_at > datetime.timedelta(minutes=30)
        except (TypeError, ValueError):
            return True

    @staticmethod
    def __display_value(value: Any) -> str:
        """把枚举或普通值转换为可序列化文本。"""
        return str(getattr(value, "value", value) or "")

    @staticmethod
    def __safe_name(name: Any) -> str:
        """清理115不接受的路径字符，并拒绝空名称和相对目录名称。"""
        clean = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", str(name or ""))
        clean = re.sub(r"\s+", " ", clean).strip(" .")
        return "" if clean in {"", ".", ".."} else clean[:255]

    @staticmethod
    def __split_tokens(value: Any) -> List[str]:
        """把保存的拆分字符转换为按长度优先的字面量列表。"""
        text = str(value or "")
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, list):
            tokens = [str(part) for part in parsed if str(part)]
        elif "|" in text:
            tokens = [part for part in text.split("|") if part]
        else:
            tokens = list(text)
        return list(dict.fromkeys(sorted(tokens, key=len, reverse=True)))

    @classmethod
    def __split_filename(cls, name: str, tokens: List[str], template: str,
                         keep_extension: bool) -> Tuple[List[str], str]:
        """按鼠标选中的字面量拆分文件名，并以数字占位符重新组合。"""
        suffix = PurePosixPath(name).suffix
        stem = name[:-len(suffix)] if suffix else name
        clean_tokens = list(dict.fromkeys(token for token in tokens if token))
        pattern = "|".join(re.escape(token) for token in sorted(clean_tokens, key=len, reverse=True))
        parts = [part.strip() for part in re.split(pattern, stem) if part.strip()] if pattern else [stem]

        def replace_part(match: re.Match) -> str:
            index = int(match.group(1)) - 1
            return parts[index] if 0 <= index < len(parts) else ""

        rendered = str(template or "")
        rendered = rendered.replace("{stem}", stem).replace("{name}", name).replace("{ext}", suffix)
        rendered = re.sub(r"\{(\d+)\}", replace_part, rendered)
        rendered = re.sub(r"\s+", " ", rendered).strip(" .-_")
        new_name = cls.__safe_name(rendered)
        if keep_extension and suffix and new_name and not new_name.casefold().endswith(suffix.casefold()):
            new_name = cls.__safe_name(f"{new_name}{suffix}")
        return parts, new_name

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
                                            "model": "rename_enabled",
                                            "label": "启用识别改名",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "rename_directories",
                                            "label": "同步修改媒体目录",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "rename_max_files",
                                            "label": "单次识别上限",
                                            "type": "number",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "enabled", "label": "启用插件"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "auto_organize", "label": "自动整理"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {"model": "notify_enabled", "label": "发送通知"},
                                    }
                                ],
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
                                        },
                                    }
                                ],
                            },
                        ],
                    },
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "auth_mode",
                                            "label": "提交授权方式",
                                            "items": [
                                                {"title": "共用MP 115授权", "value": "mp_oauth"},
                                                {"title": "手动填写Cookie", "value": "cookie"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSelect",
                                        "props": {
                                            "model": "transfer_type",
                                            "label": "整理方式",
                                            "items": [
                                                {"title": "移动", "value": "move"},
                                                {"title": "复制", "value": "copy"},
                                            ],
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VSwitch",
                                        "props": {
                                            "model": "cleanup_empty_folder",
                                            "label": "整理后清理空源目录",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
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
                                            "label": "115 Cookie",
                                            "type": "password",
                                            "placeholder": "仅 Cookie 提交模式需要填写",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
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
                                            "placeholder": "如 /待整理",
                                        },
                                    }
                                ],
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
                                            "placeholder": "留空则使用MoviePilot目录配置",
                                        },
                                    }
                                ],
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
                                            "placeholder": "如 /整理失败",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
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
                                            "placeholder": "5",
                                            "hint": "建议不少于5分钟",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "api_interval",
                                            "label": "API间隔(秒)",
                                            "placeholder": "1",
                                            "hint": "115接口调用前等待",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "stabilize_cycles",
                                            "label": "完成后等待轮数",
                                            "placeholder": "1",
                                            "hint": "避免文件列表未刷新",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "max_retries",
                                            "label": "整理失败重试次数",
                                            "placeholder": "3",
                                        },
                                    }
                                ],
                            },
                        ],
                    },
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
                                            "model": "max_tasks_per_poll",
                                            "label": "每轮最多处理任务",
                                            "placeholder": "20",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {
                                            "model": "history_retention_days",
                                            "label": "记录保留天数",
                                            "placeholder": "30",
                                            "hint": "0表示仅按数量保留",
                                            "persistent-hint": True,
                                        },
                                    }
                                ],
                            },
                        ],
                    },
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
                                            "placeholder": "支持磁力、ed2k、115分享链接；每行一个，保存后自动提交并清空",
                                            "rows": 5,
                                            "clearable": True,
                                        },
                                    }
                                ],
                            }
                        ],
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
                                            "type": "warning",
                                            "variant": "tonal",
                                            "text": "使用115离线下载接口存在风控风险；建议小号使用，并调大轮询间隔和API间隔。",
                                        },
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], self.__default_config()

    def get_page(self) -> List[dict]:
        return []

    def __get_legacy_page(self) -> List[dict]:
        status_section = self.__build_status_section()
        config_section = self.__build_config_section()
        browser_section = self.__build_browser_section()
        rename_section = self.__build_rename_section()
        task_section = self.__build_task_section()
        action_section = self.__build_action_section()
        return [c for c in [status_section, config_section, browser_section, rename_section, task_section, action_section] if c]

    def get_service(self) -> List[Dict[str, Any]]:
        if self._enabled and self._auto_organize and self._download_path:
            return [
                {
                    "id": "Transfer115Monitor",
                    "name": "115离线下载监控",
                    "trigger": IntervalTrigger(minutes=self._poll_interval),
                    "func": self.__check_and_organize,
                    "kwargs": {},
                }
            ]
        return []

    def stop_service(self):
        self._checking = False

    def _get_u115_oper(self):
        """获取MoviePilot内置115存储实例。"""
        try:
            from app.modules.filemanager.storages.u115 import U115Pan

            oper = U115Pan()
            if oper.check():
                return oper
        except Exception as e:
            logger.warning(f"Transfer115: 获取115存储实例失败: {e}")
        return None

    def _get_cookie_oper(self):
        """初始化Cookie客户端，仅用于提交离线任务和读取任务列表。"""
        if not self._cookie:
            return None
        try:
            from p115client import P115Client

            return P115Client(cookies=self._cookie)
        except Exception as e:
            logger.warning(f"Transfer115: 初始化Cookie客户端失败: {e}")
            return None

    def _sleep_if_needed(self):
        if self._api_interval > 0:
            time.sleep(self._api_interval)

    def _get_folder_id_by_path_cookie(self, path: str, oper) -> Optional[int]:
        try:
            parts = [p for p in self.__clean_path(path).strip("/").split("/") if p]
            current_id = 0
            for part in parts:
                self._sleep_if_needed()
                resp = oper.fs_files({"cid": current_id, "limit": 1000})
                items = resp.get("data", []) if isinstance(resp, dict) else []
                found = None
                for item in items:
                    if item.get("n") == part and item.get("fid") is None:
                        found = item.get("cid")
                        break
                if found is None:
                    logger.warning(f"Transfer115: Cookie模式未找到目录: {part}")
                    return None
                current_id = int(found)
            return current_id
        except Exception as e:
            logger.warning(f"Transfer115: Cookie模式获取目录ID失败: {e}")
            return None

    def __submit_links(self, lines: List[str]) -> dict:
        oper = self._get_cookie_oper() if self._auth_mode == "cookie" else self._get_u115_oper()
        if not oper:
            message = "115未授权或Cookie无效，无法提交链接"
            logger.warning(f"Transfer115: {message}")
            self.__upsert_task_record("离线任务提交", "提交失败")
            return {"code": 1, "msg": message, "submitted": 0}

        try:
            wp_path_id = self.__resolve_download_folder_id(oper)
            payload = {"urls": "\n".join(lines)}
            if wp_path_id is not None:
                payload["wp_path_id"] = wp_path_id

            self._sleep_if_needed()
            if self._auth_mode == "cookie":
                response = oper.offline_add_urls(payload)
                # 旧版 p115client 可能以 None 表示请求完成；只有明确的失败响应才拒绝。
                error = "" if response is None else self.__offline_response_error(response)
            else:
                # 复用MoviePilot内置U115Pan的授权、限流、Token刷新和错误处理。
                response = oper._request_api(
                    "POST",
                    "/open/offline/add_task_urls",
                    data=payload,
                )
                error = self.__offline_response_error(response)
            if error:
                raise RuntimeError(error)

            logger.info(f"Transfer115: 添加离线任务成功，共 {len(lines)} 条")
            self.__record_recent_tasks(oper)
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Organize,
                    title="115离线任务已提交",
                    text=f"已提交 {len(lines)} 条离线下载任务",
                )
            return {
                "code": 0,
                "msg": f"已提交 {len(lines)} 条离线下载任务",
                "submitted": len(lines),
                "download_path": self._download_path or "/",
            }
        except Exception as e:
            logger.error(f"Transfer115: 添加离线任务失败: {e}")
            self.__upsert_task_record("离线任务提交", "提交失败")
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Manual,
                    title="115离线任务提交失败",
                    text=str(e),
                )
            return {"code": 1, "msg": f"离线任务提交失败: {e}", "submitted": 0}

    @staticmethod
    def __offline_response_error(response: Any) -> str:
        """统一判断内置U115Pan与p115client的离线提交响应。"""
        if response is None or response is False:
            return "115接口未返回成功结果"
        if not isinstance(response, dict):
            return ""
        if response.get("state") is False or response.get("success") is False:
            return str(response.get("message") or response.get("error") or "115接口返回失败")
        code = response.get("code")
        if code not in (None, 0, "0", 20004, "20004"):
            return str(response.get("message") or response.get("error") or f"115错误码: {code}")
        return ""

    def __resolve_download_folder_id(self, oper) -> Optional[int]:
        if not self._download_path:
            return None

        if self._auth_mode == "cookie":
            return self._get_folder_id_by_path_cookie(self._download_path, oper)

        try:
            folder_item = oper.get_folder(Path(self._download_path))
            if folder_item and folder_item.fileid:
                return int(folder_item.fileid)
        except Exception as e:
            logger.warning(f"Transfer115: 无法解析下载目录ID，将使用根目录: {e}")
        return None

    def __record_recent_tasks(self, oper):
        try:
            tasks = self.__list_offline_tasks(oper)
            processed = set(self.get_data("processed_tasks") or [])
            recorded = 0
            for task in tasks:
                task_key = self.__task_key(task)
                task_name = self.__task_name(task)
                if not task_key or task_key in processed:
                    continue
                if not self.__task_in_download_path(task):
                    continue
                self.__upsert_task_record(task_name, "下载中")
                recorded += 1
            logger.info(f"Transfer115: 已记录 {recorded} 个新任务为下载中")
        except Exception as e:
            logger.warning(f"Transfer115: 提交后查询任务列表失败: {e}")

    def __check_and_organize(self, force: bool = False):
        if self._checking:
            logger.info("Transfer115: 上一轮任务检查仍在运行，跳过本轮")
            return
        if not force and (not self._enabled or not self._auto_organize):
            return

        oper = self._get_cookie_oper() if self._auth_mode == "cookie" else self._get_u115_oper()
        if not oper:
            logger.warning("Transfer115: 115未授权，跳过任务检查")
            return

        self._checking = True
        summary = {"checked": 0, "downloading": 0, "completed": 0, "organized": 0, "failed": 0, "skipped": 0}
        try:
            tasks = self.__list_offline_tasks(oper)
            if not tasks:
                self.__save_poll_summary(summary)
                return

            processed = set(self.get_data("processed_tasks") or [])
            failed_tasks: Dict[str, int] = self.get_data("failed_tasks") or {}
            done_wait: Dict[str, int] = self.__load_done_wait()
            changed = False

            for task in tasks:
                if summary["checked"] >= self._max_tasks_per_poll:
                    break

                task_key = self.__task_key(task)
                if not task_key:
                    summary["skipped"] += 1
                    continue
                if task_key in processed:
                    continue

                task_name = self.__task_name(task)
                if not self.__task_in_download_path(task):
                    summary["skipped"] += 1
                    continue

                summary["checked"] += 1
                if not self.__is_task_finished(task):
                    summary["downloading"] += 1
                    self.__upsert_task_record(task_name, "下载中")
                    continue

                summary["completed"] += 1
                retry_count = int(failed_tasks.get(task_key, 0) or 0)
                if retry_count >= self._max_retries:
                    summary["skipped"] += 1
                    continue

                wait_count = int(done_wait.get(task_key, 0) or 0)
                if wait_count < self._stabilize_cycles:
                    done_wait[task_key] = wait_count + 1
                    self.__upsert_task_record(task_name, "下载完成")
                    changed = True
                    continue

                logger.info(f"Transfer115: 开始整理任务: {task_name}")
                success = self.__organize_task(task=task, task_name=task_name, oper=oper)
                done_wait.pop(task_key, None)
                changed = True

                if success:
                    summary["organized"] += 1
                    processed.add(task_key)
                    failed_tasks.pop(task_key, None)
                    self.__upsert_task_record(task_name, "整理完成")
                else:
                    summary["failed"] += 1
                    retry_count += 1
                    failed_tasks[task_key] = retry_count
                    self.__upsert_task_record(task_name, "整理失败")
                    if retry_count >= self._max_retries:
                        logger.warning(f"Transfer115: 任务 {task_name} 已失败 {retry_count} 次，不再重试")
                        self.__move_folder_to_fail(task=task, task_name=task_name, oper=oper)
                        processed.add(task_key)
                        failed_tasks.pop(task_key, None)

            if changed:
                self.save_data("processed_tasks", list(processed)[-500:])
                self.save_data("failed_tasks", failed_tasks)
                self.save_data("download_done_tasks", done_wait)
            self.__save_poll_summary(summary)
            self.__cleanup_history()
        except Exception as e:
            logger.error(f"Transfer115: 任务检查异常: {e}")
        finally:
            self._checking = False

    def __organize_task(self, task: dict, task_name: str, oper) -> bool:
        fileitem = self.__build_task_fileitem(task=task, task_name=task_name)
        if not fileitem:
            logger.warning(f"Transfer115: 无法构造任务文件项: {task_name}")
            return False

        if not self._get_u115_oper():
            logger.warning("Transfer115: 自动整理需要MoviePilot内置115网盘授权；Cookie仅用于提交/查询离线任务")
            return False

        state, errmsg = self.__manual_transfer_fileitem(fileitem=fileitem)
        if state:
            logger.info(f"Transfer115: 整理成功: {task_name}")
            self.__cleanup_source_folder(fileitem)
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Organize,
                    title="115离线整理完成",
                    text=f"✅ {task_name}",
                )
            return True

        logger.warning(f"Transfer115: 整理失败: {task_name}，原因: {errmsg}")
        if self._notify_enabled:
            self.post_message(
                mtype=NotificationType.Manual,
                title="115离线整理失败",
                text=f"❌ {task_name}\n{errmsg}",
            )
        return False

    def __manual_transfer_fileitem(self, fileitem) -> Tuple[bool, str]:
        try:
            from app.chain.transfer import TransferChain

            transfer_kwargs = {
                "fileitem": fileitem,
                "transfer_type": self._transfer_type,
                "background": False,
                "sync_extra_files": True,
            }
            if self._library_path:
                transfer_kwargs["target_path"] = Path(self._library_path)

            try:
                return TransferChain().manual_transfer(**transfer_kwargs)
            except TypeError:
                transfer_kwargs.pop("sync_extra_files", None)
                transfer_kwargs.pop("background", None)
                return TransferChain().manual_transfer(**transfer_kwargs)
        except Exception as e:
            logger.error(f"Transfer115: 调用整理链异常: {e}")
            return False, str(e)

    def __move_folder_to_fail(self, task: dict, task_name: str, oper):
        if not self._fail_path:
            return

        try:
            if self._auth_mode == "cookie":
                folder_id = task.get("file_id") or task.get("cid") or ""
                fail_folder_id = self._get_folder_id_by_path_cookie(self._fail_path, oper)
                if not folder_id or fail_folder_id is None:
                    logger.warning(f"Transfer115: Cookie模式无法移动失败任务: {task_name}")
                    return
                self._sleep_if_needed()
                oper.fs_move([int(folder_id)], pid=int(fail_folder_id))
            else:
                task_path = self.__task_folder_path(task=task, task_name=task_name)
                task_item = oper.get_item(Path(task_path)) if task_path else None
                if not task_item:
                    logger.warning(f"Transfer115: 无法获取任务文件夹，跳过移动: {task_name}")
                    return
                self._sleep_if_needed()
                oper.move(task_item, Path(self._fail_path), task_item.name)

            logger.info(f"Transfer115: 已将失败任务 {task_name} 移至: {self._fail_path}")
            if self._notify_enabled:
                self.post_message(
                    mtype=NotificationType.Manual,
                    title="115整理失败-已归档",
                    text=f"❌ {task_name}\n文件夹已移至失败目录: {self._fail_path}",
                )
        except Exception as e:
            logger.error(f"Transfer115: 移动失败目录异常 ({task_name}): {e}")

    def __cleanup_source_folder(self, fileitem):
        if not self._cleanup_empty_folder or self._transfer_type != "move":
            return
        try:
            from app.chain.storage import StorageChain

            storage_chain = StorageChain()
            self._sleep_if_needed()
            children = storage_chain.list_files(fileitem) or []
            if children:
                logger.debug(f"Transfer115: 源目录非空，跳过清理: {fileitem.path}")
                return
            storage_chain.delete_file(fileitem)
            logger.info(f"Transfer115: 已清理空源目录: {fileitem.path}")
        except Exception as e:
            logger.debug(f"Transfer115: 清理源目录跳过: {e}")

    def __list_offline_tasks(self, oper) -> List[dict]:
        if self._auth_mode == "cookie":
            self._sleep_if_needed()
            resp = oper.offline_list({"page": 1})
        else:
            self._sleep_if_needed()
            resp = oper._request_api("GET", "/open/offline/get_task_list", params={"page": 1})
        return self.__extract_tasks(resp)

    @staticmethod
    def __extract_tasks(resp: Any) -> List[dict]:
        if not resp:
            return []
        if isinstance(resp, list):
            return [item for item in resp if isinstance(item, dict)]
        if not isinstance(resp, dict):
            return []
        data = resp.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            tasks = data.get("tasks") or data.get("list") or data.get("items")
            if isinstance(tasks, list):
                return [item for item in tasks if isinstance(item, dict)]
        tasks = resp.get("tasks") or resp.get("list") or resp.get("items")
        if isinstance(tasks, list):
            return [item for item in tasks if isinstance(item, dict)]
        return []

    @staticmethod
    def __task_key(task: dict) -> str:
        return str(
            task.get("info_hash")
            or task.get("hash")
            or task.get("file_id")
            or task.get("id")
            or ""
        )

    @staticmethod
    def __task_name(task: dict) -> str:
        return str(task.get("name") or task.get("file_name") or task.get("title") or Transfer115.__task_key(task))

    @classmethod
    def __offline_task_view(cls, task: dict) -> dict:
        """把不同115客户端返回的任务结构归一化为前端展示模型。"""
        raw_status = task.get("status", task.get("state", ""))
        status_text = str(raw_status or "").strip().lower()
        if cls.__is_task_finished(task):
            status = "completed"
            status_label = "已完成"
        elif raw_status in (-1, 3, 4) or status_text in {"-1", "failed", "error", "failure"}:
            status = "failed"
            status_label = "失败"
        elif raw_status in (0, 1) or status_text in {"0", "1", "waiting", "pending", "downloading", "running"}:
            status = "downloading"
            status_label = "下载中"
        else:
            status = "unknown"
            status_label = str(raw_status or "未知")

        progress = task.get("percentDone", task.get("progress", task.get("percent", 0)))
        try:
            progress_value = float(progress or 0)
            if 0 < progress_value <= 1:
                progress_value *= 100
            progress_value = max(0, min(100, round(progress_value, 1)))
        except (TypeError, ValueError):
            progress_value = 0

        size = task.get("size") or task.get("file_size") or 0
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = 0

        return {
            "id": cls.__task_key(task),
            "name": cls.__task_name(task),
            "status": status,
            "status_label": status_label,
            "progress": progress_value,
            "size": size,
            "save_path": str(task.get("file_path") or task.get("save_path") or ""),
            "created_at": str(task.get("create_time") or task.get("created_at") or task.get("time") or ""),
            "error": str(task.get("error_msg") or task.get("message") or task.get("error") or ""),
        }

    @staticmethod
    def __is_task_finished(task: dict) -> bool:
        status = task.get("status")
        if isinstance(status, int):
            return status == 2
        status_text = str(status or task.get("state") or "").strip().lower()
        return status_text in {"2", "done", "finish", "finished", "complete", "completed", "success"}

    def __task_in_download_path(self, task: dict) -> bool:
        if not self._download_path:
            return False
        expected = self._download_path.strip("/")
        if not expected:
            return True
        task_file_path = str(task.get("file_path") or task.get("save_path") or "").strip("/")
        if not task_file_path:
            return True
        return task_file_path == expected or task_file_path.startswith(f"{expected}/")

    def __task_folder_path(self, task: dict, task_name: str) -> str:
        task_file_path = str(task.get("file_path") or task.get("save_path") or "").strip("/")
        if task_file_path:
            return f"/{task_file_path}"
        return f"{self._download_path.rstrip('/')}/{task_name}"

    def __build_task_fileitem(self, task: dict, task_name: str):
        folder_path = self.__task_folder_path(task=task, task_name=task_name)
        fileid = str(task.get("file_id") or task.get("cid") or "")
        return self.__build_folder_fileitem(folder_path=folder_path, fileid=fileid)

    def __build_folder_fileitem(self, folder_path: str, fileid: str = ""):
        try:
            from app.chain.storage import StorageChain
            from app.schemas import FileItem

            path = self.__dir_path(folder_path)
            folder_name = Path(path.rstrip("/")).name or "115"
            fileitem = FileItem(
                storage="u115",
                type="dir",
                path=path,
                name=folder_name,
                fileid=str(fileid or "") or None,
            )
            if fileitem.fileid:
                return fileitem
            self._sleep_if_needed()
            found = StorageChain().get_item(fileitem)
            return found or fileitem
        except Exception as e:
            logger.warning(f"Transfer115: 构造文件夹对象失败: {e}")
            return None

    def __load_done_wait(self) -> Dict[str, int]:
        raw = self.get_data("download_done_tasks") or {}
        if isinstance(raw, dict):
            return {str(k): int(v or 0) for k, v in raw.items()}
        if isinstance(raw, list):
            return {str(k): self._stabilize_cycles for k in raw}
        return {}

    def __save_poll_summary(self, summary: Dict[str, int]):
        summary = dict(summary)
        summary["time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_data("last_poll_summary", summary)

    def __upsert_task_record(self, name: str, status: str):
        records = self.get_data("task_records") or []
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for record in records:
            if record.get("name") == name:
                record["status"] = status
                record["time"] = now
                self.save_data("task_records", records[-self._max_records :])
                return
        records.append({"name": name, "status": status, "time": now})
        self.save_data("task_records", records[-self._max_records :])

    def __cleanup_history(self):
        if self._history_retention_days <= 0:
            return
        records = self.get_data("task_records") or []
        if not records:
            return
        cutoff = datetime.datetime.now() - datetime.timedelta(days=self._history_retention_days)
        kept = []
        for record in records:
            try:
                record_time = datetime.datetime.strptime(record.get("time", ""), "%Y-%m-%d %H:%M:%S")
            except Exception:
                kept.append(record)
                continue
            if record_time >= cutoff:
                kept.append(record)
        if len(kept) != len(records):
            self.save_data("task_records", kept[-self._max_records :])

    def __build_status_section(self) -> dict:
        if not self._enabled:
            return {
                "component": "VAlert",
                "props": {"type": "info", "variant": "tonal", "text": "插件未启用"},
            }

        if self._auth_mode == "cookie":
            if not self._cookie:
                return {
                    "component": "VAlert",
                    "props": {"type": "error", "variant": "tonal", "text": "Cookie模式未填写Cookie"},
                }
            return {
                "component": "VAlert",
                "props": {
                    "type": "warning",
                    "variant": "tonal",
                    "text": "Cookie模式可提交和查询离线任务；自动整理仍需要MoviePilot内置115网盘授权。",
                },
            }

        if self._get_u115_oper():
            return {
                "component": "VAlert",
                "props": {"type": "success", "variant": "tonal", "text": "MP 115网盘已授权"},
            }
        return {
            "component": "VAlert",
            "props": {"type": "error", "variant": "tonal", "text": "115未授权，请前往 设置 -> 存储 -> 115网盘 登录"},
        }

    def __build_config_section(self) -> dict:
        summary = self.get_data("last_poll_summary") or {}
        summary_text = "暂无检查记录"
        if summary:
            summary_text = (
                f"{summary.get('time', '')}  检查 {summary.get('checked', 0)}，"
                f"下载中 {summary.get('downloading', 0)}，完成 {summary.get('completed', 0)}，"
                f"整理 {summary.get('organized', 0)}，失败 {summary.get('failed', 0)}"
            )
        return {
            "component": "VList",
            "props": {"lines": "two", "density": "compact"},
            "content": [
                {
                    "component": "VListItem",
                    "content": [
                        {"component": "VListItemTitle", "text": f"下载目录: {self._download_path or '未设置'}"},
                        {"component": "VListItemSubtitle", "text": f"媒体库: {self._library_path or '使用MP目录配置'}"},
                    ],
                },
                {
                    "component": "VListItem",
                    "content": [
                        {"component": "VListItemTitle", "text": f"失败目录: {self._fail_path or '未设置'}"},
                        {
                            "component": "VListItemSubtitle",
                            "text": f"轮询 {self._poll_interval} 分钟，API间隔 {self._api_interval} 秒，整理方式 {self._transfer_type}",
                        },
                    ],
                },
                {
                    "component": "VListItem",
                    "content": [
                        {"component": "VListItemTitle", "text": "上次检查"},
                        {"component": "VListItemSubtitle", "text": summary_text},
                    ],
                },
            ],
        }

    def __build_browser_section(self) -> Optional[dict]:
        if not self._enabled:
            return None
        if self._auth_mode == "cookie":
            return {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "density": "compact",
                    "text": "Cookie模式请在设置页手动填写目录；目录浏览使用MoviePilot内置115授权。",
                },
            }

        browse_path = self.get_data("browse_path") or "/"
        browse_path = self.__clean_path(browse_path, default="/")
        parent_path = None
        if browse_path != "/":
            parent = browse_path.rstrip("/").rsplit("/", 1)[0]
            parent_path = f"{parent}/" if parent else "/"

        dir_items = []
        dir_error = None
        try:
            from app.chain.storage import StorageChain
            from app.schemas import FileItem

            fileitem = FileItem(storage="u115", path=self.__dir_path(browse_path), type="dir")
            self._sleep_if_needed()
            items = StorageChain().list_files(fileitem) or []
            dir_items = [item for item in items if item.type == "dir"]
        except Exception as e:
            dir_error = str(e)

        nav_buttons = [
            {"component": "span", "text": f"当前路径: {browse_path}", "props": {"class": "text-body-2 mr-2"}}
        ]
        if parent_path is not None:
            nav_buttons.append(
                {
                    "component": "VBtn",
                    "props": {"size": "x-small", "variant": "tonal", "color": "secondary", "class": "mr-1"},
                    "text": "返回上级",
                    "events": {"click": {"api": "plugin/Transfer115/nav_dir", "method": "get", "params": {"path": parent_path}}},
                }
            )
        nav_buttons.append(
            {
                "component": "VBtn",
                "props": {"size": "x-small", "variant": "tonal", "color": "primary", "class": "mr-1"},
                "text": "设为下载目录",
                "events": {"click": {"api": "plugin/Transfer115/set_path", "method": "get", "params": {"field": "download_path", "path": browse_path}}},
            }
        )
        nav_buttons.append(
            {
                "component": "VBtn",
                "props": {"size": "x-small", "variant": "tonal", "color": "success", "class": "mr-1"},
                "text": "设为媒体库",
                "events": {"click": {"api": "plugin/Transfer115/set_path", "method": "get", "params": {"field": "library_path", "path": browse_path}}},
            }
        )
        nav_buttons.append(
            {
                "component": "VBtn",
                "props": {"size": "x-small", "variant": "tonal", "color": "warning"},
                "text": "设为失败目录",
                "events": {"click": {"api": "plugin/Transfer115/set_path", "method": "get", "params": {"field": "fail_path", "path": browse_path}}},
            }
        )

        content = [
            {
                "component": "VRow",
                "props": {"class": "align-center mb-1"},
                "content": [{"component": "VCol", "props": {"cols": 12}, "content": nav_buttons}],
            }
        ]
        if dir_error:
            content.append(
                {
                    "component": "VAlert",
                    "props": {"type": "warning", "variant": "tonal", "density": "compact", "text": f"列出目录失败: {dir_error}"},
                }
            )
        elif not dir_items:
            content.append({"component": "div", "text": "此目录下无子目录", "props": {"class": "text-caption text-center pa-2"}})
        else:
            rows = []
            for item in dir_items:
                rows.append(
                    {
                        "component": "VListItem",
                        "props": {"density": "compact"},
                        "content": [
                            {"component": "VListItemTitle", "props": {"class": "text-body-2"}, "text": f"📁 {item.name}"},
                            {
                                "component": "VListItemSubtitle",
                                "content": [
                                    {
                                        "component": "VBtn",
                                        "props": {"size": "x-small", "variant": "tonal", "color": "secondary", "class": "mr-1"},
                                        "text": "进入",
                                        "events": {"click": {"api": "plugin/Transfer115/nav_dir", "method": "get", "params": {"path": item.path}}},
                                    },
                                    {
                                        "component": "VBtn",
                                        "props": {"size": "x-small", "variant": "tonal", "color": "primary"},
                                        "text": "设为下载目录",
                                        "events": {"click": {"api": "plugin/Transfer115/set_path", "method": "get", "params": {"field": "download_path", "path": item.path}}},
                                    },
                                ],
                            },
                        ],
                    }
                )
            content.append({"component": "VList", "props": {"lines": "two", "density": "compact"}, "content": rows})

        return {
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mt-2"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-body-1"}, "text": "目录浏览器"},
                {"component": "VCardText", "content": content},
            ],
        }

    def __build_task_section(self) -> dict:
        records = self.get_data("task_records") or []
        if not records:
            return {"component": "div", "text": "暂无任务记录", "props": {"class": "text-center pa-4"}}

        rows = []
        for record in reversed(records[-50:]):
            status = record.get("status", "")
            if status == "整理完成":
                status_text = "✅ 整理完成"
            elif status == "整理失败":
                status_text = "❌ 整理失败"
            elif status == "下载完成":
                status_text = "📥 下载完成"
            elif status == "提交失败":
                status_text = "❌ 提交失败"
            else:
                status_text = "⏳ 下载中"
            rows.append(
                {
                    "component": "VListItem",
                    "props": {"density": "compact"},
                    "content": [
                        {"component": "VListItemTitle", "props": {"class": "text-caption text-truncate"}, "text": record.get("name", "")},
                        {"component": "VListItemSubtitle", "text": f"{record.get('time', '')}  {status_text}"},
                    ],
                }
            )
        return {"component": "VList", "props": {"lines": "two"}, "content": rows}

    def __build_rename_section(self) -> Optional[dict]:
        """展示最近一次识别改名预览，供用户确认后执行。"""
        if not self._rename_enabled:
            return None
        plan = self.get_data("rename_plan") or {}
        if not plan:
            return {
                "component": "VAlert",
                "props": {
                    "type": "info",
                    "variant": "tonal",
                    "density": "compact",
                    "text": "识别改名：点击“生成改名预览”后，这里会显示原名称与推荐名称。",
                },
            }

        preview_rows = []
        for item in (plan.get("items") or [])[:50]:
            preview_rows.append(
                {
                    "component": "VListItem",
                    "props": {"density": "compact"},
                    "content": [
                        {
                            "component": "VListItemTitle",
                            "props": {"class": "text-caption text-truncate"},
                            "text": f"{item.get('name', '')}  →  {item.get('new_name', '')}",
                        },
                        {
                            "component": "VListItemSubtitle",
                            "text": f"{item.get('type', 'file')}  {item.get('title', '')}",
                        },
                    ],
                }
            )
        if len(plan.get("items") or []) > 50:
            preview_rows.append(
                {
                    "component": "VListItem",
                    "content": [{"component": "VListItemSubtitle", "text": "仅展示前50项，执行时将处理完整预览计划。"}],
                }
            )
        errors = plan.get("errors") or []
        content = [
            {
                "component": "VAlert",
                "props": {
                    "type": "warning" if errors else "success",
                    "variant": "tonal",
                    "density": "compact",
                    "text": f"预览 {plan.get('created_at', '')}：扫描 {plan.get('scanned', 0)} 个媒体文件，待改名 {len(plan.get('items') or [])} 项，未变化 {plan.get('unchanged', 0)} 项。",
                },
            },
            {"component": "VList", "props": {"lines": "two", "density": "compact"}, "content": preview_rows},
        ]
        if errors:
            content.append(
                {
                    "component": "VAlert",
                    "props": {
                        "type": "error",
                        "variant": "outlined",
                        "density": "compact",
                        "text": f"有 {len(errors)} 项未纳入改名计划，详情请查看接口返回。",
                    },
                }
            )
        return {
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mt-2"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-body-1"}, "text": "识别改名预览"},
                {"component": "VCardText", "content": content},
            ],
        }

    def __build_action_section(self) -> dict:
        plan = self.get_data("rename_plan") or {}
        plan_id = str(plan.get("plan_id") or "")
        return {
            "component": "VRow",
            "props": {"class": "mt-2"},
            "content": [
                {
                    "component": "VCol",
                    "props": {"cols": 12, "class": "text-center"},
                    "content": [
                        {
                            "component": "VBtn",
                            "props": {"color": "primary", "variant": "tonal", "size": "small"},
                            "text": "检查任务",
                            "events": {"click": {"api": "plugin/Transfer115/refresh_tasks", "method": "get"}},
                        },
                        {
                            "component": "VBtn",
                            "props": {"color": "success", "variant": "tonal", "size": "small", "class": "ml-2"},
                            "text": "整理下载目录",
                            "events": {"click": {"api": "plugin/Transfer115/organize_all", "method": "get"}},
                        },
                        {
                            "component": "VBtn",
                            "props": {"color": "info", "variant": "tonal", "size": "small", "class": "ml-2"},
                            "text": "生成改名预览",
                            "events": {"click": {"api": "plugin/Transfer115/scan_rename", "method": "get", "params": {"folder_path": self._download_path}}},
                        },
                        {
                            "component": "VBtn",
                            "props": {"color": "warning", "variant": "tonal", "size": "small", "class": "ml-2", "disabled": not bool(plan_id)},
                            "text": "确认批量改名",
                            "events": {"click": {"api": "plugin/Transfer115/apply_rename", "method": "post", "params": {"plan_id": plan_id}}},
                        },
                        {
                            "component": "VBtn",
                            "props": {"color": "error", "variant": "tonal", "size": "small", "class": "ml-2"},
                            "text": "清空记录",
                            "events": {"click": {"api": "plugin/Transfer115/clear_logs", "method": "get"}},
                        },
                    ],
                }
            ],
        }

    def __save_config(self, link_input: str = "", onlyonce: bool = False):
        self.update_config(
            {
                "enabled": self._enabled,
                "notify_enabled": self._notify_enabled,
                "auto_organize": self._auto_organize,
                "auth_mode": self._auth_mode,
                "cookie": self._cookie,
                "download_path": self._download_path,
                "library_path": self._library_path,
                "fail_path": self._fail_path,
                "transfer_type": self._transfer_type,
                "poll_interval": self._poll_interval,
                "api_interval": self._api_interval,
                "max_retries": self._max_retries,
                "stabilize_cycles": self._stabilize_cycles,
                "max_tasks_per_poll": self._max_tasks_per_poll,
                "cleanup_empty_folder": self._cleanup_empty_folder,
                "history_retention_days": self._history_retention_days,
                "rename_enabled": self._rename_enabled,
                "rename_directories": self._rename_directories,
                "rename_max_files": self._rename_max_files,
                "split_delimiters": self._split_delimiters,
                "split_template": self._split_template,
                "split_keep_extension": self._split_keep_extension,
                "onlyonce": onlyonce,
                "link_input": link_input,
            }
        )

    @staticmethod
    def __default_config() -> Dict[str, Any]:
        return {
            "enabled": False,
            "notify_enabled": False,
            "auto_organize": True,
            "auth_mode": "mp_oauth",
            "cookie": "",
            "download_path": "",
            "library_path": "",
            "fail_path": "",
            "transfer_type": "move",
            "poll_interval": 5,
            "api_interval": 1,
            "max_retries": 3,
            "stabilize_cycles": 1,
            "max_tasks_per_poll": 20,
            "cleanup_empty_folder": True,
            "history_retention_days": 30,
            "rename_enabled": True,
            "rename_directories": True,
            "rename_max_files": 200,
            "split_delimiters": "",
            "split_template": "{1} - {2}",
            "split_keep_extension": True,
            "onlyonce": False,
            "link_input": "",
        }

    @staticmethod
    def __parse_links(link_input: str) -> List[str]:
        seen = set()
        links = []
        for line in link_input.splitlines():
            link = line.strip()
            if not link or link in seen:
                continue
            seen.add(link)
            links.append(link)
        return links

    @staticmethod
    def __safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return max(minimum, min(maximum, number))

    @staticmethod
    def __clean_path(path: str, default: str = "") -> str:
        clean = str(path or "").strip()
        if not clean:
            return default
        clean = clean.replace("\\", "/")
        if not clean.startswith("/"):
            clean = f"/{clean}"
        if clean != "/":
            clean = clean.rstrip("/")
        return clean

    @classmethod
    def __dir_path(cls, path: str) -> str:
        clean = cls.__clean_path(path, default="/")
        return clean if clean.endswith("/") else f"{clean}/"
