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
- `examples/app.py` and `examples/tag.py`.

### Changed
- The metadata model `Prompt` is now `PromptInfo`; `Prompt` is the renderable object.

### Removed
- `tags.is_protected` (migration `0002`).
- `api_keys` table (migration `0004`): no user accounts or API keys; servers use an
  optional shared token instead.
