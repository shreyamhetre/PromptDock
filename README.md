<div align="center">

<img src="https://raw.githubusercontent.com/shreyamhetre/PromptDock/main/docs/assets/logo.svg" alt="PromptDock logo" width="88" height="88">

# PromptDock

**Version your prompts like code. Ship them like releases.**

Immutable prompt versions · movable `dev` / `preprod` / `prod` tags · eval-gated promotion · one-click rollback

[![PyPI](https://img.shields.io/pypi/v/promptdock?color=2a78d6&label=PyPI)](https://pypi.org/project/promptdock/)
[![Python](https://img.shields.io/pypi/pyversions/promptdock?color=2a78d6)](https://pypi.org/project/promptdock/)
[![CI](https://github.com/shreyamhetre/PromptDock/actions/workflows/ci.yml/badge.svg)](https://github.com/shreyamhetre/PromptDock/actions/workflows/ci.yml)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-2a78d6?logo=docker&logoColor=white)](https://github.com/shreyamhetre/PromptDock/pkgs/container/promptdock)
[![License: MIT](https://img.shields.io/badge/license-MIT-2a78d6)](https://github.com/shreyamhetre/PromptDock/blob/main/LICENSE)

[Quickstart](#quickstart) · [Dashboard](#dashboard) · [CLI](#command-line) · [AI agents](#ai-agents-mcp) · [Docker](#docker) · [Changelog](https://github.com/shreyamhetre/PromptDock/blob/main/CHANGELOG.md)

</div>

## Why PromptDock

Prompts change more often than code, but they usually ship with the code — so every wording
tweak is a deploy, and every bad prompt is an incident with no quick undo.

PromptDock separates the two. Your app asks for a **tag**; you decide which **version** the
tag points to.

```python
prompt = client.get_prompt("support-bot", tag="prod")  # never a hard-coded version
```

| Step | What you do | Versions | `dev` | `preprod` | `prod` |
| :-: | --- | :-: | :-: | :-: | :-: |
| 1 | Save a prompt | v1 | – | – | – |
| 2 | Promote it through the environments | v1 | v1 | v1 | v1 |
| 3 | Edit and save | v1, v2 | v1 | v1 | v1 |
| 4 | Promote v2 — the eval gate checks its scores first | v1, v2 | v2 | v2 | v2 |
| 5 | v2 misbehaves: **roll back** prod | v1, v2 | v2 | v2 | **v1** |

Apps pick up every promote and rollback within their cache time (60 s by default). **No redeploy, no code change.**

## Features

| | |
| --- | --- |
| **Immutable versions** | Text or chat templates with `{{ variables }}` and model settings. Saving identical content never creates a duplicate. |
| **Tags as pointers** | `dev`, `preprod`, `prod` out of the box, plus your own (`canary-eu`, per-customer…). |
| **Eval gates** | Push scores from any eval tool. A gate like `accuracy ≥ 0.85` blocks promotion of a worse version. |
| **Instant rollback** | Undo the last promote — again and again, like undo. Never blocked by gates. |
| **Full audit log** | Every move records who, when, from → to and why. Forced promotes are flagged. |
| **Leaderboard & diff** | Compare versions by score and see exactly what changed in text and settings. |
| **Resilient reads** | Cached, and apps keep the last good prompt if the database or server is down. |
| **Use it your way** | Python library, REST API, dashboard, CLI, MCP server for AI agents, or Docker. |

## Quickstart

```bash
pip install promptdock
export DATABASE_URL=postgresql://user:password@localhost:5432/promptdock
promptdock migrate
```

```python
from openai import OpenAI
from promptdock import Client

client = Client()  # reads DATABASE_URL; your OS username is recorded as the actor
llm = OpenAI()

client.create_prompt("support-bot")
client.create_version(
    "support-bot",
    [
        {"role": "system", "content": "You support {{ product }}. Be concise."},
        {"role": "user", "content": "{{ question }}"},
    ],
    model_config={"model": "gpt-4o", "temperature": 0.2},
    commit_message="First version",
)
client.promote("support-bot", "prod", 1)

# In your app
prompt = client.get_prompt("support-bot", tag="prod")
messages = prompt.render(product="Acme", question="How do I reset my password?")
response = llm.chat.completions.create(messages=messages, **prompt.model_config)
```

`render()` raises `MissingVariableError` naming any variable you forgot. Ready-to-run
examples for [OpenAI](https://github.com/shreyamhetre/PromptDock/blob/main/examples/openai_app.py), [Anthropic](https://github.com/shreyamhetre/PromptDock/blob/main/examples/anthropic_app.py),
[LangChain](https://github.com/shreyamhetre/PromptDock/blob/main/examples/langchain_app.py) and an [LLM-as-judge eval script](https://github.com/shreyamhetre/PromptDock/blob/main/examples/push_evals_llm_judge.py)
are in [`examples/`](https://github.com/shreyamhetre/PromptDock/tree/main/examples/).

### Ways to run it

| Mode | Install | Run | Best for |
| --- | --- | --- | --- |
| Library | `pip install promptdock` | `Client()` | One app talking to its own Postgres |
| Server | `pip install "promptdock[server]"` | `promptdock serve` | Many apps or languages sharing one registry |
| Dashboard | `pip install "promptdock[ui]"` | `promptdock serve --ui` | Teams who want to see and promote in a browser |
| Docker | — | `docker run ghcr.io/shreyamhetre/promptdock` | Non-Python teams, servers without pip |
| AI agents | `pip install "promptdock[mcp]"` | `promptdock mcp` | Claude Desktop, Cursor and other MCP clients |

Requirements: Python 3.10+ and Postgres 14+.

## Eval gates

Push results from any evaluation — a script, an LLM judge, a CI job — in one fixed shape:

```json
{"prompt": "support-bot", "version": 4, "metric": "accuracy", "score": 0.87,
 "run_id": "run-2026-10-30", "evaluator": "llm-judge", "metadata": {"dataset": "faq-100"}}
```

Then require a quality bar before a tag can move:

```bash
promptdock gate set support-bot prod --min accuracy=0.85 --max latency_ms=1200
promptdock promote support-bot prod 5
# Error: Gate for tag 'prod' on prompt 'support-bot' failed:
#   - accuracy: 0.81 is below the minimum 0.85
```

`min` means higher is better, `max` means lower is better. The gate uses each metric's latest
score; a missing score fails. `--force --reason "…"` bypasses it and is recorded.

## Dashboard

```bash
pip install "promptdock[ui]"
promptdock serve --ui            # http://127.0.0.1:8000/ui/
```

The dashboard shows each prompt's deployment pipeline (`dev` → `preprod` → `prod`), its
versions, a sortable leaderboard with a score chart per metric, a diff of any two versions and
the audit log. You can promote (the gate result is shown) and roll back with a confirmation.
No Node.js needed — the dashboard ships inside the package.

## Server and REST API

```bash
pip install "promptdock[server]"
promptdock serve                 # http://127.0.0.1:8000 — interactive API docs at /docs
```

```python
client = Client(base_url="http://127.0.0.1:8000")  # same methods as library mode
```

Any language can use it: `curl "http://127.0.0.1:8000/prompts/support-bot?tag=prod"`.
Responses carry an `ETag`, so unchanged prompts cost a tiny `304`.

<details>
<summary><b>Securing your server</b></summary>
<br>

There are no user accounts. `promptdock serve` listens only on this machine by default. To
share it, run it on a private network **or** set a shared token:

```bash
PROMPTDOCK_TOKEN=change-me promptdock serve --host 0.0.0.0
```

Every request except `/health` must then send `Authorization: Bearer <token>`; clients pass
`token=...` or set `PROMPTDOCK_TOKEN`. Listening on `0.0.0.0` without a token prints a warning.

Who made a change is self-reported in the `X-Actor` header (the Python client sends its
`actor`, which defaults to your OS username) — an honest team history, like a git author,
not a security control.
</details>

## Command line

The CLI connects like the client: `PROMPTDOCK_URL` (+ `PROMPTDOCK_TOKEN`) for a server,
otherwise `DATABASE_URL`.

```bash
promptdock export ./prompts                        # one YAML file per prompt
promptdock push ./prompts --tag dev -m "Friendlier"  # new versions for changed files only
promptdock evals push results.jsonl                # eval results, one JSON object per line
promptdock promote support-bot prod 3 --reason "evals passed"
promptdock rollback support-bot prod --reason "complaints"
promptdock leaderboard support-bot --sort accuracy
promptdock diff support-bot 3 4
promptdock history support-bot prod
```

`push` never overwrites anything and never moves `prod` — promoting to production is always
an explicit step.

## AI agents (MCP)

Let Claude Desktop, Cursor or any MCP client read and version prompts:

```json
{
  "mcpServers": {
    "promptdock": {
      "command": "promptdock",
      "args": ["mcp"],
      "env": { "DATABASE_URL": "postgresql://user:password@localhost:5432/promptdock" }
    }
  }
}
```

Tools: `list_prompts`, `get_prompt`, `create_version`, `compare_versions`, `get_leaderboard`.
`promote` is available only with `"args": ["mcp", "--allow-promote"]`; gates still apply and
agents can never force. Agent changes are recorded as `mcp:<your OS username>`.

## Docker

```bash
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:password@db-host:5432/promptdock \
  -e PROMPTDOCK_TOKEN=change-me \
  ghcr.io/shreyamhetre/promptdock
```

The container migrates the database, then serves the API and dashboard on port 8000. To try
everything locally with a bundled Postgres: `docker compose --profile server up -d`.

## Privacy

PromptDock collects **no telemetry or usage data**. It talks only to your own Postgres and,
if you run one, your own PromptDock server.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](https://github.com/shreyamhetre/PromptDock/blob/main/CONTRIBUTING.md) for setup, tests and the
release process.

## License

[MIT](https://github.com/shreyamhetre/PromptDock/blob/main/LICENSE)
