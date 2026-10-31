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

client = Client()  # reads DATABASE_URL; or Client("postgresql://...")

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
client.promote("support-bot", "prod", 1, actor="shreya")

# In your app: always ask for a tag, never a hard-coded version.
prompt = client.get_prompt("support-bot", tag="prod")
messages = prompt.render(product="PromptDock", question="How do I roll back?")
# call your LLM with messages and prompt.model_config

client.rollback("support-bot", "prod")  # apps pick this up within the cache TTL (60 s)
```

Reads are cached for `cache_ttl` seconds (default 60). If the database is unreachable,
`get_prompt` returns the last version it fetched and logs a warning; pass
`snapshot_path="prompts.json"` to keep those copies on disk for restarts.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
