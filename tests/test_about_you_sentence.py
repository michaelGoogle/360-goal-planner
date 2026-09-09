"""70 About You 'tell us in one sentence' cases: happy, negative, and voice-mishear.

Regex path: live chips (mirrors frontend parse.ts).
LLM path: OpenAI extract + normalize_fields (mocked in CI; optional live).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from src.app import api
from src.parse_sentence import extract_about_you, normalize_fields

from tests.sentence_regex import parse_sentence_regex

CASES_PATH = Path(__file__).parent / "fixtures" / "about_you_sentences.json"
CASES = json.loads(CASES_PATH.read_text(encoding="utf-8"))
assert len(CASES) == 70, f"expected 70 cases, found {len(CASES)}"

HAPPY = [c for c in CASES if c["kind"] == "happy"]
NEGATIVE = [c for c in CASES if c["kind"] == "negative"]
VOICE = [c for c in CASES if c["kind"] == "voice"]
assert len(HAPPY) == 30 and len(NEGATIVE) == 20 and len(VOICE) == 20


def _ids(cases: list[dict]) -> list[str]:
    return [c["id"] for c in cases]


def assert_spec(got: dict, spec: dict, *, label: str) -> None:
    for key, want in (spec.get("expect") or {}).items():
        assert got.get(key) == want, f"{label} {key}: got {got.get(key)!r}, want {want!r} (full={got})"
    for key in spec.get("absent") or []:
        assert key not in got, f"{label} {key} should be absent, got {got.get(key)!r} (full={got})"
    for key, banned in (spec.get("not_expect") or {}).items():
        assert got.get(key) != banned, f"{label} {key} should not be {banned!r} (full={got})"


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_regex_parse(case: dict) -> None:
    got = parse_sentence_regex(case["text"])
    assert_spec(got, case["regex"], label=f"{case['id']} regex")


@pytest.mark.parametrize("case", CASES, ids=_ids(CASES))
def test_llm_parse(case: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = case["llm"]
    if spec.get("mode") == "short":
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = TestClient(api)
        r = client.post("/v1/parse-sentence", json={"text": case["text"]})
        assert r.status_code == 200
        body = r.json()
        assert body["fields"] == {}
        return

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    raw = json.dumps(spec["raw"])
    with patch("src.parse_sentence._call_openai", return_value=raw):
        got = extract_about_you(case["text"])
    assert_spec(got, spec, label=f"{case['id']} llm")
    assert got == normalize_fields(spec["raw"])


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("GP_LIVE_PARSE"), reason="set GP_LIVE_PARSE=1 to call Claude")
def test_llm_live_all() -> None:
    failures: list[str] = []
    for case in CASES:
        spec = case["llm"]
        if spec.get("mode") == "short":
            continue
        got = extract_about_you(case["text"])
        try:
            assert_spec(got, spec, label=f"{case['id']} llm-live")
        except AssertionError as exc:
            failures.append(str(exc))
    assert not failures, "\n".join(failures)
