"""T-07 Vite helpers: dev mode (`public/hot`) and production (manifest). Pure unit tests."""

from __future__ import annotations

import json

import pytest

from fastogram.foundation import paths
from fastogram.inertia import vite as vite_module
from fastogram.inertia.vite import (
    ViteManifestNotFound,
    inertia_head,
    manifest_hash,
    vite,
    vite_asset,
    vite_react_refresh,
)


@pytest.fixture(autouse=True)
def _project(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "_base", tmp_path)
    vite_module._manifest_cache.clear()
    yield
    vite_module._manifest_cache.clear()


def _write_manifest(tmp_path, data: dict) -> None:
    build_dir = tmp_path / "public" / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "manifest.json").write_text(json.dumps(data))


# -- dev mode --------------------------------------------------------------------------------


def test_dev_mode_emits_vite_client_and_entry_tags(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "hot").write_text("http://localhost:5173")

    html = str(vite("resources/js/app.tsx"))
    assert '<script type="module" src="http://localhost:5173/@vite/client"></script>' in html
    assert '<script type="module" src="http://localhost:5173/resources/js/app.tsx"></script>' in html


def test_dev_mode_emits_a_stylesheet_link_for_css_entries(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "hot").write_text("http://localhost:5173")

    html = str(vite("resources/css/app.css"))
    assert '<link rel="stylesheet" href="http://localhost:5173/resources/css/app.css">' in html


def test_dev_mode_vite_react_refresh_prints_the_preamble(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "hot").write_text("http://localhost:5173")

    html = str(vite_react_refresh())
    assert "@react-refresh" in html
    assert "$RefreshReg$" in html


def test_dev_mode_asset_version_is_empty(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "hot").write_text("http://localhost:5173")
    assert manifest_hash() == ""


# -- production mode --------------------------------------------------------------------------


def test_production_mode_reads_the_manifest_and_emits_hashed_tags(tmp_path):
    _write_manifest(
        tmp_path,
        {
            "resources/js/app.tsx": {"file": "assets/app-abc123.js", "css": ["assets/app-abc123.css"]},
        },
    )
    html = str(vite("resources/js/app.tsx"))
    assert '<link rel="stylesheet" href="/build/assets/app-abc123.css">' in html
    assert '<script type="module" src="/build/assets/app-abc123.js"></script>' in html


def test_production_mode_walks_imports_for_modulepreload_and_css(tmp_path):
    _write_manifest(
        tmp_path,
        {
            "resources/js/app.tsx": {
                "file": "assets/app.js",
                "imports": ["_shared.js"],
            },
            "_shared.js": {"file": "assets/shared.js", "css": ["assets/shared.css"]},
        },
    )
    html = str(vite("resources/js/app.tsx"))
    assert '<link rel="modulepreload" href="/build/assets/shared.js">' in html
    assert '<link rel="stylesheet" href="/build/assets/shared.css">' in html


def test_production_mode_missing_entry_raises(tmp_path):
    _write_manifest(tmp_path, {})
    with pytest.raises(ViteManifestNotFound):
        vite("resources/js/app.tsx")


def test_production_mode_missing_page_entry_is_skipped_silently(tmp_path):
    _write_manifest(tmp_path, {})
    html = str(vite("resources/js/pages/posts/index.tsx"))
    assert html == ""


def test_production_mode_vite_react_refresh_is_empty(tmp_path):
    _write_manifest(tmp_path, {})
    assert str(vite_react_refresh()) == ""


def test_production_mode_asset_version_is_the_manifest_md5(tmp_path):
    _write_manifest(tmp_path, {"a": {"file": "a.js"}})
    first = manifest_hash()
    assert first and len(first) == 32

    # re-reading an unchanged manifest returns the cached digest
    assert manifest_hash() == first

    # a changed manifest (and therefore a changed mtime) changes the digest
    _write_manifest(tmp_path, {"a": {"file": "a.js"}, "b": {"file": "b.js"}})
    (tmp_path / "public" / "build" / "manifest.json").touch()
    assert manifest_hash() != first


def test_no_manifest_and_no_hot_file_is_empty(tmp_path):
    assert str(vite("resources/js/app.tsx")) == ""
    assert manifest_hash() == ""


def test_vite_asset_resolves_a_single_file(tmp_path):
    _write_manifest(tmp_path, {"resources/images/logo.png": {"file": "assets/logo-xyz.png"}})
    assert vite_asset("resources/images/logo.png") == "/build/assets/logo-xyz.png"


def test_vite_asset_missing_raises(tmp_path):
    _write_manifest(tmp_path, {})
    with pytest.raises(ViteManifestNotFound):
        vite_asset("resources/images/logo.png")


def test_inertia_head_prints_the_fallback():
    assert str(inertia_head("<title>Hi</title>")) == "<title>Hi</title>"
