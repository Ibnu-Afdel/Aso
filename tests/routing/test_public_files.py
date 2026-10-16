"""`public/` files are served at the site root, after routes (T-07)."""

from __future__ import annotations

import httpx2 as httpx
from starlette.responses import PlainTextResponse

from aso.routing.static import PublicFilesFirst


async def _fallback(scope, receive, send):
    await PlainTextResponse("fallback 404", status_code=404)(scope, receive, send)


async def test_public_file_is_served_and_unknown_path_falls_through(tmp_path):
    (tmp_path / "build" / "assets").mkdir(parents=True)
    (tmp_path / "build" / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "hot").write_text("http://localhost:5173")
    (tmp_path / ".secret").write_text("x")
    app = PublicFilesFirst(_fallback, directory=tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/build/assets/app.js")
        assert r.status_code == 200 and r.text == "console.log(1)"
        for path in ("/nope.js", "/hot", "/.secret", "/build/../hot", "/"):
            assert (await c.get(path)).text == "fallback 404", path
        assert (await c.post("/build/assets/app.js")).text == "fallback 404"
