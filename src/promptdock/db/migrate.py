"""Run Alembic migrations programmatically (used by ``promptdock migrate``)."""

from collections.abc import Callable
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy.exc import OperationalError

from promptdock.db.engine import make_engine
from promptdock.errors import DatabaseUnavailableError

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def alembic_config() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    return cfg


def upgrade(database_url: str | None = None, revision: str = "head") -> str | None:
    """Upgrade the database to ``revision`` and return the resulting revision id."""
    return _run(database_url, lambda cfg: command.upgrade(cfg, revision))


def downgrade(database_url: str | None = None, revision: str = "base") -> str | None:
    """Downgrade the database to ``revision`` and return the resulting revision id."""
    return _run(database_url, lambda cfg: command.downgrade(cfg, revision))


def current_revision(database_url: str | None = None) -> str | None:
    """Return the database's current revision id, or None if it was never migrated."""
    return _run(database_url, lambda cfg: None)


def _run(database_url: str | None, action: Callable[[Config], None]) -> str | None:
    engine = make_engine(database_url)
    try:
        with engine.begin() as connection:
            cfg = alembic_config()
            cfg.attributes["connection"] = connection
            action(cfg)
            return MigrationContext.configure(connection).get_current_revision()
    except OperationalError as exc:
        raise DatabaseUnavailableError(f"Could not connect to the database: {exc.orig}") from None
    finally:
        engine.dispose()
