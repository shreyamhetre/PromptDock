"""The interface every backend implements. Methods mirror ``promptdock.core.service``."""

from collections.abc import Sequence
from typing import Protocol

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


class Backend(Protocol):
    """Raises ``DatabaseUnavailableError`` when the store cannot be reached."""

    def create_prompt(self, project: str, name: str, description: str | None) -> PromptInfo: ...

    def get_prompt_info(self, project: str, name: str) -> PromptInfo: ...

    def list_prompts(self, project: str) -> list[PromptInfo]: ...

    def create_version(
        self, project: str, name: str, data: PromptVersionCreate
    ) -> PromptVersion: ...

    def get_version(self, project: str, name: str, version: int | None) -> PromptVersion: ...

    def get_by_tag(self, project: str, name: str, tag: str) -> PromptVersion: ...

    def list_versions(self, project: str, name: str) -> list[PromptVersion]: ...

    def list_tags(self, project: str, name: str) -> list[Tag]: ...

    def set_gate(self, project: str, name: str, tag: str, gate: Gate | None) -> Tag: ...

    def promote(
        self,
        project: str,
        name: str,
        tag: str,
        version: int,
        actor: str | None,
        force: bool,
        reason: str | None,
    ) -> Tag: ...

    def rollback(
        self, project: str, name: str, tag: str, actor: str | None, reason: str | None
    ) -> Tag: ...

    def get_tag_history(self, project: str, name: str, tag: str | None) -> list[TagEvent]: ...

    def add_eval_results(self, results: Sequence[EvalResultIn]) -> list[EvalResult]: ...

    def get_eval_results(
        self, project: str, name: str, version: int | None
    ) -> list[EvalResult]: ...

    def close(self) -> None: ...
