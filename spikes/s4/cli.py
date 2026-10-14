"""S-4 spike: Typer with artisan-style colon command names and grouped help."""

import typer

app = typer.Typer(help="FastoGram — Laravel-style framework for Python", no_args_is_help=True,
                  rich_markup_mode="rich")


@app.command("serve", rich_help_panel="Available commands")
def serve(port: int = 8000) -> None:
    """Serve the application on the PHP… er, uvicorn development server."""
    typer.echo(f"serve {port}")


@app.command("make:controller", rich_help_panel="make")
def make_controller(name: str, resource: bool = typer.Option(False, "--resource", "-r")) -> None:
    """Create a new controller class."""
    typer.echo(f"make:controller {name} resource={resource}")


@app.command("make:model", rich_help_panel="make")
def make_model(name: str, m: bool = typer.Option(False, "-m"), c: bool = typer.Option(False, "-c")) -> None:
    """Create a new model class."""
    typer.echo(f"make:model {name} m={m} c={c}")


@app.command("migrate", rich_help_panel="migrate")
def migrate() -> None:
    """Run the database migrations."""
    typer.echo("migrate")


@app.command("migrate:fresh", rich_help_panel="migrate")
def migrate_fresh(seed: bool = False) -> None:
    """Drop all tables and re-run all migrations."""
    typer.echo(f"migrate:fresh seed={seed}")


@app.command("route:list", rich_help_panel="route")
def route_list() -> None:
    """List all registered routes."""
    typer.echo("route:list")


if __name__ == "__main__":
    app()
