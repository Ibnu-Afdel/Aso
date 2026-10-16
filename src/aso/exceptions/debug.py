"""The debug error page (T-20), shown only when `APP_DEBUG=true`.

Traceback with source context, request headers (cookie and authorization values redacted),
session keys without values, the matched route and the user id. Rendering must never raise:
every section is built defensively, because this runs while handling another error.
"""

from __future__ import annotations

import html
import linecache
import traceback
from typing import Any

REDACTED_HEADERS = {"cookie", "authorization", "x-xsrf-token", "x-csrf-token", "proxy-authorization"}

_STYLE = """
body{font-family:ui-sans-serif,system-ui,sans-serif;margin:0;background:#f8fafc;color:#0f172a}
header{background:#dc2626;color:#fff;padding:24px 32px}header h1{margin:0;font-size:22px}
header p{margin:8px 0 0;font-size:15px;opacity:.95;white-space:pre-wrap}
main{padding:24px 32px}section{background:#fff;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:20px}
section h2{font-size:14px;margin:0;padding:12px 16px;border-bottom:1px solid #e2e8f0;text-transform:uppercase;letter-spacing:.04em;color:#475569}
.frame{border-bottom:1px solid #f1f5f9;padding:10px 16px}.frame .loc{font-family:ui-monospace,monospace;font-size:13px}
.app .loc{font-weight:700}.vendor{opacity:.6}
pre{margin:6px 0 0;font-size:12px;background:#0f172a;color:#e2e8f0;padding:8px;border-radius:4px;overflow:auto}
.hl{background:#7f1d1d}table{width:100%;border-collapse:collapse;font-size:13px}
td{padding:6px 16px;border-bottom:1px solid #f1f5f9;vertical-align:top;font-family:ui-monospace,monospace}
td:first-child{width:220px;color:#475569}
"""


def _safe(fn: Any, default: str = "") -> str:
    try:
        return fn()
    except Exception:  # noqa: BLE001 - the debug page must never fail
        return default


def _frames(exc: BaseException) -> str:
    parts: list[str] = []
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        vendor = "site-packages" in frame.filename or "/aso/" in frame.filename
        lines = []
        if frame.lineno:
            for n in range(max(1, frame.lineno - 4), frame.lineno + 4):
                text = linecache.getline(frame.filename, n)
                if not text and n > frame.lineno:
                    break
                cls = ' class="hl"' if n == frame.lineno else ""
                lines.append(f"<span{cls}>{n:>5}  {html.escape(text.rstrip())}</span>")
        code = f"<pre>{chr(10).join(lines)}</pre>" if lines and not vendor else ""
        parts.append(
            f'<div class="frame {"vendor" if vendor else "app"}"><div class="loc">'
            f"{html.escape(frame.filename)}:{frame.lineno} in {html.escape(frame.name)}</div>{code}</div>"
        )
    return "".join(parts)


def _table(rows: list[tuple[str, str]]) -> str:
    if not rows:
        return "<table><tr><td>(none)</td><td></td></tr></table>"
    return "<table>" + "".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>" for k, v in rows) + "</table>"


def _headers(request: Any) -> list[tuple[str, str]]:
    return [(k, "[redacted]" if k.lower() in REDACTED_HEADERS else v) for k, v in request.headers.items()]


def _context_rows() -> list[tuple[str, str]]:
    from aso import context

    ctx = context.current()
    if ctx is None:
        return []
    rows: list[tuple[str, str]] = []
    route = ctx.route
    if route is not None:
        rows.append(("route", f"{getattr(route, 'route_name', None) or ''} {getattr(route, 'path', '')}".strip()))
        rows.append(("action", repr(getattr(route, "action", ""))))
    user = ctx.user
    if user is not None and user is not context.UNRESOLVED:
        rows.append(("user id", str(getattr(user, "id", "?"))))
    if ctx.session is not None:
        keys = sorted(k for k in ctx.session.all() if not k.startswith("_"))
        rows.append(("session keys", ", ".join(keys) or "(none)"))
    request_id = (ctx.scope.get("state") or {}).get("request_id")
    if request_id:
        rows.append(("request id", str(request_id)))
    return rows


def render(request: Any, exc: BaseException) -> str:
    title = html.escape(type(exc).__qualname__)
    message = html.escape(str(exc))
    method = _safe(lambda: request.method)
    url = _safe(lambda: str(request.url))
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title><style>{_STYLE}</style></head><body>"
        f"<header><h1>{title}</h1><p>{message}</p></header><main>"
        f"<section><h2>Request</h2>{_table([('method', method), ('url', url), *_safe(_context_rows, []) ])}</section>"
        f"<section><h2>Stack trace</h2>{_safe(lambda: _frames(exc), '<pre>' + html.escape(''.join(traceback.format_exception(exc))) + '</pre>')}</section>"
        f"<section><h2>Headers</h2>{_table(_safe(lambda: _headers(request), []))}</section>"
        "</main></body></html>"
    )
