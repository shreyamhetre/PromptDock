"""Library mode: talk to Postgres directly through ``promptdock.core.service``."""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import TypeVar

from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from promptdock.core import service
from promptdock.db.engine import make_engine
from promptdock.errors import DatabaseUnavailableError
from promptdock.models import (
    EvalResult,
    EvalResultIn,
    Gate,
    PromptInfo,
    PromptVersion,
    PromptVersionCreate,
    Tag,
    TagEvent,
)

T = TypeVar("T")


class DbBackend:
    """Each call runs in its own transaction and commits on success."""

    def __init__(self, database_url: str | None = None, connect_timeout: int = 10) -> None:
        self._engine = make_engine(database_url, connect_timeout)

    def run(self, fn: Callable[[Session], T]) -> T:
        """Run ``fn`` in its own transaction, committing on success."""
        with self._session() as session:
            return fn(session)

    @contextmanager
    def _session(self) -> Iterator[Session]:
        try:
            with Session(self._engine) as session, session.begin():
                yield session
        except (OperationalError, InterfaceError) as exc:
            raise DatabaseUnavailableError(f"Database unavailable: {exc.orig}") from exc

    def create_prompt(self, project: str, name: str, description: str | None) -> PromptInfo:
        return self.run(lambda s: service.create_prompt(s, name, description, project))

    def get_prompt_info(self, project: str, name: str) -> PromptInfo:
        return self.run(lambda s: service.get_prompt(s, name, project))

    def list_prompts(self, project: str) -> list[PromptInfo]:
        return self.run(lambda s: service.list_prompts(s, project))

    def create_version(
        self, project: str, name: str, data: PromptVersionCreate, actor: str | None
    ) -> PromptVersion:
        return self.run(lambda s: service.create_version(s, name, data, project, actor))

    def get_version(self, project: str, name: str, version: int | None) -> PromptVersion:
        return self.run(lambda s: service.get_version(s, name, version, project))

    def get_by_tag(self, project: str, name: str, tag: str) -> PromptVersion:
        return self.run(lambda s: service.get_by_tag(s, name, tag, project))

    def list_versions(self, project: str, name: str) -> list[PromptVersion]:
        return self.run(lambda s: service.list_versions(s, name, project))

    def list_tags(self, project: str, name: str) -> list[Tag]:
        return self.run(lambda s: service.list_tags(s, name, project))

    def set_gate(
        self, project: str, name: str, tag: str, gate: Gate | None, actor: str | None
    ) -> Tag:
        return self.run(lambda s: service.set_gate(s, name, tag, gate, project, actor))

    def promote(
        self,
        project: str,
        name: str,
        tag: str,
        version: int,
        actor: str | None,
        reason: str | None,
        force: bool,
    ) -> Tag:
        return self.run(
            lambda s: service.promote(s, name, tag, version, actor, reason, force, project)
        )

    def rollback(
        self, project: str, name: str, tag: str, actor: str | None, reason: str | None
    ) -> Tag:
        return self.run(lambda s: service.rollback(s, name, tag, actor, reason, project))

    def list_tag_events(self, project: str, name: str, tag: str | None) -> list[TagEvent]:
        return self.run(lambda s: service.list_tag_events(s, name, tag, project))

    def add_eval_results(self, results: Sequence[EvalResultIn]) -> list[EvalResult]:
        return self.run(lambda s: service.add_eval_results(s, results))

    def get_eval_results(self, project: str, name: str, version: int | None) -> list[EvalResult]:
        return self.run(lambda s: service.get_eval_results(s, name, version, project))

    def close(self) -> None:
        self._engine.dispose()
