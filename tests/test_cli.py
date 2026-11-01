"""Phase 5 'done when': a full flow works from the terminal only, in direct and server mode."""

import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner, Result

from promptdock.cli import app
from promptdock.db import migrate

NAME = "support-bot"
runner = CliRunner()


@pytest.fixture
def db_url(empty_db_url: str) -> str:
    migrate.upgrade(empty_db_url)
    return empty_db_url


@pytest.fixture
def direct(db_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    """Direct mode: only DATABASE_URL is set."""
    monkeypatch.delenv("PROMPTDOCK_URL", raising=False)
    monkeypatch.delenv("PROMPTDOCK_TOKEN", raising=False)
    monkeypatch.setenv("DATABASE_URL", db_url)
    return db_url


@pytest.fixture
def server(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Server mode: a real uvicorn server with a token; the CLI only knows its URL."""
    import uvicorn

    from promptdock.server import create_app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    config = uvicorn.Config(create_app(db_url, token="team-secret"), port=port, log_level="error")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    while not srv.started:
        time.sleep(0.05)

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PROMPTDOCK_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("PROMPTDOCK_TOKEN", "team-secret")
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    thread.join(timeout=5)


def run(*args: str) -> Result:
    result = runner.invoke(app, list(args))
    return result


def ok(*args: str) -> str:
    result = run(*args)
    assert result.exit_code == 0, result.output
    return result.output


def _write(folder: Path, name: str, template: object, **extra: object) -> Path:
    folder.mkdir(exist_ok=True)
    path = folder / f"{name}.yaml"
    path.write_text(yaml.safe_dump({"name": name, "template": template, **extra}), encoding="utf-8")
    return path


def _full_flow(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    _write(prompts, NAME, "Hi {{ user }}!", model_config={"model": "gpt-4o"})

    # 1. push creates the prompt and v1; no tags move
    assert "support-bot: new prompt v1" in ok("push", str(prompts), "--actor", "shreya")
    assert "prod=-" in ok("prompts", "list")

    # 2. evals, then promote through a gate from the terminal
    evals = tmp_path / "results.jsonl"
    evals.write_text(
        json.dumps({"prompt": NAME, "version": 1, "metric": "accuracy", "score": 0.9}) + "\n"
    )
    assert "Saved 1 eval results" in ok("evals", "push", str(evals))
    assert "prod -> v1" in ok("promote", NAME, "prod", "1", "--actor", "shreya")

    # 3. edit the file, push with --tag dev: new version, dev moves, prod stays
    _write(prompts, NAME, "Hello {{ user }}, ask me anything.", model_config={"model": "gpt-4o"})
    out = ok("push", str(prompts), "--tag", "dev", "-m", "friendlier", "--actor", "parth")
    assert "support-bot: new version v2, dev -> v2" in out
    assert "unchanged (v2)" in ok("push", str(prompts))  # pushing again changes nothing

    listing = ok("versions", "list", NAME)
    assert "v2       dev" in listing and "v1       prod" in listing
    assert "friendlier" in listing and "parth" in listing
    assert "Hello {{ user }}" in ok("versions", "show", NAME)

    # 4. push can never move prod
    refused = run("push", str(prompts), "--tag", "prod")
    assert refused.exit_code == 1 and "never move 'prod'" in refused.output

    # 5. promote v2 to prod, roll back, read the history
    ok("promote", NAME, "prod", "2", "--actor", "shreya", "--reason", "release")
    assert "prod rolled back -> v1" in ok("rollback", NAME, "prod", "--reason", "complaints")
    history = ok("history", NAME, "prod")
    assert "rollback     v2 -> v1" in history and "reason: complaints" in history
    assert "by shreya" in history and "reason: release" in history


def test_full_flow_direct_mode(direct: str, tmp_path: Path) -> None:
    _full_flow(tmp_path)


def test_full_flow_server_mode(server: str, tmp_path: Path) -> None:
    _full_flow(tmp_path)


def test_wrong_token_is_reported(server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMPTDOCK_TOKEN", "wrong")
    result = run("prompts", "list")
    assert result.exit_code == 1 and "Error:" in result.output


def test_not_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "PROMPTDOCK_URL"):
        monkeypatch.delenv(var, raising=False)
    result = run("prompts", "list")
    assert result.exit_code == 1 and "Not connected" in result.output


def test_export_then_push_round_trip(direct: str, tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    chat = [
        {"role": "system", "content": "You support {{ product }}.\nBe brief."},
        {"role": "user", "content": "{{ question }}"},
    ]
    _write(prompts, NAME, chat, description="FAQ bot", model_config={"temperature": 0.2})
    ok("push", str(prompts))
    ok("promote", NAME, "dev", "1")

    exported = tmp_path / "exported"
    assert "Exported 1 prompts" in ok("export", str(exported))
    data = yaml.safe_load((exported / f"{NAME}.yaml").read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["template"] == chat
    assert data["model_config"] == {"temperature": 0.2}
    assert data["description"] == "FAQ bot"
    assert data["tags"] == {"dev": 1, "preprod": None, "prod": None}
    # multi-line text is written as a readable block
    assert "content: |-" in (exported / f"{NAME}.yaml").read_text(encoding="utf-8")

    assert "unchanged (v1)" in ok("push", str(exported))


def test_push_warns_when_database_is_newer(direct: str, tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    _write(prompts, NAME, "one")
    ok("push", str(prompts))
    exported = tmp_path / "exported"
    ok("export", str(exported))  # file says version: 1

    _write(prompts, NAME, "two")
    ok("push", str(prompts))  # someone else creates v2

    edited = yaml.safe_load((exported / f"{NAME}.yaml").read_text(encoding="utf-8"))
    edited["template"] = "three"
    (exported / f"{NAME}.yaml").write_text(yaml.safe_dump(edited), encoding="utf-8")
    out = ok("push", str(exported))
    assert "new version v3" in out
    assert "database has v2, newer than v1" in out


def test_push_dry_run_changes_nothing(direct: str, tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    _write(prompts, NAME, "one")
    assert "[dry run] support-bot: new prompt v1" in ok("push", str(prompts), "--dry-run")
    assert "No prompts yet" in ok("prompts", "list")


def test_push_reports_bad_files_and_continues(direct: str, tmp_path: Path) -> None:
    prompts = tmp_path / "prompts"
    _write(prompts, "good", "fine {{ x }}")
    _write(prompts, "broken", "{{ unclosed")
    result = run("push", str(prompts))
    assert result.exit_code == 1
    assert "good: new prompt v1" in result.output
    assert "broken: error" in result.output


def test_promote_refused_by_gate(direct: str, tmp_path: Path) -> None:
    from promptdock import Client

    with Client(direct) as client:
        client.create_prompt(NAME)
        client.create_version(NAME, "x")
        client.set_gate(NAME, "prod", {"rules": [{"metric": "accuracy", "min": 0.8}]})
    refused = run("promote", NAME, "prod", "1")
    assert refused.exit_code == 1
    assert "accuracy: no eval result" in refused.output
    forced = ok("promote", NAME, "prod", "1", "--force", "--reason", "hotfix")
    assert "prod -> v1" in forced


def test_evals_push_rejects_bad_lines(direct: str, tmp_path: Path) -> None:
    bad = tmp_path / "results.jsonl"
    bad.write_text('{"prompt": "x", "version": 1, "metric": "m", "score": "high"}\n')
    result = run("evals", "push", str(bad))
    assert result.exit_code == 1 and "line 1" in result.output
