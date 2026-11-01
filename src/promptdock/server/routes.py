"""REST endpoints. Routes only translate HTTP into calls to the backend and core."""

from typing import Annotated

from fastapi import APIRouter, Header, Query, Response, status
from sqlalchemy import text

from promptdock.config import DEFAULT_PROJECT
from promptdock.errors import InvalidInputError
from promptdock.models import (
    CreatePromptRequest,
    EvalResult,
    EvalResultIn,
    PromoteRequest,
    PromptInfo,
    PromptVersion,
    PromptVersionCreate,
    RollbackRequest,
    SetGateRequest,
    Tag,
    TagEvent,
)
from promptdock.server.access import Actor, Backend

public_router = APIRouter()
router = APIRouter()

Project = Annotated[str, Query(description="Project name")]


@public_router.get("/health", tags=["system"])
def health(backend: Backend) -> dict[str, str]:
    """Never needs a token. Returns 503 if the database is unreachable."""
    backend.run(lambda s: s.execute(text("SELECT 1")))
    return {"status": "ok"}


# --- prompts -----------------------------------------------------------------------------


@router.post("/prompts", status_code=status.HTTP_201_CREATED, tags=["prompts"])
def create_prompt(
    body: CreatePromptRequest, backend: Backend, project: Project = DEFAULT_PROJECT
) -> PromptInfo:
    return backend.create_prompt(project, body.name, body.description)


@router.get("/prompts", tags=["prompts"])
def list_prompts(backend: Backend, project: Project = DEFAULT_PROJECT) -> list[PromptInfo]:
    return backend.list_prompts(project)


@router.get("/prompts/{name}", response_model=PromptVersion, tags=["prompts"])
def get_prompt(
    name: str,
    backend: Backend,
    tag: str | None = None,
    version: int | None = None,
    project: Project = DEFAULT_PROJECT,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    """The hot path: the version a tag points to (``?tag=prod``), a specific version
    (``?version=3``), or the latest. Send ``If-None-Match`` with the last ``ETag`` to get
    an empty 304 when nothing changed."""
    if tag is not None and version is not None:
        raise InvalidInputError("Pass tag or version, not both")
    if tag is not None:
        result = backend.get_by_tag(project, name, tag)
    else:
        result = backend.get_version(project, name, version)

    # Versions never change, so the version's id identifies its content exactly.
    etag = f'"{result.id}"'
    if if_none_match == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"ETag": etag})
    return Response(
        content=result.model_dump_json(by_alias=True),
        media_type="application/json",
        headers={"ETag": etag},
    )


@router.get("/prompts/{name}/info", tags=["prompts"])
def get_prompt_info(name: str, backend: Backend, project: Project = DEFAULT_PROJECT) -> PromptInfo:
    return backend.get_prompt_info(project, name)


# --- versions ----------------------------------------------------------------------------


@router.post("/prompts/{name}/versions", status_code=status.HTTP_201_CREATED, tags=["versions"])
def create_version(
    name: str,
    body: PromptVersionCreate,
    backend: Backend,
    actor: Actor,
    project: Project = DEFAULT_PROJECT,
) -> PromptVersion:
    """Saving content identical to the latest version returns that version."""
    return backend.create_version(project, name, body, actor)


@router.get("/prompts/{name}/versions", tags=["versions"])
def list_versions(
    name: str, backend: Backend, project: Project = DEFAULT_PROJECT
) -> list[PromptVersion]:
    return backend.list_versions(project, name)


@router.get("/prompts/{name}/versions/{version}", tags=["versions"])
def get_version(
    name: str, version: int, backend: Backend, project: Project = DEFAULT_PROJECT
) -> PromptVersion:
    return backend.get_version(project, name, version)


# --- tags --------------------------------------------------------------------------------


@router.get("/prompts/{name}/tags", tags=["tags"])
def list_tags(name: str, backend: Backend, project: Project = DEFAULT_PROJECT) -> list[Tag]:
    return backend.list_tags(project, name)


@router.put("/prompts/{name}/tags/{tag}", tags=["tags"])
def promote(
    name: str,
    tag: str,
    body: PromoteRequest,
    backend: Backend,
    actor: Actor,
    project: Project = DEFAULT_PROJECT,
) -> Tag:
    """Point the tag at a version. Refused with 409 if the tag's gate fails, unless
    ``force`` is true and a ``reason`` is given."""
    return backend.promote(project, name, tag, body.version, actor, body.reason, body.force)


@router.post("/prompts/{name}/tags/{tag}/rollback", tags=["tags"])
def rollback(
    name: str,
    tag: str,
    backend: Backend,
    actor: Actor,
    body: RollbackRequest | None = None,
    project: Project = DEFAULT_PROJECT,
) -> Tag:
    """Undo the tag's most recent promote; call again to keep going back."""
    reason = body.reason if body is not None else None
    return backend.rollback(project, name, tag, actor, reason)


@router.get("/prompts/{name}/tags/{tag}/events", tags=["tags"])
def tag_events(
    name: str, tag: str, backend: Backend, project: Project = DEFAULT_PROJECT
) -> list[TagEvent]:
    """Audit log for one tag (newest first): when, from -> to, actor, reason."""
    return backend.list_tag_events(project, name, tag)


@router.get("/prompts/{name}/events", tags=["tags"])
def prompt_events(
    name: str, backend: Backend, project: Project = DEFAULT_PROJECT
) -> list[TagEvent]:
    """Audit log for every tag of the prompt (newest first)."""
    return backend.list_tag_events(project, name, None)


@router.put("/prompts/{name}/tags/{tag}/gate", tags=["tags"])
def set_gate(
    name: str,
    tag: str,
    body: SetGateRequest,
    backend: Backend,
    actor: Actor,
    project: Project = DEFAULT_PROJECT,
) -> Tag:
    """Set the eval gate for a tag; ``{"gate": null}`` removes it."""
    return backend.set_gate(project, name, tag, body.gate, actor)


# --- evals -------------------------------------------------------------------------------


@router.post("/evals", status_code=status.HTTP_201_CREATED, tags=["evals"])
def add_evals(body: list[EvalResultIn], backend: Backend) -> list[EvalResult]:
    """Store a batch of results; all are saved or none are."""
    return backend.add_eval_results(body)


@router.get("/prompts/{name}/evals", tags=["evals"])
def get_evals(
    name: str,
    backend: Backend,
    version: int | None = None,
    project: Project = DEFAULT_PROJECT,
) -> list[EvalResult]:
    return backend.get_eval_results(project, name, version)
