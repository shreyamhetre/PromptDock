import logging
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from promptdock import Client, DatabaseUnavailableError, GateFailedError, MissingVariableError
from promptdock.db import migrate
from promptdock.errors import ConfigError, NotFoundError, TagNotSetError

NAME = "support-bot"


@pytest.fixture
def db_url(empty_db_url: str) -> str:
    migrate.upgrade(empty_db_url)
    return empty_db_url


@pytest.fixture
def client(db_url: str) -> Iterator[Client]:
    with Client(db_url, cache_ttl=0) as c:
        yield c


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
    with pytest.raises(GateFailedError):
        client.promote(NAME, "prod", 2)

    assert [r.score for r in client.get_eval_results(NAME)] == [0.9, 0.5]
    assert {t.name: t.version for t in client.list_tags(NAME)}["prod"] == 1
    assert [e.actor for e in client.get_history(NAME, "prod")] == ["shreya"]
    assert [p.name for p in client.list_prompts()] == [NAME]
    assert [v.version for v in client.list_versions(NAME)] == [1, 2]


def test_projects_are_separate(db_url: str) -> None:
    with Client(db_url, project="team-a") as a, Client(db_url, project="team-b") as b:
        a.create_prompt(NAME)
        a.create_version(NAME, "from a")
        b.create_prompt(NAME)
        b.create_version(NAME, "from b")
        assert a.get_prompt(NAME).render() == "from a"
        assert b.get_prompt(NAME).render() == "from b"


def test_rollback_reaches_other_clients_after_ttl(db_url: str) -> None:
    """Phase 3 'done when': an app sees a rollback after the TTL, with no code change."""
    with Client(db_url) as admin, Client(db_url, cache_ttl=0.5) as app:
        _seed(admin)
        admin.promote(NAME, "prod", 1)
        admin.promote(NAME, "prod", 2)
        assert app.get_prompt(NAME, tag="prod").version == 2

        admin.rollback(NAME, "prod")
        assert app.get_prompt(NAME, tag="prod").version == 2  # still cached
        time.sleep(0.6)
        assert app.get_prompt(NAME, tag="prod").version == 1


def test_own_promote_is_visible_immediately(db_url: str) -> None:
    with Client(db_url, cache_ttl=60) as c:
        _seed(c)
        c.promote(NAME, "prod", 1)
        assert c.get_prompt(NAME, tag="prod").version == 1
        c.promote(NAME, "prod", 2)
        assert c.get_prompt(NAME, tag="prod").version == 2


def test_falls_back_to_last_known_good(db_url: str, caplog: pytest.LogCaptureFixture) -> None:
    with Client(db_url) as admin:
        _seed(admin)
        admin.promote(NAME, "prod", 1)

    with Client(db_url, cache_ttl=0) as app:
        assert app.get_prompt(NAME, tag="prod").is_stale is False
        _drop_database(db_url)

        with caplog.at_level(logging.WARNING, logger="promptdock"):
            prompt = app.get_prompt(NAME, tag="prod")
        assert (prompt.version, prompt.is_stale) == (1, True)
        assert prompt.render(name="Ana") == "v1: Hi Ana"
        assert "last known good" in caplog.text

        with pytest.raises(DatabaseUnavailableError):
            app.get_prompt(NAME, tag="dev")  # never fetched: nothing to fall back to


def test_snapshot_file_covers_cold_start(db_url: str, tmp_path: Path) -> None:
    snapshot = tmp_path / "prompts.json"
    with Client(db_url) as admin:
        _seed(admin)
        admin.promote(NAME, "prod", 1)
    with Client(db_url, snapshot_path=snapshot) as app:
        app.get_prompt(NAME, tag="prod")

    _drop_database(db_url)

    with Client(db_url, snapshot_path=snapshot) as restarted:
        prompt = restarted.get_prompt(NAME, tag="prod")
        assert (prompt.version, prompt.is_stale) == (1, True)


def test_config_errors(db_url: str) -> None:
    with pytest.raises(ConfigError, match="not both"):
        Client(db_url, base_url="http://x")
    with pytest.raises(ConfigError, match="not available yet"):
        Client(base_url="http://x")
    with pytest.raises(ConfigError):
        Client(db_url, cache_ttl=-1)
