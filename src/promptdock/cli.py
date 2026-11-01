"""PromptDock command-line interface.

Commands that read or change prompts connect the same way as ``Client``:
``PROMPTDOCK_URL`` (+ ``PROMPTDOCK_TOKEN`` if the server has one) means server mode,
otherwise ``DATABASE_URL`` means direct mode. There is no config file.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from promptdock import __version__
from promptdock.config import DEFAULT_PROJECT
from promptdock.errors import ConfigError, PromptDockError

if TYPE_CHECKING:
    from promptdock.client import Client

app = typer.Typer(help="PromptDock: prompt versioning.", no_args_is_help=True)
versions_app = typer.Typer(help="Inspect versions.", no_args_is_help=True)
prompts_app = typer.Typer(help="Inspect prompts.", no_args_is_help=True)
evals_app = typer.Typer(help="Send eval results.", no_args_is_help=True)
app.add_typer(versions_app, name="versions")
app.add_typer(prompts_app, name="prompts")
app.add_typer(evals_app, name="evals")

# --- shared options ------------------------------------------------------------------------

DatabaseUrlOption = Annotated[
    str | None,
    typer.Option(
        "--database-url",
        envvar="DATABASE_URL",
        help="Postgres URL for direct mode. Defaults to DATABASE_URL.",
        show_default=False,
    ),
]
ServerUrlOption = Annotated[
    str | None,
    typer.Option(
        "--url",
        envvar="PROMPTDOCK_URL",
        help="PromptDock server URL (server mode). Defaults to PROMPTDOCK_URL.",
        show_default=False,
    ),
]
TokenOption = Annotated[
    str | None,
    typer.Option(
        envvar="PROMPTDOCK_TOKEN",
        help="Server token, if the server sets one. Defaults to PROMPTDOCK_TOKEN.",
        show_default=False,
    ),
]
ProjectOption = Annotated[str, typer.Option(help="Project name.")]
ActorOption = Annotated[
    str | None,
    typer.Option(
        help="Who is making the change. Defaults to your OS username.", show_default=False
    ),
]
ReasonOption = Annotated[
    str | None, typer.Option(help="Why (recorded in the history).", show_default=False)
]


def _fail(message: str) -> typer.Exit:
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    return typer.Exit(code=1)


@contextmanager
def _client(
    url: str | None,
    token: str | None,
    database_url: str | None,
    project: str,
    actor: str | None = None,
) -> Iterator["Client"]:
    """A Client for the CLI's connection settings; errors become a clean exit."""
    from promptdock.client import Client

    try:
        if url:
            client = Client(base_url=url, token=token, project=project, actor=actor, cache_ttl=0)
        elif database_url:
            client = Client(database_url, project=project, actor=actor, cache_ttl=0)
        else:
            raise ConfigError(
                "Not connected. Set PROMPTDOCK_URL (server mode) or DATABASE_URL (direct mode)"
            )
    except PromptDockError as exc:
        raise _fail(str(exc)) from None
    try:
        yield client
    except PromptDockError as exc:
        raise _fail(str(exc)) from None
    finally:
        client.close()


def _v(version: int | None) -> str:
    return f"v{version}" if version is not None else "-"


# --- basics --------------------------------------------------------------------------------


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
        raise _fail(str(exc)) from None
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
    r"""Run the REST server (API docs at /docs). Needs: pip install promptdock\[server]."""
    try:
        import uvicorn

        from promptdock.server import create_app
    except ImportError:
        raise _fail("The server is not installed. Run: pip install 'promptdock[server]'") from None

    try:
        server_app = create_app(database_url, token=token)
    except PromptDockError as exc:
        raise _fail(str(exc)) from None

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


# --- reading -------------------------------------------------------------------------------


@prompts_app.command("list")
def prompts_list(
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """List prompts and where their tags point."""
    with _client(url, token, database_url, project) as client:
        prompts = client.list_prompts()
        if not prompts:
            typer.echo("No prompts yet. Create some with `promptdock push ./prompts`.")
        for p in prompts:
            tags = ", ".join(f"{t.name}={_v(t.version)}" for t in client.list_tags(p.name))
            typer.echo(f"{p.name:<30} {tags}")


@versions_app.command("list")
def versions_list(
    name: Annotated[str, typer.Argument(help="Prompt name.")],
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """List a prompt's versions, newest first, with the tags pointing at each."""
    with _client(url, token, database_url, project) as client:
        tags_by_version: dict[int, list[str]] = {}
        for t in client.list_tags(name):
            if t.version is not None:
                tags_by_version.setdefault(t.version, []).append(t.name)
        typer.echo(f"{'version':<8} {'tags':<20} {'created':<17} {'by':<15} message")
        for v in reversed(client.list_versions(name)):
            tags = ", ".join(tags_by_version.get(v.version, []))
            created = v.created_at.strftime("%Y-%m-%d %H:%M")
            typer.echo(
                f"{_v(v.version):<8} {tags:<20} {created:<17} {v.created_by or '-':<15} "
                f"{v.commit_message or ''}"
            )


@versions_app.command("show")
def versions_show(
    name: Annotated[str, typer.Argument(help="Prompt name.")],
    version: Annotated[int | None, typer.Argument(help="Version (default: latest).")] = None,
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """Print one version's template, variables and model_config."""
    with _client(url, token, database_url, project) as client:
        v = client.get_version(name, version)
        typer.echo(f"{name} {_v(v.version)} ({v.template_type})  variables: {v.variables}")
        typer.echo(f"model_config: {json.dumps(v.llm_config)}")
        typer.echo("---")
        if isinstance(v.template, str):
            typer.echo(v.template)
        else:
            for m in v.template:
                typer.echo(f"[{m.role}] {m.content}")


@app.command()
def history(
    name: Annotated[str, typer.Argument(help="Prompt name.")],
    tag: Annotated[str | None, typer.Argument(help="Only this tag.")] = None,
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """Show every promote and rollback (newest first): when, from -> to, actor, reason."""
    with _client(url, token, database_url, project) as client:
        events = client.list_tag_events(name, tag)
        if not events:
            typer.echo("No tag moves yet.")
        for e in events:
            when = e.created_at.strftime("%Y-%m-%d %H:%M")
            forced = " (forced)" if e.forced else ""
            reason = f"  reason: {e.reason}" if e.reason else ""
            typer.echo(
                f"{when}  {e.tag:<10} {e.action:<9} {_v(e.from_version):>5} -> "
                f"{_v(e.to_version):<5} by {e.actor or '-'}{forced}{reason}"
            )


# --- changing tags -------------------------------------------------------------------------


@app.command()
def promote(
    name: Annotated[str, typer.Argument(help="Prompt name.")],
    tag: Annotated[str, typer.Argument(help="Tag to move, e.g. prod.")],
    version: Annotated[int, typer.Argument(help="Version to point the tag at.")],
    force: Annotated[
        bool, typer.Option("--force", help="Bypass a failing gate (needs --reason).")
    ] = False,
    actor: ActorOption = None,
    reason: ReasonOption = None,
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """Point a tag at a version (checked against the tag's eval gate)."""
    with _client(url, token, database_url, project, actor) as client:
        result = client.promote(name, tag, version, reason=reason, force=force)
        typer.echo(f"{name}: {tag} -> {_v(result.version)}")


@app.command()
def rollback(
    name: Annotated[str, typer.Argument(help="Prompt name.")],
    tag: Annotated[str, typer.Argument(help="Tag to move back.")],
    actor: ActorOption = None,
    reason: ReasonOption = None,
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """Undo the tag's last promote (run again to keep going back). Never gated."""
    with _client(url, token, database_url, project, actor) as client:
        result = client.rollback(name, tag, reason=reason)
        typer.echo(f"{name}: {tag} rolled back -> {_v(result.version)}")


# --- evals ---------------------------------------------------------------------------------


@evals_app.command("push")
def evals_push(
    file: Annotated[Path, typer.Argument(help="JSON Lines file, one result per line.")],
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """Send eval results (all saved, or none if any line is invalid).

    Each line: {"prompt": "support-bot", "version": 4, "metric": "accuracy", "score": 0.87,
    "run_id": "...", "evaluator": "...", "metadata": {...}}
    """
    from pydantic import ValidationError

    from promptdock.models import EvalResultIn

    if not file.is_file():
        raise _fail(f"{file} not found")
    results = []
    for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            results.append(EvalResultIn.model_validate({"project": project, **json.loads(line)}))
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            raise _fail(f"{file.name} line {number}: {exc}") from None
    with _client(url, token, database_url, project) as client:
        stored = client.add_eval_results(results)
        typer.echo(f"Saved {len(stored)} eval results.")


# --- files ---------------------------------------------------------------------------------


@app.command()
def export(
    directory: Annotated[Path, typer.Argument(help="Folder to write <name>.yaml files to.")],
    prompt: Annotated[
        list[str] | None, typer.Option(help="Only these prompts (repeatable).")
    ] = None,
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """Write one YAML file per prompt with its latest version and current tags."""
    from promptdock.sync import export_prompts

    with _client(url, token, database_url, project) as client:
        written = export_prompts(client, directory, prompt)
        for path in written:
            typer.echo(f"wrote {path}")
        typer.echo(f"Exported {len(written)} prompts to {directory}")


@app.command()
def push(
    directory: Annotated[Path, typer.Argument(help="Folder of <name>.yaml files.")],
    tag: Annotated[
        str | None,
        typer.Option(help="Move this tag (e.g. dev) to each new version. Never prod."),
    ] = None,
    message: Annotated[
        str | None, typer.Option("--message", "-m", help="Commit message for new versions.")
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show what would change, change nothing.")
    ] = False,
    actor: ActorOption = None,
    url: ServerUrlOption = None,
    token: TokenOption = None,
    database_url: DatabaseUrlOption = None,
    project: ProjectOption = DEFAULT_PROJECT,
) -> None:
    """Create a new version for each changed file; never overwrites, moves no tags by default."""
    from promptdock.sync import push_prompts

    with _client(url, token, database_url, project, actor) as client:
        results = push_prompts(client, directory, tag=tag, message=message, dry_run=dry_run)
    prefix = "[dry run] " if dry_run else ""
    failed = False
    for r in results:
        if r.status == "unchanged":
            typer.echo(f"{prefix}{r.name}: unchanged ({_v(r.version)})")
        elif r.status in ("created", "new_version"):
            what = "new prompt" if r.status == "created" else "new version"
            moved = f", {r.tag_moved} -> {_v(r.version)}" if r.tag_moved else ""
            typer.echo(f"{prefix}{r.name}: {what} {_v(r.version)}{moved}")
        if r.warning:
            typer.secho(f"  warning: {r.warning}", fg=typer.colors.YELLOW)
        if r.error:
            failed = True
            typer.secho(f"{r.name}: error: {r.error}", fg=typer.colors.RED, err=True)
    if not results:
        typer.echo(f"No .yaml files in {directory}")
    if failed:
        raise typer.Exit(code=1)
