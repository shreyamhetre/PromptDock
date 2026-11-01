"""Connecting from tools (CLI, MCP) the same way everywhere.

``PROMPTDOCK_URL`` (+ ``PROMPTDOCK_TOKEN`` if the server has one) means server mode;
otherwise ``DATABASE_URL`` means direct mode. There is no config file.
"""

from promptdock.client import Client
from promptdock.config import DEFAULT_PROJECT
from promptdock.errors import ConfigError


def connect(
    url: str | None,
    token: str | None,
    database_url: str | None,
    project: str = DEFAULT_PROJECT,
    actor: str | None = None,
    cache_ttl: float = 0,
) -> Client:
    """Build a Client from explicit settings (callers pass the environment's values)."""
    if url:
        return Client(base_url=url, token=token, project=project, actor=actor, cache_ttl=cache_ttl)
    if database_url:
        return Client(database_url, project=project, actor=actor, cache_ttl=cache_ttl)
    raise ConfigError(
        "Not connected. Set PROMPTDOCK_URL (server mode) or DATABASE_URL (direct mode)"
    )
