from __future__ import annotations

from pathlib import Path
import re
import textwrap

import typer

app = typer.Typer(add_completion=False, help="Fast CLI for the FastGram template.")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _modules_dir() -> Path:
    return _repo_root() / "app" / "modules"


def _normalize_module_name(raw: str) -> str:
    name = raw.strip().lower().replace("-", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)
    return name


def _class_name(module_name: str) -> str:
    parts = module_name.split("_")
    base = "".join(p.capitalize() for p in parts if p)
    if base.endswith("s") and not base.endswith("Ss"):
        base = base[:-1]
    return base or "Module"


def _print_box(title: str, body: str) -> None:
    lines = [line.rstrip() for line in body.splitlines()]
    width = max([len(title)] + [len(line) for line in lines]) + 4
    border = "┌" + "─" * (width - 2) + "┐"
    footer = "└" + "─" * (width - 2) + "┘"
    typer.echo(border)
    typer.echo(f"│ {title.ljust(width - 4)} │")
    typer.echo("├" + "─" * (width - 2) + "┤")
    for line in lines:
        typer.echo(f"│ {line.ljust(width - 4)} │")
    typer.echo(footer)


@app.command("make-module")
def make_module(
    name: str = typer.Argument(..., help="Module name, e.g. orders"),
    force: bool = typer.Option(False, "--force", help="Overwrite if module exists"),
) -> None:
    module_name = _normalize_module_name(name)
    if not module_name or not re.fullmatch(r"[a-z][a-z0-9_]*", module_name):
        typer.secho(
            "Invalid module name. Use letters, numbers, and underscores, starting with a letter.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    module_dir = _modules_dir() / module_name
    if module_dir.exists() and not force:
        typer.secho(
            f"Module already exists: {module_dir}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    module_dir.mkdir(parents=True, exist_ok=True)
    class_name = _class_name(module_name)
    table_name = module_name

    templates: dict[str, str] = {
        "models.py": textwrap.dedent(
            f"""\
            from sqlalchemy import Integer
            from sqlalchemy.orm import Mapped, mapped_column

            from app.core.db import Base


            class {class_name}(Base):
                __tablename__ = "{table_name}"

                id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
            """
        ),
        "schemas.py": textwrap.dedent(
            f"""\
            from pydantic import BaseModel


            class {class_name}Create(BaseModel):
                pass


            class {class_name}Read(BaseModel):
                id: int

                class Config:
                    from_attributes = True
            """
        ),
        "repository.py": textwrap.dedent(
            f"""\
            from sqlalchemy.ext.asyncio import AsyncSession

            from app.modules.{module_name}.models import {class_name}


            class {class_name}Repository:
                def __init__(self, session: AsyncSession) -> None:
                    self._session = session

                async def create(self, **data) -> {class_name}:
                    item = {class_name}(**data)
                    self._session.add(item)
                    await self._session.commit()
                    await self._session.refresh(item)
                    return item
            """
        ),
        "service.py": textwrap.dedent(
            f"""\
            from app.modules.{module_name}.repository import {class_name}Repository


            class {class_name}Service:
                def __init__(self, repo: {class_name}Repository) -> None:
                    self._repo = repo

                async def create(self, **data):
                    return await self._repo.create(**data)
            """
        ),
    }

    for filename, content in templates.items():
        path = module_dir / filename
        path.write_text(content, encoding="utf-8")

    typer.secho(f"Created module: {module_dir}", fg=typer.colors.GREEN)
    typer.echo("Next: wire it into handlers/routes and add migrations if needed.")


@app.command("help")
def help_command() -> None:
    body = textwrap.dedent(
        """\
        What is a module?
        - A self-contained business unit under app/modules/<name>
        - It always has: models.py, schemas.py, repository.py, service.py
        - Services call repositories; handlers/routes call services

        Useful CLI commands
        - make module name=orders
        - make module orders
        - make help

        Direct CLI (after uv sync)
        - uv run fast make-module orders
        - uv run fast help

        Helpful Make targets
        - make setup        # create .env and install deps
        - make run          # start dev server
        - make sync         # install/update deps
        - make shell        # open IPython in project env
        - make lint         # ruff check (app + tests)
        - make lint-fix     # ruff check --fix (app + tests)
        - make format       # ruff format (app + tests)
        - make migrate      # apply db migrations
        - make revision     # create migration
        - make docker-up    # start docker stack
        - make docker-down  # stop docker stack

        Run options
        - make run PORT=8001          # run on a different port
        - make run HOST=0.0.0.0       # expose to local network
        - make run HOST=0.0.0.0 PORT=9000
        """
    ).strip()
    _print_box("Fast CLI Help", body)


if __name__ == "__main__":
    app()
