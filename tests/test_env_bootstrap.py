from unittest.mock import patch

from src.env_bootstrap import load_env_files
from src.upstream import fm_public


def test_workspace_env_wins_over_gp(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    gp = ws / "GP"
    gp.mkdir(parents=True)
    (gp / ".env").write_text("FM_UPSTREAM=http://gp-only:8062\nSHARED=gp-only\n", encoding="utf-8")
    (ws / ".env").write_text("FM_UPSTREAM=http://192.168.1.43:8062\n", encoding="utf-8")
    monkeypatch.setenv("FM_UPSTREAM", "")
    monkeypatch.delenv("SHARED", raising=False)

    load_env_files(gp_root=gp, workspace_root=ws)

    import os

    assert os.environ["FM_UPSTREAM"] == "http://192.168.1.43:8062"
    assert os.environ["SHARED"] == "gp-only"


def test_fm_public_uses_fm_upstream_env(monkeypatch):
    monkeypatch.setenv("FM_UPSTREAM", "http://192.168.1.43:8062")
    with patch("src.upstream.requests.post") as post:
        post.return_value.status_code = 200
        post.return_value.json.return_value = {"success": True}
        status, data = fm_public("people-like-you", {}, None)
    assert status == 200
    assert data["success"] is True
    assert post.call_args[0][0] == "http://192.168.1.43:8062/v1/public/people-like-you"
