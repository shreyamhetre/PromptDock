"""FastAPI application factory."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from promptdock import __version__
from promptdock.backends.db import DbBackend
from promptdock.server.access import check_token
from promptdock.server.errors import install_error_handlers
from promptdock.server.routes import public_router, router

TOKEN_ENV = "PROMPTDOCK_TOKEN"


def create_app(database_url: str | None = None, token: str | None = None) -> FastAPI:
    """Build the app. ``database_url`` defaults to ``DATABASE_URL`` and ``token`` to
    ``PROMPTDOCK_TOKEN``. With no token, the server is open to whoever can reach it."""
    backend = DbBackend(database_url, connect_timeout=5)
    token = token if token is not None else os.environ.get(TOKEN_ENV)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        backend.close()

    app = FastAPI(
        title="PromptDock",
        version=__version__,
        description="Immutable prompt versions, movable tags, eval-gated promotion. "
        "If the server sets a token, send `Authorization: Bearer <token>`. "
        "Send `X-Actor: <your name>` to record who made a change.",
        lifespan=lifespan,
    )
    app.state.backend = backend
    app.state.token = token or None
    install_error_handlers(app)
    app.include_router(public_router)
    app.include_router(router, dependencies=[Depends(check_token)])
    return app
