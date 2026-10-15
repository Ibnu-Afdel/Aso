from __future__ import annotations

from fastogram.database import DB


async def search_posts(term: str) -> object:
    sql = f"SELECT * FROM posts WHERE title LIKE '%{term}%'"
    return await DB.select(sql)
