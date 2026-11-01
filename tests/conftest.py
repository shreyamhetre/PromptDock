import os
import uuid
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from promptdock import Client
from promptdock.db import migrate

# Token used by the "server+token" client mode.
TOKEN = "s3cret-token"

MakeClient = Callable[..., Client]

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


@pytest.fixture
def db_url(empty_db_url: str) -> str:
    migrate.upgrade(empty_db_url)
    return empty_db_url


@pytest.fixture(params=["library", "server", "server+token"])
def make_client(request: pytest.FixtureRequest, db_url: str) -> Iterator[MakeClient]:
    """Factory for clients in the mode under test; all are closed afterwards."""
    clients: list[Client] = []
    app = None
    if request.param != "library":
        from promptdock.server import create_app

        app = create_app(db_url, token=TOKEN if request.param == "server+token" else "")

    def factory(**kwargs: Any) -> Client:
        if app is None:
            client = Client(db_url, **kwargs)
        else:
            import httpx
            from fastapi.testclient import TestClient

            token = TOKEN if request.param == "server+token" else None
            http = cast(httpx.Client, TestClient(app))
            client = Client(base_url="http://testserver", token=token, http_client=http, **kwargs)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        client.close()
    if app is not None:
        app.state.backend.close()
