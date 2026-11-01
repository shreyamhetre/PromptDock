# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project scaffold: packaging, lint, type checks, CI, local Postgres via docker-compose.
- Database schema (projects, prompts, prompt_versions, tags, tag_events, eval_results) with Alembic migrations and a seeded `default` project.
- `promptdock migrate` command; `DATABASE_URL` validation (Postgres only).
- Pydantic models: `PromptVersion`, `Tag`, `TagEvent`, `EvalResultIn`, `EvalResult`, `Gate`.
- Core service: create prompts (with dev/preprod/prod tags) and versions (auto-numbered,
  deduplicated by content hash, variables extracted), get by version or tag, promote with
  eval gates (`force` needs a reason), undo-style rollback, eval results, tag audit log.
- Row locking so concurrent promotes and version creation stay consistent.
- Read-only views with names and version numbers instead of ids (migration `0003`):
  `v_prompt_status`, `v_versions`, `v_tags`, `v_tag_history`, `v_eval_results`.
- `Client` (library mode): `get_prompt` by tag, version or latest returning a `Prompt`
  with `.render(**values)`, `.version` and `.model_config`; methods for versions, tags,
  gates, eval results and history.
- Sandboxed Jinja2 rendering; `MissingVariableError` names every missing variable.
- Cache: 60 s TTL for tag lookups, versions cached forever; last-known-good fallback
  when the database is down, optional snapshot file for cold starts.
- `examples/app.py`.
- `Client(actor=...)`: who made each change (versions, promotes, rollbacks, gates);
  defaults to the OS username, self-reported like a git author. `Client(token=...)` for
  servers that set a shared token.
- REST server (`pip install promptdock[server]`, `promptdock serve`): prompts, versions,
  tags, gates, tag events (`/prompts/{name}/tags/{tag}/events`), evals; OpenAPI docs at
  `/docs`; `ETag`/304 on the prompt fetch endpoint.
- Optional shared token (`PROMPTDOCK_TOKEN` / `--token`); listens on 127.0.0.1 by default
  and warns when exposed without a token. Actor via the `X-Actor` header.
- `Client(base_url=..., token=...)` server mode with the same methods as library mode.
- CLI: `prompts list`, `versions list|show`, `promote`, `rollback`, `history`,
  `evals push results.jsonl`, `export ./prompts`, `push ./prompts [--tag dev] [--dry-run]`;
  `--actor` / `--reason` on writes; connects via `PROMPTDOCK_URL` or `DATABASE_URL`.
- Eval gates from the CLI: `promptdock gate set NAME TAG --min accuracy=0.85 --max
  latency_ms=1200 [--require-better-than-current]`, `gate show`, `gate clear`.
- Leaderboard (versions x metrics, latest score per metric, sort by any column):
  `GET /prompts/{name}/leaderboard`, `Client.get_leaderboard`, `promptdock leaderboard`.
- Diff of two versions (template text, model_config, variables):
  `GET /prompts/{name}/diff?a=&b=`, `Client.diff`, `promptdock diff`.
- Promote warns when a version needs template variables the tag's current version did
  not; `strict=True` / `--strict` refuses instead.
- Dashboard (`pip install promptdock[ui]`, `promptdock serve --ui`, at `/ui/`): prompts
  list, versions, tags with promote (gate result shown, force with reason) and rollback
  (confirm), sortable leaderboard with one score-over-versions chart per metric, diff of
  two versions, audit log. Asks once for a name (X-Actor) and the token if needed.
- MCP server (`pip install promptdock[mcp]`, `promptdock mcp`, stdio): `list_prompts`,
  `get_prompt`, `create_version`, `compare_versions`, `get_leaderboard`, and `promote`
  only with `--allow-promote` (never forced); actor `mcp:<OS username>`.

### Changed
- Gate rules: `min` means higher is better and `max` means lower is better (no separate
  `higher_is_better` setting); `require_better_than_current` passes when a metric is at
  least as good as the current version's.
- Core API matches the revised plan: `create_version(..., actor=None)` saves the actor as
  `created_by`; `list_tag_events(name, tag)`; `promote(name, tag, version, actor, reason,
  force)`.
- The metadata model `Prompt` is now `PromptInfo`; `Prompt` is the renderable object.

### Removed
- `tags.is_protected` (migration `0002`).
- `api_keys` table (migration `0004`): no user accounts or API keys; servers use an
  optional shared token instead.
