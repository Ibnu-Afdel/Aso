"""Every non-model, non-controller `make:*` generator (T-51): paths, class names, imports, and
that the generated Python passes `uv run ruff check`."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner


def _ruff_check(path: Path) -> None:
    result = subprocess.run(["ruff", "check", str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_make_request(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:request", "StorePostRequest"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "http" / "requests" / "store_post_request.py"
    assert path.is_file()
    assert "Created:" in result.output
    content = path.read_text()
    assert "class StorePostRequest(FormRequest):" in content
    assert "from aso.http import FormRequest" in content
    _ruff_check(path)


def test_make_middleware(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:middleware", "EnsureUserIsSubscribed"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "http" / "middleware" / "ensure_user_is_subscribed.py"
    assert path.is_file()
    content = path.read_text()
    assert "class EnsureUserIsSubscribed(Middleware):" in content
    assert "async def handle(self, request: Request, next: Next) -> Response:" in content
    _ruff_check(path)


def test_make_page(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:page", "posts/index"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "resources" / "js" / "pages" / "posts" / "index.tsx"
    assert path.is_file()
    content = path.read_text()
    assert "export default function Index" in content
    assert 'import { Head } from "@inertiajs/react";' in content


def test_make_factory_with_explicit_model(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:factory", "PostFactory", "--model=Post"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "database" / "factories" / "post_factory.py"
    assert path.is_file()
    content = path.read_text()
    assert "class PostFactory(Factory):" in content
    assert "model = Post" in content
    assert "from app.models.post import Post" in content
    _ruff_check(path)


def test_make_factory_infers_model_from_name(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:factory", "PostFactory"])
    assert result.exit_code == 0, result.output
    content = (console_app_dir / "database" / "factories" / "post_factory.py").read_text()
    assert "model = Post" in content


def test_make_seeder(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:seeder", "PostSeeder"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "database" / "seeders" / "post_seeder.py"
    assert path.is_file()
    content = path.read_text()
    assert "class PostSeeder(Seeder):" in content
    assert "from database.factories.post_factory import PostFactory" in content
    assert "await PostFactory.new().count(10).create()" in content
    _ruff_check(path)


def test_make_policy(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:policy", "PostPolicy", "--model=Post"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "policies" / "post_policy.py"
    assert path.is_file()
    content = path.read_text()
    assert "class PostPolicy:" in content
    assert "async def update(self, user: User, post: Post) -> bool:" in content
    assert "async def delete(self, user: User, post: Post) -> bool:" in content
    _ruff_check(path)


def test_make_job(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:job", "SendWelcomeEmail"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "jobs" / "send_welcome_email.py"
    content = path.read_text()
    assert "class SendWelcomeEmail(Job):" in content
    assert "from aso.queue import Job" in content
    _ruff_check(path)


def test_make_event(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:event", "OrderShipped"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "events" / "order_shipped.py"
    content = path.read_text()
    assert "class OrderShipped(Event):" in content
    _ruff_check(path)


def test_make_listener_with_event(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:listener", "SendShipmentNotification", "--event=OrderShipped"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "listeners" / "send_shipment_notification.py"
    content = path.read_text()
    assert "from app.events.order_shipped import OrderShipped" in content
    assert "async def handle(self, event: OrderShipped) -> None:" in content
    assert "queued = True" not in content
    _ruff_check(path)


def test_make_listener_queued(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:listener", "SendShipmentNotification", "--event=OrderShipped", "--queued"])
    assert result.exit_code == 0, result.output
    content = (console_app_dir / "app" / "listeners" / "send_shipment_notification.py").read_text()
    assert "queued = True" in content
    _ruff_check(console_app_dir / "app" / "listeners" / "send_shipment_notification.py")


def test_make_mail(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:mail", "WelcomeMail"])
    assert result.exit_code == 0, result.output
    py_path = console_app_dir / "app" / "mail" / "welcome_mail.py"
    view_path = console_app_dir / "resources" / "views" / "mail" / "welcome_mail.html"
    assert py_path.is_file()
    assert view_path.is_file()
    content = py_path.read_text()
    assert 'Envelope(subject="Welcome Mail")' in content
    assert 'Content(view="mail/welcome_mail.html")' in content
    _ruff_check(py_path)


def test_make_command(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:command", "SendReport"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "console" / "commands" / "send_report.py"
    content = path.read_text()
    assert 'signature = "app:send-report"' in content
    assert "class SendReport(Command):" in content
    _ruff_check(path)


def test_make_test_feature(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:test", "PostTest"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "tests" / "feature" / "test_post.py"
    assert path.is_file()
    _ruff_check(path)


def test_make_test_unit(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:test", "PostTest", "--unit"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "tests" / "unit" / "test_post.py"
    assert path.is_file()
    _ruff_check(path)
