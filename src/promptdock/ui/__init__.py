"""The dashboard: React files built into ``static/`` and served by ``promptdock serve --ui``.

The built files ship inside the wheel; building them needs Node (``npm run build`` in
``ui/``), using them does not.
"""

from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"


def is_built(directory: Path = STATIC_DIR) -> bool:
    return (directory / "index.html").is_file()
