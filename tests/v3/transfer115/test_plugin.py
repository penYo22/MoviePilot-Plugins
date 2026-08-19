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
