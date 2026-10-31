"""PromptDock command-line interface."""

from typing import Annotated

import typer

from promptdock import __version__
from promptdock.errors import PromptDockError

app = typer.Typer(help="PromptDock: prompt versioning.", no_args_is_help=True)

DatabaseUrlOption = Annotated[
    str | None,
    typer.Option(
        "--database-url",
        envvar="DATABASE_URL",
        help="Postgres URL. Defaults to the DATABASE_URL environment variable.",
        show_default=False,
    ),
]


@app.callback()
def main() -> None:
    """PromptDock: prompt versioning."""


@app.command()
def version() -> None:
    """Print the installed PromptDock version."""
    typer.echo(__version__)


@app.command()
def migrate(database_url: DatabaseUrlOption = None) -> None:
    """Create or upgrade the PromptDock tables in the database."""
    from promptdock.db.migrate import upgrade

    try:
        revision = upgrade(database_url)
    except PromptDockError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Database is up to date (revision {revision}).")
