"""Move a tag from the command line (a stand-in until the Phase 5 CLI).

python -m uv run python examples/tag.py promote demo-bot prod 2
python -m uv run python examples/tag.py rollback demo-bot prod
python -m uv run python examples/tag.py status demo-bot
"""

import sys

from promptdock import Client, PromptDockError

USAGE = __doc__ or ""

args = sys.argv[1:]
try:
    with Client() as client:
        if len(args) == 4 and args[0] == "promote":
            _, name, tag, version = args
            moved = client.promote(name, tag, int(version), actor="tag.py")
            print(f"{tag} -> v{moved.version}")
        elif len(args) == 3 and args[0] == "rollback":
            _, name, tag = args
            moved = client.rollback(name, tag, actor="tag.py")
            print(f"{tag} rolled back -> v{moved.version}")
        elif len(args) == 2 and args[0] == "status":
            for t in client.list_tags(args[1]):
                print(f"{t.name:<10} {'v' + str(t.version) if t.version else '-'}")
        else:
            sys.exit(USAGE)
except PromptDockError as exc:
    sys.exit(f"Error: {exc}")
