"""Leaderboard and diff: comparing versions of one prompt."""

import difflib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from promptdock.config import DEFAULT_PROJECT
from promptdock.core import service
from promptdock.db.tables import EvalResult as EvalResultRow
from promptdock.db.tables import PromptVersion as VersionRow
from promptdock.db.tables import Tag as TagRow
from promptdock.errors import InvalidInputError
from promptdock.models import (
    ConfigChange,
    Leaderboard,
    LeaderboardRow,
    PromptVersion,
    Template,
    VersionDiff,
)

BUILT_IN_SORTS = ("version", "created_at")


def leaderboard(
    session: Session,
    name: str,
    sort_by: str = "version",
    descending: bool = True,
    project: str = DEFAULT_PROJECT,
) -> Leaderboard:
    """Every version with its latest score per metric, in one query per table.

    ``sort_by`` is ``version``, ``created_at`` or any metric name; versions without a
    score for the sorted metric always come last.
    """
    prompt = service._prompt_row(session, name, project)
    versions = session.scalars(
        select(VersionRow).where(VersionRow.prompt_id == prompt.id).order_by(VersionRow.version)
    ).all()
    by_id = {v.id: v for v in versions}

    latest: dict[int, dict[str, float]] = {v.id: {} for v in versions}
    results = session.execute(
        select(EvalResultRow.version_id, EvalResultRow.metric, EvalResultRow.score)
        .join(VersionRow, EvalResultRow.version_id == VersionRow.id)
        .where(VersionRow.prompt_id == prompt.id)
        .order_by(EvalResultRow.created_at, EvalResultRow.id)
    ).all()
    for version_id, metric, score in results:  # oldest first: later results win
        latest[version_id][metric] = score
    metrics = sorted({metric for scores in latest.values() for metric in scores})

    if sort_by not in BUILT_IN_SORTS and sort_by not in metrics:
        options = ", ".join([*BUILT_IN_SORTS, *metrics])
        raise InvalidInputError(f"Cannot sort by '{sort_by}'; choose one of: {options}")

    tags: dict[int, list[str]] = {}
    for tag_name, tagged_id in session.execute(
        select(TagRow.name, TagRow.version_id)
        .where(TagRow.prompt_id == prompt.id, TagRow.version_id.is_not(None))
        .order_by(TagRow.name)
    ).all():
        if tagged_id is not None:
            tags.setdefault(tagged_id, []).append(tag_name)

    rows = [
        LeaderboardRow(
            version=v.version,
            created_at=v.created_at,
            created_by=v.created_by,
            commit_message=v.commit_message,
            tags=tags.get(v.id, []),
            scores={m: latest[v.id].get(m) for m in metrics},
        )
        for v in by_id.values()
    ]
    if sort_by in BUILT_IN_SORTS:
        rows.sort(key=lambda r: getattr(r, sort_by), reverse=descending)
    else:
        scored = [r for r in rows if r.scores[sort_by] is not None]
        unscored = [r for r in rows if r.scores[sort_by] is None]
        scored.sort(key=lambda r: (r.scores[sort_by], r.version), reverse=descending)
        rows = scored + unscored
    return Leaderboard(
        prompt=name, metrics=metrics, sort_by=sort_by, descending=descending, rows=rows
    )


def diff(
    session: Session, name: str, a: int, b: int, project: str = DEFAULT_PROJECT
) -> VersionDiff:
    """Text diff of the templates of versions ``a`` and ``b`` plus model_config changes."""
    first = service.get_version(session, name, a, project)
    second = service.get_version(session, name, b, project)
    return diff_versions(first, second)


def diff_versions(first: PromptVersion, second: PromptVersion) -> VersionDiff:
    old, new = _as_lines(first.template), _as_lines(second.template)
    template_diff = "".join(
        difflib.unified_diff(
            old, new, fromfile=f"v{first.version}", tofile=f"v{second.version}", lineterm="\n"
        )
    )
    return VersionDiff(
        prompt=first.prompt,
        a=first.version,
        b=second.version,
        template_changed=old != new,
        template_diff=template_diff,
        model_config_changes=_config_changes(first.llm_config, second.llm_config),
        variables_added=sorted(set(second.variables) - set(first.variables)),
        variables_removed=sorted(set(first.variables) - set(second.variables)),
    )


def _as_lines(template: Template) -> list[str]:
    """Text templates as-is; chat templates as ``[role]`` headers followed by content."""
    if isinstance(template, str):
        text = template
    else:
        text = "\n".join(f"[{m.role}]\n{m.content}" for m in template)
    return [line + "\n" for line in text.split("\n")]


def _config_changes(a: dict[str, Any], b: dict[str, Any]) -> list[ConfigChange]:
    changes = []
    for key in sorted(set(a) | set(b)):
        if key not in a:
            changes.append(ConfigChange(key=key, change="added", b=b[key]))
        elif key not in b:
            changes.append(ConfigChange(key=key, change="removed", a=a[key]))
        elif a[key] != b[key]:
            changes.append(ConfigChange(key=key, change="changed", a=a[key], b=b[key]))
    return changes
