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

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
