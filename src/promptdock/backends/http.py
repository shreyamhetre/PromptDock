"""Server mode: talk to a ``promptdock serve`` instance over HTTP."""

from collections.abc import Sequence
from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, TypeAdapter

from promptdock import errors
from promptdock.models import (
    CreatePromptRequest,
    EvalResult,
    EvalResultIn,
    Gate,
    PromoteRequest,
    PromptInfo,
    PromptVersion,
    PromptVersionCreate,
    RollbackRequest,
    SetGateRequest,
    Tag,
    TagEvent,
)

M = TypeVar("M", bound=BaseModel)

_ERROR_CLASSES: dict[str, type[errors.PromptDockError]] = {
    name: cls
    for name, cls in vars(errors).items()
    if isinstance(cls, type) and issubclass(cls, errors.PromptDockError)
}


class HttpBackend:
    """Implements the same methods as ``DbBackend`` by calling the REST API.

    Server errors are raised as the same exception classes library mode raises.
    """

    def __init__(
        self,
        base_url: str,
        token: str | None,
        timeout: float = 5.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if http_client is None:
            self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
        else:
            http_client.headers.update(headers)
            self._http = http_client
        # Last response per prompt URL, for conditional requests (ETag / 304).
        self._etags: dict[str, tuple[str, PromptVersion]] = {}

    # --- prompts -------------------------------------------------------------------------

    def create_prompt(self, project: str, name: str, description: str | None) -> PromptInfo:
        body = CreatePromptRequest(name=name, description=description)
        return self._call(PromptInfo, "POST", "/prompts", project, json=_dump(body))

    def get_prompt_info(self, project: str, name: str) -> PromptInfo:
        return self._call(PromptInfo, "GET", f"/prompts/{_q(name)}/info", project)

    def list_prompts(self, project: str) -> list[PromptInfo]:
        return self._call_list(PromptInfo, "GET", "/prompts", project)

    # --- versions ------------------------------------------------------------------------

    def create_version(
        self, project: str, name: str, data: PromptVersionCreate, actor: str | None
    ) -> PromptVersion:
        path = f"/prompts/{_q(name)}/versions"
        return self._call(
            PromptVersion, "POST", path, project, json=_dump(data), headers=_actor(actor)
        )

    def get_version(self, project: str, name: str, version: int | None) -> PromptVersion:
        if version is None:
            return self._get_conditional(project, name, {})
        path = f"/prompts/{_q(name)}/versions/{version}"
        return self._call(PromptVersion, "GET", path, project)

    def get_by_tag(self, project: str, name: str, tag: str) -> PromptVersion:
        return self._get_conditional(project, name, {"tag": tag})

    def list_versions(self, project: str, name: str) -> list[PromptVersion]:
        return self._call_list(PromptVersion, "GET", f"/prompts/{_q(name)}/versions", project)

    # --- tags ----------------------------------------------------------------------------

    def list_tags(self, project: str, name: str) -> list[Tag]:
        return self._call_list(Tag, "GET", f"/prompts/{_q(name)}/tags", project)

    def set_gate(
        self, project: str, name: str, tag: str, gate: Gate | None, actor: str | None
    ) -> Tag:
        path = f"/prompts/{_q(name)}/tags/{_q(tag)}/gate"
        body = _dump(SetGateRequest(gate=gate))
        return self._call(Tag, "PUT", path, project, json=body, headers=_actor(actor))

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
        body = PromoteRequest(version=version, reason=reason, force=force)
        path = f"/prompts/{_q(name)}/tags/{_q(tag)}"
        return self._call(Tag, "PUT", path, project, json=_dump(body), headers=_actor(actor))

    def rollback(
        self, project: str, name: str, tag: str, actor: str | None, reason: str | None
    ) -> Tag:
        body = RollbackRequest(reason=reason)
        path = f"/prompts/{_q(name)}/tags/{_q(tag)}/rollback"
        return self._call(Tag, "POST", path, project, json=_dump(body), headers=_actor(actor))

    def list_tag_events(self, project: str, name: str, tag: str | None) -> list[TagEvent]:
        if tag is None:
            path = f"/prompts/{_q(name)}/events"
        else:
            path = f"/prompts/{_q(name)}/tags/{_q(tag)}/events"
        return self._call_list(TagEvent, "GET", path, project)

    # --- evals ---------------------------------------------------------------------------

    def add_eval_results(self, results: Sequence[EvalResultIn]) -> list[EvalResult]:
        body = [_dump(r) for r in results]
        return self._call_list(EvalResult, "POST", "/evals", None, json=body)

    def get_eval_results(self, project: str, name: str, version: int | None) -> list[EvalResult]:
        params = {"version": version} if version is not None else {}
        path = f"/prompts/{_q(name)}/evals"
        return self._call_list(EvalResult, "GET", path, project, params=params)

    def close(self) -> None:
        self._http.close()

    # --- plumbing ------------------------------------------------------------------------

    def _get_conditional(self, project: str, name: str, params: dict[str, Any]) -> PromptVersion:
        """GET /prompts/{name}, sending the last ETag so an unchanged prompt costs a 304."""
        path = f"/prompts/{_q(name)}"
        cache_key = f"{project}|{path}|{sorted(params.items())}"
        headers = {}
        previous = self._etags.get(cache_key)
        if previous is not None:
            headers["If-None-Match"] = previous[0]
        response = self._send("GET", path, project, params=params, headers=headers)
        if response.status_code == 304 and previous is not None:
            return previous[1]
        result = PromptVersion.model_validate(response.json())
        if etag := response.headers.get("ETag"):
            self._etags[cache_key] = (etag, result)
        return result

    def _call(self, model: type[M], method: str, path: str, project: str | None, **kw: Any) -> M:
        return model.model_validate(self._send(method, path, project, **kw).json())

    def _call_list(
        self, model: type[M], method: str, path: str, project: str | None, **kw: Any
    ) -> list[M]:
        return TypeAdapter(list[model]).validate_python(  # type: ignore[valid-type]
            self._send(method, path, project, **kw).json()
        )

    def _send(
        self,
        method: str,
        path: str,
        project: str | None,
        *,
        params: dict[str, Any] | None = None,
        **kw: Any,
    ) -> httpx.Response:
        params = dict(params or {})
        if project is not None:
            params["project"] = project
        try:
            response = self._http.request(method, path, params=params, **kw)
        except httpx.TransportError as exc:
            raise errors.ServerUnavailableError(f"PromptDock server unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise _to_error(response)
        return response


def _to_error(response: httpx.Response) -> errors.PromptDockError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None

    if isinstance(error, dict):
        cls = _ERROR_CLASSES.get(str(error.get("type")), errors.PromptDockError)
        message = str(error.get("message", ""))
        if cls is errors.GateFailedError:
            return errors.GateFailedError(error["prompt"], error["tag"], list(error["failures"]))
        if cls is errors.MissingVariableError:
            return errors.InvalidInputError(message)
        if cls is errors.DatabaseUnavailableError:
            # The server is up but its database is not: from here, the server is unavailable.
            return errors.ServerUnavailableError(message)
        return cls(message)

    if response.status_code == 422:
        return errors.InvalidInputError(f"Invalid request: {payload.get('detail', payload)}")
    if response.status_code == 401:
        return errors.AuthenticationError("The server requires a token")
    if response.status_code >= 500:
        return errors.ServerUnavailableError(f"PromptDock server error {response.status_code}")
    return errors.PromptDockError(f"Unexpected response {response.status_code}: {response.text}")


def _actor(actor: str | None) -> dict[str, str]:
    """X-Actor header; URL-encoded so names with any characters fit in a header."""
    return {"X-Actor": quote(actor, safe="")} if actor else {}


def _dump(model: BaseModel) -> Any:
    return model.model_dump(mode="json", by_alias=True)


def _q(segment: str) -> str:
    return quote(segment, safe="")
