"""Build config/parameters/v24.json from the WP0 model export.

The workbook is the source of truth for values (see docs/calculations). This
script copies them into the config store and adds the two things the workbook does
not carry: which level a parameter belongs to, and the bounds a customer edit must
stay inside.

    python scripts/build_parameters.py            # writes config/parameters/v24.json
    python scripts/build_parameters.py --check    # fails if the file has drifted

``--check`` is what the parity test runs, so a hand edit to the JSON that does not
match the workbook is caught rather than silently kept.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "model_v0_24" / "parameters.json"
OUT = REPO / "config" / "parameters" / "v24.json"

# Everything the customer can see or change. The rest is admin-only: costs, steps,
# bands, the HappiU envelope, and the system settings.
#
# The lifestyle multipliers stay admin even though the customer picks a lifestyle:
# the choice is the customer's, the value behind each choice is not.
CUSTOMER: dict[str, tuple[float | None, float | None]] = {
    # Assumption box, as rates per annum.
    "inflationRate": (0.0, 0.15),
    "interestRate": (0.0, 0.15),
    "incomeGrowthRate": (0.0, 0.15),
    "investmentReturn": (0.0, 0.20),
    "assetReturn": (0.0, 0.20),
    "loanRate": (0.0, 0.20),
    # Ages the customer sets on the goal cards.
    "ageOfRetirement": (40, 80),
    "lifeExpectancyDefault": (60, 110),
    "LTC_START_AGE": (60, 100),
    "EDU_TARGET_AGE": (18, 80),
    "SAV_TARGET_AGE": (18, 80),
    "PRP_TARGET_AGE": (18, 80),
}

# Admin bounds worth stating, because a typo here changes every session. Anything
# not listed is unbounded, which is deliberate for codes and years.
ADMIN_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "CASH_SAVINGS_SHARE": (0.0, 1.0),
    "INVESTMENTS_SHARE": (0.0, 1.0),
    "PROPERTY_LTV": (0.0, 1.0),
    "FREE_BUDGET_SHARE": (0.0, 1.0),
    "assetsSaveShare": (0.0, 1.0),
    "liabilityRatio": (0.0, 2.0),
    "spendShareBase": (0.0, 1.0),
    "spendShareCap": (0.0, 1.0),
    "spendSharePerDependant": (0.0, 0.5),
    "lifePremiumRate": (0.0, 0.1),
    "protectionPremiumRate": (0.0, 0.1),
    "gfr": (0.0, 1.0),
    "huNumSims": (1, 100_000),
    "realReturn": (-0.5, 0.5),
}


def build() -> dict[str, Any]:
    export = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for name, row in export["parameters"].items():
        lo, hi = CUSTOMER.get(name, ADMIN_BOUNDS.get(name, (None, None)))
        entry: dict[str, Any] = {
            "value": row["value"],
            "unit": row.get("unit", "") or "",
            "currency": "" if row.get("currency") in (None, "—") else row["currency"],
            "level": "customer" if name in CUSTOMER else "admin",
            "label": row.get("label", "") or name,
            "codeSource": row.get("codeSource", "") or "",
            "changedIn": row.get("changedIn", "") or "",
        }
        if lo is not None:
            entry["min"] = lo
        if hi is not None:
            entry["max"] = hi
        out[name] = entry
    return {
        "version": "v24",
        "model": export["model"],
        "createdAt": "2026-09-25",
        "createdBy": "scripts/build_parameters.py",
        "note": "Generated from the V0-24 workbook export. Do not hand edit.",
        "parameters": out,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="compare instead of writing")
    args = ap.parse_args(argv)

    built = build()
    text = json.dumps(built, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not OUT.exists():
            print(f"missing {OUT}", file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT} differs from the workbook export", file=sys.stderr)
            return 1
        print(f"{OUT.name} matches the workbook ({len(built['parameters'])} parameters)")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} ({len(built['parameters'])} parameters)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
