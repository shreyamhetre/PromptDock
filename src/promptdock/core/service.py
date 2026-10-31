"""Core business rules: prompts, versions, tags, promote/rollback and eval results.

Every function takes a SQLAlchemy ``Session`` and leaves committing to the caller, so a
caller can group several calls in one transaction. Functions that move a tag or add a
version take row locks (``SELECT ... FOR UPDATE``), which are held until that commit.
"""

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from promptdock.config import DEFAULT_PROJECT
from promptdock.core.gates import evaluate_gate
from promptdock.db.tables import EvalResult as EvalResultRow
from promptdock.db.tables import Project as ProjectRow
from promptdock.db.tables import Prompt as PromptRow
from promptdock.db.tables import PromptVersion as VersionRow
from promptdock.db.tables import Tag as TagRow
from promptdock.db.tables import TagEvent as TagEventRow
from promptdock.errors import (
    AlreadyExistsError,
    GateFailedError,
    InvalidInputError,
    NothingToRollBackError,
    PromptNotFoundError,
    TagNotFoundError,
    TagNotSetError,
    VersionNotFoundError,
)
from promptdock.models import (
    DEFAULT_TAGS,
    NAME_PATTERN,
    EvalResult,
    EvalResultIn,
    Gate,
    PromptInfo,
    PromptVersion,
    PromptVersionCreate,
    Tag,
    TagEvent,
    Template,
    template_type_of,
)
from promptdock.templates import extract_variables

_NAME_RE = re.compile(NAME_PATTERN)


# --- prompts -----------------------------------------------------------------------------


def create_prompt(
    session: Session,
    name: str,
    description: str | None = None,
    project: str = DEFAULT_PROJECT,
) -> PromptInfo:
    """Create a prompt with the default tags (dev, preprod, prod), none pointing anywhere yet.

    The project is created if it does not exist.
    """
    _check_name(name, "prompt name", 200)
    _check_name(project, "project name", 200)
    session.execute(
        pg_insert(ProjectRow).values(name=project).on_conflict_do_nothing(index_elements=["name"])
    )
    project_row = session.scalars(select(ProjectRow).where(ProjectRow.name == project)).one()

    inserted = session.execute(
        pg_insert(PromptRow)
        .values(project_id=project_row.id, name=name, description=description)
        .on_conflict_do_nothing(index_elements=["project_id", "name"])
        .returning(PromptRow.id)
    ).scalar_one_or_none()
    if inserted is None:
        raise AlreadyExistsError(f"Prompt '{name}' already exists in project '{project}'")

    session.add_all(TagRow(prompt_id=inserted, name=tag) for tag in DEFAULT_TAGS)
    session.flush()
    return _prompt_model(session.get_one(PromptRow, inserted), project)


def get_prompt(session: Session, name: str, project: str = DEFAULT_PROJECT) -> PromptInfo:
    return _prompt_model(_prompt_row(session, name, project), project)


def list_prompts(session: Session, project: str = DEFAULT_PROJECT) -> list[PromptInfo]:
    rows = session.scalars(
        select(PromptRow)
        .join(ProjectRow, PromptRow.project_id == ProjectRow.id)
        .where(ProjectRow.name == project)
        .order_by(PromptRow.name)
    ).all()
    return [_prompt_model(row, project) for row in rows]


# --- versions ----------------------------------------------------------------------------


def create_version(
    session: Session,
    name: str,
    data: PromptVersionCreate,
    project: str = DEFAULT_PROJECT,
) -> PromptVersion:
    """Save a new immutable version and return it.

    If the template and model_config are identical to the latest version, no new version
    is created and the latest one is returned instead.
    """
    prompt = _prompt_row(session, name, project, for_update=True)
    variables = extract_variables(data.template)
    content_hash = compute_content_hash(data.template, data.llm_config)

    latest = session.scalars(
        select(VersionRow)
        .where(VersionRow.prompt_id == prompt.id)
        .order_by(VersionRow.version.desc())
        .limit(1)
    ).first()
    if latest is not None and latest.content_hash == content_hash:
        return _version_model(latest, name)

    row = VersionRow(
        prompt_id=prompt.id,
        version=(latest.version + 1) if latest else 1,
        template_type=template_type_of(data.template),
        template=_template_json(data.template),
        variables=variables,
        model_config=data.llm_config,
        commit_message=data.commit_message,
        created_by=data.created_by,
        content_hash=content_hash,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return _version_model(row, name)


def get_version(
    session: Session, name: str, version: int | None = None, project: str = DEFAULT_PROJECT
) -> PromptVersion:
    """Return one version of a prompt, or the latest version if ``version`` is None."""
    prompt = _prompt_row(session, name, project)
    return _version_model(_version_row(session, prompt, version), name)


def list_versions(
    session: Session, name: str, project: str = DEFAULT_PROJECT
) -> list[PromptVersion]:
    prompt = _prompt_row(session, name, project)
    rows = session.scalars(
        select(VersionRow).where(VersionRow.prompt_id == prompt.id).order_by(VersionRow.version)
    ).all()
    return [_version_model(row, name) for row in rows]


def compute_content_hash(template: Template, llm_config: dict[str, Any]) -> str:
    """SHA-256 over the template and model_config, independent of key order."""
    payload = {
        "template_type": template_type_of(template),
        "template": _template_json(template),
        "model_config": llm_config,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


# --- tags --------------------------------------------------------------------------------


def get_by_tag(
    session: Session, name: str, tag: str, project: str = DEFAULT_PROJECT
) -> PromptVersion:
    """Return the version a tag currently points to."""
    prompt = _prompt_row(session, name, project)
    tag_row = _tag_row(session, prompt, tag)
    if tag_row.version_id is None:
        raise TagNotSetError(f"Tag '{tag}' on prompt '{name}' does not point to a version yet")
    return _version_model(session.get_one(VersionRow, tag_row.version_id), name)


def list_tags(session: Session, name: str, project: str = DEFAULT_PROJECT) -> list[Tag]:
    prompt = _prompt_row(session, name, project)
    rows = session.scalars(
        select(TagRow).where(TagRow.prompt_id == prompt.id).order_by(TagRow.name)
    ).all()
    numbers = _version_numbers(session, prompt.id)
    return [_tag_model(row, name, numbers) for row in rows]


def set_gate(
    session: Session, name: str, tag: str, gate: Gate | None, project: str = DEFAULT_PROJECT
) -> Tag:
    """Attach a gate to a tag (creating the tag if needed), or remove it with ``None``."""
    prompt = _prompt_row(session, name, project)
    tag_row = _lock_or_create_tag(session, prompt, tag)
    tag_row.gate = gate.model_dump() if gate is not None else None
    session.flush()
    return _tag_model(tag_row, name, _version_numbers(session, prompt.id))


def promote(
    session: Session,
    name: str,
    tag: str,
    version: int,
    actor: str | None = None,
    force: bool = False,
    reason: str | None = None,
    project: str = DEFAULT_PROJECT,
) -> Tag:
    """Point ``tag`` at ``version``, creating custom tags on first use.

    If the tag has a gate the version must pass it, otherwise ``GateFailedError`` is raised.
    ``force=True`` bypasses a failing gate but requires a ``reason``; the bypass is
    recorded in the tag's history. Promoting to the version the tag already points to
    changes nothing.
    """
    if force and not (reason and reason.strip()):
        raise InvalidInputError("force=True requires a reason")

    prompt = _prompt_row(session, name, project)
    target = _version_row(session, prompt, version)
    tag_row = _lock_or_create_tag(session, prompt, tag)
    numbers = _version_numbers(session, prompt.id)

    if tag_row.version_id == target.id:
        return _tag_model(tag_row, name, numbers)

    forced = False
    if tag_row.gate is not None:
        gate = Gate.model_validate(tag_row.gate)
        current = None if tag_row.version_id is None else latest_scores(session, tag_row.version_id)
        failures = evaluate_gate(gate, latest_scores(session, target.id), current)
        if failures and not force:
            raise GateFailedError(name, tag, failures)
        forced = bool(failures)

    _move_tag(session, tag_row, target.id, "promote", actor, reason, forced)
    return _tag_model(tag_row, name, numbers)


def rollback(
    session: Session,
    name: str,
    tag: str,
    actor: str | None = None,
    reason: str | None = None,
    project: str = DEFAULT_PROJECT,
) -> Tag:
    """Undo the tag's most recent promote that has not been rolled back yet.

    Repeated rollbacks walk further back through the promote history, like undo.
    Rollbacks are not gated. Raises ``NothingToRollBackError`` when nothing is left to undo.
    """
    prompt = _prompt_row(session, name, project)
    tag_row = _tag_row(session, prompt, tag, for_update=True)
    events = session.scalars(
        select(TagEventRow).where(TagEventRow.tag_id == tag_row.id).order_by(TagEventRow.id.desc())
    ).all()

    target_id = _undo_target(events)
    if target_id is None:
        raise NothingToRollBackError(
            f"Tag '{tag}' on prompt '{name}' has no earlier version to roll back to"
        )

    _move_tag(session, tag_row, target_id, "rollback", actor, reason, forced=False)
    return _tag_model(tag_row, name, _version_numbers(session, prompt.id))


def get_tag_history(
    session: Session, name: str, tag: str | None = None, project: str = DEFAULT_PROJECT
) -> list[TagEvent]:
    """Return the audit log of tag moves for a prompt (newest first), optionally for one tag."""
    prompt = _prompt_row(session, name, project)
    stmt = (
        select(TagEventRow, TagRow.name)
        .join(TagRow, TagEventRow.tag_id == TagRow.id)
        .where(TagRow.prompt_id == prompt.id)
        .order_by(TagEventRow.id.desc())
    )
    if tag is not None:
        stmt = stmt.where(TagRow.name == tag)
    numbers = _version_numbers(session, prompt.id)
    return [
        TagEvent(
            id=event.id,
            prompt=name,
            tag=tag_name,
            from_version=numbers.get(event.from_version_id) if event.from_version_id else None,
            to_version=numbers[event.to_version_id],
            action=event.action,
            forced=event.forced,
            actor=event.actor,
            reason=event.reason,
            created_at=event.created_at,
        )
        for event, tag_name in session.execute(stmt).all()
    ]


# --- eval results ------------------------------------------------------------------------


def add_eval_results(session: Session, results: Sequence[EvalResultIn]) -> list[EvalResult]:
    """Store a batch of eval results. All are saved, or none if any version is unknown."""
    stored: list[EvalResult] = []
    version_ids: dict[tuple[str, str, int], int] = {}
    for result in results:
        key = (result.project, result.prompt, result.version)
        if key not in version_ids:
            prompt = _prompt_row(session, result.prompt, result.project)
            version_ids[key] = _version_row(session, prompt, result.version).id
        row = EvalResultRow(
            version_id=version_ids[key],
            metric=result.metric,
            score=result.score,
            run_id=result.run_id,
            evaluator=result.evaluator,
            metadata_=result.metadata,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        stored.append(_eval_model(row, result.prompt, result.version))
    return stored


def get_eval_results(
    session: Session, name: str, version: int | None = None, project: str = DEFAULT_PROJECT
) -> list[EvalResult]:
    """Return eval results for one version, or for every version if ``version`` is None."""
    prompt = _prompt_row(session, name, project)
    stmt = (
        select(EvalResultRow, VersionRow.version)
        .join(VersionRow, EvalResultRow.version_id == VersionRow.id)
        .where(VersionRow.prompt_id == prompt.id)
        .order_by(VersionRow.version, EvalResultRow.id)
    )
    if version is not None:
        stmt = stmt.where(VersionRow.id == _version_row(session, prompt, version).id)
    return [_eval_model(row, name, number) for row, number in session.execute(stmt).all()]


def latest_scores(session: Session, version_id: int) -> dict[str, float]:
    """Latest score per metric for a version."""
    rows = session.execute(
        select(EvalResultRow.metric, EvalResultRow.score)
        .where(EvalResultRow.version_id == version_id)
        .order_by(EvalResultRow.created_at, EvalResultRow.id)
    ).all()
    # Oldest first, so later results overwrite earlier ones for the same metric.
    return {metric: score for metric, score in rows}


# --- helpers -----------------------------------------------------------------------------


def _check_name(value: str, what: str, max_length: int) -> None:
    if not _NAME_RE.match(value) or len(value) > max_length:
        raise InvalidInputError(
            f"Invalid {what} '{value}': use letters, digits, '-', '_' or '.', "
            f"starting with a letter or digit (max {max_length} characters)"
        )


def _prompt_row(
    session: Session, name: str, project: str, *, for_update: bool = False
) -> PromptRow:
    stmt = (
        select(PromptRow)
        .join(ProjectRow, PromptRow.project_id == ProjectRow.id)
        .where(ProjectRow.name == project, PromptRow.name == name)
    )
    if for_update:
        stmt = stmt.with_for_update(of=PromptRow)
    row = session.scalars(stmt).first()
    if row is None:
        raise PromptNotFoundError(f"Prompt '{name}' not found in project '{project}'")
    return row


def _version_row(session: Session, prompt: PromptRow, version: int | None) -> VersionRow:
    stmt = select(VersionRow).where(VersionRow.prompt_id == prompt.id)
    if version is None:
        stmt = stmt.order_by(VersionRow.version.desc()).limit(1)
    else:
        stmt = stmt.where(VersionRow.version == version)
    row = session.scalars(stmt).first()
    if row is None:
        which = "any version" if version is None else f"version {version}"
        raise VersionNotFoundError(f"Prompt '{prompt.name}' has no {which}")
    return row


def _tag_row(session: Session, prompt: PromptRow, tag: str, *, for_update: bool = False) -> TagRow:
    stmt = select(TagRow).where(TagRow.prompt_id == prompt.id, TagRow.name == tag)
    if for_update:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    row = session.scalars(stmt).first()
    if row is None:
        raise TagNotFoundError(f"Tag '{tag}' not found on prompt '{prompt.name}'")
    return row


def _lock_or_create_tag(session: Session, prompt: PromptRow, tag: str) -> TagRow:
    _check_name(tag, "tag name", 100)
    try:
        return _tag_row(session, prompt, tag, for_update=True)
    except TagNotFoundError:
        pass
    # Only insert when missing: an INSERT that hits the conflict still uses up an id.
    session.execute(
        pg_insert(TagRow)
        .values(prompt_id=prompt.id, name=tag)
        .on_conflict_do_nothing(index_elements=["prompt_id", "name"])
    )
    return _tag_row(session, prompt, tag, for_update=True)


def _move_tag(
    session: Session,
    tag_row: TagRow,
    to_version_id: int,
    action: str,
    actor: str | None,
    reason: str | None,
    forced: bool,
) -> None:
    session.add(
        TagEventRow(
            tag_id=tag_row.id,
            from_version_id=tag_row.version_id,
            to_version_id=to_version_id,
            action=action,
            forced=forced,
            actor=actor,
            reason=reason,
        )
    )
    tag_row.version_id = to_version_id
    tag_row.updated_by = actor
    tag_row.updated_at = func.now()
    session.flush()
    session.refresh(tag_row)


def _undo_target(events: Sequence[TagEventRow]) -> int | None:
    """Walk events newest-first; each rollback cancels the next older promote."""
    pending_rollbacks = 0
    for event in events:
        if event.action == "rollback":
            pending_rollbacks += 1
        elif pending_rollbacks:
            pending_rollbacks -= 1
        else:
            return event.from_version_id
    return None


def _version_numbers(session: Session, prompt_id: int) -> dict[int, int]:
    rows = session.execute(
        select(VersionRow.id, VersionRow.version).where(VersionRow.prompt_id == prompt_id)
    ).all()
    return {version_id: number for version_id, number in rows}


def _template_json(template: Template) -> Any:
    if isinstance(template, str):
        return template
    return [message.model_dump() for message in template]


def _prompt_model(row: PromptRow, project: str) -> PromptInfo:
    return PromptInfo(
        id=row.id,
        project=project,
        name=row.name,
        description=row.description,
        created_at=row.created_at,
    )


def _version_model(row: VersionRow, prompt_name: str) -> PromptVersion:
    return PromptVersion.model_validate(
        {
            "id": row.id,
            "prompt": prompt_name,
            "version": row.version,
            "template_type": row.template_type,
            "template": row.template,
            "variables": row.variables,
            "model_config": row.model_config,
            "commit_message": row.commit_message,
            "created_by": row.created_by,
            "created_at": row.created_at,
            "content_hash": row.content_hash,
        }
    )


def _tag_model(row: TagRow, prompt_name: str, numbers: dict[int, int]) -> Tag:
    return Tag(
        id=row.id,
        prompt=prompt_name,
        name=row.name,
        version=numbers.get(row.version_id) if row.version_id is not None else None,
        gate=Gate.model_validate(row.gate) if row.gate is not None else None,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def _eval_model(row: EvalResultRow, prompt_name: str, version: int) -> EvalResult:
    return EvalResult(
        id=row.id,
        prompt=prompt_name,
        version=version,
        metric=row.metric,
        score=row.score,
        run_id=row.run_id,
        evaluator=row.evaluator,
        metadata=row.metadata_,
        created_at=row.created_at,
    )
