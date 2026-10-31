import json
from datetime import datetime, timezone
from pathlib import Path

from promptdock.cache import PromptCache
from promptdock.models import PromptVersion


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _version(version_id: int, number: int = 1) -> PromptVersion:
    return PromptVersion(
        id=version_id,
        prompt="p",
        version=number,
        template_type="text",
        template=f"t{number}",
        created_at=datetime.now(timezone.utc),
        content_hash="h",
    )


def test_entries_expire_after_ttl() -> None:
    clock = FakeClock()
    cache = PromptCache(ttl=60, clock=clock)
    cache.put("k", _version(1))
    clock.now = 59
    assert cache.get_fresh("k") is not None
    clock.now = 60
    assert cache.get_fresh("k") is None
    assert cache.get_stale("k") is not None


def test_immutable_entries_never_expire() -> None:
    clock = FakeClock()
    cache = PromptCache(ttl=1, clock=clock)
    cache.put("k", _version(1), immutable=True)
    clock.now = 10_000
    assert cache.get_fresh("k") is not None


def test_zero_ttl_disables_caching_but_keeps_fallback() -> None:
    cache = PromptCache(ttl=0)
    cache.put("k", _version(1))
    assert cache.get_fresh("k") is None
    assert cache.get_stale("k") is not None


def test_stale_flag_sticks_until_a_real_fetch() -> None:
    clock = FakeClock()
    cache = PromptCache(ttl=10, clock=clock)
    cache.put("k", _version(1))
    clock.now = 20
    cache.put("k", _version(1), stale=True)
    hit = cache.get_fresh("k")
    assert hit is not None and hit[1] is True

    cache.put("k", _version(1))
    hit = cache.get_fresh("k")
    assert hit is not None and hit[1] is False


def test_invalidate() -> None:
    clock = FakeClock()
    cache = PromptCache(ttl=10, clock=clock)
    cache.put("a/x", _version(1))
    cache.put("b/x", _version(2))
    cache.invalidate("a/")
    assert cache.get_fresh("a/x") is None
    assert cache.get_fresh("b/x") is not None


def test_snapshot_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "snap" / "prompts.json"
    PromptCache(ttl=60, snapshot_path=path).put("k", _version(7, number=3))

    fresh_process = PromptCache(ttl=60, snapshot_path=path)
    assert fresh_process.get_fresh("k") is None
    restored = fresh_process.get_stale("k")
    assert restored is not None
    assert (restored.id, restored.version) == (7, 3)
    assert "model_config" in json.loads(path.read_text())["k"]


def test_corrupt_snapshot_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "prompts.json"
    path.write_text("{not json")
    assert PromptCache(ttl=60, snapshot_path=path).get_stale("k") is None
