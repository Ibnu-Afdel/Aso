"""`storage(disk)` unit tests (T-43): `local`/`public` defaults, put/get/exists/delete/url,
path-traversal rejection, `storage.fake()`."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastogram.config import set_config
from fastogram.storage import storage
from fastogram.storage.manager import Disk, _disk_spec


def test_local_disk_defaults_when_config_filesystems_is_missing():
    set_config("filesystems", {})
    spec = _disk_spec("local")
    assert spec["driver"] == "local"
    assert spec["root"].endswith("storage/app")


def test_public_disk_default_has_a_url_under_app_url():
    set_config("filesystems", {})
    spec = _disk_spec("public")
    assert spec["root"].endswith("storage/app/public")
    assert spec["url"].endswith("/storage")


def test_unconfigured_disk_name_raises_a_clear_error():
    set_config("filesystems", {})
    try:
        _disk_spec("s3")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "s3" in str(exc)


def test_explicit_disk_config_overrides_the_built_in_default(tmp_path):
    set_config("filesystems", {"disks": {"local": {"driver": "local", "root": str(tmp_path)}}})
    try:
        disk = storage("local")
        assert disk.root == tmp_path
    finally:
        set_config("filesystems", {})


async def test_put_get_exists_delete_round_trip(tmp_path):
    disk = Disk("local", tmp_path, None)
    await disk.put("a/b.txt", b"hello")
    assert await disk.exists("a/b.txt") is True
    assert await disk.get("a/b.txt") == b"hello"
    assert await disk.delete("a/b.txt") is True
    assert await disk.exists("a/b.txt") is False
    assert await disk.delete("a/b.txt") is False


async def test_put_accepts_str_and_stores_it_as_bytes(tmp_path):
    disk = Disk("local", tmp_path, None)
    await disk.put("note.txt", "hello world")
    assert await disk.get("note.txt") == b"hello world"


async def test_put_creates_intermediate_directories(tmp_path):
    disk = Disk("local", tmp_path, None)
    await disk.put("deep/nested/dir/file.txt", b"x")
    assert (tmp_path / "deep" / "nested" / "dir" / "file.txt").exists()


def test_url_joins_the_configured_prefix():
    disk = Disk("public", Path("/irrelevant"), "http://localhost:8000/storage")
    assert disk.url("avatars/a.jpg") == "http://localhost:8000/storage/avatars/a.jpg"


def test_url_raises_when_the_disk_has_no_url_configured():
    disk = Disk("local", Path("/irrelevant"), None)
    with pytest.raises(RuntimeError):
        disk.url("x.txt")


@pytest.mark.parametrize("bad_path", ["../escape.txt", "/etc/passwd", "a/../../escape.txt"])
async def test_path_traversal_and_absolute_paths_are_rejected(tmp_path, bad_path):
    disk = Disk("local", tmp_path, None)
    with pytest.raises(ValueError):
        await disk.put(bad_path, b"x")
    with pytest.raises(ValueError):
        await disk.get(bad_path)


async def test_storage_fake_swaps_the_disk_root_to_an_empty_temp_dir():
    tmp_dir = storage.fake("local")
    assert tmp_dir.exists()
    assert not any(tmp_dir.iterdir())
    disk = storage("local")
    assert disk.root == tmp_dir
    await disk.put("x.txt", b"y")
    assert await storage("local").exists("x.txt")


def test_reset_fakes_restores_the_real_disk_root():
    real_disk_before = storage("local")
    storage.fake("local")
    assert storage("local").root != real_disk_before.root
    storage.reset_fakes()
    assert storage("local").root == real_disk_before.root
