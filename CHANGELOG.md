# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project scaffold: packaging, lint, type checks, CI, local Postgres via docker-compose.
- Database schema (projects, prompts, prompt_versions, tags, tag_events, eval_results,
  api_keys) with Alembic migrations and a seeded `default` project.
- `promptdock migrate` command; `DATABASE_URL` validation (Postgres only).
- Pydantic models: `PromptVersion`, `Tag`, `TagEvent`, `EvalResultIn`, `EvalResult`, `Gate`.
- Core service: create prompts (with dev/preprod/prod tags) and versions (auto-numbered,
  deduplicated by content hash, variables extracted), get by version or tag, promote with
  eval gates (`force` needs a reason), undo-style rollback, eval results, tag audit log.
- Row locking so concurrent promotes and version creation stay consistent.

### Removed
- `tags.is_protected` (migration `0002`).
