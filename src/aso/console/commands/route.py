"""`route:list` (T-10, T-50)."""

from __future__ import annotations

import json

from aso.console.command import Command
from aso.console.registry import register


class RouteListCommand(Command):
    signature = (
        "route:list {--method= : Filter the routes by method} {--name= : Filter the routes by name} "
        "{--path= : Filter the routes by path} {--json : Output the routes as JSON}"
    )
    description = "List all registered routes"

    async def handle(self) -> int:
        from aso.routing import route_list

        rows = route_list()
        method = (self.option("method") or "").upper()
        name = self.option("name") or ""
        path = self.option("path") or ""
        if method:
            rows = [r for r in rows if method in r["method"].split("|")]
        if name:
            rows = [r for r in rows if name in r["name"]]
        if path:
            rows = [r for r in rows if path in r["uri"]]

        if self.option("json"):
            self.line(json.dumps(rows))
            return 0

        self.table(
            ["Method", "URI", "Name", "Action", "Middleware"],
            [[r["method"], r["uri"], r["name"], r["action"], ", ".join(r["middleware"])] for r in rows],
        )
        return 0


def register_all() -> None:
    register(RouteListCommand, source="framework")
