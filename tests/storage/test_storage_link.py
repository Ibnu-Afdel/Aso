"""`link_public_storage()` (T-43 "storage:link"): a relative symlink `public/storage` ->
the `public` disk's root."""

from __future__ import annotations

import os

from fastogram.config import set_config
from fastogram.foundation import paths
from fastogram.storage import link_public_storage


def test_creates_a_relative_symlink_to_the_public_disk(tmp_path):
    previous_base = paths._base  # noqa: SLF001 -- restore the module-global base path after the test
    try:
        paths.set_base_path(tmp_path)
        set_config("filesystems", {})

        link = link_public_storage()

        assert link == tmp_path / "public" / "storage"
        assert link.is_symlink()
        target = os.readlink(link)
        assert not os.path.isabs(target)
        assert link.resolve() == (tmp_path / "storage" / "app" / "public").resolve()
    finally:
        paths._base = previous_base  # noqa: SLF001
        set_config("filesystems", {})


def test_relinking_replaces_an_existing_symlink(tmp_path):
    previous_base = paths._base  # noqa: SLF001
    try:
        paths.set_base_path(tmp_path)
        set_config("filesystems", {})

        link_public_storage()
        link = link_public_storage()  # must not raise on a second call

        assert link.is_symlink()
    finally:
        paths._base = previous_base  # noqa: SLF001
        set_config("filesystems", {})


def test_refuses_to_replace_a_real_directory(tmp_path):
    previous_base = paths._base  # noqa: SLF001
    try:
        paths.set_base_path(tmp_path)
        set_config("filesystems", {})
        (tmp_path / "public" / "storage").mkdir(parents=True)

        try:
            link_public_storage()
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert "storage" in str(exc)
    finally:
        paths._base = previous_base  # noqa: SLF001
        set_config("filesystems", {})
