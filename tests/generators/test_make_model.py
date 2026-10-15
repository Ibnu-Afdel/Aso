"""`make:model` (T-51, T-31): `--fields` parsing/rendering, `-m -f -s -c -r -a`, and the
`--fields` output applied end to end through `migrate`."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner


def _ruff_check(path: Path) -> None:
    result = subprocess.run(["ruff", "check", str(path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_model_with_no_fields_has_a_pass_body(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:model", "Comment"])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "models" / "comment.py"
    content = path.read_text()
    assert "class Comment(Model):" in content
    assert "pass" in content
    _ruff_check(path)


def test_model_with_fields_renders_every_type(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    fields = (
        "title:string slug:string:unique body:text published_at:datetime? "
        "views:integer total:big_integer featured:boolean price:decimal "
        "meta:json token:uuid user:foreign"
    )
    result = runner.invoke(cli_group, ["make:model", "Article", "--fields", fields])
    assert result.exit_code == 0, result.output
    path = console_app_dir / "app" / "models" / "article.py"
    content = path.read_text()

    assert 'title: Mapped[str] = mapped_column(String(255))' in content
    assert "slug: Mapped[str] = mapped_column(String(255), unique=True)" in content
    assert "body: Mapped[str] = mapped_column(Text)" in content
    assert "published_at: Mapped[datetime | None]" in content
    assert "views: Mapped[int]" in content
    assert "total: Mapped[int]" in content
    assert "featured: Mapped[bool] = mapped_column(Boolean, default=False)" in content
    assert "price: Mapped[Decimal] = mapped_column(Numeric(10, 2))" in content
    assert "meta: Mapped[Any] = mapped_column(JSON)" in content
    assert "token: Mapped[uuid.UUID] = mapped_column(Uuid)" in content
    assert 'user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))' in content
    assert 'user: Mapped["User"] = belongs_to("User")' in content

    fillable_block = content[content.index("__fillable__") : content.index("]") + 1]
    assert '"user"' not in fillable_block  # foreign columns are never fillable
    assert '"title"' in fillable_block and '"slug"' in fillable_block

    _ruff_check(path)


def test_dash_a_generates_everything(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:model", "Article", "-a", "--fields=title:string"])
    assert result.exit_code == 0, result.output

    assert (console_app_dir / "app" / "models" / "article.py").is_file()
    assert (console_app_dir / "app" / "http" / "controllers" / "article_controller.py").is_file()
    assert (console_app_dir / "app" / "http" / "requests" / "store_article_request.py").is_file()
    assert (console_app_dir / "app" / "http" / "requests" / "update_article_request.py").is_file()
    assert (console_app_dir / "database" / "factories" / "article_factory.py").is_file()
    assert (console_app_dir / "database" / "seeders" / "article_seeder.py").is_file()
    assert (console_app_dir / "app" / "policies" / "article_policy.py").is_file()

    migrations = list((console_app_dir / "database" / "migrations").glob("*.py"))
    assert len(migrations) == 1
    migration_content = migrations[0].read_text()
    assert "op.create_table('articles'" in migration_content

    controller_content = (console_app_dir / "app" / "http" / "controllers" / "article_controller.py").read_text()
    assert "StoreArticleRequest" in controller_content
    assert "UpdateArticleRequest" in controller_content


def test_dash_mf_combine_as_one_short_flag_token(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:model", "Comment", "-mf", "--fields=body:text"])
    assert result.exit_code == 0, result.output
    assert (console_app_dir / "app" / "models" / "comment.py").is_file()
    assert (console_app_dir / "database" / "factories" / "comment_factory.py").is_file()
    migrations = list((console_app_dir / "database" / "migrations").glob("*.py"))
    assert len(migrations) == 1
    assert (console_app_dir / "app" / "policies" / "comment_policy.py").is_file() is False


def test_dash_c_alone_generates_a_plain_controller(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:model", "Comment", "-c", "--fields=body:text"])
    assert result.exit_code == 0, result.output
    content = (console_app_dir / "app" / "http" / "controllers" / "comment_controller.py").read_text()
    assert "pass" in content
    assert "async def index(" not in content


def test_dash_c_and_dash_r_generate_a_resource_controller(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:model", "Comment", "-cr", "--fields=body:text"])
    assert result.exit_code == 0, result.output
    content = (console_app_dir / "app" / "http" / "controllers" / "comment_controller.py").read_text()
    for method in ("index", "create", "store", "show", "edit", "update", "destroy"):
        assert f"async def {method}(" in content


def test_invalid_field_spec_reports_an_error(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:model", "Broken", "--fields=notatype"])
    assert result.exit_code == 1
    assert "Invalid field" in result.output


def test_unknown_field_type_reports_an_error(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(cli_group, ["make:model", "Broken", "--fields=x:bogus"])
    assert result.exit_code == 1
    assert "Unknown field type" in result.output


def test_make_model_fields_end_to_end_through_migrate(cli_group, runner: CliRunner, console_app_dir: Path) -> None:
    result = runner.invoke(
        cli_group, ["make:model", "Article", "-m", "--fields=title:string body:text published_at:datetime?"]
    )
    assert result.exit_code == 0, result.output

    migrate_result = runner.invoke(cli_group, ["migrate"])
    assert migrate_result.exit_code == 0, migrate_result.output

    table = runner.invoke(cli_group, ["db:table", "articles"])
    assert table.exit_code == 0, table.output
    assert "title" in table.output
    assert "body" in table.output
    assert "published_at" in table.output
