"""Engine creation."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from promptdock.config import resolve_database_url

DEFAULT_CONNECT_TIMEOUT_S = 10


def make_engine(database_url: str | None = None) -> Engine:
    """Create an engine for ``database_url`` (or ``DATABASE_URL`` from the environment).

    Connections time out after 10 seconds unless the URL sets ``connect_timeout``.
    """
    url = make_url(resolve_database_url(database_url))
    connect_args = {}
    if "connect_timeout" not in url.query:
        connect_args["connect_timeout"] = DEFAULT_CONNECT_TIMEOUT_S
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)
