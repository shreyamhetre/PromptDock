"""Who can reach the server, and who they say they are.

There are no user accounts or API keys. Teams control access by where the server runs
(it binds to 127.0.0.1 by default) and, optionally, one shared token: if the server has
a token, every request except /health must send ``Authorization: Bearer <token>``.

The actor is self-reported in the ``X-Actor`` header (URL-encoded so any name fits in
a header). It is recorded, not verified, like a git author.
"""

import secrets
from typing import Annotated
from urllib.parse import unquote

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from promptdock.backends.db import DbBackend
from promptdock.errors import AuthenticationError

_bearer = HTTPBearer(
    auto_error=False,
    description="Only needed if the server sets PROMPTDOCK_TOKEN.",
)


def get_backend(request: Request) -> DbBackend:
    backend: DbBackend = request.app.state.backend
    return backend


def check_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    """Dependency: if the server has a token, the request must carry it."""
    expected: str | None = request.app.state.token
    if expected is None:
        return
    if credentials is None:
        raise AuthenticationError(
            "This server requires a token: send 'Authorization: Bearer <token>'"
        )
    if not secrets.compare_digest(credentials.credentials.encode(), expected.encode()):
        raise AuthenticationError("Wrong token")


def get_actor(x_actor: Annotated[str | None, Header()] = None) -> str | None:
    """The self-reported actor from the X-Actor header; missing means unknown (null)."""
    if x_actor is None:
        return None
    actor = unquote(x_actor).strip()
    return actor or None


Backend = Annotated[DbBackend, Depends(get_backend)]
Actor = Annotated[str | None, Depends(get_actor)]
