"""Pydantic models shared by the library, the server and the CLI.

``model_config`` is reserved by Pydantic, so the per-version model settings are exposed
as the ``llm_config`` attribute in Python and as ``"model_config"`` in JSON.
"""

import math
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from promptdock.config import DEFAULT_PROJECT

TemplateType = Literal["text", "chat"]
TagAction = Literal["promote", "rollback"]

DEFAULT_TAGS: tuple[str, ...] = ("dev", "preprod", "prod")

NAME_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$"


class _Model(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


class ChatMessage(_Model):
    role: str = Field(min_length=1, max_length=50)
    content: str


Template = str | list[ChatMessage]


def template_type_of(template: Template) -> TemplateType:
    return "text" if isinstance(template, str) else "chat"


class Project(_Model):
    id: int
    name: str
    created_at: datetime


class PromptInfo(_Model):
    id: int
    project: str = DEFAULT_PROJECT
    name: str
    description: str | None = None
    created_at: datetime


class PromptVersionCreate(_Model):
    """What a user sends to save a new version."""

    template: Template
    llm_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    commit_message: str | None = None

    @field_validator("template")
    @classmethod
    def _not_empty(cls, value: Template) -> Template:
        if isinstance(value, list) and not value:
            raise ValueError("chat template must contain at least one message")
        return value


class PromptVersion(_Model):
    id: int
    prompt: str
    version: int = Field(ge=1)
    template_type: TemplateType
    template: Template
    variables: list[str] = Field(default_factory=list)
    llm_config: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    commit_message: str | None = None
    created_by: str | None = None
    created_at: datetime
    content_hash: str

    @model_validator(mode="after")
    def _type_matches_template(self) -> "PromptVersion":
        if template_type_of(self.template) != self.template_type:
            raise ValueError(f"template does not match template_type '{self.template_type}'")
        return self


class GateRule(_Model):
    metric: str = Field(min_length=1)
    min: float | None = None
    max: float | None = None
    higher_is_better: bool = True

    @model_validator(mode="after")
    def _has_bound(self) -> "GateRule":
        if self.min is None and self.max is None:
            raise ValueError(f"gate rule for '{self.metric}' needs a min or a max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"gate rule for '{self.metric}' has min greater than max")
        return self


class Gate(_Model):
    rules: list[GateRule] = Field(default_factory=list)
    require_better_than_current: bool = False


class Tag(_Model):
    id: int
    prompt: str
    name: str = Field(pattern=NAME_PATTERN, max_length=100)
    version: int | None = None
    gate: Gate | None = None
    updated_by: str | None = None
    updated_at: datetime


class TagEvent(_Model):
    id: int
    prompt: str
    tag: str
    from_version: int | None = None
    to_version: int
    action: TagAction
    forced: bool = False
    actor: str | None = None
    reason: str | None = None
    created_at: datetime


class EvalResultIn(_Model):
    """One eval result as submitted by a user (the fixed submission schema)."""

    project: str = DEFAULT_PROJECT
    prompt: str = Field(min_length=1)
    version: int = Field(ge=1)
    metric: str = Field(min_length=1, max_length=200)
    score: float
    run_id: str | None = None
    evaluator: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("score")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("score must be a finite number")
        return value


class EvalResult(_Model):
    id: int
    prompt: str
    version: int
    metric: str
    score: float
    run_id: str | None = None
    evaluator: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
