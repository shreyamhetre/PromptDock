"""Who made a change: a self-reported name, like a git author. Not verified."""

import getpass


def default_actor() -> str | None:
    """The OS username, or None if it cannot be determined."""
    try:
        return getpass.getuser() or None
    except Exception:  # getuser raises if no user name is available (e.g. some containers)
        return None
