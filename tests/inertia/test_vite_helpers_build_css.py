"""A CSS entry in build mode becomes a stylesheet link, never a module script (found by the e2e run)."""

from __future__ import annotations

import json

from aso.foundation import paths
from aso.inertia import vite as vite_mod


def test_css_entry_is_a_stylesheet(tmp_path, monkeypatch) -> None:
    (tmp_path / "public" / "build").mkdir(parents=True)
    (tmp_path / "public" / "build" / "manifest.json").write_text(json.dumps({
        "resources/css/app.css": {"file": "assets/app-1.css", "src": "resources/css/app.css", "isEntry": True},
        "resources/js/app.tsx": {"file": "assets/app-2.js", "src": "resources/js/app.tsx", "isEntry": True, "css": ["assets/app-1.css"]},
    }))
    monkeypatch.setattr(paths, "_base", tmp_path)
    html = str(vite_mod.vite("resources/css/app.css", "resources/js/app.tsx"))
    assert '<link rel="stylesheet" href="/build/assets/app-1.css">' in html
    assert html.count("app-1.css") == 1
    assert '<script type="module" src="/build/assets/app-1.css">' not in html
    assert '<script type="module" src="/build/assets/app-2.js"></script>' in html
