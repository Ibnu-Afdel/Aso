"""End-to-end tests for `response()` (T-15): `.json`, `.download`, `.file`, `.stream`, `.no_content`."""

from __future__ import annotations

import os
import tempfile

import httpx2 as httpx


async def test_json_with_status_and_headers(client: httpx.AsyncClient):
    r = await client.get("/misc/json")
    assert r.status_code == 201
    assert r.json() == {"ok": True}
    assert r.headers["x-report-id"] == "7"


async def test_no_content(client: httpx.AsyncClient):
    r = await client.get("/misc/no-content")
    assert r.status_code == 204
    assert r.content == b""


async def test_download_sends_attachment_content_disposition(client: httpx.AsyncClient):
    tf = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    try:
        tf.write(b"a,b,c")
        tf.close()
        r = await client.get("/misc/download", params={"path": tf.name, "name": "report.csv"})
        assert r.status_code == 200
        assert r.headers["content-disposition"] == 'attachment; filename="report.csv"'
        assert r.content == b"a,b,c"
    finally:
        os.unlink(tf.name)


async def test_file_sends_inline_content_disposition(client: httpx.AsyncClient):
    tf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        tf.write(b"%PDF-fake")
        tf.close()
        r = await client.get("/misc/file", params={"path": tf.name})
        assert r.status_code == 200
        assert r.content == b"%PDF-fake"
        # Starlette's FileResponse only emits Content-Disposition when a filename is given;
        # response().file() passes none, so the header may be absent -- but never "attachment".
        assert "attachment" not in r.headers.get("content-disposition", "")
    finally:
        os.unlink(tf.name)


async def test_stream_sends_the_generators_chunks(client: httpx.AsyncClient):
    r = await client.get("/misc/stream")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text == "line 0\nline 1\nline 2\n"
