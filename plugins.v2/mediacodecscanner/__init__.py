import datetime
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.interval import IntervalTrigger

from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import NotificationType


class MediaCodecScanner(_PluginBase):
    plugin_name = "媒体编码扫描"
    plugin_desc = "扫描媒体库视频编码，收集 Chrome 可能无法直接播放的文件并通知管理员。"
    plugin_icon = "https://raw.githubusercontent.com/jxxghp/MoviePilot-Frontend/refs/heads/v2/src/assets/logo.png"
    plugin_version = "1.1"
    plugin_author = "penYo22"
    author_url = "https://github.com/penYo22"
    plugin_config_prefix = "mediacodecscanner_"
    plugin_order = 11
    auth_level = 1

    _video_exts = {
        ".mp4",
        ".m4v",
        ".mov",
        ".webm",
        ".mkv",
        ".avi",
        ".wmv",
        ".ts",
        ".m2ts",
        ".mpg",
        ".mpeg",
        ".flv",
        ".rmvb",
    }
    _chrome_containers = {"mp4", "mov", "m4v", "webm"}
    _chrome_video_codecs = {"h264", "avc1", "vp8", "vp9", "av1"}
    _chrome_audio_codecs = {"aac", "mp3", "opus", "vorbis", "flac"}
    _problem_video_codecs = {"hevc", "h265", "vc1", "mpeg2video", "mpeg4", "msmpeg4v3", "wmv3", "rv40"}
    _problem_audio_codecs = {"dts", "truehd", "eac3", "ac3", "wmapro", "wmav2"}
    _container_options = ["mp4", "mov", "m4v", "webm", "matroska", "avi", "mpegts", "mpeg", "flv"]
    _video_codec_options = [
        "h264",
        "avc1",
        "hevc",
        "h265",
        "vp8",
        "vp9",
        "av1",
        "mpeg2video",
        "mpeg4",
        "vc1",
        "wmv3",
        "msmpeg4v3",
        "rv40",
    ]
    _audio_codec_options = ["aac", "mp3", "opus", "vorbis", "flac", "ac3", "eac3", "dts", "truehd", "wmapro", "wmav2"]
    _profile_options = [
        {"title": "Chrome 默认（推荐）", "value": "chrome"},
        {"title": "严格网页播放", "value": "strict"},
        {"title": "宽松模式", "value": "relaxed"},
        {"title": "自定义规则", "value": "custom"},
    ]
    _profile_rules = {
        "chrome": {
            "containers": _chrome_containers,
            "video": _chrome_video_codecs,
            "audio": _chrome_audio_codecs,
            "blocked_video": _problem_video_codecs,
            "blocked_audio": _problem_audio_codecs,
        },
        "strict": {
            "containers": {"mp4", "webm"},
            "video": {"h264", "avc1", "vp8", "vp9", "av1"},
            "audio": {"aac", "mp3", "opus"},
            "blocked_video": _problem_video_codecs,
            "blocked_audio": _problem_audio_codecs | {"flac", "vorbis"},
        },
        "relaxed": {
            "containers": _chrome_containers | {"matroska", "mpegts"},
            "video": _chrome_video_codecs | {"hevc", "h265"},
            "audio": _chrome_audio_codecs | {"ac3", "eac3"},
            "blocked_video": _problem_video_codecs - {"hevc", "h265"},
            "blocked_audio": _problem_audio_codecs - {"ac3", "eac3"},
        },
    }

    _enabled: bool = False
    _notify_enabled: bool = True
    _only_new: bool = True
    _profile: str = "chrome"
    _extra_allowed_video_codecs: List[str] = []
    _extra_blocked_video_codecs: List[str] = []
    _scan_paths: str = ""
    _exclude_paths: str = ""
    _ffprobe_path: str = "ffprobe"
    _interval_hours: int = 24
    _timeout_seconds: int = 20
    _max_files_per_scan: int = 3000
    _min_file_mb: int = 50
    _api_interval: float = 0.0
    _report_limit: int = 30
    _history_retention_days: int = 90
    _allowed_containers: List[str] = []
    _allowed_video_codecs: List[str] = []
    _allowed_audio_codecs: List[str] = []
    _blocked_video_codecs: List[str] = []
    _blocked_audio_codecs: List[str] = []
    _onlyonce: bool = False
    _scanning: bool = False

    def init_plugin(self, config: dict = None):
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify_enabled = bool(config.get("notify_enabled", True))
        self._only_new = bool(config.get("only_new", True))
        legacy_rule_keys = {
            "allowed_containers",
            "allowed_video_codecs",
            "allowed_audio_codecs",
            "blocked_video_codecs",
            "blocked_audio_codecs",
        }
        default_profile = "custom" if "profile" not in config and legacy_rule_keys & config.keys() else "chrome"
        self._profile = str(config.get("profile") or default_profile).strip().lower()
        if self._profile not in {*self._profile_rules, "custom"}:
            self._profile = "chrome"
        self._extra_allowed_video_codecs = self.__codec_list(config.get("extra_allowed_video_codecs"), set())
        self._extra_blocked_video_codecs = self.__codec_list(config.get("extra_blocked_video_codecs"), set())
        self._scan_paths = str(config.get("scan_paths") or "").strip()
        self._exclude_paths = str(config.get("exclude_paths") or "").strip()
        self._ffprobe_path = str(config.get("ffprobe_path") or "ffprobe").strip() or "ffprobe"
        self._interval_hours = self.__safe_int(config.get("interval_hours"), 24, 1, 720)
        self._timeout_seconds = self.__safe_int(config.get("timeout_seconds"), 20, 5, 300)
        self._max_files_per_scan = self.__safe_int(config.get("max_files_per_scan"), 3000, 1, 200000)
        self._min_file_mb = self.__safe_int(config.get("min_file_mb"), 50, 0, 1048576)
        self._api_interval = self.__safe_float(config.get("api_interval"), 0.0, 0.0, 60.0)
        self._report_limit = self.__safe_int(config.get("report_limit"), 30, 1, 500)
        self._history_retention_days = self.__safe_int(config.get("history_retention_days"), 90, 0, 3650)
        self._allowed_containers = self.__codec_list(config.get("allowed_containers"), self._chrome_containers)
        self._allowed_video_codecs = self.__codec_list(config.get("allowed_video_codecs"), self._chrome_video_codecs)
        self._allowed_audio_codecs = self.__codec_list(config.get("allowed_audio_codecs"), self._chrome_audio_codecs)
        self._blocked_video_codecs = self.__codec_list(config.get("blocked_video_codecs"), self._problem_video_codecs)
        self._blocked_audio_codecs = self.__codec_list(config.get("blocked_audio_codecs"), self._problem_audio_codecs)
        self._onlyonce = bool(config.get("onlyonce", False))

        self.__cleanup_history()

        if self._onlyonce:
            self.__scan_media_library(manual=True)
            self.__save_config(onlyonce=False)

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        return []

    def get_api(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": "/scan",
                "endpoint": self.api_scan,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "立即扫描媒体编码",
            },
            {
                "path": "/clear",
                "endpoint": self.api_clear,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "清空扫描记录",
            },
            {
                "path": "/ignore",
                "endpoint": self.api_ignore,
                "methods": ["GET"],
                "auth": "bear",
                "summary": "忽略问题文件",
            },
        ]

    def api_scan(self) -> dict:
        if not self._enabled:
            return {"code": 1, "msg": "插件未启用"}
        summary = self.__scan_media_library(manual=True)
        if summary.get("error"):
            return {"code": 1, "msg": summary["error"]}
        return {"code": 0, "msg": self.__summary_text(summary)}

    def api_clear(self) -> dict:
        for key in ("last_summary", "problem_records", "seen_problem_keys", "ignored_problem_keys"):
            self.del_data(key)
        return {"code": 0, "msg": "扫描记录已清空"}

    def api_ignore(self, key: str = "") -> dict:
        key = str(key or "").strip()
        if not key:
            return {"code": 1, "msg": "缺少文件标识"}
        ignored = set(self.get_data("ignored_problem_keys") or [])
        ignored.add(key)
        self.save_data("ignored_problem_keys", sorted(ignored))
        return {"code": 0, "msg": "已忽略"}

    def get_service(self) -> List[Dict[str, Any]]:
        if not self._enabled or not self._scan_paths:
            return []
        return [
            {
                "id": "MediaCodecScanner",
                "name": "媒体编码扫描",
                "trigger": IntervalTrigger(hours=self._interval_hours),
                "func": self.__scan_media_library,
                "kwargs": {},
            }
        ]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        full_form, defaults = self.__full_form_schema()
        fields = full_form[0]["content"]
        simple_fields = [
            {
                "component": "VAlert",
                "props": {"type": "info", "variant": "tonal", "class": "mb-3"},
                "text": "首次使用只需选择扫描目录和兼容策略；其他参数保持默认即可。",
            },
            fields[0],
            {"component": "VRow", "content": [fields[3]["content"][0]]},
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
                                    "model": "profile",
                                    "label": "兼容策略",
                                    "items": self._profile_options,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 6, "md": 3},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {"model": "interval_hours", "label": "扫描间隔(小时)", "type": "number"},
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 6, "md": 3},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {"model": "min_file_mb", "label": "最小文件(MB)", "type": "number"},
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
                                "component": "VCombobox",
                                "props": {
                                    "model": "extra_allowed_video_codecs",
                                    "label": "额外允许的视频编码（可选）",
                                    "items": self._video_codec_options,
                                    "multiple": True,
                                    "chips": True,
                                    "closable-chips": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VCombobox",
                                "props": {
                                    "model": "extra_blocked_video_codecs",
                                    "label": "额外标记的视频编码（可选）",
                                    "items": self._video_codec_options,
                                    "multiple": True,
                                    "chips": True,
                                    "closable-chips": True,
                                },
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VExpansionPanels",
                "props": {"variant": "accordion", "class": "mt-2"},
                "content": [
                    {
                        "component": "VExpansionPanel",
                        "content": [
                            {"component": "VExpansionPanelTitle", "text": "高级设置与自定义规则"},
                            {
                                "component": "VExpansionPanelText",
                                "content": [
                                    {
                                        "component": "VAlert",
                                        "props": {"type": "warning", "variant": "tonal", "class": "mb-3"},
                                        "text": "仅选择“自定义规则”时，下方完整编码规则才会生效。",
                                    },
                                    fields[1],
                                    fields[2],
                                    {"component": "VRow", "content": [fields[3]["content"][1]]},
                                    {
                                        "component": "VRow",
                                        "content": [fields[4]["content"][0], fields[4]["content"][2]],
                                    },
                                    {
                                        "component": "VRow",
                                        "content": [
                                            fields[5]["content"][0],
                                            fields[5]["content"][2],
                                            fields[5]["content"][3],
                                            fields[6]["content"][0],
                                        ],
                                    },
                                ],
                            },
                        ],
                    }
                ],
            },
        ]
        return [{"component": "VForm", "content": simple_fields}], defaults

    def __full_form_schema(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VForm",
                "content": [
                    {
                        "component": "VRow",
                        "content": [
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "enabled", "label": "启用插件"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "notify_enabled", "label": "发送通知"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "only_new", "label": "仅通知新增"}}],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [{"component": "VSwitch", "props": {"model": "onlyonce", "label": "立即扫描一次"}}],
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
                                        "component": "VCombobox",
                                        "props": {
                                            "model": "allowed_containers",
                                            "label": "允许封装",
                                            "items": self._container_options,
                                            "multiple": True,
                                            "chips": True,
                                            "closable-chips": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VCombobox",
                                        "props": {
                                            "model": "allowed_video_codecs",
                                            "label": "允许视频编码",
                                            "items": self._video_codec_options,
                                            "multiple": True,
                                            "chips": True,
                                            "closable-chips": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VCombobox",
                                        "props": {
                                            "model": "allowed_audio_codecs",
                                            "label": "允许音频编码",
                                            "items": self._audio_codec_options,
                                            "multiple": True,
                                            "chips": True,
                                            "closable-chips": True,
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
                                        "component": "VCombobox",
                                        "props": {
                                            "model": "blocked_video_codecs",
                                            "label": "强制风险视频编码",
                                            "items": self._video_codec_options,
                                            "multiple": True,
                                            "chips": True,
                                            "closable-chips": True,
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 6},
                                "content": [
                                    {
                                        "component": "VCombobox",
                                        "props": {
                                            "model": "blocked_audio_codecs",
                                            "label": "强制风险音频编码",
                                            "items": self._audio_codec_options,
                                            "multiple": True,
                                            "chips": True,
                                            "closable-chips": True,
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
                                            "model": "scan_paths",
                                            "label": "扫描目录",
                                            "rows": 3,
                                            "placeholder": "/media/movies\n/media/tv",
                                        },
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12},
                                "content": [
                                    {
                                        "component": "VTextarea",
                                        "props": {
                                            "model": "exclude_paths",
                                            "label": "排除目录",
                                            "rows": 2,
                                            "placeholder": "/media/downloads\n/media/.temp",
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
                                        "component": "VTextField",
                                        "props": {"model": "ffprobe_path", "label": "ffprobe路径", "placeholder": "ffprobe"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "interval_hours", "label": "扫描间隔(小时)", "type": "number"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 4},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "timeout_seconds", "label": "单文件超时(秒)", "type": "number"},
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
                                        "props": {"model": "max_files_per_scan", "label": "单次最大文件数", "type": "number"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "min_file_mb", "label": "最小文件(MB)", "type": "number"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "api_interval", "label": "扫描间隔(秒)", "type": "number", "step": "0.1"},
                                    }
                                ],
                            },
                            {
                                "component": "VCol",
                                "props": {"cols": 12, "md": 3},
                                "content": [
                                    {
                                        "component": "VTextField",
                                        "props": {"model": "report_limit", "label": "通知条数上限", "type": "number"},
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
                                        "component": "VTextField",
                                        "props": {"model": "history_retention_days", "label": "记录保留天数", "type": "number"},
                                    }
                                ],
                            }
                        ],
                    },
                ],
            }
        ], self.__default_config()

    def get_page(self) -> List[dict]:
        summary = self.get_data("last_summary") or {}
        records = self.get_data("problem_records") or []
        return [
            self.__build_status_card(summary),
            self.__build_action_card(),
            self.__build_records_card(records),
        ]

    def stop_service(self):
        pass

    def __scan_media_library(self, manual: bool = False) -> Dict[str, Any]:
        if self._scanning:
            return {"error": "已有扫描任务正在运行"}
        self._scanning = True
        start_time = datetime.datetime.now()
        summary = {
            "time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "manual": manual,
            "scanned": 0,
            "skipped": 0,
            "problem": 0,
            "new_problem": 0,
            "error": "",
        }
        try:
            roots = self.__parse_paths(self._scan_paths)
            if not roots:
                summary["error"] = "未配置扫描目录"
                self.save_data("last_summary", summary)
                return summary

            ffprobe_error = self.__check_ffprobe()
            if ffprobe_error:
                summary["error"] = ffprobe_error
                self.save_data("last_summary", summary)
                return summary

            excludes = self.__parse_paths(self._exclude_paths)
            ignored = set(self.get_data("ignored_problem_keys") or [])
            seen = set(self.get_data("seen_problem_keys") or [])
            existing_records = self.get_data("problem_records") or []
            records_by_key = {
                str(record.get("key")): record
                for record in existing_records
                if isinstance(record, dict) and record.get("key")
            }
            notify_records: List[Dict[str, Any]] = []

            for file_path in self.__iter_video_files(roots=roots, excludes=excludes, summary=summary):
                if summary["scanned"] >= self._max_files_per_scan:
                    break
                summary["scanned"] += 1
                if self._api_interval > 0:
                    time.sleep(self._api_interval)
                probe = self.__probe_file(file_path)
                if probe.get("error"):
                    record = self.__build_error_record(file_path, probe["error"])
                else:
                    record = self.__analyze_probe(file_path, probe)
                if not record:
                    continue
                key = record["key"]
                if key in ignored:
                    continue
                summary["problem"] += 1
                is_new = key not in seen
                if is_new:
                    summary["new_problem"] += 1
                records_by_key[key] = record
                if self._notify_enabled and (is_new or not self._only_new):
                    notify_records.append(record)

            self.save_data("seen_problem_keys", sorted(set(records_by_key.keys()) | seen))
            records = sorted(records_by_key.values(), key=lambda item: item.get("updated_at", ""), reverse=True)
            self.save_data("problem_records", records[:1000])
            self.save_data("last_summary", summary)
            if notify_records:
                self.__notify_problem_records(notify_records, summary)
            logger.info(f"MediaCodecScanner: {self.__summary_text(summary)}")
            return summary
        except Exception as e:
            summary["error"] = str(e)
            self.save_data("last_summary", summary)
            logger.error(f"MediaCodecScanner: 扫描异常: {e}")
            return summary
        finally:
            self._scanning = False

    def __iter_video_files(self, roots: List[str], excludes: List[str], summary: Dict[str, Any]):
        exclude_paths = [Path(item).expanduser() for item in excludes]
        min_size = self._min_file_mb * 1024 * 1024
        for root in roots:
            root_path = Path(root).expanduser()
            if not root_path.exists():
                logger.warning(f"MediaCodecScanner: 扫描目录不存在: {root_path}")
                continue
            for dirpath, dirnames, filenames in os.walk(root_path):
                current = Path(dirpath)
                if self.__is_excluded(current, exclude_paths):
                    dirnames[:] = []
                    continue
                for filename in filenames:
                    file_path = current / filename
                    if file_path.suffix.lower() not in self._video_exts:
                        continue
                    try:
                        if min_size > 0 and file_path.stat().st_size < min_size:
                            summary["skipped"] += 1
                            continue
                    except OSError:
                        summary["skipped"] += 1
                        continue
                    yield file_path

    def __probe_file(self, file_path: Path) -> Dict[str, Any]:
        cmd = [
            self._ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(file_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"error": "ffprobe超时"}
        except FileNotFoundError:
            return {"error": f"找不到ffprobe: {self._ffprobe_path}"}
        except Exception as e:
            return {"error": str(e)}
        if proc.returncode != 0:
            return {"error": (proc.stderr or "ffprobe解析失败").strip()[:500]}
        try:
            return json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as e:
            return {"error": f"ffprobe输出不是JSON: {e}"}

    def __analyze_probe(self, file_path: Path, probe: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        streams = probe.get("streams") or []
        fmt = probe.get("format") or {}
        format_name = str(fmt.get("format_name") or file_path.suffix.lstrip(".")).lower()
        containers = {item.strip() for item in format_name.split(",") if item.strip()}
        video_streams = [item for item in streams if item.get("codec_type") == "video"]
        audio_streams = [item for item in streams if item.get("codec_type") == "audio"]
        video_codecs = [str(item.get("codec_name") or "").lower() for item in video_streams]
        audio_codecs = [str(item.get("codec_name") or "").lower() for item in audio_streams]
        reasons = []

        (
            allowed_containers,
            allowed_video_codecs,
            allowed_audio_codecs,
            blocked_video_codecs,
            blocked_audio_codecs,
        ) = self.__active_rules()

        if containers and not (containers & allowed_containers):
            reasons.append(f"封装 {format_name} 非Chrome原生友好")
        for codec in video_codecs:
            if codec in blocked_video_codecs or codec not in allowed_video_codecs:
                reasons.append(f"视频编码 {codec or 'unknown'}")
        for codec in audio_codecs:
            if codec in blocked_audio_codecs or codec not in allowed_audio_codecs:
                reasons.append(f"音频编码 {codec}")

        if not reasons:
            return None

        width, height = self.__resolution(video_streams)
        return self.__build_record(
            file_path=file_path,
            container=format_name,
            video=", ".join(video_codecs) or "unknown",
            audio=", ".join(audio_codecs) or "unknown",
            resolution=f"{width}x{height}" if width and height else "",
            reasons=reasons,
        )

    def __active_rules(self) -> Tuple[set, set, set, set, set]:
        if self._profile == "custom":
            allowed_containers = set(self._allowed_containers or self._chrome_containers)
            allowed_video = set(self._allowed_video_codecs or self._chrome_video_codecs)
            allowed_audio = set(self._allowed_audio_codecs or self._chrome_audio_codecs)
            blocked_video = set(self._blocked_video_codecs or self._problem_video_codecs)
            blocked_audio = set(self._blocked_audio_codecs or self._problem_audio_codecs)
        else:
            rules = self._profile_rules.get(self._profile, self._profile_rules["chrome"])
            allowed_containers = set(rules["containers"])
            allowed_video = set(rules["video"])
            allowed_audio = set(rules["audio"])
            blocked_video = set(rules["blocked_video"])
            blocked_audio = set(rules["blocked_audio"])

        for codec in self._extra_allowed_video_codecs:
            allowed_video.add(codec)
            blocked_video.discard(codec)
        for codec in self._extra_blocked_video_codecs:
            blocked_video.add(codec)
            allowed_video.discard(codec)
        return allowed_containers, allowed_video, allowed_audio, blocked_video, blocked_audio

    def __build_error_record(self, file_path: Path, error: str) -> Dict[str, Any]:
        return self.__build_record(
            file_path=file_path,
            container=file_path.suffix.lstrip(".").lower(),
            video="unknown",
            audio="unknown",
            resolution="",
            reasons=[f"探测失败: {error}"],
        )

    def __build_record(
        self,
        file_path: Path,
        container: str,
        video: str,
        audio: str,
        resolution: str,
        reasons: List[str],
    ) -> Dict[str, Any]:
        try:
            stat = file_path.stat()
            size_mb = round(stat.st_size / 1024 / 1024, 1)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            size_mb = 0
            mtime = ""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path_text = str(file_path)
        return {
            "key": self.__file_key(path_text),
            "name": file_path.stem,
            "path": path_text,
            "container": container,
            "video": video,
            "audio": audio,
            "resolution": resolution,
            "size_mb": size_mb,
            "mtime": mtime,
            "reason": "；".join(dict.fromkeys(reasons)),
            "updated_at": now,
        }

    def __notify_problem_records(self, records: List[Dict[str, Any]], summary: Dict[str, Any]):
        shown = records[: self._report_limit]
        lines = [
            f"本次扫描发现 {summary.get('new_problem', 0)} 个新增问题文件，累计问题 {summary.get('problem', 0)} 个。"
        ]
        for idx, record in enumerate(shown, 1):
            lines.append(
                f"{idx}. {record.get('name')}\n"
                f"   {record.get('container')} | {record.get('video')} | {record.get('audio')}\n"
                f"   {record.get('reason')}\n"
                f"   {record.get('path')}"
            )
        if len(records) > len(shown):
            lines.append(f"还有 {len(records) - len(shown)} 个文件未在通知中展示，请到插件详情页查看。")
        self.post_message(
            mtype=NotificationType.Manual,
            title="媒体编码兼容性提醒",
            text="\n\n".join(lines),
        )

    def __build_status_card(self, summary: Dict[str, Any]) -> dict:
        if summary.get("error"):
            alert_type = "error"
            text = summary["error"]
        elif summary:
            alert_type = "success"
            text = self.__summary_text(summary)
        else:
            alert_type = "info"
            text = "暂无扫描记录"
        return {
            "component": "VAlert",
            "props": {"type": alert_type, "variant": "tonal", "text": text},
        }

    @staticmethod
    def __build_action_card() -> dict:
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
                            "text": "立即扫描",
                            "events": {"click": {"api": "plugin/MediaCodecScanner/scan", "method": "get"}},
                        },
                        {
                            "component": "VBtn",
                            "props": {"color": "error", "variant": "tonal", "size": "small", "class": "ml-2"},
                            "text": "清空记录",
                            "events": {"click": {"api": "plugin/MediaCodecScanner/clear", "method": "get"}},
                        },
                    ],
                }
            ],
        }

    def __build_records_card(self, records: List[Dict[str, Any]]) -> dict:
        if not records:
            body = [{"component": "div", "text": "暂无问题记录", "props": {"class": "text-center pa-4"}}]
        else:
            rows = []
            for record in records[:100]:
                subtitle = (
                    f"{record.get('container')} | {record.get('video')} | {record.get('audio')} "
                    f"{record.get('resolution') or ''} | {record.get('size_mb')}MB"
                )
                rows.append(
                    {
                        "component": "VListItem",
                        "props": {"density": "compact"},
                        "content": [
                            {"component": "VListItemTitle", "props": {"class": "text-caption text-truncate"}, "text": record.get("name", "")},
                            {"component": "VListItemSubtitle", "text": subtitle},
                            {"component": "VListItemSubtitle", "props": {"class": "text-error"}, "text": record.get("reason", "")},
                            {"component": "VListItemSubtitle", "props": {"class": "text-truncate"}, "text": record.get("path", "")},
                        ],
                    }
                )
            body = [{"component": "VList", "props": {"lines": "three", "density": "compact"}, "content": rows}]
        return {
            "component": "VCard",
            "props": {"variant": "outlined", "class": "mt-2"},
            "content": [
                {"component": "VCardTitle", "props": {"class": "text-body-1"}, "text": "问题文件"},
                {"component": "VCardText", "content": body},
            ],
        }

    def __save_config(self, onlyonce: bool = False):
        self.update_config(
            {
                "enabled": self._enabled,
                "notify_enabled": self._notify_enabled,
                "only_new": self._only_new,
                "profile": self._profile,
                "extra_allowed_video_codecs": self._extra_allowed_video_codecs,
                "extra_blocked_video_codecs": self._extra_blocked_video_codecs,
                "scan_paths": self._scan_paths,
                "exclude_paths": self._exclude_paths,
                "ffprobe_path": self._ffprobe_path,
                "interval_hours": self._interval_hours,
                "timeout_seconds": self._timeout_seconds,
                "max_files_per_scan": self._max_files_per_scan,
                "min_file_mb": self._min_file_mb,
                "api_interval": self._api_interval,
                "report_limit": self._report_limit,
                "history_retention_days": self._history_retention_days,
                "allowed_containers": self._allowed_containers,
                "allowed_video_codecs": self._allowed_video_codecs,
                "allowed_audio_codecs": self._allowed_audio_codecs,
                "blocked_video_codecs": self._blocked_video_codecs,
                "blocked_audio_codecs": self._blocked_audio_codecs,
                "onlyonce": onlyonce,
            }
        )

    @staticmethod
    def __default_config() -> Dict[str, Any]:
        return {
            "enabled": False,
            "notify_enabled": True,
            "only_new": True,
            "profile": "chrome",
            "extra_allowed_video_codecs": [],
            "extra_blocked_video_codecs": [],
            "scan_paths": "",
            "exclude_paths": "",
            "ffprobe_path": "ffprobe",
            "interval_hours": 24,
            "timeout_seconds": 20,
            "max_files_per_scan": 3000,
            "min_file_mb": 50,
            "api_interval": 0,
            "report_limit": 30,
            "history_retention_days": 90,
            "allowed_containers": sorted(MediaCodecScanner._chrome_containers),
            "allowed_video_codecs": sorted(MediaCodecScanner._chrome_video_codecs),
            "allowed_audio_codecs": sorted(MediaCodecScanner._chrome_audio_codecs),
            "blocked_video_codecs": sorted(MediaCodecScanner._problem_video_codecs),
            "blocked_audio_codecs": sorted(MediaCodecScanner._problem_audio_codecs),
            "onlyonce": False,
        }

    def __cleanup_history(self):
        if self._history_retention_days <= 0:
            return
        records = self.get_data("problem_records") or []
        if not records:
            return
        cutoff = datetime.datetime.now() - datetime.timedelta(days=self._history_retention_days)
        kept = []
        for record in records:
            try:
                updated_at = datetime.datetime.strptime(record.get("updated_at", ""), "%Y-%m-%d %H:%M:%S")
            except Exception:
                kept.append(record)
                continue
            if updated_at >= cutoff:
                kept.append(record)
        if len(kept) != len(records):
            self.save_data("problem_records", kept[-1000:])
            self.save_data("seen_problem_keys", sorted({item.get("key") for item in kept if item.get("key")}))

    def __check_ffprobe(self) -> str:
        try:
            proc = subprocess.run(
                [self._ffprobe_path, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except FileNotFoundError:
            return f"找不到ffprobe: {self._ffprobe_path}"
        except Exception as e:
            return f"ffprobe不可用: {e}"
        if proc.returncode != 0:
            return (proc.stderr or "ffprobe不可用").strip()[:500]
        return ""

    @staticmethod
    def __parse_paths(value: str) -> List[str]:
        paths = []
        seen = set()
        for line in str(value or "").replace(";", "\n").splitlines():
            item = line.strip()
            if not item or item.startswith("#") or item in seen:
                continue
            seen.add(item)
            paths.append(item)
        return paths

    @staticmethod
    def __codec_list(value: Any, default: set) -> List[str]:
        if value is None or value == "":
            return sorted(default)
        if isinstance(value, str):
            raw_items = value.replace(";", ",").replace("\n", ",").split(",")
        elif isinstance(value, (list, tuple, set)):
            raw_items = list(value)
        else:
            raw_items = [value]

        items = []
        seen = set()
        for item in raw_items:
            codec = str(item or "").strip().lower()
            if not codec or codec in seen:
                continue
            seen.add(codec)
            items.append(codec)
        return items

    @staticmethod
    def __is_excluded(path: Path, excludes: List[Path]) -> bool:
        if not excludes:
            return False
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        for exclude in excludes:
            try:
                exclude_resolved = exclude.resolve()
            except OSError:
                exclude_resolved = exclude
            if resolved == exclude_resolved or exclude_resolved in resolved.parents:
                return True
        return False

    @staticmethod
    def __resolution(video_streams: List[Dict[str, Any]]) -> Tuple[int, int]:
        for stream in video_streams:
            width = stream.get("width")
            height = stream.get("height")
            if width and height:
                return int(width), int(height)
        return 0, 0

    @staticmethod
    def __file_key(path_text: str) -> str:
        return hashlib.sha1(path_text.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def __summary_text(summary: Dict[str, Any]) -> str:
        return (
            f"{summary.get('time', '')} 扫描 {summary.get('scanned', 0)} 个，"
            f"跳过 {summary.get('skipped', 0)} 个，问题 {summary.get('problem', 0)} 个，"
            f"新增 {summary.get('new_problem', 0)} 个"
        )

    @staticmethod
    def __safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        return max(minimum, min(maximum, number))

    @staticmethod
    def __safe_float(value: Any, default: float, minimum: float, maximum: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return max(minimum, min(maximum, number))
