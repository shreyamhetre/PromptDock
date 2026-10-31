"""PromptDock: prompt versioning with immutable versions and movable tags."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("promptdock")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
