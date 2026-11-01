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

Tests use Postgres 16 by default. CI runs Python 3.10–3.13 against Postgres 14 and 17;
to try another version locally: `PROMPTDOCK_TEST_POSTGRES_IMAGE=postgres:14 uv run pytest`.

## Dashboard

The UI source lives in `ui/` (React + Vite + Recharts). Build it into the Python package
with `cd ui && npm ci && npm run build` (output: `src/promptdock/ui/static/`, git-ignored
but included in the wheel). For live reload, run `promptdock serve` and `npm run dev`
(it proxies API calls to port 8000).

## Workflow

- `main` is protected: open a pull request, get one review, keep CI green.
- Track work as GitHub Issues with a milestone per phase.
- Keep business logic in `src/promptdock/core/`; backends and server routes only call into it.
