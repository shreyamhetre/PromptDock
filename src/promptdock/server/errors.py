"""Map PromptDock exceptions to HTTP responses.

Error bodies look like ``{"error": {"type": "GateFailedError", "message": "..."}}`` so the
HTTP backend can raise the same exception class on the client side.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from promptdock.errors import (
    AlreadyExistsError,
    AuthenticationError,
    GateFailedError,
    InvalidInputError,
    NewVariablesError,
    NotFoundError,
    NothingToRollBackError,
    PromptDockError,
    UnavailableError,
)

# Checked in order; subclasses must come before their base classes.
STATUS_CODES: list[tuple[type[PromptDockError], int]] = [
    (AuthenticationError, 401),
    (NotFoundError, 404),
    (AlreadyExistsError, 409),
    (GateFailedError, 409),
    (NothingToRollBackError, 409),
    (NewVariablesError, 409),
    (InvalidInputError, 422),
    (UnavailableError, 503),
]


def status_for(exc: PromptDockError) -> int:
    for cls, status in STATUS_CODES:
        if isinstance(exc, cls):
            return status
    return 500


def error_body(exc: PromptDockError) -> dict[str, Any]:
    body: dict[str, Any] = {"type": type(exc).__name__, "message": str(exc)}
    if isinstance(exc, GateFailedError):
        body.update(prompt=exc.prompt, tag=exc.tag, failures=exc.failures)
    return {"error": body}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PromptDockError)
    async def _handle(request: Request, exc: PromptDockError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
        return JSONResponse(status_code=status_for(exc), content=error_body(exc), headers=headers)
