"""Shared access to the model V0-24 fixtures.

Parity tests run with ``GP_SVC_FX=snapshot`` so they use the rates the workbook was
built on rather than whatever FM published today.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "model_v0_24"


def cases(prefix: str = "") -> list[str]:
    index = json.loads((FIX / "index.json").read_text(encoding="utf-8"))["cases"]
    return [c["case"] for c in index if c["case"].startswith(prefix)]


def personas() -> list[str]:
    return cases("personas/")


def load(case: str) -> dict:
    return json.loads((FIX / f"{case}.json").read_text(encoding="utf-8"))


def parameters() -> dict:
    return json.loads((FIX / "parameters.json").read_text(encoding="utf-8"))["parameters"]


@pytest.fixture(autouse=True)
def _snapshot_fx(monkeypatch):
    monkeypatch.setenv("GP_SVC_FX", "snapshot")
