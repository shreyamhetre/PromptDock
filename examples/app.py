"""A tiny "app" that keeps using whatever version a tag points to.

    python -m uv run python examples/app.py                 # demo-bot, tag prod
    python -m uv run python examples/app.py demo-bot dev    # pick prompt and tag

Leave it running, move the tag from another terminal with examples/tag.py, and watch
the version change within the cache TTL (10 seconds here) without restarting the app.
Stop it with Ctrl+C. Run examples/core_flow.py first to create demo-bot.
"""

import logging
import sys
import time

from promptdock import Client, PromptDockError

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

name = sys.argv[1] if len(sys.argv) > 1 else "demo-bot"
tag = sys.argv[2] if len(sys.argv) > 2 else "prod"

try:
    client = Client(cache_ttl=10, snapshot_path=".promptdock-snapshot.json")
except PromptDockError as exc:
    sys.exit(f"Error: {exc}")
print(f"Reading '{name}' tag '{tag}' every 2s (cache TTL 10s). Ctrl+C to stop.\n")

try:
    while True:
        prompt = client.get_prompt(name, tag=tag)
        values = {var: f"<{var}>" for var in prompt.variables}
        stale = "  (database down: last known good)" if prompt.is_stale else ""
        print(f"{time.strftime('%H:%M:%S')}  v{prompt.version}  {prompt.render(**values)}{stale}")
        time.sleep(2)
except KeyboardInterrupt:
    client.close()
