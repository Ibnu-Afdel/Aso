"""T-34 Pagination: LengthAwarePaginator/SimplePaginator/CursorPaginator."""

from __future__ import annotations

from sqlalchemy import String

from fastogram.database import Mapped, Model, mapped_column


def _post_model():
    class Post(Model):
        title: Mapped[str] = mapped_column(String(50))

    return Post


async def _make_posts(Post, n: int) -> None:
    for i in range(n):
        await Post.create(title=f"post-{i:02d}")


# ---------------------------------------------------------------- LengthAwarePaginator


async def test_paginate_default_shape_and_keys(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 50)
    request_context("/posts", {"page": "2"})

    page = await Post.order_by(Post.id).paginate(15)
    data = page.to_dict()

    assert set(data.keys()) == {
        "current_page",
        "data",
        "first_page_url",
        "from",
        "last_page",
        "last_page_url",
        "links",
        "next_page_url",
        "path",
        "per_page",
        "prev_page_url",
        "to",
        "total",
    }
    assert data["current_page"] == 2
    assert data["per_page"] == 15
    assert data["total"] == 50
    assert data["last_page"] == 4
    assert data["from"] == 16
    assert data["to"] == 30
    assert len(data["data"]) == 15
    assert data["data"][0]["title"] == "post-15"


async def test_paginate_page_from_query_string(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 20)
    request_context("/posts", {"page": "3"})
    page = await Post.order_by(Post.id).paginate(5)
    assert page.current_page == 3
    assert [p.title for p in page] == ["post-10", "post-11", "post-12", "post-13", "post-14"]


async def test_paginate_invalid_or_missing_page_defaults_to_1(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 10)
    request_context("/posts", {"page": "banana"})
    page = await Post.order_by(Post.id).paginate(5)
    assert page.current_page == 1

    request_context("/posts", {"page": "-3"})
    page2 = await Post.order_by(Post.id).paginate(5)
    assert page2.current_page == 1

    request_context("/posts", {})
    page3 = await Post.order_by(Post.id).paginate(5)
    assert page3.current_page == 1


async def test_paginate_explicit_page_argument_overrides_request(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 10)
    request_context("/posts", {"page": "1"})
    page = await Post.order_by(Post.id).paginate(5, page=2)
    assert page.current_page == 2


async def test_paginate_with_several_named_paginators(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 10)
    request_context("/posts", {"users": "2"})
    page = await Post.order_by(Post.id).paginate(5, page_name="users")
    assert page.current_page == 2
    assert page.to_dict()["first_page_url"].endswith("users=1")


async def test_paginate_empty_table(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    request_context("/posts", {})
    page = await Post.order_by(Post.id).paginate(15)
    data = page.to_dict()
    assert data["total"] == 0
    assert data["from"] is None
    assert data["to"] is None
    assert data["data"] == []
    assert data["last_page"] == 1


async def test_links_first_page_labels(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 50)  # 4 pages of 15
    request_context("/posts", {"page": "1"})
    page = await Post.order_by(Post.id).paginate(15)
    links = page.to_dict()["links"]
    assert links[0]["label"] == "&laquo; Previous"
    assert links[0]["url"] is None
    assert links[0]["active"] is False
    assert links[-1]["label"] == "Next &raquo;"
    assert links[-1]["active"] is False
    page_links = links[1:-1]
    assert [link["label"] for link in page_links] == ["1", "2", "3", "4"]
    assert page_links[0]["active"] is True


async def test_links_middle_page_has_both_prev_and_next(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 50)
    request_context("/posts", {"page": "2"})
    page = await Post.order_by(Post.id).paginate(15)
    links = page.to_dict()["links"]
    assert links[0]["url"] is not None
    assert links[0]["page"] == 1
    assert links[-1]["url"] is not None
    assert links[-1]["page"] == 3


async def test_links_collapse_with_ellipsis_for_many_pages(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 300)  # 20 pages of 15
    request_context("/posts", {"page": "10"})
    page = await Post.order_by(Post.id).paginate(15)
    links = page.to_dict()["links"]
    labels = [link["label"] for link in links]
    assert "..." in labels
    ellipsis_entries = [link for link in links if link["label"] == "..."]
    for entry in ellipsis_entries:
        assert entry["url"] is None
        assert entry["page"] is None


async def test_on_each_side_changes_the_window(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 300)
    request_context("/posts", {"page": "10"})
    wide = (await Post.order_by(Post.id).paginate(15)).on_each_side(10)
    narrow = (await Post.order_by(Post.id).paginate(15)).on_each_side(1)
    wide_labels = [link["label"] for link in wide.to_dict()["links"]]
    narrow_labels = [link["label"] for link in narrow.to_dict()["links"]]
    assert len(wide_labels) > len(narrow_labels)


# ---------------------------------------------------------------- customising links


async def test_with_query_string_keeps_other_params(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 30)
    request_context("/posts", {"page": "1", "search": "hello"})
    page = (await Post.order_by(Post.id).paginate(15)).with_query_string()
    url = page.to_dict()["next_page_url"]
    assert "search=hello" in url
    assert "page=2" in url


async def test_appends_adds_extra_params(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 30)
    request_context("/posts", {"page": "1"})
    page = (await Post.order_by(Post.id).paginate(15)).appends({"sort": "votes"})
    url = page.to_dict()["next_page_url"]
    assert "sort=votes" in url


async def test_with_path_and_fragment(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 30)
    request_context("/posts", {"page": "1"})
    page = (await Post.order_by(Post.id).paginate(15)).with_path("/admin/posts").fragment("list")
    url = page.to_dict()["next_page_url"]
    assert url.startswith("/admin/posts?")
    assert url.endswith("#list")


async def test_through_transforms_items(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 3)
    request_context("/posts", {})
    page = (await Post.order_by(Post.id).paginate(15)).through(lambda p: p.only("title"))
    assert page.to_dict()["data"][0] == {"title": "post-00"}


async def test_paginator_supports_iteration_len_and_indexing(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 3)
    request_context("/posts", {})
    page = await Post.order_by(Post.id).paginate(15)
    assert len(page) == 3
    assert [p.title for p in page] == ["post-00", "post-01", "post-02"]
    assert page[0].title == "post-00"


# ---------------------------------------------------------------- SimplePaginator


async def test_simple_paginate_shape(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 20)
    request_context("/posts", {"page": "2"})
    page = await Post.order_by(Post.id).simple_paginate(5)
    data = page.to_dict()
    assert set(data.keys()) == {
        "current_page",
        "current_page_url",
        "data",
        "first_page_url",
        "from",
        "next_page_url",
        "path",
        "per_page",
        "prev_page_url",
        "to",
    }
    assert data["current_page"] == 2
    assert len(data["data"]) == 5
    assert data["next_page_url"] is not None


async def test_simple_paginate_has_no_next_on_last_page(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 7)
    request_context("/posts", {"page": "2"})
    page = await Post.order_by(Post.id).simple_paginate(5)
    assert len(page) == 2
    assert page.to_dict()["next_page_url"] is None


async def test_simple_paginate_does_not_run_a_count_query(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 7)
    request_context("/posts", {})
    page = await Post.order_by(Post.id).simple_paginate(5)
    assert not hasattr(page, "total")


# ---------------------------------------------------------------- CursorPaginator


async def test_cursor_paginate_shape_and_first_page(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 25)
    request_context("/posts", {})
    page = await Post.order_by(Post.id).cursor_paginate(10)
    data = page.to_dict()
    assert set(data.keys()) == {
        "data",
        "path",
        "per_page",
        "next_cursor",
        "next_page_url",
        "prev_cursor",
        "prev_page_url",
    }
    assert len(data["data"]) == 10
    assert data["next_cursor"] is not None
    assert data["prev_cursor"] is None
    assert data["prev_page_url"] is None


async def test_cursor_paginate_walks_forward(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 25)
    request_context("/posts", {})
    first = await Post.order_by(Post.id).cursor_paginate(10)
    cursor = first.to_dict()["next_cursor"]

    request_context("/posts", {"cursor": cursor})
    second = await Post.order_by(Post.id).cursor_paginate(10)
    assert [p.title for p in second] == [f"post-{i:02d}" for i in range(10, 20)]
    assert second.to_dict()["prev_cursor"] is not None


async def test_cursor_paginate_last_page_has_no_next_cursor(db, request_context):
    Post = _post_model()
    await db.run_sync(Model.metadata.create_all)
    await _make_posts(Post, 15)
    request_context("/posts", {})
    first = await Post.order_by(Post.id).cursor_paginate(10)
    cursor = first.to_dict()["next_cursor"]
    request_context("/posts", {"cursor": cursor})
    second = await Post.order_by(Post.id).cursor_paginate(10)
    assert len(second) == 5
    assert second.to_dict()["next_cursor"] is None


async def test_cursor_paginate_requires_order_by():
    Post = _post_model()
    import pytest

    with pytest.raises(ValueError, match="order_by"):
        await Post.cursor_paginate(10)
