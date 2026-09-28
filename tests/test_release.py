import json

from fastapi.testclient import TestClient
from src.app import api
from src.release_info import load_release_id


def test_load_release_id(tmp_path, monkeypatch):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"R": "0.6-260923"}), encoding="utf-8")
    monkeypatch.setenv("GP_RELEASE_NOTES_PATH", str(path))
    assert load_release_id() == "0.6-260923"


def test_release_endpoint(tmp_path, monkeypatch):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"R": "0.6-260923"}), encoding="utf-8")
    monkeypatch.setenv("GP_RELEASE_NOTES_PATH", str(path))
    client = TestClient(api)
    response = client.get("/v1/release")
    assert response.status_code == 200
    assert response.json() == {"R": "0.6-260923", "release": "0.6-260923"}
