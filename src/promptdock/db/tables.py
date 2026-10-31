"""SQLAlchemy table definitions.

Versions, tag events and eval results are append-only; only tag pointers change.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_prompts_project_id_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_prompt_id_version"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("template_type IN ('text', 'chat')", name="template_type_valid"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey("prompts.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # A string for text prompts, a list of {"role", "content"} objects for chat prompts.
    template: Mapped[Any] = mapped_column(JSONB, nullable=False)
    variables: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    model_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    commit_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created_at()
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("prompt_id", "name", name="uq_tags_prompt_id_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prompt_id: Mapped[int] = mapped_column(
        ForeignKey("prompts.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Null until the tag is first promoted to a version.
    version_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT")
    )
    gate: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    updated_by: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TagEvent(Base):
    __tablename__ = "tag_events"
    __table_args__ = (
        CheckConstraint("action IN ('promote', 'rollback')", name="action_valid"),
        Index("ix_tag_events_tag_id_created_at", "tag_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="RESTRICT"), nullable=False)
    from_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT")
    )
    to_version_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    # True when an admin bypassed the tag's gate with force=true.
    forced: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    actor: Mapped[str | None] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class EvalResult(Base):
    __tablename__ = "eval_results"
    __table_args__ = (
        Index("ix_eval_results_version_id_metric_created_at", "version_id", "metric", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_id: Mapped[int] = mapped_column(
        ForeignKey("prompt_versions.id", ondelete="RESTRICT"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(200), nullable=False)
    score: Mapped[float] = mapped_column(Double, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(200))
    evaluator: Mapped[str | None] = mapped_column(String(200))
    # "metadata" is reserved on declarative classes, so the attribute has a trailing underscore.
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = _created_at()


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = _created_at()
