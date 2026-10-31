"""The PromptDock ``Client``: one API whether you talk to Postgres or to a server."""

import logging
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from types import TracebackType
from typing import Any

from promptdock.backends.base import Backend
from promptdock.cache import PromptCache
from promptdock.config import DEFAULT_PROJECT
from promptdock.errors import ConfigError, DatabaseUnavailableError
from promptdock.models import (
    ChatMessage,
    EvalResult,
    EvalResultIn,
    Gate,
    PromptInfo,
    PromptVersion,
    PromptVersionCreate,
    Tag,
    TagEvent,
)
from promptdock.prompt import Prompt

logger = logging.getLogger("promptdock")

DEFAULT_CACHE_TTL_S = 60.0
DEFAULT_CONNECT_TIMEOUT_S = 5


class Client:
    """Read and manage versioned prompts.

    Library mode (talks to Postgres directly)::

        client = Client(db_url="postgresql://...")   # or set DATABASE_URL

    Server mode (talks to a ``promptdock serve`` instance)::

        client = Client(base_url="https://prompts.internal", api_key="...")

    ``get_prompt`` results are cached for ``cache_ttl`` seconds (0 disables caching).
    If the database or server is unreachable, ``get_prompt`` returns the last version it
    fetched successfully and logs a warning. Set ``snapshot_path`` to also keep those
    copies in a JSON file, so a freshly started app can fall back to them.
    ``connect_timeout`` (seconds) bounds how long a call waits for an unreachable database.
    """

    def __init__(
        self,
        db_url: str | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        project: str = DEFAULT_PROJECT,
        cache_ttl: float = DEFAULT_CACHE_TTL_S,
        snapshot_path: str | Path | None = None,
        connect_timeout: int = DEFAULT_CONNECT_TIMEOUT_S,
    ) -> None:
        if db_url is not None and base_url is not None:
            raise ConfigError("Pass either db_url or base_url, not both")
        if base_url is not None:
            raise ConfigError(
                "Server mode (base_url) is not available yet; use db_url or DATABASE_URL"
            )
        if cache_ttl < 0:
            raise ConfigError("cache_ttl must be zero or positive")

        from promptdock.backends.db import DbBackend

        self._backend: Backend = DbBackend(db_url, connect_timeout)
        self.project = project
        self._cache = PromptCache(cache_ttl, snapshot_path)

    # --- reading prompts (cached, with fallback) -----------------------------------------

    def get_prompt(
        self, name: str, *, tag: str | None = None, version: int | None = None
    ) -> Prompt:
        """Fetch a prompt by tag, by version number, or (with neither) its latest version.

        Returns a ``Prompt`` with ``.render(**values)``, ``.version`` and ``.model_config``.
        """
        if tag is not None and version is not None:
            raise ValueError("Pass tag or version, not both")

        if version is not None:
            key = self._key(name, f"version:{version}")
        elif tag is not None:
            key = self._key(name, f"tag:{tag}")
        else:
            key = self._key(name, "latest")

        cached = self._cache.get_fresh(key)
        if cached is not None:
            value, is_stale = cached
            return Prompt(value, tag, is_stale=is_stale)

        try:
            if tag is not None:
                data = self._backend.get_by_tag(self.project, name, tag)
            else:
                data = self._backend.get_version(self.project, name, version)
        except DatabaseUnavailableError as exc:
            stale = self._cache.get_stale(key)
            if stale is None:
                raise
            logger.warning(
                "PromptDock unavailable (%s); using last known good %s v%d",
                exc,
                name,
                stale.version,
            )
            self._cache.put(key, stale, immutable=version is not None, stale=True)
            return Prompt(stale, tag, is_stale=True)

        self._cache.put(key, data, immutable=version is not None)
        return Prompt(data, tag)

    # --- prompts and versions -------------------------------------------------------------

    def create_prompt(self, name: str, description: str | None = None) -> PromptInfo:
        """Create a prompt; it starts with tags dev, preprod and prod pointing nowhere."""
        return self._backend.create_prompt(self.project, name, description)

    def get_prompt_info(self, name: str) -> PromptInfo:
        return self._backend.get_prompt_info(self.project, name)

    def list_prompts(self) -> list[PromptInfo]:
        return self._backend.list_prompts(self.project)

    def create_version(
        self,
        name: str,
        template: str | Sequence[ChatMessage | Mapping[str, str]],
        *,
        model_config: Mapping[str, Any] | None = None,
        commit_message: str | None = None,
        created_by: str | None = None,
    ) -> PromptVersion:
        """Save a new version. ``template`` is a string, or a list of chat messages
        (``{"role": ..., "content": ...}``). Saving content identical to the latest
        version returns that version instead of creating a new one."""
        data = PromptVersionCreate.model_validate(
            {
                "template": template,
                "model_config": dict(model_config or {}),
                "commit_message": commit_message,
                "created_by": created_by,
            }
        )
        version = self._backend.create_version(self.project, name, data)
        self._cache.invalidate(self._key(name, "latest"))
        return version

    def get_version(self, name: str, version: int | None = None) -> PromptVersion:
        """The full stored record of a version (uncached). ``None`` means the latest."""
        return self._backend.get_version(self.project, name, version)

    def list_versions(self, name: str) -> list[PromptVersion]:
        return self._backend.list_versions(self.project, name)

    # --- tags -----------------------------------------------------------------------------

    def list_tags(self, name: str) -> list[Tag]:
        return self._backend.list_tags(self.project, name)

    def promote(
        self,
        name: str,
        tag: str,
        version: int,
        *,
        actor: str | None = None,
        force: bool = False,
        reason: str | None = None,
    ) -> Tag:
        """Point ``tag`` at ``version``. Refused with ``GateFailedError`` if the tag's gate
        fails, unless ``force=True`` with a ``reason``."""
        result = self._backend.promote(self.project, name, tag, version, actor, force, reason)
        self._cache.invalidate(self._key(name, f"tag:{tag}"))
        return result

    def rollback(
        self, name: str, tag: str, *, actor: str | None = None, reason: str | None = None
    ) -> Tag:
        """Undo the tag's most recent promote; repeat to keep going back."""
        result = self._backend.rollback(self.project, name, tag, actor, reason)
        self._cache.invalidate(self._key(name, f"tag:{tag}"))
        return result

    def set_gate(self, name: str, tag: str, gate: Gate | Mapping[str, Any] | None) -> Tag:
        """Require eval results before ``tag`` can move, e.g.
        ``{"rules": [{"metric": "accuracy", "min": 0.85}]}``. ``None`` removes the gate."""
        parsed = Gate.model_validate(gate) if gate is not None else None
        return self._backend.set_gate(self.project, name, tag, parsed)

    def get_history(self, name: str, tag: str | None = None) -> list[TagEvent]:
        """Every promote and rollback for the prompt (newest first)."""
        return self._backend.get_tag_history(self.project, name, tag)

    # --- eval results ---------------------------------------------------------------------

    def add_eval_results(
        self, results: Iterable[EvalResultIn | Mapping[str, Any]]
    ) -> list[EvalResult]:
        """Store eval results in the fixed schema; all are saved or none are."""
        parsed = [
            r
            if isinstance(r, EvalResultIn)
            else EvalResultIn.model_validate({"project": self.project, **r})
            for r in results
        ]
        return self._backend.add_eval_results(parsed)

    def get_eval_results(self, name: str, version: int | None = None) -> list[EvalResult]:
        return self._backend.get_eval_results(self.project, name, version)

    # --- lifecycle ------------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Make the next ``get_prompt`` calls go to the database."""
        self._cache.invalidate()

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _key(self, name: str, selector: str) -> str:
        return f"{self.project}/{name}/{selector}"
