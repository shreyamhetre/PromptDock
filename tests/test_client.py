"""Client tests. Every test using ``make_client`` runs in three modes: library (straight to
Postgres), server without a token, and server with a token. All must behave the same."""

import logging
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from promptdock import Client, GateFailedError, MissingVariableError
from promptdock.errors import ConfigError, NotFoundError, TagNotSetError, UnavailableError

NAME = "support-bot"
MakeClient = Callable[..., Client]


@pytest.fixture
def client(make_client: MakeClient) -> Client:
    return make_client(cache_ttl=0)


def _seed(client: Client) -> None:
    client.create_prompt(NAME)
    client.create_version(NAME, "v1: Hi {{ name }}", model_config={"model": "gpt-4o"})
    client.create_version(
        NAME,
        [{"role": "system", "content": "v2"}, {"role": "user", "content": "{{ question }}"}],
    )


def _drop_database(url: str) -> None:
    admin_url = make_url(url).set(database="postgres")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE "{make_url(url).database}" WITH (FORCE)'))
    admin.dispose()


def test_get_prompt_by_tag_version_and_latest(client: Client) -> None:
    _seed(client)
    client.promote(NAME, "prod", 1)

    prod = client.get_prompt(NAME, tag="prod")
    assert (prod.name, prod.version, prod.tag) == (NAME, 1, "prod")
    assert prod.model_config == {"model": "gpt-4o"}
    assert prod.render(name="Ana") == "v1: Hi Ana"

    assert client.get_prompt(NAME, version=2).render(question="Why?") == [
        {"role": "system", "content": "v2"},
        {"role": "user", "content": "Why?"},
    ]
    assert client.get_prompt(NAME).version == 2


def test_render_reports_missing_variables(client: Client) -> None:
    _seed(client)
    with pytest.raises(MissingVariableError, match="name"):
        client.get_prompt(NAME, version=1).render()


def test_errors(client: Client) -> None:
    _seed(client)
    with pytest.raises(TagNotSetError):
        client.get_prompt(NAME, tag="prod")
    with pytest.raises(NotFoundError):
        client.get_prompt("nope")
    with pytest.raises(ValueError):
        client.get_prompt(NAME, tag="prod", version=1)


def test_full_flow_through_client(client: Client) -> None:
    _seed(client)
    client.set_gate(NAME, "prod", {"rules": [{"metric": "accuracy", "min": 0.85}]})
    client.add_eval_results(
        [
            {"prompt": NAME, "version": 1, "metric": "accuracy", "score": 0.9},
            {"prompt": NAME, "version": 2, "metric": "accuracy", "score": 0.5},
        ]
    )
    client.promote(NAME, "prod", 1, actor="shreya")
    with pytest.raises(GateFailedError) as refused:
        client.promote(NAME, "prod", 2)
    assert refused.value.failures == ["accuracy: 0.5 is below the minimum 0.85"]

    client.promote(NAME, "prod", 2, reason="hotfix", force=True)
    client.rollback(NAME, "prod", reason="bad answers")

    assert [r.score for r in client.get_eval_results(NAME)] == [0.9, 0.5]
    assert {t.name: t.version for t in client.list_tags(NAME)}["prod"] == 1
    events = client.list_tag_events(NAME, "prod")
    assert [(e.action, e.forced, e.reason) for e in events] == [
        ("rollback", False, "bad answers"),
        ("promote", True, "hotfix"),
        ("promote", False, None),
    ]
    assert events[2].actor == "shreya"
    assert len(client.list_tag_events(NAME)) == 3
    assert [p.name for p in client.list_prompts()] == [NAME]
    assert [v.version for v in client.list_versions(NAME)] == [1, 2]


def test_projects_are_separate(make_client: MakeClient) -> None:
    a, b = make_client(project="team-a"), make_client(project="team-b")
    a.create_prompt(NAME)
    a.create_version(NAME, "from a")
    b.create_prompt(NAME)
    b.create_version(NAME, "from b")
    assert a.get_prompt(NAME).render() == "from a"
    assert b.get_prompt(NAME).render() == "from b"


def test_rollback_reaches_other_clients_after_ttl(make_client: MakeClient) -> None:
    """Phase 3 'done when': an app sees a rollback after the TTL, with no code change."""
    admin, app = make_client(), make_client(cache_ttl=0.5)
    _seed(admin)
    admin.promote(NAME, "prod", 1)
    admin.promote(NAME, "prod", 2)
    assert app.get_prompt(NAME, tag="prod").version == 2

    admin.rollback(NAME, "prod")
    assert app.get_prompt(NAME, tag="prod").version == 2  # still cached
    time.sleep(0.6)
    assert app.get_prompt(NAME, tag="prod").version == 1


def test_own_promote_is_visible_immediately(make_client: MakeClient) -> None:
    c = make_client(cache_ttl=60)
    _seed(c)
    c.promote(NAME, "prod", 1)
    assert c.get_prompt(NAME, tag="prod").version == 1
    c.promote(NAME, "prod", 2)
    assert c.get_prompt(NAME, tag="prod").version == 2


def test_falls_back_to_last_known_good(
    make_client: MakeClient, db_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    admin = make_client()
    _seed(admin)
    admin.promote(NAME, "prod", 1)

    app = make_client(cache_ttl=0)
    assert app.get_prompt(NAME, tag="prod").is_stale is False
    _drop_database(db_url)

    with caplog.at_level(logging.WARNING, logger="promptdock"):
        prompt = app.get_prompt(NAME, tag="prod")
    assert (prompt.version, prompt.is_stale) == (1, True)
    assert prompt.render(name="Ana") == "v1: Hi Ana"
    assert "last known good" in caplog.text

    with pytest.raises(UnavailableError):
        app.get_prompt(NAME, tag="dev")  # never fetched: nothing to fall back to


def test_snapshot_file_covers_cold_start(
    make_client: MakeClient, db_url: str, tmp_path: Path
) -> None:
    snapshot = tmp_path / "prompts.json"
    admin = make_client()
    _seed(admin)
    admin.promote(NAME, "prod", 1)
    make_client(snapshot_path=snapshot).get_prompt(NAME, tag="prod")

    _drop_database(db_url)

    prompt = make_client(snapshot_path=snapshot).get_prompt(NAME, tag="prod")
    assert (prompt.version, prompt.is_stale) == (1, True)


def test_actor_defaults_to_os_username(
    make_client: MakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("getpass.getuser", lambda: "os-user")
    c = make_client()
    assert c.actor == "os-user"
    _seed(c)
    c.promote(NAME, "prod", 1)
    assert c.list_versions(NAME)[0].created_by == "os-user"
    assert c.list_tag_events(NAME, "prod")[0].actor == "os-user"


def test_actor_setting_is_used_for_every_write(make_client: MakeClient) -> None:
    c = make_client(actor="Shreya Mhetre")
    _seed(c)
    c.set_gate(NAME, "prod", {"rules": [{"metric": "accuracy", "min": 0.5}]})
    assert {t.name: t.updated_by for t in c.list_tags(NAME)}["prod"] == "Shreya Mhetre"
    c.set_gate(NAME, "prod", None)

    c.promote(NAME, "prod", 1)
    c.promote(NAME, "prod", 2, actor="pärth")  # per-call override, non-ASCII
    c.rollback(NAME, "prod", reason="bad")
    assert [(e.action, e.actor) for e in c.list_tag_events(NAME, "prod")] == [
        ("rollback", "Shreya Mhetre"),
        ("promote", "pärth"),
        ("promote", "Shreya Mhetre"),
    ]
    assert {v.created_by for v in c.list_versions(NAME)} == {"Shreya Mhetre"}


def test_unknown_os_user_records_no_actor(monkeypatch: pytest.MonkeyPatch) -> None:
    from promptdock.actor import default_actor

    def fail() -> str:
        raise OSError("no user")

    monkeypatch.setattr("getpass.getuser", fail)
    assert default_actor() is None


def test_config_errors(db_url: str) -> None:
    with pytest.raises(ConfigError, match="not both"):
        Client(db_url, base_url="http://x")
    with pytest.raises(ConfigError):
        Client(db_url, cache_ttl=-1)
