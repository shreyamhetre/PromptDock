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


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@app.command()
def serve(
    database_url: DatabaseUrlOption = None,
    host: Annotated[
        str, typer.Option(help="Interface to listen on. The default only allows this machine.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8000,
    token: Annotated[
        str | None,
        typer.Option(
            envvar="PROMPTDOCK_TOKEN",
            help="Optional shared token; if set, every request except /health must send it.",
            show_default=False,
        ),
    ] = None,
) -> None:
    """Run the REST server (API docs at /docs). Needs: pip install promptdock[server]."""
    try:
        import uvicorn

        from promptdock.server import create_app
    except ImportError:
        typer.secho(
            "The server is not installed. Run: pip install 'promptdock[server]'",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from None

    try:
        server_app = create_app(database_url, token=token)
    except PromptDockError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None

    if host not in LOOPBACK_HOSTS and not token:
        typer.secho(
            f"\nWARNING: listening on {host} with no token. Anyone who can reach this "
            "machine can read and change your prompts.\n"
            "Set PROMPTDOCK_TOKEN (or --token), or run it only on a private network.\n",
            fg=typer.colors.YELLOW,
            bold=True,
            err=True,
        )
    lock = "token required" if token else "no token"
    typer.echo(f"PromptDock {__version__} ({lock}): API docs at http://{host}:{port}/docs")
    uvicorn.run(server_app, host=host, port=port)
