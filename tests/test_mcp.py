"""Phase 8: the MCP server, tested with a real MCP client (in memory and over stdio)."""

import json
import os
import sys
from collections.abc import Awaitable, Callable
from typing import Any

import anyio
import pytest
from mcp.client.client import Client as McpClient
from mcp.client.stdio import StdioServerParameters

from promptdock import Client
from promptdock.mcp.server import agent_actor, build_server

NAME = "support-bot"


def _result(result: Any) -> Any:
    """The tool's return value (structured content, else the JSON text block)."""
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured.get("result", structured)
    return json.loads(result.content[0].text)


def _error_text(result: Any) -> str:
    return str(getattr(result.content[0], "text", ""))


def _session(server: Any, body: Callable[[McpClient], Awaitable[None]]) -> None:
    async def main() -> None:
        async with McpClient(server) as mcp:
            await body(mcp)

    anyio.run(main)


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Client:
    monkeypatch.setattr("getpass.getuser", lambda: "shreya")
    c = Client(db_url, actor=agent_actor(), cache_ttl=0)
    c.create_prompt(NAME, "FAQ bot")
    c.create_version(NAME, "Hi {{ user }}", model_config={"model": "gpt-4o"})
    c.add_eval_results([{"prompt": NAME, "version": 1, "metric": "accuracy", "score": 0.9}])
    return c


def test_tools_without_promote(client: Client) -> None:
    async def body(mcp: McpClient) -> None:
        tools = {t.name for t in (await mcp.list_tools()).tools}
        assert tools == {
            "list_prompts",
            "get_prompt",
            "create_version",
            "compare_versions",
            "get_leaderboard",
        }

        listed = _result(await mcp.call_tool("list_prompts", {}))
        assert listed == [
            {
                "name": NAME,
                "description": "FAQ bot",
                "tags": {"dev": None, "preprod": None, "prod": None},
            }
        ]

        latest = _result(await mcp.call_tool("get_prompt", {"name": NAME}))
        assert (latest["version"], latest["model_config"]) == (1, {"model": "gpt-4o"})

        created = _result(
            await mcp.call_tool(
                "create_version",
                {
                    "name": NAME,
                    "template": "Hi {{ user }}, about {{ product }}",
                    "commit_message": "agent edit",
                },
            )
        )
        assert (created["version"], created["created_by"]) == (2, "mcp:shreya")

        brand_new = _result(
            await mcp.call_tool(
                "create_version",
                {"name": "new-bot", "template": [{"role": "system", "content": "Be brief."}]},
            )
        )
        assert (brand_new["prompt"], brand_new["version"]) == ("new-bot", 1)

        diff = _result(await mcp.call_tool("compare_versions", {"name": NAME, "a": 1, "b": 2}))
        assert diff["variables_added"] == ["product"]

        board = _result(await mcp.call_tool("get_leaderboard", {"name": NAME}))
        assert [r["version"] for r in board["rows"]] == [2, 1]
        assert board["rows"][1]["scores"] == {"accuracy": 0.9}

        missing = await mcp.call_tool("get_prompt", {"name": "nope"})
        assert missing.is_error
        assert "not found" in _error_text(missing)

    _session(build_server(client), body)


def test_promote_only_when_allowed_and_never_forced(client: Client) -> None:
    client.set_gate(NAME, "prod", {"rules": [{"metric": "accuracy", "min": 0.95}]})

    async def body(mcp: McpClient) -> None:
        tools = {t.name: t for t in (await mcp.list_tools()).tools}
        assert "promote" in tools
        assert "force" not in json.dumps(tools["promote"].input_schema)

        refused = await mcp.call_tool("promote", {"name": NAME, "tag": "prod", "version": 1})
        assert refused.is_error and "below the minimum 0.95" in _error_text(refused)

        moved = _result(await mcp.call_tool("promote", {"name": NAME, "tag": "dev", "version": 1}))
        assert moved["version"] == 1

    _session(build_server(client, allow_promote=True), body)
    assert client.list_tag_events(NAME, "dev")[0].actor == "mcp:shreya"


def test_stdio_server_like_claude_desktop(client: Client, db_url: str) -> None:
    """Spawn `promptdock mcp` as a subprocess and talk to it over stdio."""
    env = {**os.environ, "DATABASE_URL": db_url}
    env.pop("PROMPTDOCK_URL", None)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from promptdock.cli import app; app()", "mcp"],
        env=env,
    )

    async def body(mcp: McpClient) -> None:
        tools = {t.name for t in (await mcp.list_tools()).tools}
        assert "get_prompt" in tools and "promote" not in tools
        prompt = _result(await mcp.call_tool("get_prompt", {"name": NAME, "version": 1}))
        assert prompt["template"] == "Hi {{ user }}"

    _session(params, body)
