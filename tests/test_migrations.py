import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from typer.testing import CliRunner

from promptdock.cli import app
from promptdock.db import migrate
from promptdock.db.tables import Base

EXPECTED_TABLES = {
    "projects",
    "prompts",
    "prompt_versions",
    "tags",
    "tag_events",
    "eval_results",
    "api_keys",
}


def test_upgrade_creates_all_tables_and_default_project(empty_db_url: str) -> None:
    assert migrate.current_revision(empty_db_url) is None

    assert migrate.upgrade(empty_db_url) == "0003"

    engine = create_engine(empty_db_url)
    try:
        assert set(inspect(engine).get_table_names()) >= EXPECTED_TABLES
        with engine.connect() as conn:
            assert conn.execute(text("SELECT name FROM projects")).scalars().all() == ["default"]
    finally:
        engine.dispose()


def test_upgrade_is_idempotent(empty_db_url: str) -> None:
    migrate.upgrade(empty_db_url)
    assert migrate.upgrade(empty_db_url) == "0003"


def test_migrations_match_table_definitions(empty_db_url: str) -> None:
    migrate.upgrade(empty_db_url)
    engine = create_engine(empty_db_url)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": True})
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()
    assert diff == []


def test_downgrade_removes_tables(empty_db_url: str) -> None:
    migrate.upgrade(empty_db_url)
    assert migrate.downgrade(empty_db_url) is None

    engine = create_engine(empty_db_url)
    try:
        assert not (EXPECTED_TABLES & set(inspect(engine).get_table_names()))
    finally:
        engine.dispose()


def test_constraints_are_enforced(empty_db_url: str) -> None:
    migrate.upgrade(empty_db_url)
    engine = create_engine(empty_db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO prompts (project_id, name) VALUES (1, 'support-bot')"))
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(text("INSERT INTO prompts (project_id, name) VALUES (1, 'support-bot')"))
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO prompt_versions (prompt_id, version, template_type, template,"
                    " content_hash) VALUES (1, 1, 'html', '\"hi\"', 'x')"
                )
            )
    finally:
        engine.dispose()


def test_cli_migrate(empty_db_url: str) -> None:
    result = CliRunner().invoke(app, ["migrate", "--database-url", empty_db_url])
    assert result.exit_code == 0, result.output
    assert "revision 0003" in result.stdout


def test_cli_migrate_reads_env(empty_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", empty_db_url)
    result = CliRunner().invoke(app, ["migrate"])
    assert result.exit_code == 0, result.output


def test_cli_migrate_unreachable_database() -> None:
    result = CliRunner().invoke(
        app,
        ["migrate", "--database-url", "postgresql://u:p@127.0.0.1:1/nodb?connect_timeout=2"],
    )
    assert result.exit_code == 1
    assert "Could not connect" in result.output
