"""Initial schema: projects, prompts, versions, tags, tag events, eval results, API keys.

Revision ID: 0001
Revises:
Create Date: 2026-10-31
"""

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger()),
        sa.Column("name", sa.String(200), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("name", name="uq_projects_name"),
    )

    op.create_table(
        "prompts",
        sa.Column("id", sa.BigInteger()),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_prompts"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_prompts_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("project_id", "name", name="uq_prompts_project_id_name"),
    )

    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.BigInteger()),
        sa.Column("prompt_id", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template_type", sa.String(10), nullable=False),
        sa.Column("template", postgresql.JSONB(), nullable=False),
        sa.Column("variables", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("model_config", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("commit_message", sa.Text()),
        sa.Column("created_by", sa.String(200)),
        _created_at(),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_versions"),
        sa.ForeignKeyConstraint(
            ["prompt_id"],
            ["prompts.id"],
            name="fk_prompt_versions_prompt_id_prompts",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_prompt_id_version"),
        sa.CheckConstraint("version >= 1", name="ck_prompt_versions_version_positive"),
        sa.CheckConstraint(
            "template_type IN ('text', 'chat')", name="ck_prompt_versions_template_type_valid"
        ),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger()),
        sa.Column("prompt_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("version_id", sa.BigInteger()),
        sa.Column("is_protected", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("gate", postgresql.JSONB()),
        sa.Column("updated_by", sa.String(200)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.ForeignKeyConstraint(
            ["prompt_id"], ["prompts.id"], name="fk_tags_prompt_id_prompts", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["prompt_versions.id"],
            name="fk_tags_version_id_prompt_versions",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("prompt_id", "name", name="uq_tags_prompt_id_name"),
    )

    op.create_table(
        "tag_events",
        sa.Column("id", sa.BigInteger()),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.Column("from_version_id", sa.BigInteger()),
        sa.Column("to_version_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("forced", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("actor", sa.String(200)),
        sa.Column("reason", sa.Text()),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_tag_events"),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="fk_tag_events_tag_id_tags", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["from_version_id"],
            ["prompt_versions.id"],
            name="fk_tag_events_from_version_id_prompt_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_version_id"],
            ["prompt_versions.id"],
            name="fk_tag_events_to_version_id_prompt_versions",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("action IN ('promote', 'rollback')", name="ck_tag_events_action_valid"),
    )
    op.create_index("ix_tag_events_tag_id_created_at", "tag_events", ["tag_id", "created_at"])

    op.create_table(
        "eval_results",
        sa.Column("id", sa.BigInteger()),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.Column("metric", sa.String(200), nullable=False),
        sa.Column("score", sa.Double(), nullable=False),
        sa.Column("run_id", sa.String(200)),
        sa.Column("evaluator", sa.String(200)),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_eval_results"),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["prompt_versions.id"],
            name="fk_eval_results_version_id_prompt_versions",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_eval_results_version_id_metric_created_at",
        "eval_results",
        ["version_id", "metric", "created_at"],
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.BigInteger()),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), server_default="[]", nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name="pk_api_keys"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )

    op.execute("INSERT INTO projects (name) VALUES ('default')")


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_index("ix_eval_results_version_id_metric_created_at", table_name="eval_results")
    op.drop_table("eval_results")
    op.drop_index("ix_tag_events_tag_id_created_at", table_name="tag_events")
    op.drop_table("tag_events")
    op.drop_table("tags")
    op.drop_table("prompt_versions")
    op.drop_table("prompts")
    op.drop_table("projects")
