import datetime
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_CANDIDATES = [
    Path(os.environ["MOVIEPILOT_BACKEND_PATH"]) if os.environ.get("MOVIEPILOT_BACKEND_PATH") else None,
    REPO_ROOT.parent / "MoviePilot",
    REPO_ROOT.parent / "moviepilot-v3",
]
BACKEND_ROOT = next(
    (path for path in BACKEND_CANDIDATES if path and (path / "app").is_dir()),
    None,
)
if not BACKEND_ROOT:
    pytest.skip("MoviePilot v3 backend is required", allow_module_level=True)

sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(REPO_ROOT / "plugins.v3"))

import transfer115
from transfer115 import Transfer115


def test_safe_name_removes_path_characters() -> None:
    """远端名称不得包含路径分隔符、控制字符或相对目录名称。"""
    clean = Transfer115._Transfer115__safe_name(' Movie:/S01*E01?.mkv\x00 ')

    assert clean == "Movie S01 E01 .mkv"
    assert Transfer115._Transfer115__safe_name("../") == ""


def test_mouse_selected_text_splits_and_rebuilds_filename() -> None:
    """鼠标拖选的文字应按字面量拆分，模板重组后自动保留扩展名。"""
    parts, new_name = Transfer115._Transfer115__split_filename(
        "Show.Name.-.S01E02.1080p.mkv",
        [".-."],
        "{2} - {1}",
        True,
    )

    assert parts == ["Show.Name", "S01E02.1080p"]
    assert new_name == "S01E02.1080p - Show.Name.mkv"


def test_split_tokens_supports_selected_pipe_text() -> None:
    """保存格式不得把用户拖选的竖线误当成内部字段分隔符。"""
    tokens = Transfer115._Transfer115__split_tokens('[" | ", "-"]')

    assert tokens == [" | ", "-"]


def test_rename_plan_expiration() -> None:
    """改名预览超过30分钟后必须失效。"""
    fresh = {
        "created_at": (datetime.datetime.now() - datetime.timedelta(minutes=29)).isoformat()
    }
    stale = {
        "created_at": (datetime.datetime.now() - datetime.timedelta(minutes=31)).isoformat()
    }

    assert not Transfer115._Transfer115__rename_plan_expired(fresh)
    assert Transfer115._Transfer115__rename_plan_expired(stale)
    assert Transfer115._Transfer115__rename_plan_expired({})


def test_apply_requires_exact_preview_id() -> None:
    """执行改名前必须携带当前预览计划ID。"""
    plugin = object.__new__(Transfer115)
    plugin._enabled = True
    plugin._rename_enabled = True
    plugin.get_data = lambda _key: {
        "plan_id": "current-plan",
        "created_at": datetime.datetime.now().isoformat(),
        "items": [],
    }

    result = plugin.api_apply_rename(payload={"plan_id": "old-plan"})

    assert result["code"] == 1
    assert "重新扫描" in result["msg"]


def test_offline_api_routes_are_registered() -> None:
    """离线工作台所需的提交和任务查询接口必须继续暴露。"""
    plugin = object.__new__(Transfer115)
    routes = {route["path"] for route in plugin.get_api()}

    assert "/submit_offline" in routes
    assert "/offline_tasks" in routes


def test_offline_response_error_accepts_mp_success_and_rejects_failure() -> None:
    """内置115 API的成功响应应通过，失败响应应给出错误信息。"""
    error = Transfer115._Transfer115__offline_response_error

    assert error({"code": 0, "state": True}) == ""
    assert error({"code": 20004, "state": True}) == ""
    assert "余额不足" in error({"code": 10001, "message": "余额不足"})
    assert error(None)


def test_offline_task_view_normalizes_status_and_progress() -> None:
    """不同115任务字段应统一为工作台可直接展示的状态模型。"""
    view = Transfer115._Transfer115__offline_task_view

    downloading = view({"id": "a", "name": "Movie", "status": 1, "percent": 0.25, "size": "1024"})
    completed = view({"id": "b", "title": "Done", "status": 2})
    failed = view({"id": "c", "name": "Bad", "status": "failed", "error_msg": "链接失效"})

    assert downloading["status"] == "downloading"
    assert downloading["progress"] == 25
    assert downloading["size"] == 1024
    assert completed["status"] == "completed"
    assert failed["status"] == "failed"
    assert failed["error"] == "链接失效"


def test_renamed_file_tmdb_result_distinguishes_tv_and_movie(monkeypatch) -> None:
    """改名后的文件名应通过MoviePilot识别链返回电影或电视剧类型。"""
    from app.schemas.types import MediaSource, MediaType

    recognized = SimpleNamespace(
        type=MediaType.TV,
        title="Example Show",
        title_year="Example Show (2026)",
        tmdb_id=123,
        media_source=MediaSource.TMDB,
        media_id="123",
    )

    class FakeMediaChain:
        def recognize_by_path(self, path, media_source=None, obtain_images=False):
            assert path == "/Downloads/Example Show S01E01.mkv"
            assert media_source == MediaSource.TMDB
            assert obtain_images is False
            return SimpleNamespace(
                meta_info=SimpleNamespace(begin_season=1, episode_list=[3]),
                media_info=recognized,
            )

    import app.chain.media as media_module

    monkeypatch.setattr(media_module, "MediaChain", FakeMediaChain)

    plugin = object.__new__(Transfer115)
    result = plugin._Transfer115__recognize_renamed_file(
        "/Downloads/raw.mkv",
        "Example Show S01E01.mkv",
    )

    assert result["matched"] is True
    assert result["type"] == "tv"
    assert result["type_label"] == "电视剧"
    assert result["season"] == 1
    assert result["episodes"] == [3]
    assert result["episode_label"] == "第 1 季 · 第 3 集"
    assert result["tmdb_id"] == "123"
    assert result["path"] == "/Downloads/Example Show S01E01.mkv"


def test_renamed_file_tmdb_miss_does_not_raise(monkeypatch) -> None:
    """TMDB未命中时应返回未命中结果，不能影响已经完成的改名。"""
    class FakeMediaChain:
        def recognize_by_path(self, **_kwargs):
            return SimpleNamespace(
                meta_info=SimpleNamespace(begin_season=1, episode_list=[1]),
                media_info=None,
            )

    import app.chain.media as media_module

    monkeypatch.setattr(media_module, "MediaChain", FakeMediaChain)

    plugin = object.__new__(Transfer115)
    result = plugin._Transfer115__recognize_renamed_file("/Downloads/raw.mkv", "unknown.mkv")

    assert result["matched"] is False
    assert result["type_label"] == "未命中"
    assert result["error"] == ""


def test_preview_custom_rename_returns_native_recognition(monkeypatch) -> None:
    """测试改名时应直接返回MoviePilot内置识别结果。"""
    from app.schemas.types import MediaSource, MediaType

    class FakeStorageChain:
        @staticmethod
        def get_item(_item):
            return SimpleNamespace(fileid="11")

    recognized = SimpleNamespace(
        type=MediaType.TV,
        title="Example Show",
        title_year="Example Show (2026)",
        tmdb_id=123,
        media_source=MediaSource.TMDB,
        media_id="123",
    )

    class FakeMediaChain:
        def recognize_by_path(self, path, media_source=None, obtain_images=False):
            assert path == "/Downloads/Example Show S01E03.mkv"
            return SimpleNamespace(
                meta_info=SimpleNamespace(begin_season=1, episode_list=[3]),
                media_info=recognized,
            )

    import app.chain.media as media_module
    import app.chain.storage as storage_module

    monkeypatch.setattr(media_module, "MediaChain", FakeMediaChain)
    monkeypatch.setattr(storage_module, "StorageChain", FakeStorageChain)

    plugin = object.__new__(Transfer115)
    plugin._enabled = True
    plugin._rename_enabled = True
    plugin._rename_max_files = 20
    plugin._split_template = "{1}"
    plugin._split_keep_extension = True
    plugin.save_data = lambda _key, _value: None
    result = plugin.api_preview_custom_rename(
        payload={
            "selected_paths": ["/Downloads/raw.Example Show.mkv"],
            "split_tokens": ["."],
            "template": "{2} S01E03",
            "keep_extension": True,
        }
    )

    assert result["code"] == 0
    assert result["recognition_results"][0]["type_label"] == "电视剧"
    assert result["recognition_results"][0]["episode_label"] == "第 1 季 · 第 3 集"
    assert result["items"][0]["recognition"]["tmdb_id"] == "123"


def test_format_episode_label_supports_single_and_multiple_episodes() -> None:
    """电视剧季集应以简洁中文格式展示，电影不显示季集。"""
    formatter = Transfer115._Transfer115__format_episode_label

    assert formatter("tv", 1, [3]) == "第 1 季 · 第 3 集"
    assert formatter("tv", 1, [3, 4, 5]) == "第 1 季 · 第 3-5 集"
    assert formatter("tv", 1, [1, 3]) == "第 1 季 · 第 1、3 集"
    assert formatter("movie", None, []) == ""


def test_build_rename_plan_uses_media_identity_and_mp_name(monkeypatch) -> None:
    """预览应保存V3媒体身份，并使用MoviePilot推荐名称。"""
    root_item = SimpleNamespace(
        type="dir",
        path="/Downloads/Show/",
        name="Show",
        fileid="10",
    )
    media_file = SimpleNamespace(
        type="file",
        path="/Downloads/Show/raw.name.S01E02.mkv",
        name="raw.name.S01E02.mkv",
        fileid="11",
    )
    recognized = SimpleNamespace(
        media_source=SimpleNamespace(value="themoviedb"),
        media_id="123",
        title="Example Show",
        title_year="Example Show (2026)",
    )

    class FakeStorageChain:
        @staticmethod
        def list_files(_root, recursion=False):
            assert recursion is True
            return [media_file]

        @staticmethod
        def get_item(_item):
            return root_item

    class FakeMediaChain:
        @staticmethod
        def recognize_media(meta=None):
            assert meta is not None
            return recognized

    class FakeTransferChain:
        @staticmethod
        def recommend_name(meta=None, mediainfo=None):
            assert meta is not None
            assert mediainfo is recognized
            return "TV/Example Show (2026)/Season 1/Example Show (2026) - S01E02.mkv"

    import app.chain.media as media_module
    import app.chain.storage as storage_module
    import app.chain.transfer as transfer_module

    monkeypatch.setattr(media_module, "MediaChain", FakeMediaChain)
    monkeypatch.setattr(storage_module, "StorageChain", FakeStorageChain)
    monkeypatch.setattr(transfer_module, "TransferChain", FakeTransferChain)
    monkeypatch.setattr(transfer115, "MetaInfoPath", lambda _path: SimpleNamespace())
    monkeypatch.setattr(transfer115.settings, "RMT_MEDIAEXT", [".mkv"])

    plugin = object.__new__(Transfer115)
    plugin._rename_directories = True
    plugin._rename_max_files = 20
    plugin._Transfer115__build_folder_fileitem = lambda folder_path, fileid="": root_item

    result = plugin._Transfer115__build_rename_plan("/Downloads")

    assert result["code"] == 0
    assert result["scanned"] == 1
    assert result["errors"] == []
    file_plan = next(item for item in result["items"] if item["type"] == "file")
    dir_plan = next(item for item in result["items"] if item["type"] == "dir")
    assert file_plan["new_name"] == "Example Show (2026) - S01E02.mkv"
    assert file_plan["media_source"] == "themoviedb"
    assert file_plan["media_id"] == "123"
    assert dir_plan["new_name"] == "Example Show (2026)"
