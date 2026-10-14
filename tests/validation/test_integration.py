"""End-to-end T-19 behaviour through the real stack (`tests/fixtures/validation_app`)."""

from __future__ import annotations

INERTIA = {"X-Inertia": "true", "X-Inertia-Version": ""}


async def test_required_precheck_and_cleanup_redirect_back_with_errors_and_old_input(client, csrf_headers):
    headers = {**INERTIA, **csrf_headers}
    r = await client.post("/forms", json={"title": "  ", "body": "Text"}, headers=headers)
    assert r.status_code == 302 and r.headers["location"] == "/forms/create"

    dump = (await client.get("/debug/session")).json()
    assert dump["errors"]["default"] == {"title": ["The title field is required."]}
    assert dump["old_input"]["body"] == "Text"
    assert dump["old_input"]["title"] == "  "  # old input is flashed as submitted, not cleaned


async def test_min_length_message_matches_the_default_table(client, csrf_headers):
    headers = {**INERTIA, **csrf_headers}
    r = await client.post("/forms", json={"title": "ab", "body": "Text"}, headers=headers)
    assert r.status_code == 302
    dump = (await client.get("/debug/session")).json()
    assert dump["errors"]["default"]["title"] == ["The title field must be at least 3 characters."]


async def test_prepare_for_validation_merge_runs_before_validation(client, csrf_headers):
    headers = {**INERTIA, **csrf_headers}
    r = await client.post("/forms", json={"title": "Hello World", "body": "Text"}, headers=headers)
    assert r.status_code == 302 and r.headers["location"] == "/forms/create"
    page = (await client.get("/forms/create", headers=INERTIA)).json()
    assert page["props"]["errors"] == {}
    assert page["flash"] == {"success": "Created with slug hello-world."}


async def test_authorize_false_renders_403(client, csrf_headers):
    headers = {**INERTIA, **csrf_headers}
    r = await client.post("/forms/secure", json={"title": "Hello"}, headers=headers)
    assert r.status_code == 403


async def test_nested_array_errors_use_dot_keys(client, csrf_headers):
    headers = csrf_headers
    r = await client.post(
        "/forms/orders",
        json={"lines": [{"product_id": 1, "quantity": 0}]},
        headers={**headers, "Accept": "application/json"},
    )
    assert r.status_code == 422
    assert r.json()["errors"]["lines.0.quantity"] == ["The quantity field must be at least 1."]


async def test_after_hook_cross_field_check(client, csrf_headers):
    headers = csrf_headers
    r = await client.post(
        "/forms/invoices",
        json={"issued_on": "2026-01-02", "due_on": "2026-01-01"},
        headers={**headers, "Accept": "application/json"},
    )
    assert r.status_code == 422
    assert r.json()["errors"]["due_on"] == ["The due date must be after the issue date."]

    ok = await client.post(
        "/forms/invoices",
        json={"issued_on": "2026-01-01", "due_on": "2026-01-02"},
        headers={**INERTIA, **headers},
    )
    assert ok.status_code == 302


async def test_messages_and_attributes_overrides(client, csrf_headers):
    headers = csrf_headers
    r = await client.post(
        "/forms/custom-messages",
        json={"title": "", "published_at": "nope"},
        headers={**headers, "Accept": "application/json"},
    )
    body = r.json()
    assert body["errors"]["title"] == ["Every post needs a title."]
    assert body["errors"]["published_at"] == ["The publish date field must be a valid date."]


async def test_error_bag_is_flashed_under_its_own_key(client, csrf_headers):
    headers = csrf_headers
    r = await client.post("/forms/invite", json={"email": "not-an-email"}, headers={**INERTIA, **headers})
    assert r.status_code == 302
    dump = (await client.get("/debug/session")).json()
    assert "invite" in dump["errors"]
    assert "default" not in dump["errors"] or dump["errors"].get("default") == {}
    assert dump["errors"]["invite"]["email"] == ["The email field must be a valid email address."]


async def test_unique_rule_against_sqlite_with_ignore(client, csrf_headers):
    # Seed a user directly through the DB, inside the same app.
    from fastogram.database.scope import open_scope

    async with open_scope():
        from app.models.user import User

        existing = await User.create(email="taken@example.com")
        existing_id = existing.id

    headers = csrf_headers
    dupe = await client.post(
        "/forms/email", json={"email": "taken@example.com"}, headers={**headers, "Accept": "application/json"}
    )
    assert dupe.status_code == 422
    assert dupe.json()["errors"]["email"] == ["The email has already been taken."]

    ignored = await client.post(
        "/forms/email",
        json={"email": "taken@example.com", "exclude_id": existing_id},
        headers={**headers, "Accept": "application/json"},
    )
    assert ignored.status_code == 200

    fresh = await client.post(
        "/forms/email", json={"email": "new@example.com"}, headers={**headers, "Accept": "application/json"}
    )
    assert fresh.status_code == 200


async def test_exists_rule_against_sqlite(client, csrf_headers):
    from fastogram.database.scope import open_scope

    async with open_scope():
        from app.models.team import Team

        team = await Team.create(name="Engineering")
        team_id = team.id

    headers = csrf_headers
    missing = await client.post(
        "/forms/team", json={"team_id": 999999}, headers={**headers, "Accept": "application/json"}
    )
    assert missing.status_code == 422
    assert missing.json()["errors"]["team_id"] == ["The selected team id is invalid."]

    found = await client.post(
        "/forms/team", json={"team_id": team_id}, headers={**headers, "Accept": "application/json"}
    )
    assert found.status_code == 200


async def test_confirmed_and_password_builder_rules(client, csrf_headers):
    headers = csrf_headers
    mismatch = await client.post(
        "/forms/password",
        json={"password": "Strong1!x", "password_confirmation": "different"},
        headers={**headers, "Accept": "application/json"},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["errors"]["password"] == ["The password field confirmation does not match."]

    weak = await client.post(
        "/forms/password",
        json={"password": "weak", "password_confirmation": "weak"},
        headers={**headers, "Accept": "application/json"},
    )
    assert weak.status_code == 422
    assert "at least 8 characters" in weak.json()["errors"]["password"][0]

    good = await client.post(
        "/forms/password",
        json={"password": "Strong1!x", "password_confirmation": "Strong1!x"},
        headers={**headers, "Accept": "application/json"},
    )
    assert good.status_code == 200


async def test_accepted_rule(client, csrf_headers):
    headers = csrf_headers
    no = await client.post("/forms/terms", json={"terms": False}, headers={**headers, "Accept": "application/json"})
    assert no.status_code == 422
    assert no.json()["errors"]["terms"] == ["The terms field must be accepted."]
    yes = await client.post("/forms/terms", json={"terms": "yes"}, headers={**headers, "Accept": "application/json"})
    assert yes.status_code == 200


async def test_file_rule_rejects_bad_mime_and_accepts_good_one(client, csrf_headers):
    headers = csrf_headers
    bad = await client.post(
        "/forms/avatar",
        files={"avatar": ("avatar.gif", b"x" * 10, "image/gif")},
        headers={**headers, "Accept": "application/json"},
    )
    assert bad.status_code == 422
    assert bad.json()["errors"]["avatar"] == ["The avatar field must be a file of type: jpg, png."]

    good = await client.post(
        "/forms/avatar",
        files={"avatar": ("avatar.jpg", b"x" * 10, "image/jpeg")},
        headers={**headers, "Accept": "application/json"},
    )
    assert good.status_code == 200
    assert good.json()["size"] == 10


async def test_image_rule_with_fake_upload(client, csrf_headers):
    from fastogram.validation.uploaded_file import UploadedFile

    image = UploadedFile.fake().image("photo.png", width=4, height=4)
    headers = csrf_headers
    r = await client.post(
        "/forms/photo",
        files={"photo": (image.filename, await image.read(), image.content_type)},
        headers={**headers, "Accept": "application/json"},
    )
    assert r.status_code == 200
    assert r.json()["size"] == image.size


async def test_bracket_keys_and_optional_file_in_one_multipart_submission(client, csrf_headers):
    headers = csrf_headers
    r = await client.post(
        "/forms/mixed",
        data={"name": "Order", "tags[]": ["a", "b"]},
        files={"avatar": ("a.png", b"xyz", "image/png")},
        headers={**headers, "Accept": "application/json"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body == {"name": "Order", "tags": ["a", "b"], "avatar_size": 3}


async def test_mixed_upload_without_a_file_is_fine_optional_field_skips_its_rule(client, csrf_headers):
    headers = csrf_headers
    r = await client.post(
        "/forms/mixed",
        data={"name": "Order", "tags[]": ["a"]},
        headers={**headers, "Accept": "application/json"},
    )
    assert r.status_code == 200
    assert r.json() == {"name": "Order", "tags": ["a"], "avatar_size": None}


async def test_api_route_returns_laravel_style_422_json(client):
    r = await client.post("/api/forms", json={"title": "", "body": ""})
    assert r.status_code == 422
    body = r.json()
    assert body["errors"]["title"] == ["The title field is required."]
    assert body["errors"]["body"] == ["The body field is required."]
    assert "message" in body
    assert "set-cookie" not in r.headers


async def test_validate_one_off_helper(client, csrf_headers):
    headers = csrf_headers
    too_long = await client.post(
        "/forms/adhoc", json={"q": "way-too-long"}, headers={**headers, "Accept": "application/json"}
    )
    assert too_long.status_code == 422
    ok = await client.post("/forms/adhoc", json={"q": "ok"}, headers={**headers, "Accept": "application/json"})
    assert ok.status_code == 200
    assert ok.json() == {"q": "ok"}


async def test_old_helper_reads_flashed_input_on_the_next_request(client, csrf_headers):
    headers = {**INERTIA, **csrf_headers}
    await client.post("/forms", json={"title": "", "body": "Text"}, headers=headers)
    r = await client.get("/forms/old")
    assert r.json() == {"title": ""}


async def test_form_request_never_appears_in_the_openapi_schema(client):
    schema = client.app.openapi()
    dumped = str(schema)
    assert "StorePostRequest" not in dumped
    assert "CustomMessagesRequest" not in dumped
