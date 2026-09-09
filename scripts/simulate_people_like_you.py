"""Call People Like You via Claude (workspace .env) and print Your Money figures.

Loads ``ANTHROPIC_API_KEY`` from the workspace ``.env`` through FM's env
bootstrap and runs FM's predictor in-process.

  python scripts/simulate_people_like_you.py
  python scripts/simulate_people_like_you.py --json
  python scripts/simulate_people_like_you.py --fm https://mgzh11.synology.me:8462
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

GP_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = GP_ROOT.parent
ENV_PATH = WORKSPACE / ".env"
FM_BOOTSTRAP = WORKSPACE / "FM" / "src" / "env_bootstrap.py"
FM_SERVICE = WORKSPACE / "FM" / "src" / "services" / "people_like_you_service.py"

if str(GP_ROOT) not in sys.path:
    sys.path.insert(0, str(GP_ROOT))

from src.cpf import session_employee_cpf, session_take_home  # noqa: E402
from src.predict import _apply_plu, _assumed_life_policy, _round_to_100k, plu_body  # noqa: E402
from src.hu_payload import dob_from_age  # noqa: E402

TIMEOUT = float(os.environ.get("GP_UPSTREAM_TIMEOUT_S", "90"))
LOCAL_FM = "local"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_workspace_env() -> Path:
    """Load FM/.env then workspace .env (workspace wins) via FM bootstrap."""
    boot = _load_module("fm_env_bootstrap", FM_BOOTSTRAP)
    boot.load_env_files()
    if not ENV_PATH.is_file():
        raise FileNotFoundError(f"No .env at {ENV_PATH}")
    return ENV_PATH


def llm_configured() -> bool:
    return bool(
        (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    )


def money(n: float) -> str:
    return f"S${n:,.0f}"


def _fm_plu():
    return _load_module("fm_people_like_you_service", FM_SERVICE)


def fetch_people_like_you_local(body: dict[str, Any]) -> dict[str, Any]:
    load_workspace_env()
    if not llm_configured():
        raise RuntimeError(f"ANTHROPIC_API_KEY is empty in {ENV_PATH}")
    plu = _fm_plu()
    demographics = {
        "dob": body.get("dob") or body.get("dateOfBirth"),
        "dateOfBirth": body.get("dateOfBirth") or body.get("dob"),
        "occupation": body.get("occupation"),
        "country": body.get("country"),
        "city": body.get("city"),
        "dependents": int(body.get("dependents") or 0),
        "maritalStatus": body.get("maritalStatus"),
        "yearsEmployed": body.get("yearsEmployed"),
        "gender": body.get("gender"),
    }
    predictions = plu.predict_people_like_you(
        dob=demographics["dob"],
        occupation=demographics["occupation"],
        country=demographics["country"],
        city=demographics["city"],
        dependents=demographics["dependents"],
        marital_status=demographics.get("maritalStatus"),
        years_employed=demographics.get("yearsEmployed"),
        gender=demographics.get("gender"),
    )
    mapped = plu.map_predictions_to_onboarding(predictions, demographics=demographics)
    return {
        "success": True,
        "result": mapped["result"],
        "onboarding": {
            "data": {"finance": mapped["finance"]},
            "home_currency": mapped.get("home_currency"),
        },
        "timing": mapped.get("timing") or predictions.get("_timing"),
    }


def fetch_people_like_you_remote(fm: str, body: dict[str, Any]) -> dict[str, Any]:
    url = f"{fm.rstrip('/')}/v1/public/people-like-you"
    r = requests.post(url, json=body, timeout=TIMEOUT)
    try:
        data = r.json()
    except ValueError as exc:
        raise RuntimeError(f"{url} returned HTTP {r.status_code}, not JSON: {r.text[:400]}") from exc
    if r.status_code != 200:
        detail = data.get("detail") if isinstance(data, dict) else data
        raise RuntimeError(f"{url} HTTP {r.status_code}: {detail}")
    if isinstance(data, dict) and data.get("success") is False:
        raise RuntimeError(f"{url} success=false: {data}")
    return data


def simulate(
    *,
    fm: str = LOCAL_FM,
    age: int = 42,
    occupation: str = "CEO",
    gender: str = "Male",
    dependents: int = 2,
    residency: str = "Singapore Citizen",
    name: str = "Michael",
) -> dict[str, Any]:
    session = {
        "name": name,
        "age": age,
        "gender": gender,
        "residency": residency,
        "occupation": occupation,
        "dependents": dependents,
        "dateOfBirth": dob_from_age(age),
        "incomeMonthly": 0,
        "expenseMonthly": 0,
        "cash": 0,
        "investments": 0,
        "property": 0,
        "mortgage": 0,
        "policies": [],
    }
    body = plu_body(session, persist=False)
    if not fm or fm == LOCAL_FM:
        plu = fetch_people_like_you_local(body)
        fm_label = f"in-process FM ({ENV_PATH})"
    else:
        plu = fetch_people_like_you_remote(fm, body)
        fm_label = fm.rstrip("/")
    session = _apply_plu(session, plu)
    mapped = plu.get("result") or {}
    income = float(session["incomeMonthly"] or 0)
    mortgage_cover = (
        _round_to_100k(float(session.get("mortgage") or 0)) if float(session.get("property") or 0) > 0 else 0
    )
    dependents_cover = int(round(income * 12 * 5)) if dependents > 0 else 0
    life = _assumed_life_policy(session)
    own = bool((mapped.get("ownershipInformation") or {}).get("property"))
    return {
        "fm": fm_label,
        "input": {
            "name": name,
            "age": age,
            "dob": session["dateOfBirth"],
            "gender": gender,
            "dependents": dependents,
            "residency": residency,
            "occupation": occupation,
            "request": body,
        },
        "llm": {
            "income": mapped.get("income"),
            "currency": mapped.get("currency"),
            "property": own,
            "car": (mapped.get("ownershipInformation") or {}).get("car"),
            "riskAbility": mapped.get("riskAbility"),
            "priceSensitivity": mapped.get("priceSensitivity"),
            "lifeExpectancy": mapped.get("lifeExpectancy"),
            "clientPreferences": mapped.get("clientPreferences"),
        },
        "fm_formulas": {
            "expenses": mapped.get("expenses"),
            "assets": mapped.get("assets"),
            "liabilities": mapped.get("liabilities"),
        },
        "money": {
            "source": session.get("source"),
            "incomeMonthly": session["incomeMonthly"],
            "cpfMonthly": session_employee_cpf(session),
            "expenseMonthly": session["expenseMonthly"],
            "availableBudget": session_take_home(session) - float(session["expenseMonthly"] or 0),
            "cash": session.get("cash") or 0,
            "investments": session.get("investments") or 0,
            "savings": (session.get("cash") or 0) + (session.get("investments") or 0),
            "property": session.get("property") or 0,
            "mortgage": session.get("mortgage") or 0,
            "netWealth": (session.get("cash") or 0)
            + (session.get("investments") or 0)
            + (session.get("property") or 0)
            - (session.get("mortgage") or 0),
            "policies": session.get("policies") or [],
        },
        "life_cover": {
            "mortgageRounded": mortgage_cover,
            "fiveTimesAnnual": dependents_cover,
            "chosen": (life or {}).get("sum"),
            "premium": (life or {}).get("premium"),
            "winner": "dependants"
            if life and dependents_cover >= mortgage_cover
            else ("mortgage" if life else None),
        },
        "timing": plu.get("timing"),
        "raw": plu,
    }


def render(result: dict[str, Any]) -> str:
    inp = result["input"]
    llm = result["llm"]
    fm = result["fm_formulas"]
    m = result["money"]
    life = result["life_cover"]
    lines = [
        f"FM {result['fm']}",
        f"Profile  {inp['name']} · {inp['age']} · {inp['gender']} · {inp['dependents']} dependants · {inp['residency']} · {inp['occupation']}",
        f"DOB sent {inp['dob']}",
        "",
        "LLM (Claude via FM)",
        f"  Monthly income     {money(float(llm['income'] or 0))}  ({llm.get('currency') or '?'})",
        f"  Owns property      {llm['property']}",
        f"  Owns car           {llm.get('car')}",
        f"  Risk ability       {llm.get('riskAbility')}",
        f"  Life expectancy    {llm.get('lifeExpectancy')}",
        "",
        "FM formulas (not the model)",
        f"  Expenses           {money(float(fm['expenses'] or 0))}  (share of take-home)",
        f"  Liquid assets      {money(float(fm['assets'] or 0))}  (surplus × 12 × 0.5 × years since 21)",
        f"  Liabilities        {money(float(fm['liabilities'] or 0))}  (assets × 0.7)",
        "",
        "Your Money (after GP mapping)",
        f"  Money coming in        {money(m['incomeMonthly'])}",
        f"  Your CPF               {money(m['cpfMonthly'])}",
        f"  Money going out        {money(m['expenseMonthly'])}",
        f"  Available budget       {money(m['availableBudget'])}",
        f"  Savings & investments  {money(m['savings'])}  (cash {money(m['cash'])} / investments {money(m['investments'])})",
        f"  Property               {money(m['property'])}"
        + ("  (from income band if LLM says own)" if llm["property"] else "  (no property)"),
        f"  Loans outstanding      {money(m['mortgage'])}",
        f"  Net wealth             {money(m['netWealth'])}",
        f"  Life cover             {money(life['chosen'] or 0)}  "
        f"(mortgage {money(life['mortgageRounded'])} vs 5× income {money(life['fiveTimesAnnual'])}; "
        f"{life['winner'] or 'none'} wins)",
        f"  Annual premium         {money(life['premium'] or 0)}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Simulate Your Money numbers from People Like You (LLM)")
    p.add_argument(
        "--fm",
        default=LOCAL_FM,
        help="local (default: workspace .env + in-process FM) or an FM origin URL",
    )
    p.add_argument("--age", type=int, default=42)
    p.add_argument("--occupation", default="CEO")
    p.add_argument("--gender", default="Male")
    p.add_argument("--dependents", type=int, default=2)
    p.add_argument("--residency", default="Singapore Citizen")
    p.add_argument("--name", default="Michael")
    p.add_argument("--json", action="store_true", help="Print result JSON instead of the table")
    args = p.parse_args(argv)

    try:
        result = simulate(
            fm=args.fm,
            age=args.age,
            occupation=args.occupation,
            gender=args.gender,
            dependents=args.dependents,
            residency=args.residency,
            name=args.name,
        )
    except Exception as exc:
        print(f"People Like You failed: {exc}", file=sys.stderr)
        return 1
    if args.json:
        out = dict(result)
        out.pop("raw", None)
        print(json.dumps(out, indent=2, default=str))
    else:
        print(render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
