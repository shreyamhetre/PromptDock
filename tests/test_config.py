import pytest
from typer.testing import CliRunner

from promptdock.cli import app
from promptdock.config import resolve_database_url
from promptdock.errors import ConfigError


@pytest.mark.parametrize(
    "url",
    [
        "postgres://u:p@host:5432/db",
        "postgresql://u:p@host:5432/db",
        "postgresql+psycopg://u:p@host:5432/db",
    ],
)
def test_postgres_urls_use_psycopg(url: str) -> None:
    assert resolve_database_url(url) == "postgresql+psycopg://u:p@host:5432/db"


def test_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert resolve_database_url() == "postgresql+psycopg://u:p@host/db"


def test_argument_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@env/db")
    assert resolve_database_url("postgresql://u:p@arg/db").endswith("@arg/db")


def test_missing_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        resolve_database_url()


@pytest.mark.parametrize(
    "url",
    ["sqlite:///x.db", "mysql://u:p@h/db", "postgresql+asyncpg://u:p@h/db", "not a url"],
)
def test_rejects_non_postgres(url: str) -> None:
    with pytest.raises(ConfigError):
        resolve_database_url(url)


def test_cli_migrate_without_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = CliRunner().invoke(app, ["migrate"])
    assert result.exit_code == 1
    assert "No database configured" in result.output
