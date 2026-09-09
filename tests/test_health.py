from fastapi.testclient import TestClient
from src.app import api


def test_healthz():
    client = TestClient(api)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["service"] == "gp"

