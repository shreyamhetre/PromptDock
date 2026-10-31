"""Read-only views that show names and version numbers instead of internal ids.

For people looking inside the database (psql, BI tools). PromptDock itself never
reads them.

    v_prompt_status  one row per prompt: latest version and where dev/preprod/prod point
    v_versions       every version, with the tags currently pointing at it
    v_tags           every tag and the version it points to
    v_tag_history    every promote/rollback, numbered per prompt
    v_eval_results   every eval result with prompt name and version number

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VIEWS = {
    "v_tags": """
        SELECT pr.name AS project, p.name AS prompt, t.name AS tag, v.version,
               t.gate IS NOT NULL AS has_gate, t.gate, t.updated_by, t.updated_at
        FROM tags t
        JOIN prompts p ON p.id = t.prompt_id
        JOIN projects pr ON pr.id = p.project_id
        LEFT JOIN prompt_versions v ON v.id = t.version_id
    """,
    "v_versions": """
        SELECT pr.name AS project, p.name AS prompt, v.version,
               (SELECT string_agg(t.name, ', ' ORDER BY t.name)
                FROM tags t WHERE t.version_id = v.id) AS tags,
               v.template_type, v.template, v.variables, v.model_config,
               v.commit_message, v.created_by, v.created_at
        FROM prompt_versions v
        JOIN prompts p ON p.id = v.prompt_id
        JOIN projects pr ON pr.id = p.project_id
    """,
    "v_prompt_status": """
        SELECT pr.name AS project, p.name AS prompt,
               (SELECT max(v.version) FROM prompt_versions v
                WHERE v.prompt_id = p.id) AS latest_version,
               max(v.version) FILTER (WHERE t.name = 'dev') AS dev,
               max(v.version) FILTER (WHERE t.name = 'preprod') AS preprod,
               max(v.version) FILTER (WHERE t.name = 'prod') AS prod,
               string_agg(t.name || '=v' || v.version, ', ' ORDER BY t.name)
                   FILTER (WHERE t.name NOT IN ('dev', 'preprod', 'prod')
                           AND v.version IS NOT NULL) AS other_tags
        FROM prompts p
        JOIN projects pr ON pr.id = p.project_id
        LEFT JOIN tags t ON t.prompt_id = p.id
        LEFT JOIN prompt_versions v ON v.id = t.version_id
        GROUP BY pr.name, p.id, p.name
    """,
    "v_tag_history": """
        SELECT row_number() OVER (PARTITION BY p.id ORDER BY e.id) AS step,
               pr.name AS project, p.name AS prompt, t.name AS tag, e.action,
               fv.version AS from_version, tv.version AS to_version,
               e.forced, e.actor, e.reason, e.created_at
        FROM tag_events e
        JOIN tags t ON t.id = e.tag_id
        JOIN prompts p ON p.id = t.prompt_id
        JOIN projects pr ON pr.id = p.project_id
        LEFT JOIN prompt_versions fv ON fv.id = e.from_version_id
        JOIN prompt_versions tv ON tv.id = e.to_version_id
    """,
    "v_eval_results": """
        SELECT pr.name AS project, p.name AS prompt, v.version, r.metric, r.score,
               r.run_id, r.evaluator, r.metadata, r.created_at
        FROM eval_results r
        JOIN prompt_versions v ON v.id = r.version_id
        JOIN prompts p ON p.id = v.prompt_id
        JOIN projects pr ON pr.id = p.project_id
    """,
}


def upgrade() -> None:
    for name, query in VIEWS.items():
        op.execute(f"CREATE VIEW {name} AS {query}")


def downgrade() -> None:
    for name in reversed(VIEWS):
        op.execute(f"DROP VIEW IF EXISTS {name}")
