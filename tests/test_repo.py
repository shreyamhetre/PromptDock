import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_tracked_text_files_are_utf8() -> None:
    files = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    bad = []
    for name in files:
        try:
            (ROOT / name).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            bad.append(name)
        except FileNotFoundError:
            pass
    assert bad == []
