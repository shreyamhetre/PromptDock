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
}


def test_upgrade_creates_all_tables_and_default_project(empty_db_url: str) -> None:
    assert migrate.current_revision(empty_db_url) is None

    assert migrate.upgrade(empty_db_url) == "0004"

    engine = create_engine(empty_db_url)
    try:
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES | {"alembic_version"}
        with engine.connect() as conn:
            assert conn.execute(text("SELECT name FROM projects")).scalars().all() == ["default"]
    finally:
        engine.dispose()


def test_upgrade_is_idempotent(empty_db_url: str) -> None:
    migrate.upgrade(empty_db_url)
    assert migrate.upgrade(empty_db_url) == "0004"


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
    assert "revision 0004" in result.stdout


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


def test_data_survives_upgrades_from_the_first_schema(empty_db_url: str) -> None:
    """Data written at revision 0001 is intact and usable after upgrading to head."""
    from sqlalchemy.orm import Session

    from promptdock.core import service
    from promptdock.models import PromptVersionCreate

    migrate.upgrade(empty_db_url, "0001")
    engine = create_engine(empty_db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO prompts (project_id, name) VALUES (1, 'old-bot')"))
            conn.execute(
                text(
                    "INSERT INTO prompt_versions (prompt_id, version, template_type, template,"
                    " variables, content_hash) VALUES (1, 1, 'text', '\"Hi {{ u }}\"', '[\"u\"]',"
                    " 'h1')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO tags (prompt_id, name, version_id, is_protected)"
                    " VALUES (1, 'prod', 1, true)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO tag_events (tag_id, to_version_id, action, actor)"
                    " VALUES (1, 1, 'promote', 'shreya')"
                )
            )
            conn.execute(
                text("INSERT INTO api_keys (name, key_hash, scopes) VALUES ('k', 'x', '[]')")
            )

        assert migrate.upgrade(empty_db_url) == "0004"

        with Session(engine) as session:
            assert service.get_by_tag(session, "old-bot", "prod").template == "Hi {{ u }}"
            assert service.list_tag_events(session, "old-bot", "prod")[0].actor == "shreya"
            service.create_version(
                session, "old-bot", PromptVersionCreate(template="Hello {{ u }}")
            )
            assert service.promote(session, "old-bot", "prod", 2).version == 2
            session.commit()
    finally:
        engine.dispose()


def test_full_downgrade_and_upgrade_round_trip(empty_db_url: str) -> None:
    migrate.upgrade(empty_db_url)
    for revision in ("0003", "0002", "0001", "base"):
        migrate.downgrade(empty_db_url, revision)
    assert migrate.upgrade(empty_db_url) == "0004"
