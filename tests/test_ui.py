"""Phase 7: the dashboard is served by `serve --ui` from files inside the package."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from promptdock.cli import app as cli
from promptdock.errors import ConfigError
from promptdock.server import create_app
from promptdock.ui import STATIC_DIR, is_built


@pytest.fixture
def fake_ui(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html><div id=root></div></html>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('hi')", encoding="utf-8")
    return tmp_path


def test_dashboard_is_served_and_public(db_url: str, fake_ui: Path) -> None:
    app = create_app(db_url, token="secret", ui=True, ui_dir=fake_ui)
    with TestClient(app) as api:
        page = api.get("/ui/")
        assert page.status_code == 200 and "id=root" in page.text
        assert api.get("/ui/assets/app.js").status_code == 200
        root = api.get("/", follow_redirects=False)
        assert (root.status_code, root.headers["location"]) == (307, "/ui/")
        # The page is public, but the API it calls still needs the token.
        assert api.get("/prompts").status_code == 401


def test_no_dashboard_without_flag(db_url: str) -> None:
    with TestClient(create_app(db_url, token="")) as api:
        assert api.get("/ui/").status_code == 404


def test_missing_build_is_a_clear_error(db_url: str, tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="npm run build"):
        create_app(db_url, ui=True, ui_dir=tmp_path)


def test_serve_ui_flag(db_url: str, fake_ui: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("promptdock.ui.STATIC_DIR", fake_ui)
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: None)
    result = CliRunner().invoke(cli, ["serve", "--ui", "--database-url", db_url])
    assert result.exit_code == 0, result.output
    assert "Dashboard at http://127.0.0.1:8000/ui/" in result.output


@pytest.mark.skipif(not is_built(), reason="dashboard not built (cd ui && npm run build)")
def test_real_build_is_served(db_url: str) -> None:
    with TestClient(create_app(db_url, token="", ui=True)) as api:
        page = api.get("/ui/")
        assert page.status_code == 200 and "/ui/assets/" in page.text
        asset = next((STATIC_DIR / "assets").glob("*.js")).name
        assert api.get(f"/ui/assets/{asset}").status_code == 200
