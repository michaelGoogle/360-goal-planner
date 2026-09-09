from unittest.mock import patch

from fastapi.testclient import TestClient
from src.app import api
from src.openai_client import _settings
from src.parse_sentence import normalize_fields


def test_normalize_maps_ceo_and_drops_bad_age():
    got = normalize_fields(
        {
            "name": None,
            "age": 42,
            "gender": "Male",
            "res": "Singapore Citizen",
            "deps": "2",
            "occ": "CEO",
        }
    )
    assert got == {
        "age": "42",
        "gender": "Male",
        "res": "Singapore Citizen",
        "deps": "2",
        "occ": "Chief Executive Officer",
    }
    assert "age" not in normalize_fields({"age": 9})


def test_normalize_drops_garbage_occupation_and_maps_mail():
    assert "occ" not in normalize_fields({"occ": "0"})
    assert "occ" not in normalize_fields({"occ": "two kids"})
    assert "occ" not in normalize_fields({"occ": "Driver yeah"})
    assert "occ" not in normalize_fields({"occ": "kids"})
    assert normalize_fields({"gender": "mail"})["gender"] == "Male"
    assert normalize_fields({"occ": "see eo"})["occ"] == "Chief Executive Officer"
    assert normalize_fields({"residency": "resident of Singapore"})["res"] == "Singapore Citizen"
    assert normalize_fields({"res": "Singapore"})["res"] == "Singapore Citizen"
    assert normalize_fields({"res": "PR"})["res"] == "Permanent Resident"


def test_parse_sentence_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = TestClient(api)
    r = client.post(
        "/v1/parse-sentence",
        json={"text": "I'm a 42 year old male CEO in Singapore with two kids"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is False
    assert body["source"] == "unavailable"
    assert body["fields"] == {}


def test_parse_sentence_uses_llm_when_configured(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = TestClient(api)
    payload = {
        "name": None,
        "age": 42,
        "gender": "Male",
        "res": "Singapore Citizen",
        "deps": "2",
        "occ": "Chief Executive Officer",
    }
    with patch("src.app.extract_about_you", return_value=normalize_fields(payload)):
        r = client.post(
            "/v1/parse-sentence",
            json={
                "text": (
                    "hi my legs 42 years old living in Singapore and have Singapore "
                    "citizenship I'm a CEO as occupation and I have two kids"
                )
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["source"] == "llm"
    assert body["fields"]["occ"] == "Chief Executive Officer"
    assert body["fields"]["age"] == "42"
    assert body["fields"]["deps"] == "2"


def test_extract_about_you_parses_mocked_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    raw = '{"name":null,"age":42,"gender":"Male","res":"Singapore Citizen","deps":"2","occ":"CEO"}'
    with patch("src.parse_sentence._call_openai", return_value=raw):
        from src.parse_sentence import extract_about_you

        got = extract_about_you("I'm a CEO as occupation and I have two kids")
    assert got["occ"] == "Chief Executive Officer"
    assert got["age"] == "42"
    assert got["deps"] == "2"


def test_parse_sentence_key_rejected(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = TestClient(api)

    class AuthenticationError(Exception):
        pass

    with patch("src.app.extract_about_you", side_effect=AuthenticationError("bad key")):
        r = client.post("/v1/parse-sentence", json={"text": "My name is Alex, 42, male Singapore citizen"})
    assert r.status_code == 503
    assert "API key was rejected" in r.json()["detail"]


def test_parse_sentence_short_text_is_empty():
    client = TestClient(api)
    r = client.post("/v1/parse-sentence", json={"text": "hi"})
    assert r.status_code == 200
    assert r.json()["fields"] == {}


def test_llm_settings_prefers_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    monkeypatch.setenv("AN_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-test")
    provider, key, model = _settings()
    assert provider == "anthropic"
    assert key == "ant-test"
    assert model == "claude-sonnet-4-5"
