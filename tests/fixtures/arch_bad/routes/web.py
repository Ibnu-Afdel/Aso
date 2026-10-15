from __future__ import annotations

from fastogram.inertia import inertia


def render_posts() -> object:
    return inertia("posts/indx", {})
