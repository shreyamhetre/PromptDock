"""In-memory TTL cache with a last-known-good fallback and an optional snapshot file."""

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from promptdock.models import PromptVersion

logger = logging.getLogger("promptdock")


@dataclass
class _Entry:
    value: PromptVersion
    fetched_at: float
    immutable: bool
    stale: bool


class PromptCache:
    """Caches prompt versions by lookup key.

    Entries for a tag (or "latest") are fresh for ``ttl`` seconds. Entries fetched by
    version number never expire, because versions never change. Expired entries are kept
    as the last known good copy for when the database is unreachable.

    If ``snapshot_path`` is set, every fetched version is also written to that JSON file
    so a freshly started process can fall back to it before its first successful read.
    """

    def __init__(
        self,
        ttl: float,
        snapshot_path: str | Path | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl = ttl
        self.snapshot_path = Path(snapshot_path) if snapshot_path is not None else None
        self._clock = clock
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.Lock()

    def get_fresh(self, key: str) -> tuple[PromptVersion, bool] | None:
        """``(value, is_stale)`` if the entry has not expired, else None."""
        with self._lock:
            entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.immutable or self._clock() - entry.fetched_at < self.ttl:
            return entry.value, entry.stale
        return None

    def get_stale(self, key: str) -> PromptVersion | None:
        """Last known good value from memory, else from the snapshot file."""
        with self._lock:
            entry = self._entries.get(key)
        if entry is not None:
            return entry.value
        return self._read_snapshot().get(key)

    def put(
        self, key: str, value: PromptVersion, *, immutable: bool = False, stale: bool = False
    ) -> None:
        """Store a value. ``stale=True`` re-stores a last-known-good copy while the database
        is down, so it is served (and the database retried) once per TTL, not every call."""
        with self._lock:
            previous = self._entries.get(key)
            self._entries[key] = _Entry(value, self._clock(), immutable, stale)
        if not stale and (previous is None or previous.value.id != value.id):
            self._write_snapshot(key, value)

    def invalidate(self, prefix: str = "") -> None:
        """Expire entries whose key starts with ``prefix`` (all entries by default).

        They stay available as last-known-good copies.
        """
        with self._lock:
            for key, entry in self._entries.items():
                if key.startswith(prefix) and not entry.immutable:
                    entry.fetched_at = float("-inf")

    def _read_snapshot(self) -> dict[str, PromptVersion]:
        if self.snapshot_path is None or not self.snapshot_path.exists():
            return {}
        try:
            raw = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            return {key: PromptVersion.model_validate(value) for key, value in raw.items()}
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable prompt snapshot %s: %s", self.snapshot_path, exc)
            return {}

    def _write_snapshot(self, key: str, value: PromptVersion) -> None:
        if self.snapshot_path is None:
            return
        with self._lock:
            try:
                data: dict[str, object] = {}
                if self.snapshot_path.exists():
                    data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
                data[key] = value.model_dump(mode="json", by_alias=True)
                self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.snapshot_path.with_suffix(self.snapshot_path.suffix + ".tmp")
                tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
                os.replace(tmp, self.snapshot_path)
            except (OSError, ValueError) as exc:
                logger.warning("Could not write prompt snapshot %s: %s", self.snapshot_path, exc)
