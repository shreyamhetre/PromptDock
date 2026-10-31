"""PromptDock: prompt versioning with immutable versions and movable tags."""

from importlib.metadata import PackageNotFoundError, version

from promptdock.client import Client
from promptdock.errors import (
    DatabaseUnavailableError,
    GateFailedError,
    MissingVariableError,
    NotFoundError,
    PromptDockError,
)
from promptdock.prompt import Prompt

try:
    __version__ = version("promptdock")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0"

__all__ = [
    "Client",
    "DatabaseUnavailableError",
    "GateFailedError",
    "MissingVariableError",
    "NotFoundError",
    "Prompt",
    "PromptDockError",
    "__version__",
]
