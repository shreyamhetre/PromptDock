# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [semantic versioning](https://semver.org/) (staying on 0.x until the API is
stable).

## [Unreleased]

## [0.1.0] - 2026-11-01

First release.

### Added

- **Versions and tags.** Immutable, numbered prompt versions (text or chat messages, Jinja2
  variables detected, identical content deduplicated) and tags (`dev`, `preprod`, `prod`
  by default, plus custom ones) that point at them. Promote moves a tag; rollback undoes
  the last promote, again and again like undo. Every move is recorded in an audit log with
  from/to versions, a self-reported actor and an optional reason.
- **Eval results and gates.** Submit results in a fixed schema (`prompt`, `version`,
  `metric`, `score`, `run_id`, `evaluator`, `metadata`). A gate on a tag requires the latest
  score per metric to meet `min` (higher is better) / `max` (lower is better) rules and,
  optionally, be at least as good as the current version. `force` with a reason bypasses
  a failing gate and is recorded. Rollback never runs the gate.
- **Leaderboard and diff.** Versions x metrics with the latest score, sortable by any
  column; text diff of two versions plus `model_config` and variable changes. Promote
  warns when a version needs new template variables (`strict` refuses instead).
- **Client** (`pip install promptdock`). One API in library mode (`Client(db_url=...)`,
  straight to Postgres) and server mode (`Client(base_url=..., token=...)`): `get_prompt`
  returns a `Prompt` with `.render(**values)`, `.version`, `.model_config`. Sandboxed
  rendering with `MissingVariableError`, 60 s cache, last-known-good fallback when the
  database or server is down, optional snapshot file for cold starts.
- **REST server** (`pip install promptdock[server]`, `promptdock serve`). OpenAPI docs at
  `/docs`, ETag/304 on the prompt fetch. No user accounts: listens on 127.0.0.1 by default,
  optional shared `PROMPTDOCK_TOKEN`, warning when exposed without one; actor via the
  `X-Actor` header.
- **Dashboard** (`pip install promptdock[ui]`, `promptdock serve --ui`). Prompts, versions,
  tags with promote (gate result shown) and rollback (confirm), leaderboard with a
  score-over-versions chart per metric, diff, audit log.
- **CLI.** `migrate`, `serve`, `prompts list`, `versions list|show`, `promote`, `rollback`,
  `history`, `evals push`, `export` / `push` (YAML files; never overwrites, never moves
  `prod`), `gate set|show|clear`, `leaderboard`, `diff`, `mcp`.
- **MCP server** (`pip install promptdock[mcp]`, `promptdock mcp`). Tools for agents:
  `list_prompts`, `get_prompt`, `create_version`, `compare_versions`, `get_leaderboard`,
  and `promote` only with `--allow-promote` (never forced); actor `mcp:<OS username>`.
- **Docker image** `ghcr.io/shreyamhetre/promptdock` (migrates, then serves API and
  dashboard) and `docker compose --profile server up` for local use.
- Read-only database views with names instead of ids: `v_prompt_status`, `v_versions`,
  `v_tags`, `v_tag_history`, `v_eval_results`.
- Examples for OpenAI, Anthropic and LangChain, and an LLM-as-judge eval script.
- No telemetry or usage tracking.

[Unreleased]: https://github.com/shreyamhetre/PromptDock/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/shreyamhetre/PromptDock/releases/tag/v0.1.0
