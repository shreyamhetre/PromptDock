from typer.testing import CliRunner

import promptdock
from promptdock.cli import app


def test_package_imports() -> None:
    assert isinstance(promptdock.__version__, str)


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == promptdock.__version__
