"""A local MCP server over stdio so AI agents (Claude Desktop, Cursor, ...) can read and
version prompts through the same ``Client`` as everything else.

Changes are recorded with the actor ``mcp:<OS username>`` so the audit log shows they came
from an agent. ``promote`` only exists with ``--allow-promote``; ``force`` is never offered.
"""

from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel

from promptdock.actor import default_actor
from promptdock.client import Client
from promptdock.errors import NotFoundError, PromptDockError

INSTRUCTIONS = (
    "PromptDock stores immutable, numbered versions of prompts and tags (dev, preprod, prod, "
    "...) that point at versions. Apps read prompts by tag. Use get_prompt to read, "
    "create_version to save an edited template (identical content returns the existing "
    "version), compare_versions and get_leaderboard to judge versions by their eval scores."
)


def agent_actor() -> str:
    return f"mcp:{default_actor() or 'unknown'}"


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)


def build_server(client: Client, *, allow_promote: bool = False) -> MCPServer:
    """Register PromptDock tools on a new MCP server backed by ``client``."""
    server = MCPServer(name="promptdock", instructions=INSTRUCTIONS)

    def call(fn: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except PromptDockError as exc:
            raise ToolError(str(exc)) from None

    @server.tool()
    def list_prompts() -> list[dict[str, Any]]:
        """List prompts with their description and where each tag points."""
        result = []
        for info in call(client.list_prompts):
            tags = {t.name: t.version for t in call(client.list_tags, info.name)}
            result.append({"name": info.name, "description": info.description, "tags": tags})
        return result

    @server.tool()
    def get_prompt(name: str, tag: str | None = None, version: int | None = None) -> dict[str, Any]:
        """Get a prompt's template, variables and model_config: by tag (e.g. "prod"), by
        version number, or the latest version if neither is given."""
        if tag is not None and version is not None:
            raise ToolError("Pass tag or version, not both")
        if tag is not None:
            prompt = call(client.get_prompt, name, tag=tag)
            data = prompt.data
        else:
            data = call(client.get_version, name, version)
        return _dump(data)

    @server.tool()
    def create_version(
        name: str,
        template: str | list[dict[str, str]],
        model_settings: dict[str, Any] | None = None,
        commit_message: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Save a new version. `template` is a string with {{ variables }}, or a list of chat
        messages [{"role": ..., "content": ...}]. `model_settings` is stored as the version's
        model_config (model, temperature, max_tokens, ...). Creates the prompt if needed.
        If the content equals the latest version, that version is returned unchanged.
        Saving a version never changes what apps read; tags move only on promote."""
        try:
            client.get_prompt_info(name)
        except NotFoundError:
            call(client.create_prompt, name, description)
        except PromptDockError as exc:
            raise ToolError(str(exc)) from None
        version = call(
            client.create_version,
            name,
            template,
            model_config=model_settings,
            commit_message=commit_message,
        )
        return _dump(version)

    @server.tool()
    def compare_versions(name: str, a: int, b: int) -> dict[str, Any]:
        """Diff two versions: unified template diff, model_config changes, and variables
        added or removed."""
        return _dump(call(client.diff, name, a, b))

    @server.tool()
    def get_leaderboard(
        name: str, sort_by: str = "version", descending: bool = True
    ) -> dict[str, Any]:
        """Every version with its latest eval score per metric. Sort by "version",
        "created_at" or a metric name."""
        return _dump(call(client.get_leaderboard, name, sort_by=sort_by, descending=descending))

    if allow_promote:

        @server.tool()
        def promote(name: str, tag: str, version: int, reason: str | None = None) -> dict[str, Any]:
            """Point a tag at a version. The tag's eval gate must pass; it cannot be
            bypassed from here. Apps reading the tag switch within their cache time."""
            return _dump(call(client.promote, name, tag, version, reason=reason))

    return server
