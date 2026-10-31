"""PromptDock command-line interface."""

import typer

from promptdock import __version__

app = typer.Typer(help="PromptDock: prompt versioning.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """PromptDock: prompt versioning."""


@app.command()
def version() -> None:
    """Print the installed PromptDock version."""
    typer.echo(__version__)
