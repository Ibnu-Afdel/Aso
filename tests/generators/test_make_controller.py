"""`make:controller` (T-51, T-13): plain, resource, api, invokable, --model, --requests."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner


def _ruff_check(path: Path) -> None:
    result = subprocess.run(["ruff", "check", str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_plain_controller_has_an_empty_body(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:controller", "PostController"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "http" / "controllers" / "post_controller.py"
    content = path.read_text()
    assert "class PostController(Controller):" in content
    assert "pass" in content
    _ruff_check(path)


def test_invokable_controller(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:controller", "ChargeCardController", "--invokable"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "http" / "controllers" / "charge_card_controller.py"
    content = path.read_text()
    assert "async def __call__(self, request: Request) -> Response:" in content
    _ruff_check(path)


def test_resource_controller_with_model_and_requests(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(
        cli_group, ["make:controller", "PostController", "--resource", "--model=Post", "--requests"]
    )
    assert result.exit_code == 0, result.output

    store_request = console_app_dir / "app" / "http" / "requests" / "store_post_request.py"
    update_request = console_app_dir / "app" / "http" / "requests" / "update_post_request.py"
    assert store_request.is_file()
    assert update_request.is_file()

    path = console_app_dir / "app" / "http" / "controllers" / "post_controller.py"
    content = path.read_text()
    assert "from app.models.post import Post" in content
    assert "from app.http.requests.store_post_request import StorePostRequest" in content
    assert "from app.http.requests.update_post_request import UpdatePostRequest" in content
    for method in ("index", "create", "store", "show", "edit", "update", "destroy"):
        assert f"async def {method}(" in content
    assert 'inertia("posts/index"' in content
    assert "await post.delete()" in content
    assert 'redirect().route("posts.index")' in content
    _ruff_check(path)
    _ruff_check(store_request)
    _ruff_check(update_request)


def test_api_resource_controller_skips_create_and_edit(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:controller", "PostController", "--api", "--model=Post"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "http" / "controllers" / "post_controller.py"
    content = path.read_text()
    assert "async def create(" not in content
    assert "async def edit(" not in content
    for method in ("index", "store", "show", "update", "destroy"):
        assert f"async def {method}(" in content
    _ruff_check(path)


def test_resource_controller_without_model_uses_an_int_id(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:controller", "PostController", "--resource"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "http" / "controllers" / "post_controller.py"
    content = path.read_text()
    assert "from app.models" not in content
    assert "id: int" in content
    _ruff_check(path)
