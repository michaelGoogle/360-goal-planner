from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.app import api
from src.explain import listed_prompt_files, load_prompt, prompt_filename


def test_prompt_files_exist_and_load():
    root = Path(__file__).resolve().parents[1] / "src" / "prompts"
    for name in listed_prompt_files():
        path = root / name
        assert path.is_file(), name
        assert len(path.read_text(encoding="utf-8").strip()) > 40, name
    system = load_prompt("mira", "d2cIntro")
    assert "Mira" in system
    assert "Start my plan" in system
    assert "predict" in system.lower()
    intro = load_prompt("intro", "d2cIntro")
    assert "goal planner" in intro.lower()
    assert "predict" in intro.lower()
    assert prompt_filename("intro", None) == "intro.md"
    money = load_prompt("mira", "d2cMoney")
    assert "incomeMonthly" in money
    assert "Glassdoor" in money
    assert prompt_filename("prod", None) == "products.md"


def test_explain_fallback_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = TestClient(api)
    r = client.post(
        "/v1/explain",
        json={
            "kind": "money",
            "route": "d2cMoney",
            "context": {
                "you": {"firstName": "Alex"},
                "money": {"incomeMonthly": 9000, "expenseMonthly": 5500, "budgetMonthly": 3500, "liquid": 120000},
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["source"] == "fallback"
    assert "month" in body["text"].lower()
    assert "glassdoor" in body["text"].lower()


def test_explain_mira_intro_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = TestClient(api)
    r = client.post("/v1/explain", json={"kind": "mira", "route": "d2cIntro", "context": {}})
    assert r.status_code == 200
    text = r.json()["text"]
    assert "Mira" in text
    assert "three minutes" in text
    assert "Start my plan" in text
    assert "predict" in text.lower()
    assert "statement" in text.lower()


def test_explain_intro_fallback(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = TestClient(api)
    r = client.post("/v1/explain", json={"kind": "intro", "route": "d2cIntro", "context": {}})
    assert r.status_code == 200
    text = r.json()["text"]
    assert "goal planner" in text.lower()
    assert "HappiU" not in text
    assert "Start my plan" in text
    assert "predict" in text.lower()
    assert "statement" in text.lower()
    assert "estimate" not in text.lower()


def test_explain_uses_llm_when_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = TestClient(api)
    spoken = "Hello, I am Mira. Your income is nine thousand dollars a month and your score is thirty eight."
    with patch("src.explain._call_openai", return_value=spoken):
        r = client.post(
            "/v1/explain",
            json={"kind": "mira", "route": "d2cMoney", "context": {"money": {"incomeMonthly": 9000}}},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "llm"
    assert body["text"] == spoken


def test_explain_rejects_unknown_kind():
    client = TestClient(api)
    r = client.post("/v1/explain", json={"kind": "weather", "route": "d2cIntro"})
    assert r.status_code == 400
