import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# CI runs the suite against several Postgres versions by setting this variable.
POSTGRES_IMAGE = os.environ.get("PROMPTDOCK_TEST_POSTGRES_IMAGE", "postgres:16")


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """A Postgres server for the whole test session (needs Docker)."""
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(POSTGRES_IMAGE, driver="psycopg") as container:
        yield container.get_connection_url()


@pytest.fixture
def empty_db_url(postgres_url: str) -> Iterator[str]:
    """URL of a brand-new, empty database, dropped after the test."""
    name = f"test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(postgres_url).set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def engine(empty_db_url: str) -> Iterator[Engine]:
    """Engine for a fresh database migrated to the latest schema."""
    from promptdock.db import migrate

    migrate.upgrade(empty_db_url)
    eng = create_engine(empty_db_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s
