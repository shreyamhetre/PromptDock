"""Alembic environment.

``promptdock migrate`` passes an open connection via ``config.attributes["connection"]``.
When run through the ``alembic`` CLI (for writing new migrations), the URL comes from
``DATABASE_URL``.
"""

from alembic import context
from sqlalchemy import Connection

from promptdock.db.engine import make_engine
from promptdock.db.tables import Base

target_metadata = Base.metadata


def run_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_with_connection(connection)
        return

    engine = make_engine()
    try:
        with engine.connect() as conn:
            run_with_connection(conn)
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported; connect to a database instead.")

run_migrations_online()
