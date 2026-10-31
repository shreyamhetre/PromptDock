# Contributing

## Setup

1. Install [uv](https://docs.astral.sh/uv/) and Docker.
2. Install dependencies: `uv sync`
3. Install git hooks: `uv run pre-commit install`
4. Start a local Postgres: `docker compose up -d`
5. Copy `.env.example` to `.env` (or export `DATABASE_URL`).

## Checks

```bash
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # type check
uv run pytest              # tests (DB tests start Postgres via testcontainers)
```

## Workflow

- `main` is protected: open a pull request, get one review, keep CI green.
- Track work as GitHub Issues with a milestone per phase.
- Keep business logic in `src/promptdock/core/`; backends and server routes only call into it.
