"""REST server (``pip install promptdock[server]``, run with ``promptdock serve``)."""

from promptdock.server.app import create_app

__all__ = ["create_app"]
