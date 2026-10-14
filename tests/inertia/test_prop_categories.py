"""T-16 "How it works" prop evaluation table: one behaviour per category, full visit + partial."""

from __future__ import annotations

from conftest import INERTIA


async def test_full_visit_skips_optional_and_defers_without_sending_them(client):
    r = await client.get("/kitchen", headers=INERTIA)
    page = r.json()
    props = page["props"]

    assert "export_preview" not in props  # optional: never sent on a full visit
    assert "permissions" not in props  # defer: left out of the first response
    assert "teams" not in props and "projects" not in props
    assert "activity" not in props


async def test_full_visit_resolves_regular_always_merge_once_scroll(client):
    r = await client.get("/kitchen", headers=INERTIA)
    page = r.json()
    props = page["props"]

    assert props["title"] == "Hello"  # regular
    assert props["stats"] == {"views": 1}  # always
    assert props["posts"]["data"] == [{"id": 1, "title": "a"}]  # merge
    assert props["chat"]["messages"] == [{"id": 1, "text": "hi"}]  # deep_merge
    assert props["plans"] == ["basic", "pro"]  # once
    assert props["feed"]["data"] == [{"id": 1}]  # scroll


async def test_deferred_props_are_grouped_in_metadata(client):
    r = await client.get("/kitchen", headers=INERTIA)
    deferred = r.json()["deferredProps"]
    assert sorted(deferred["default"]) == ["activity", "permissions"]
    assert sorted(deferred["attributes"]) == ["projects", "teams"]


async def test_always_prop_is_sent_even_on_a_partial_reload_that_did_not_select_it(client):
    headers = {**INERTIA, "X-Inertia-Partial-Component": "kitchen", "X-Inertia-Partial-Data": "title"}
    r = await client.get("/kitchen", headers=headers)
    props = r.json()["props"]
    assert "stats" in props  # always ignores only/except
    assert "title" in props
    assert "posts" not in props  # not selected -> not resolved


async def test_optional_prop_resolves_only_when_selected_on_partial(client):
    headers = {**INERTIA, "X-Inertia-Partial-Component": "kitchen", "X-Inertia-Partial-Data": "export_preview"}
    r = await client.get("/kitchen", headers=headers)
    props = r.json()["props"]
    assert props["export_preview"] == {"ready": True}
    assert "title" not in props


async def test_deferred_prop_resolves_on_the_selected_partial_reload(client):
    headers = {**INERTIA, "X-Inertia-Partial-Component": "kitchen", "X-Inertia-Partial-Data": "permissions"}
    r = await client.get("/kitchen", headers=headers)
    page = r.json()
    assert page["props"]["permissions"] == ["read", "write"]
    assert "deferredProps" not in page  # deferredProps is only on full visits


async def test_deferred_prop_with_rescue_is_omitted_and_listed_in_rescued_props(client):
    headers = {**INERTIA, "X-Inertia-Partial-Component": "kitchen", "X-Inertia-Partial-Data": "activity"}
    r = await client.get("/kitchen", headers=headers)
    page = r.json()
    assert "activity" not in page["props"]
    assert page["rescuedProps"] == ["activity"]


async def test_merge_and_deep_merge_emit_match_props_on_with_full_dot_path(client):
    r = await client.get("/kitchen", headers=INERTIA)
    page = r.json()
    assert "posts" in page["mergeProps"]
    assert "chat" in page["deepMergeProps"]
    assert "posts.data.id" in page["matchPropsOn"]
    assert "chat.messages.id" in page["matchPropsOn"]


async def test_scroll_prop_is_listed_in_scroll_props_and_merge_props(client):
    r = await client.get("/kitchen", headers=INERTIA)
    page = r.json()
    assert "feed" in page["scrollProps"]
    assert "feed" in page["mergeProps"]


async def test_infinite_scroll_merge_intent_prepend_adds_prepend_props(client):
    headers = {
        **INERTIA,
        "X-Inertia-Partial-Component": "kitchen",
        "X-Inertia-Partial-Data": "feed",
        "X-Inertia-Infinite-Scroll-Merge-Intent": "prepend",
    }
    r = await client.get("/kitchen", headers=headers)
    page = r.json()
    assert page["prependProps"] == ["feed"]


async def test_inertia_reset_header_forces_a_replace_instead_of_a_merge(client):
    headers = {**INERTIA, "X-Inertia-Reset": "posts"}
    r = await client.get("/kitchen", headers=headers)
    page = r.json()
    assert "posts" in page["props"]
    assert "posts" not in page.get("mergeProps", [])
    assert "feed" in page["mergeProps"]  # untouched merge props are unaffected


async def test_once_props_are_listed_with_their_prop_name_and_alias_identity(client):
    r = await client.get("/kitchen", headers=INERTIA)
    once_props = r.json()["onceProps"]
    assert once_props["plans"] == {"prop": "plans", "expiresAt": None}
    assert once_props["roles"] == {"prop": "member_roles", "expiresAt": None}  # .as_("roles")
    assert once_props["rates"]["expiresAt"] is not None  # .until(timedelta(days=1))


async def test_once_props_metadata_is_not_sent_on_a_partial_reload(client):
    headers = {**INERTIA, "X-Inertia-Partial-Component": "kitchen", "X-Inertia-Partial-Data": "plans"}
    r = await client.get("/kitchen", headers=headers)
    page = r.json()
    assert page["props"]["plans"] == ["basic", "pro"]
    assert "onceProps" not in page


async def test_except_once_props_skips_resolving_that_once_prop(client):
    headers = {**INERTIA, "X-Inertia-Except-Once-Props": "plans"}
    r = await client.get("/kitchen", headers=headers)
    props = r.json()["props"]
    assert "plans" not in props
    assert "countries" in props  # not excepted: still resolved


async def test_fresh_once_prop_resolves_even_when_the_client_excepted_it(client):
    headers = {**INERTIA, "X-Inertia-Except-Once-Props": "flags"}
    r = await client.get("/kitchen", headers=headers)
    props = r.json()["props"]
    assert props["flags"] == {"beta": True}  # .fresh(True) overrides the except-once header


async def test_once_prop_resolves_when_selected_on_a_partial_reload_even_if_excepted(client):
    headers = {
        **INERTIA,
        "X-Inertia-Partial-Component": "kitchen",
        "X-Inertia-Partial-Data": "plans",
        "X-Inertia-Except-Once-Props": "plans",
    }
    r = await client.get("/kitchen", headers=headers)
    assert r.json()["props"]["plans"] == ["basic", "pro"]


async def test_shared_props_metadata_lists_top_level_shared_keys(client):
    r = await client.get("/kitchen", headers=INERTIA)
    shared = r.json()["sharedProps"]
    assert sorted(shared) == ["auth", "countries", "feature_flag", "name"]
