"""WP6: the old names are gone from the code.

The plan asks for an ``rg`` check in CI. A test is that check, and it runs everywhere
pytest does rather than only on a runner.

Aliases are deliberate and live in one place each: ``src/needs.py`` and
``frontend/src/lib/needs.ts`` translate what an old session sends. Everything else that
matches is a leftover.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

GP = Path(__file__).resolve().parents[1]

# Old name -> what the Dictionary calls it now.
RENAMED = {
    "CI_COST": "CRI_COST",
    "CI_YEARS": "CRI_YEARS",
    "HOSP_MONTHS": "HOS_MONTHS",
    "EDU_TOTAL_COST": "EDU_COST",
    "LIFE_SUPPORT_MIN_YEARS": "INC_SUPPORT_MIN",
    "LIFE_SUPPORT_MAX_YEARS": "INC_SUPPORT_MAX",
    "LIFE_SUPPORT_PIVOT_AGE": "INC_SUPPORT_PIVOT_AGE",
    "savIncomeMultiple": "SAV_INCOME_MULT",
    "prpIncomeMultiple": "PRP_INCOME_MULT",
    "criMedicalPlaceholder": "CRI_COST",
    "funeralLump": "removed in V0-16",
}

# Where an old name is allowed to appear, and why.
ALLOWED = {
    # The alias tables: one line per old id, which is the point.
    "src/needs.py",
    "frontend/src/lib/needs.ts",
    # These two name them all: one lists the renames, the other proves they translate.
    "tests/test_no_old_names.py",
    "tests/test_need_codes.py",
    # A deliberate shim, removed in WP15 with the twin.
    "src/pipeline/goal_math.py",
    # The workbook and its builder describe the code as published; reissued in WP15.
    "docs/calculations/build_calculations_workbook.py",
    # Generated from the workbook, including its codeSource notes.
    "config/parameters/v24.json",
    "tests/fixtures/model_v0_24/parameters.json",
}

SEARCHED = ("src", "tests", "scripts", "frontend/src")
SKIP_DIRS = {"__pycache__", "node_modules", "dist", ".venv"}


def _files():
    for root in SEARCHED:
        base = GP / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".json"}:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            rel = path.relative_to(GP).as_posix()
            if rel in ALLOWED:
                continue
            yield rel, path


@pytest.mark.parametrize("old", sorted(RENAMED))
def test_the_old_parameter_name_is_gone(old):
    pattern = re.compile(rf"\b{re.escape(old)}\b")
    found = [rel for rel, path in _files() if pattern.search(path.read_text(encoding="utf-8"))]
    assert not found, f"{old} should be {RENAMED[old]}; still in: {', '.join(found)}"


@pytest.mark.parametrize("old", ["N_FAR", "N_HSP", "N_PTD"])
def test_the_old_need_code_is_gone(old):
    """N_HSP survives where HU's engine is addressed: hu_payload renames N_HOS for it."""
    pattern = re.compile(rf"\b{re.escape(old)}\b")
    allowed = {"src/sv_payload.py", "tests/test_payloads.py", "tests/parity/test_happiu_payload.py"} if old == "N_HSP" else set()
    found = [
        rel
        for rel, path in _files()
        if rel not in allowed and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert not found, f"{old} still in: {', '.join(found)}"


def test_the_stress_event_catalog_has_no_bare_ids():
    """'crash', 'ci', 'care' and friends are R_ codes now, outside the alias table.

    Only the ids are checked: 'crash' and 'care' are also icon names, which stay.
    """
    text = (GP / "frontend/src/lib/stressEvents.ts").read_text(encoding="utf-8")
    for code in re.findall(r"\bid: '([^']+)'", text):
        assert code.startswith("R_"), f"{code} left in the catalog"
