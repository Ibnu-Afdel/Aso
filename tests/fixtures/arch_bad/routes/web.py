from __future__ import annotations

from aso.inertia import inertia


def render_posts() -> object:
    return inertia("posts/indx", {})
