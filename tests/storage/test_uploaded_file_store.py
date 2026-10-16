"""`UploadedFile.store()` / `.store_as()` wired to `aso.storage` (T-43)."""

from __future__ import annotations

import re

import pytest

from aso.config import set_config
from aso.storage import storage
from aso.validation.uploaded_file import UploadedFile


@pytest.fixture(autouse=True)
def _default_filesystems_config():
    set_config("filesystems", {})


async def test_store_generates_a_40_character_name_with_the_original_extension():
    storage.fake("public")
    f = UploadedFile.fake().image("avatar.jpg", 20, 20)
    path = await f.store("avatars", disk="public")

    assert path.startswith("avatars/")
    stem, _, ext = path.removeprefix("avatars/").rpartition(".")
    assert ext == "jpg"
    assert len(stem) == 40
    assert re.fullmatch(r"[A-Za-z0-9]{40}", stem)


async def test_store_two_files_get_different_generated_names():
    storage.fake("public")
    f = UploadedFile.fake().create("doc.txt", size_kb=1)
    path_a = await f.store("docs", disk="public")
    path_b = await f.store("docs", disk="public")
    assert path_a != path_b


async def test_store_persists_the_file_so_it_can_be_read_back():
    storage.fake("public")
    f = UploadedFile.fake().create("report.txt", size_kb=1)
    path = await f.store("reports", disk="public")
    assert await storage("public").exists(path)
    assert await storage("public").get(path) == b"0" * 1024


async def test_store_as_uses_the_given_name():
    storage.fake("local")
    f = UploadedFile.fake().create("whatever.bin")
    path = await f.store_as("uploads", "fixed-name.bin", disk="local")
    assert path == "uploads/fixed-name.bin"
    assert await storage("local").exists(path)


async def test_store_defaults_to_the_default_disk_when_disk_is_none():
    storage.fake("local")
    f = UploadedFile.fake().create("x.txt")
    path = await f.store("x")
    assert await storage("local").exists(path)
