"""Configuration: resolving and validating DATABASE_URL."""

import os

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from promptdock.errors import ConfigError

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_PROJECT = "default"

_POSTGRES_DRIVERNAMES = {"postgres", "postgresql", "postgresql+psycopg"}


def resolve_database_url(url: str | None = None) -> str:
    """Return a SQLAlchemy URL for Postgres using the psycopg 3 driver.

    Uses ``url`` if given, otherwise the ``DATABASE_URL`` environment variable.
    Plain ``postgres://`` and ``postgresql://`` URLs are rewritten to use psycopg.
    Raises ``ConfigError`` if no URL is set or it does not point at Postgres.
    """
    raw = url if url is not None else os.environ.get(DATABASE_URL_ENV)
    if not raw or not raw.strip():
        raise ConfigError(
            f"No database configured. Pass a database URL or set {DATABASE_URL_ENV}, "
            "e.g. postgresql://user:password@localhost:5432/promptdock"
        )

    try:
        parsed: URL = make_url(raw.strip())
    except ArgumentError as exc:
        raise ConfigError(f"Invalid database URL: {exc}") from None

    if parsed.drivername not in _POSTGRES_DRIVERNAMES:
        raise ConfigError(
            f"PromptDock only supports Postgres (via psycopg 3); got '{parsed.drivername}'. "
            "Use a URL starting with postgresql:// or postgresql+psycopg://"
        )

    return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
