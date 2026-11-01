# PromptDock

Focused prompt versioning. PromptDock stores **immutable prompt versions**, points **tags**
(`dev`, `preprod`, `prod`, or your own) at them, and attaches **eval results** so a tag can only
move to a version that passes its gate. Promote and rollback move a pointer, never your code.

> Status: pre-alpha, under active development.

## Ways to use it

| Mode | Install | Run |
| --- | --- | --- |
| Library | `pip install promptdock` | import and use |
| Server | `pip install promptdock[server]` | `promptdock serve` |
| Server + UI | `pip install promptdock[ui]` | `promptdock serve --ui` |
| Docker | `docker run promptdock/server` | — |

All modes use Postgres, configured with `DATABASE_URL`.

## Quickstart (library mode)

```bash
export DATABASE_URL=postgresql://user:password@localhost:5432/promptdock
promptdock migrate
```

```python
from promptdock import Client

client = Client()  # reads DATABASE_URL; or Client("postgresql://...", actor="shreya")

client.create_prompt("support-bot")
client.create_version(
    "support-bot",
    [
        {"role": "system", "content": "You support {{ product }}."},
        {"role": "user", "content": "{{ question }}"},
    ],
    model_config={"model": "gpt-4o", "temperature": 0.2},
    commit_message="first version",
)
client.promote("support-bot", "prod", 1)  # recorded with actor = your OS username

# In your app: always ask for a tag, never a hard-coded version.
prompt = client.get_prompt("support-bot", tag="prod")
messages = prompt.render(product="PromptDock", question="How do I roll back?")
# call your LLM with messages and prompt.model_config

client.rollback("support-bot", "prod")  # apps pick this up within the cache TTL (60 s)
```

Reads are cached for `cache_ttl` seconds (default 60). If the database is unreachable,
`get_prompt` returns the last version it fetched and logs a warning; pass
`snapshot_path="prompts.json"` to keep those copies on disk for restarts.

## Quickstart (server mode)

```bash
pip install "promptdock[server]"
promptdock migrate
promptdock serve                      # http://127.0.0.1:8000, API docs at /docs
```

```python
from promptdock import Client

client = Client(base_url="http://127.0.0.1:8000")  # same methods as library mode
prompt = client.get_prompt("support-bot", tag="prod")
```

Any language can call the REST API, e.g.
`curl "http://127.0.0.1:8000/prompts/support-bot?tag=prod"`.

**Who did it:** send `X-Actor: <name>` on changes (the Python client sends its `actor`,
which defaults to your OS username). It is recorded in the history, not verified.

**Securing your server:** there are no user accounts. `promptdock serve` only listens on
this machine by default. To share it, either run it on a private network or set a shared
token: `PROMPTDOCK_TOKEN=... promptdock serve --host 0.0.0.0`. Every request except
`/health` must then send `Authorization: Bearer <token>`; clients pass `token=...` (or set
`PROMPTDOCK_TOKEN`). Listening on `0.0.0.0` without a token prints a warning.

## Dashboard

```bash
pip install "promptdock[ui]"
promptdock serve --ui          # http://127.0.0.1:8000/ui/
```

Prompts list, versions and tags, a sortable leaderboard with a score-over-versions chart
per metric, diffs between any two versions, and the audit log. You can promote (the gate
result is shown) and roll back (with a confirm step). It asks once for your name (sent as
`X-Actor`) and, if the server has one, the token; both stay in your browser. No Node is
needed to run it.

## Command line

The CLI connects like the client: `PROMPTDOCK_URL` (+ `PROMPTDOCK_TOKEN`) for a server,
otherwise `DATABASE_URL`. Changes are recorded with `--actor` (default: your OS username).

```bash
promptdock export ./prompts                  # one YAML file per prompt (latest version)
# ...edit ./prompts/support-bot.yaml...
promptdock push ./prompts --tag dev -m "friendlier tone"   # new versions only for changed files
promptdock evals push results.jsonl          # eval results, one JSON object per line
promptdock promote support-bot prod 3 --reason "evals passed"
promptdock rollback support-bot prod --reason "complaints"
promptdock versions list support-bot
promptdock history support-bot prod
```

`push` never overwrites anything and never moves `prod`; promote to `prod` explicitly.

```bash
promptdock gate set support-bot prod --min accuracy=0.85 --max latency_ms=1200
promptdock leaderboard support-bot --sort accuracy
promptdock diff support-bot 3 7
```

A gate uses the latest result per metric; a missing metric fails. `--force --reason ...`
bypasses a failing gate and is recorded. Rollback never runs the gate.

## AI agents (MCP)

`pip install "promptdock[mcp]"`, then add PromptDock to your agent's MCP config. For
Claude Desktop (`claude_desktop_config.json`) or Cursor (`.cursor/mcp.json`):

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

Use `PROMPTDOCK_URL` (+ `PROMPTDOCK_TOKEN`) instead of `DATABASE_URL` to go through a
server. Tools: `list_prompts`, `get_prompt`, `create_version`, `compare_versions`,
`get_leaderboard`. `promote` is only offered with `"args": ["mcp", "--allow-promote"]`,
gates still apply, and agents can never force. Agent changes are recorded with the actor
`mcp:<your OS username>`.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). The dashboard source is in `ui/` (React + Vite + Recharts):
`cd ui && npm ci && npm run build` writes the built files into `src/promptdock/ui/static/`.

## License

MIT
