from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from promptdock.cli import app as cli
from promptdock.db import migrate
from promptdock.server import create_app

NAME = "support-bot"
TOKEN = "team-secret"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def db_url(empty_db_url: str) -> str:
    migrate.upgrade(empty_db_url)
    return empty_db_url


@pytest.fixture
def api(db_url: str) -> Iterator[TestClient]:
    """A server with no token: open to whoever can reach it."""
    with TestClient(create_app(db_url, token="")) as client:
        yield client


@pytest.fixture
def locked(db_url: str) -> Iterator[TestClient]:
    """A server with a shared token."""
    with TestClient(create_app(db_url, token=TOKEN)) as client:
        yield client


def _seed(api: TestClient, headers: dict[str, str] | None = None) -> None:
    headers = headers or {}
    assert api.post("/prompts", json={"name": NAME}, headers=headers).status_code == 201
    for text in ("v1 {{ x }}", "v2 {{ x }}"):
        r = api.post(f"/prompts/{NAME}/versions", json={"template": text}, headers=headers)
        assert r.status_code == 201


def test_health(api: TestClient, locked: TestClient) -> None:
    assert api.get("/health").json() == {"status": "ok"}
    assert locked.get("/health").json() == {"status": "ok"}  # never needs the token


def test_without_token_everything_is_open(api: TestClient) -> None:
    _seed(api)
    assert api.put(f"/prompts/{NAME}/tags/prod", json={"version": 1}).status_code == 200


def test_token_is_required_when_set(locked: TestClient) -> None:
    missing = locked.get("/prompts")
    assert missing.status_code == 401
    assert missing.json()["error"]["type"] == "AuthenticationError"
    assert missing.headers["WWW-Authenticate"] == "Bearer"

    wrong = locked.get("/prompts", headers={"Authorization": "Bearer nope"})
    assert (wrong.status_code, wrong.json()["error"]["message"]) == (401, "Wrong token")

    _seed(locked, AUTH)
    assert locked.get("/prompts", headers=AUTH).status_code == 200
    promoted = locked.put(f"/prompts/{NAME}/tags/prod", json={"version": 1}, headers=AUTH)
    assert promoted.status_code == 200


def test_token_from_environment(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROMPTDOCK_TOKEN", "from-env")
    with TestClient(create_app(db_url)) as api:
        assert api.get("/prompts").status_code == 401
        ok = api.get("/prompts", headers={"Authorization": "Bearer from-env"})
        assert ok.status_code == 200


def test_actor_comes_from_x_actor_header(api: TestClient) -> None:
    api.post("/prompts", json={"name": NAME})
    api.post(f"/prompts/{NAME}/versions", json={"template": "a"}, headers={"X-Actor": "shreya"})
    api.post(f"/prompts/{NAME}/versions", json={"template": "b"})  # no header -> null
    api.put(f"/prompts/{NAME}/tags/prod", json={"version": 1}, headers={"X-Actor": "ci"})
    api.put(f"/prompts/{NAME}/tags/prod", json={"version": 2}, headers={"X-Actor": "P%C3%A4rth"})
    api.post(
        f"/prompts/{NAME}/tags/prod/rollback",
        json={"reason": "broken"},
        headers={"X-Actor": "shreya"},
    )

    versions = api.get(f"/prompts/{NAME}/versions").json()
    assert [v["created_by"] for v in versions] == ["shreya", None]
    events = api.get(f"/prompts/{NAME}/tags/prod/events").json()
    assert [(e["action"], e["actor"], e["reason"]) for e in events] == [
        ("rollback", "shreya", "broken"),
        ("promote", "Pärth", None),
        ("promote", "ci", None),
    ]
    assert [e["from_version"] for e in events] == [2, 1, None]


def test_events_for_all_tags(api: TestClient) -> None:
    _seed(api)
    api.put(f"/prompts/{NAME}/tags/dev", json={"version": 2})
    api.put(f"/prompts/{NAME}/tags/prod", json={"version": 1})
    events = api.get(f"/prompts/{NAME}/events").json()
    assert [(e["tag"], e["to_version"]) for e in events] == [("prod", 1), ("dev", 2)]


def test_hot_path_and_etag(api: TestClient) -> None:
    _seed(api)
    api.put(f"/prompts/{NAME}/tags/prod", json={"version": 1})

    first = api.get(f"/prompts/{NAME}", params={"tag": "prod"})
    assert first.status_code == 200
    assert (first.json()["version"], first.json()["model_config"]) == (1, {})
    etag = first.headers["ETag"]

    unchanged = api.get(f"/prompts/{NAME}", params={"tag": "prod"}, headers={"If-None-Match": etag})
    assert (unchanged.status_code, unchanged.content) == (304, b"")

    api.put(f"/prompts/{NAME}/tags/prod", json={"version": 2})
    moved = api.get(f"/prompts/{NAME}", params={"tag": "prod"}, headers={"If-None-Match": etag})
    assert (moved.status_code, moved.json()["version"]) == (200, 2)


def test_error_responses(api: TestClient) -> None:
    _seed(api)

    missing = api.get("/prompts/nope")
    assert (missing.status_code, missing.json()["error"]["type"]) == (404, "PromptNotFoundError")
    assert api.post("/prompts", json={"name": NAME}).status_code == 409

    api.put(
        f"/prompts/{NAME}/tags/prod/gate",
        json={"gate": {"rules": [{"metric": "accuracy", "min": 0.9}]}},
    )
    refused = api.put(f"/prompts/{NAME}/tags/prod", json={"version": 1})
    assert refused.status_code == 409
    assert refused.json()["error"]["failures"] == ["accuracy: no eval result for this version"]

    no_reason = api.put(f"/prompts/{NAME}/tags/prod", json={"version": 1, "force": True})
    assert no_reason.status_code == 422
    forced = api.put(
        f"/prompts/{NAME}/tags/prod", json={"version": 1, "force": True, "reason": "hotfix"}
    )
    assert forced.status_code == 200

    assert api.put(f"/prompts/{NAME}/tags/prod", json={"version": "x"}).status_code == 422
    bad_template = api.post(f"/prompts/{NAME}/versions", json={"template": "{{ oops"})
    assert bad_template.json()["error"]["type"] == "InvalidTemplateError"


def test_health_reports_database_down(db_url: str) -> None:
    with TestClient(create_app(db_url + "_missing", token="")) as api:
        assert api.get("/health").status_code == 503


@pytest.mark.parametrize(
    ("args", "warns"),
    [
        ([], False),
        (["--host", "0.0.0.0"], True),
        (["--host", "0.0.0.0", "--token", "t"], False),
    ],
)
def test_serve_warns_when_exposed_without_token(
    db_url: str, monkeypatch: pytest.MonkeyPatch, args: list[str], warns: bool
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.append(kw))
    monkeypatch.delenv("PROMPTDOCK_TOKEN", raising=False)

    result = CliRunner().invoke(cli, ["serve", "--database-url", db_url, *args])
    assert result.exit_code == 0, result.output
    assert ("WARNING" in result.output) is warns
    assert calls[0]["host"] == (args[1] if args else "127.0.0.1")
