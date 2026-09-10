"""Run a few People Like You samples (Claude + workspace .env) and check income bands."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from simulate_people_like_you import load_workspace_env, money, simulate  # noqa: E402
from src.pipeline import people_like_you as plu  # noqa: E402

CASES = [
    {"age": 28, "gender": "Male", "occupation": "CEO", "dependents": 0, "name": "Young"},
    {"age": 55, "gender": "Female", "occupation": "CEO", "dependents": 2, "name": "Older"},
    {"age": 26, "gender": "Female", "occupation": "Nurse", "dependents": 0, "name": "Young"},
    {"age": 52, "gender": "Male", "occupation": "Nurse", "dependents": 1, "name": "Older"},
    {"age": 30, "gender": "Male", "occupation": "musician", "dependents": 0, "name": "Young"},
    {"age": 48, "gender": "Female", "occupation": "musician", "dependents": 1, "name": "Older"},
    {"age": 32, "gender": "Female", "occupation": "financial accountant", "dependents": 0, "name": "Young"},
    {"age": 50, "gender": "Male", "occupation": "financial accountant", "dependents": 2, "name": "Older"},
]


def band_label(occupation: str) -> str:
    load_workspace_env()
    b = plu.get_income_bounds(occupation, "Singapore", "Singapore")
    if not b:
        return "unmatched (near nurse/teacher)"
    return f"{int(b['min']):,}–{int(b['max']):,}"


def in_band(occupation: str, income: float) -> str:
    load_workspace_env()
    b = plu.get_income_bounds(occupation, "Singapore", "Singapore")
    if not b:
        # Unmatched: expect interpolation near nurse/teacher, not CEO.
        if income < 2500 or income > 16000:
            return "CHECK"
        return "ok"
    if b["min"] <= income <= b["max"]:
        return "ok"
    return "OUT"


def main() -> int:
    print(
        f"{'who':<8} {'age':>3} {'sex':<6} {'job':<22} {'income':>10} {'band':<28} {'fit':<5} "
        f"{'out':>10} {'save':>12} {'prop':>10} {'cover':>12}"
    )
    failed = 0
    for case in CASES:
        try:
            result = simulate(
                age=case["age"],
                gender=case["gender"],
                occupation=case["occupation"],
                dependents=case["dependents"],
                name=case["name"],
            )
        except Exception as exc:
            print(f"{case['name']:<8} {case['age']:>3} {case['gender']:<6} {case['occupation']:<22} FAILED {exc}")
            failed += 1
            continue
        inc = float(result["money"]["incomeMonthly"])
        fit = in_band(case["occupation"], inc)
        if fit != "ok":
            failed += 1
        print(
            f"{case['name']:<8} {case['age']:>3} {case['gender']:<6} {case['occupation']:<22} "
            f"{money(inc):>10} {band_label(case['occupation']):<28} {fit:<5} "
            f"{money(result['money']['expenseMonthly']):>10} "
            f"{money(result['money']['savings']):>12} "
            f"{money(result['money']['property']):>10} "
            f"{money(result['life_cover']['chosen'] or 0):>12}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
