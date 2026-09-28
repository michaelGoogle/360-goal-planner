"""Build Calculations.xlsx from the live GP formulas (not the docs).

Run from anywhere:
    python GP/docs/calculations/build_calculations_workbook.py

The workbook formulas are a transcription of:
    src/cpf.py
    src/predict.py (_apply_plu, seed_property_value, _assumed_life_policy)
    src/services/need_profiler/service.py (live profiler; leftover pipeline select_unified_top)
    src/pipeline/need_calculator.py / goal_math.py
    frontend/src/lib/planProducts.ts / local.ts seedProducts
    frontend/src/lib/types.ts availableBudget
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

GP_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(GP_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import os

os.environ.setdefault("GP_SVC_FX", "snapshot")
os.environ.setdefault("GP_SVC_PREMIUM", "mock")

from deterministic_engines import (  # noqa: E402
    BRS,
    CPF_EMP,
    CPF_LIFE_PAY,
    CPF_MA,
    CPF_OA,
    CPF_SA,
    CPF_TOTAL,
    HU_RATES,
    _band,
    load_hu_tables,
    session_for,
    twin_hu,
    twin_sv,
)

from src.cpf import (  # noqa: E402
    OW_CEILING,
    employee_cpf_monthly,
    employee_cpf_rate,
    expenses_from_gross,
    spend_share,
    take_home_income,
)
from src.pipeline.goal_math import (  # noqa: E402
    CRI_COST,
    CRI_YEARS,
    EDU_COST,
    HOS_MONTHS,
    LIFE_EXPECTANCY,
    LIFE_EXPECTANCY_MAX,
    INC_SUPPORT_MAX,
    INC_SUPPORT_MIN,
    INC_SUPPORT_PIVOT_AGE,
    LIFESTYLE_RATES,
    RETIREMENT_AGE,
    TPD_COST,
    TPD_YEARS,
    fv,
    fv_annuity,
    income_support_years,
    lifestyle_rate,
    pv_annuity,
    pv_annuity_due,
    real_return,
    remaining_gap,
    round_money,
    years_in_retirement,
    years_to_retirement,
)
from src.money import to_usd  # noqa: E402
from src.pipeline.need_calculator import evaluate_session  # noqa: E402
from src.pipeline.need_profiler import (  # noqa: E402
    AI_NEED_LABELS,
)
from src.services.fx.client import SnapshotFxClient  # noqa: E402
from src.services.need_profiler import service as profiler_service  # noqa: E402
from src.services.need_profiler.models import NeedProfilerRequest  # noqa: E402
from src.services.plan import service as plan_service  # noqa: E402
from src.services.plan.models import PlanNeedInput, PlanRequest  # noqa: E402
from src.predict import (  # noqa: E402
    CASH_SAVINGS_SHARE,
    INVESTMENTS_SHARE,
    PROPERTY_LTV,
    _assumed_life_policy,
    seed_property_value,
)
from src.session_rates import DEFAULTS  # noqa: E402

# Bump the version in this filename for every workbook change. Do not overwrite
# a version the user already has open (V0-01, V0-02, … stay as snapshots).
OUT = Path(__file__).resolve().parent / "Calculations V0-25.xlsx"
import csv as _csv
FX_DIR = Path(__file__).resolve().parent / "fx_ppp"
FX_CCY = list(_csv.DictReader(open(FX_DIR / "currencies_fx.csv", encoding="utf-8")))
FX_CTRY = list(_csv.DictReader(open(FX_DIR / "countries_ppp.csv", encoding="utf-8")))
SGD_CAL = next(float(r["usd_per_1"]) for r in FX_CCY if r["currency"] == "SGD")  # V0-24: USD per SGD used to calibrate fixed amounts
ANCHORS = json.loads(
    (GP_ROOT / "src" / "pipeline" / "prompts" / "income_anchors.json").read_text(encoding="utf-8")
)
PROFILER_CFG = json.loads(
    (GP_ROOT / "src" / "pipeline" / "prompts" / "Need_profiler.json").read_text(encoding="utf-8")
)

CURRENT_YEAR = 2026
# Ten calculator needs (V0-16 added N_PAC / N_LTC). UNIFIED is the eight-type
# column set some older sheets still print.
UNIFIED = ("N_INC", "N_CRI", "N_TPD", "N_HOS", "N_RET", "N_EDU", "N_SAV", "N_PRP")
PROT = ("N_INC", "N_CRI", "N_TPD", "N_HOS")
WEALTH = ("N_RET", "N_EDU", "N_SAV", "N_PRP")
PROT_X = PROT + ("N_PAC", "N_LTC")
UNIFIED_X = PROT_X + WEALTH
PARKED = {"N_HOM": "Home Protection", "N_CAR": "Car Protection", "N_TRV": "Travel Protection"}
DROPPED_LABELS = ("Farewell",)
AI_LABELS = list(AI_NEED_LABELS.values())  # insertion order
AI_KEYS = list(AI_NEED_LABELS.keys())
WB_LABELS = [lab for lab in AI_LABELS if lab not in ("Farewell",)]  # V0-16: Farewell dropped
SHOW = {"Disability": "TPD"}  # V0-18: one name for total & permanent disability

NAVY = "1B3A4B"
TEAL = "1F6F6A"
GOLD = "C4A35A"
INK = "1A1A1A"
MUTED = "5C6B73"
PAPER = "F7F4EE"
YELLOW = "FFF3BF"
ORANGE = "FFE0C2"
GREEN = "D3F0E2"
RED = "F8D0D0"
BLUE = "D7E6F5"
WHITE = "FFFFFF"
LINE = "D4CBB8"

thin = Border(
    left=Side(style="thin", color=LINE),
    right=Side(style="thin", color=LINE),
    top=Side(style="thin", color=LINE),
    bottom=Side(style="thin", color=LINE),
)
title_font = Font(name="Calibri", size=16, bold=True, color=NAVY)
h_font = Font(name="Calibri", size=10, bold=True, color=WHITE)
sec_font = Font(name="Calibri", size=11, bold=True, color=NAVY)
body_font = Font(name="Calibri", size=10, color=INK)
note_font = Font(name="Calibri", size=9, italic=True, color=MUTED)
input_fill = PatternFill("solid", fgColor=YELLOW)
override_fill = PatternFill("solid", fgColor=ORANGE)
header_fill = PatternFill("solid", fgColor=NAVY)
sec_fill = PatternFill("solid", fgColor="E6E0D4")
paper_fill = PatternFill("solid", fgColor=PAPER)
green_fill = PatternFill("solid", fgColor=GREEN)
red_fill = PatternFill("solid", fgColor=RED)
blue_fill = PatternFill("solid", fgColor=BLUE)
input_hdr = PatternFill("solid", fgColor="B8860B")
llm_hdr = PatternFill("solid", fgColor="1D4E89")
calc_hdr = PatternFill("solid", fgColor="1F6F6A")
llm_fill = PatternFill("solid", fgColor=BLUE)
calc_fill = PatternFill("solid", fgColor=GREEN)
assume_hdr = PatternFill("solid", fgColor="6B3FA0")
assume_fill = PatternFill("solid", fgColor="EDE4F5")
override_hdr = PatternFill("solid", fgColor="C45C26")
wrap = Alignment(wrap_text=True, vertical="center")
left = Alignment(vertical="center", wrap_text=True)
center = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _fill(ws, cell, value, font=body_font, fill=None, align=left, num=None, border=True):
    c = ws[cell]
    c.value = value
    c.font = font
    c.alignment = align
    if fill:
        c.fill = fill
    if num:
        c.number_format = num
    if border:
        c.border = thin
    return c


def _headers(ws, row, headers, fill=header_fill):
    for i, h in enumerate(headers, 1):
        _fill(ws, f"{get_column_letter(i)}{row}", h, font=h_font, fill=fill, align=center)


def _group_band(ws, c1: int, c2: int, row: int, label: str, fill) -> None:
    a = f"{get_column_letter(c1)}{row}"
    b = f"{get_column_letter(c2)}{row}"
    if c2 > c1:
        ws.merge_cells(f"{a}:{b}")
    _fill(ws, a, label, font=h_font, fill=fill, align=center)
    for c in range(c1, c2 + 1):
        cell = ws[f"{get_column_letter(c)}{row}"]
        cell.fill = fill
        cell.font = h_font
        cell.alignment = center
        cell.border = thin


def _legend(ws, col: str, row: int = 1) -> None:
    """Colour key to the right of the used columns."""
    items = (
        ("A · INPUT DATA", input_hdr),
        ("B · LLM PREDICTED DATA", llm_hdr),
        ("C · DETERMINISTICALLY CALCULATED", calc_hdr),
        ("D · ASSUMPTIONS / SHARED DATA", assume_hdr),
        ("E · USER / FRONTEND OVERRIDE", override_hdr),
    )
    for i, (label, fill) in enumerate(items):
        _fill(ws, f"{col}{row + i}", label, font=h_font, fill=fill, align=center)
    ws.column_dimensions[col].width = 42


def _widths(ws, widths):
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def _name(wb, name, ref):
    # defined name scoped to workbook
    existing = [n for n in wb.defined_names.values() if n.name == name]
    for n in existing:
        del wb.defined_names[n.name]
    wb.defined_names.add(DefinedName(name, attr_text=ref))


# ---------------------------------------------------------------------------
# 50 personas — About-you attributes + placeholder LLM fields
# ---------------------------------------------------------------------------

OCC_ROWS = [
    ("Nurse", "nurse", "Aisha"),
    ("Teacher", "teacher", "Wei Ling"),
    ("Accountant", "accountant", "Daniel"),
    ("Marketing Manager", "marketing manager", "Priya"),
    ("Software Engineer", "software engineer", "Marcus"),
    ("Doctor", "doctor", "Hannah"),
    ("Investment Banker", "investment banker", "Julian"),
    ("CEO", "chief executive", "Mei Fen"),
    ("Baker", None, "Hafiz"),
    ("Driver", None, "Siti"),
]

# Five life-stage variants. Together with 10 occupations → 50 people.
# Columns: age, gender, residency, deps, property, car, smoker, hospital,
# ward, travel, sports, retirement_lifestyle, life_expectancy, risk_ability
VARIANTS = [
    (23, "Female", "Citizen", 0, False, False, False, "Public", "Ward", False, "Yoga", "Basic", 86, "conservative"),
    (28, "Male", "PR", 0, False, True, False, "Private", "Double", True, "Running", "Comfortable", 81, "moderate"),
    (35, "Female", "Citizen", 1, True, True, False, "Private", "Single", True, "Swimming", "Comfortable", 88, "moderate"),
    (42, "Male", "Citizen", 2, True, True, True, "Public", "Ward", False, "I dont do sports", "frugal", 78, "conservative"),
    (48, "Female", "Foreigner", 2, True, False, False, "Private", "A", True, "Adventurous Sports", "only the best", 90, "aggressive"),
    (33, "Male", "Citizen", 1, True, True, False, "Public", "B", True, "Life style activities", "stress-free", 83, "moderate"),
    (55, "Female", "PR", 0, True, True, False, "Private", "Single", False, "Walking", "Basic", 89, "conservative"),
    (61, "Male", "Citizen", 3, True, True, True, "Public", "Ward", False, "I dont do sports", "frugal", 76, "conservative"),
    (26, "Female", "Citizen", 0, False, False, False, "Public", "Ward", True, "HIIT", "Comfortable", 87, "moderate"),
    (38, "Male", "Foreigner", 2, False, True, False, "Private", "Double", True, "Football", "Luxurious", 80, "aggressive"),
    (52, "Female", "Citizen", 1, True, True, False, "Private", "A", True, "Pilates", "only the best", 91, "moderate"),
    (67, "Male", "Citizen", 0, True, False, False, "Public", "Ward", False, "I dont do sports", "Basic", 85, "conservative"),
    (31, "Female", "PR", 1, False, True, True, "Public", "Double", False, "Running", "Comfortable", 79, "moderate"),
    (45, "Male", "Citizen", 4, True, True, False, "Private", "Single", True, "Golf", "Luxurious", 84, "aggressive"),
    (58, "Female", "Citizen", 2, True, True, False, "Private", "B", False, "Life style activities", "stress-free", 92, "conservative"),
]


def _sg_bounds(occ_id: str | None) -> tuple[float | None, float | None]:
    if not occ_id:
        return None, None
    for occ in ANCHORS["occupations"]:
        if occ["id"] == occ_id:
            b = (occ.get("bounds") or {}).get("singapore") or {}
            return float(b["min"]), float(b["max"])
    return None, None


def _placeholder_income(occ_id: str | None, age: int) -> int:
    lo, hi = _sg_bounds(occ_id)
    if lo is None:
        # Unmatched (baker / driver): sit near the nurse band, age-tilted.
        lo, hi = 3200.0, 6200.0
    t = min(1.0, max(0.0, (age - 23) / 40.0))
    return int(round(lo + t * (hi - lo)))


def build_personas() -> list[dict]:
    people: list[dict] = []
    n = 0
    surnames = [
        "Rahman", "Tan", "Koh", "Nair", "Lim", "Wong", "Chee", "Ong",
        "Abdullah", "Hassan", "Ng", "Chua", "Lee", "Goh", "Teo",
    ]
    # 10 occupations × first 5 variants = 50, but we want more age/attribute
    # spread: walk occupations in a cycle across all 15 variants, stop at 50.
    while len(people) < 50:
        occ_label, occ_id, first = OCC_ROWS[n % len(OCC_ROWS)]
        age, gender, residency, deps, prop, car, smoker, hosp, ward, travel, sports, life, le, risk = VARIANTS[
            n % len(VARIANTS)
        ]
        # Nudge age so two people with the same occupation are not twins.
        age = min(68, max(22, age + ((n // len(VARIANTS)) % 3) - 1))
        income = _placeholder_income(occ_id, age)
        lo, hi = _sg_bounds(occ_id)
        people.append(
            {
                "id": f"P{len(people) + 1:02d}",
                "name": f"{first} {surnames[n % len(surnames)]}",
                "age": age,
                "gender": gender,
                "residency": residency,
                "occupation": occ_label,
                "dependents": deps,
                "marital_status": "",
                "llm_income": income,
                "llm_currency": "SGD",
                "llm_property": prop,
                "llm_car": car,
                "llm_smoker": smoker,
                "llm_risk_ability": risk,
                "llm_price_sensitivity": "high" if income < 6000 else ("low" if income > 15000 else "medium"),
                "llm_ward_type": ward,
                "llm_hospital_type": hosp,
                "llm_travelling": travel,
                "llm_sports": sports,
                "llm_retirement_lifestyle": life,
                "llm_life_expectancy": le,
                "country": "Singapore",
                "band_min": lo,
                "band_max": hi,
                "varies": (
                    f"{occ_label}; age {age}; {residency}; {deps} dep; "
                    f"{'home' if prop else 'rent'}; {'smoker' if smoker else 'non-smoker'}"
                ),
            }
        )
        n += 1
    return people


PERSONAS = build_personas()
N = len(PERSONAS)
assert N == 50
P_FIRST, P_LAST = 3, 2 + N  # Personas data rows
# Other sheets use the same row numbers for persona data (header on row 2).
R0, R1 = 3, 2 + N


# ---------------------------------------------------------------------------
# Twin of the live code — used to verify the Excel transcription
# ---------------------------------------------------------------------------

def twin_plu(p: dict) -> dict:
    income = float(p["llm_income"] or 0)
    lo, hi = p["band_min"], p["band_max"]
    if lo is not None and income:
        income = min(max(income, lo), hi)
    age = int(p["age"])
    res = p["residency"]
    deps = int(p["dependents"])
    cpf = employee_cpf_monthly(income, age, res)
    take = take_home_income(income, age, res)
    exp = expenses_from_gross(income, deps, age, res)
    if income and exp and age > 21:
        assets = max(0.0, (take - exp) * 12 * 0.5 * (age - 21))
    else:
        assets = 0.0
    cash = round(assets * CASH_SAVINGS_SHARE)
    inv = round(assets * INVESTMENTS_SHARE)
    if p["llm_property"]:
        prop = seed_property_value(income)
        mort = round(prop * PROPERTY_LTV)
    else:
        prop = 0
        mort = 0
    sess = {
        "incomeMonthly": income,
        "property": prop,
        "mortgage": mort,
        "dependents": deps,
    }
    life = _assumed_life_policy(sess)
    le = int(p["llm_life_expectancy"] or 0)
    le_sess = min(le, LIFE_EXPECTANCY_MAX) if le > 0 else LIFE_EXPECTANCY
    marital = p["marital_status"] or ("single" if age < 30 else "married")
    return {
        "income": income,
        "cpf_rate": employee_cpf_rate(age, res),
        "cpf": cpf,
        "take_home": take,
        "spend_share": spend_share(deps),
        "expense": exp,
        "assets": assets,
        "liabilities": assets * 0.7,
        "cash": cash,
        "investments": inv,
        "property": prop,
        "mortgage": mort,
        "life_sum": (life or {}).get("sum") or 0,
        "life_prem": (life or {}).get("premium") or 0,
        "life_expectancy": le_sess,
        "marital": marital,
    }


def twin_profiler(p: dict, plu: dict) -> dict:
    """Live Need Profiler, with the same SnapshotFx lock predict uses."""
    country = p.get("country") or "Singapore"
    currency = p.get("llm_currency") or "SGD"
    fx = SnapshotFxClient().lock(currency, country)
    req = NeedProfilerRequest(
        age=int(p["age"]),
        dependents=int(p["dependents"]),
        gender=p["gender"],
        ownsProperty=bool(p["llm_property"]),
        incomeMonthlyUsd=to_usd(float(plu["income"]), fx),
        expenseMonthlyUsd=to_usd(float(plu["expense"]), fx),
        liquidAssetsUsd=to_usd(float(plu["cash"] + plu["investments"]), fx),
        liabilitiesUsd=to_usd(float(plu["liabilities"]), fx),
        priceLevel=fx.priceLevel,
        flags={
            "occupation": p["occupation"],
            "isSmoker": bool(p["llm_smoker"]),
            "hospitalType": p["llm_hospital_type"],
            "wardType": p["llm_ward_type"],
            "retirementLifestyle": p["llm_retirement_lifestyle"],
            "sports": p["llm_sports"],
        },
    )
    resp = profiler_service.profile(req)
    enabled = {n.type for n in resp.needs if n.enabled}
    priority = {n.type: n.priority for n in resp.needs if not n.parked}
    for t in UNIFIED_X:
        priority.setdefault(t, 3)
    return {
        "raw": dict(resp.raw),
        "scaled": dict(resp.scaled),
        "enabled": enabled,
        "priority": priority,
        "picks": dict(resp.picks),
        "ranked": [],
        "fx": fx,
    }


def twin_needs(p: dict, plu: dict, enabled: set[str]) -> dict:
    country = p.get("country") or "Singapore"
    currency = p.get("llm_currency") or "SGD"
    fx = SnapshotFxClient().lock(currency, country)
    session = {
        "age": int(p["age"]),
        "country": country,
        "currency": currency,
        "fx": fx.model_dump(),
        "incomeMonthly": plu["income"],
        "expenseMonthly": plu["expense"],
        "cash": plu["cash"],
        "investments": plu["investments"],
        "mortgage": plu["mortgage"],
        "dependents": int(p["dependents"]),
        "lifeExpectancy": plu["life_expectancy"],
        "ageOfRetirement": RETIREMENT_AGE,
        "inflationRate": DEFAULTS["inflationRate"],
        "investmentReturn": DEFAULTS["investmentReturn"],
        "policies": (
            [{"type": "Life Protection", "sum": plu["life_sum"], "premium": plu["life_prem"]}]
            if plu["life_sum"]
            else []
        ),
        "needs": [
            {"type": t, "enabled": t in enabled, "needAmount": 0}
            for t in UNIFIED_X
        ],
    }
    out = evaluate_session(session)
    by = {n["type"]: n for n in out["needs"]}
    return by


def _js_round(n: float) -> int:
    return int(math.floor(n + 0.5)) if n >= 0 else int(math.ceil(n - 0.5))


def _cover_premium(sum_assured: float) -> int:
    return max(0, _js_round((sum_assured * 0.00078) / 10) * 10)


def _round_up(n: float, step: float) -> float:
    if n <= 0:
        return 0
    return math.ceil(n / step) * step


def twin_plan(p: dict, plu: dict, needs: dict, enabled: set[str]) -> dict:
    """Live Plan Calculator, same share and per-goal horizons as /v1/plan."""
    rows = []
    age = int(p["age"])
    for t in UNIFIED_X:
        row = needs[t]
        yrs = None
        if t == "N_RET":
            yrs = max(0, RETIREMENT_AGE - age)
        elif t in WEALTH:
            tgt = row.get("targetYear") or row.get("fundsNeededYear")
            yrs = max(0, int(tgt) - CURRENT_YEAR) if tgt else 0
        rows.append(
            PlanNeedInput(
                type=t,
                enabled=t in enabled,
                needAmount=float(row["needAmount"] or 0),
                have=float(row["have"] or 0),
                gap=float(row["gap"] or 0),
                horizonYears=yrs,
            )
        )
    resp = plan_service.build_plan(
        PlanRequest(
            age=age,
            gender=p["gender"],
            smoker=bool(p["llm_smoker"]),
            country=p.get("country") or "Singapore",
            currency=p.get("llm_currency") or "SGD",
            takeHomeMonthly=float(plu["take_home"]),
            expenseMonthly=float(plu["expense"]),
            ageOfRetirement=RETIREMENT_AGE,
            inflationRate=DEFAULTS["inflationRate"],
            investmentReturn=DEFAULTS["investmentReturn"],
            needs=rows,
        )
    )
    by = {n.type: n for n in resp.needs}
    return {
        "suggested": [n.type for n in resp.needs if n.suggested],
        "plan_sum": {t: n.planSum for t, n in by.items()},
        "plan_prem": {t: n.planPrem for t, n in by.items()},
        "plan_mth": {t: n.planMth for t, n in by.items()},
        "plan_lump": {t: n.planLump for t, n in by.items()},
        "share": 0,
        "invest_mth": resp.investMth,
        "invest_lump": resp.investLump,
    }


def twin_budget(plu: dict, plan: dict) -> dict:
    available = max(0.0, plu["take_home"] - plu["expense"])
    free = _js_round(available * 0.5)
    prem_mth = sum(plan["plan_prem"].values()) / 12
    contrib = plan["invest_mth"]
    monthly = _js_round(contrib + prem_mth)
    return {
        "available": available,
        "free": free,
        "prem_mth": _js_round(prem_mth),
        "contrib_mth": contrib,
        "monthly": monthly,
        "monthly_over": monthly - free,
        "lumps": plan["invest_lump"],
        "lump_over": plan["invest_lump"] - plu["investments"],
    }


def verify_twins() -> list[str]:
    """Compare twins to live GP modules. Return error strings (empty = ok)."""
    errors: list[str] = []
    for p in PERSONAS:
        plu = twin_plu(p)
        # CPF / spend must match src.cpf exactly (twin calls those functions).
        prof = twin_profiler(p, plu)
        needs = twin_needs(p, plu, prof["enabled"])
        for t in UNIFIED_X:
            row = needs[t]
            if row["enabled"] != (t in prof["enabled"]):
                errors.append(f"{p['id']} {t} enabled mismatch")
            if row["needAmount"] < 0 or row["have"] < 0:
                errors.append(f"{p['id']} {t} negative amount")
        plan = twin_plan(p, plu, needs, prof["enabled"])
        bud = twin_budget(plu, plan)
        if bud["free"] < 0:
            errors.append(f"{p['id']} negative free budget")
    # Spot-check docs sample (Need-calculator.md) against evaluate_session.
    sample_fx = SnapshotFxClient().lock("SGD", "Singapore")
    sample = {
        "age": 42,
        "country": "Singapore",
        "currency": "SGD",
        "fx": sample_fx.model_dump(),
        "incomeMonthly": 6800,
        "expenseMonthly": 4000,
        "cash": 0,
        "investments": 0,
        "mortgage": 200000,
        "dependents": 0,
        "lifeExpectancy": 85,
        "ageOfRetirement": 65,
        "inflationRate": 0.023,
        "investmentReturn": 0.042,
        "policies": [],
        "needs": [{"type": t, "enabled": True, "needAmount": 0} for t in UNIFIED],
    }
    ev = {n["type"]: n for n in evaluate_session(sample)["needs"]}
    # Code (not the doc line) is the source of truth.
    r = real_return(0.042, 0.023)
    expect_inc = round_money(0 + 200000 + pv_annuity(4000 * 12, r, income_support_years(42)))
    expect_cri = round_money(pv_annuity_due(6800 * 12, r, CRI_YEARS) + CRI_COST)
    expect_tpd = round_money(pv_annuity_due(6800 * 12, r, TPD_YEARS) + TPD_COST)
    expect_hos = round_money(6800 * HOS_MONTHS)
    expect_edu = round_money(EDU_COST * ((1 + 0.023) ** 8))
    annual = 4000 * 12 * lifestyle_rate(2)
    expect_ret = round_money(pv_annuity(fv(annual, r, 23), r, 20))
    checks = {
        "N_INC": expect_inc,
        "N_CRI": expect_cri,
        "N_TPD": expect_tpd,
        "N_HOS": expect_hos,
        "N_EDU": expect_edu,
        "N_RET": expect_ret,
    }
    for t, exp in checks.items():
        got = ev[t]["needAmount"]
        if got != exp:
            errors.append(f"sample {t}: code {got} twin {exp}")
    # Docs quote N_INC 634,401 — record the live number for the discrepancies tab.
    return errors


# ---------------------------------------------------------------------------
# Workbook
# ---------------------------------------------------------------------------

FACTOR_ROWS = [
    "Date of Birth",
    "Gender",
    "Dependants",
    "Occupation",
    "Smoking",
    "Income",
    "Expense",
    "Assets",
    "Liabilities",
    "Hospitalization",
    "Disability",
    "Hospital Type",
    "Ward Type",
    "Lifestyle",
    "Sports",
]


def _factor_weight(factor: str, need: str) -> float:
    return float((PROFILER_CFG.get("needs_factor_weights") or {}).get(factor, {}).get(need, 0) or 0)


# V0-21: Assumptions is the one parameter list. Per row: unit, currency, status, code source, changed in, open proposal.
_ST_USD, _ST_NC, _ST_SYS = "USD", "No currency", "System"
ASSUME_META = {
    "inflationRate": ("% p.a.", "—", _ST_NC, "session_rates.py", "", ""),
    "interestRate": ("% p.a.", "—", _ST_NC, "session_rates.py", "", ""),
    "loanRate": ("% p.a.", "—", _ST_NC, "session_rates.py", "", ""),
    "incomeGrowthRate": ("% p.a.", "—", _ST_NC, "session_rates.py", "", ""),
    "investmentReturn": ("% p.a.", "—", _ST_NC, "session_rates.py / riskCapacity.ts", "", ""),
    "assetReturn": ("% p.a.", "—", _ST_NC, "session_rates.py", "", ""),
    "realReturn": ("% p.a.", "—", "Derived", "goal_math.real_return", "", ""),
    "ageOfRetirement": ("age", "—", _ST_NC, "goal_math.py RETIREMENT_AGE", "", ""),
    "lifeExpectancyDefault": ("age", "—", _ST_NC, "goal_math.py LIFE_EXPECTANCY", "V0-21: the one default; GP sends it to HappiU and SV", ""),
    "currentYear": ("year", "—", _ST_NC, "", "", ""),
    "endAge": ("age", "—", "Derived", "sv_payload.py endAge", "V0-21: = default; chart uses the session LE", ""),
    "systemCurrency": ("code", "—", _ST_SYS, "", "V0-15", ""),
    "fxMode": ("A / B", "—", _ST_SYS, "", "V0-15; V0-22 B", ""),
    "PPP_BASE_COUNTRY": ("country", "—", _ST_SYS, "— (new)", "V0-22", "USD fixed amounts were calibrated in Singapore, so Singapore = 1"),
    "priceLevelOn": ("TRUE / FALSE", "—", _ST_SYS, "", "V0-15; V0-22 switched on", ""),
    "LTC_COST": ("per year", "USD", _ST_USD, "— (new)", "V0-19", ""),
    "LTC_START_AGE": ("age", "—", _ST_NC, "— (new, front-end input)", "V0-19", ""),
    "RET_LIFESTYLE_FRUGAL": ("× today's spend", "—", _ST_NC, "goal_math.py LIFESTYLE_RATES", "V0-16 renamed", ""),
    "RET_LIFESTYLE_STRESSFREE": ("× today's spend", "—", _ST_NC, "goal_math.py LIFESTYLE_RATES", "V0-16 renamed", ""),
    "RET_LIFESTYLE_ONLYTHEBEST": ("× today's spend", "—", _ST_NC, "goal_math.py LIFESTYLE_RATES", "V0-16 renamed", ""),
    "INC_SUPPORT_MIN": ("years", "—", _ST_NC, "goal_math.py LIFE_SUPPORT_MIN_YEARS", "V0-16 renamed", ""),
    "INC_SUPPORT_MAX": ("years", "—", _ST_NC, "goal_math.py LIFE_SUPPORT_MAX_YEARS", "V0-16 renamed", ""),
    "INC_SUPPORT_PIVOT_AGE": ("age", "—", _ST_NC, "goal_math.py LIFE_SUPPORT_PIVOT_AGE", "V0-16 renamed", ""),
    "CRI_YEARS": ("years", "—", _ST_NC, "goal_math.py CI_YEARS", "V0-16 renamed", ""),
    "CRI_COST": ("one-off", "USD", _ST_USD, "goal_math.py CI_COST (SGD)", "V0-15 USD; V0-21 also sent to HappiU", ""),
    "TPD_YEARS": ("years", "—", _ST_NC, "goal_math.py TPD_YEARS", "", ""),
    "TPD_COST": ("one-off", "USD", _ST_USD, "goal_math.py TPD_COST (SGD)", "V0-15 USD; V0-21 also sent to HappiU", ""),
    "HOS_MONTHS": ("months of income", "—", _ST_NC, "goal_math.py HOSP_MONTHS", "V0-16 renamed", ""),
    "EDU_COST": ("one-off", "USD", _ST_USD, "goal_math.py EDU_TOTAL_COST (SGD)", "V0-15 USD; V0-16 renamed", ""),
    "EDU_TARGET_AGE": ("age", "—", _ST_NC, "needEdit.ts (was +10 years)", "V0-24", ""),
    "SAV_TARGET_AGE": ("age", "—", _ST_NC, "needEdit.ts (was +10 years)", "V0-24", ""),
    "PRP_TARGET_AGE": ("age", "—", _ST_NC, "needEdit.ts (was +10 years)", "V0-24", ""),
    "SAV_INCOME_MULT": ("× annual income", "—", _ST_NC, "need_calculator.py", "V0-16 renamed", ""),
    "PRP_INCOME_MULT": ("× annual income", "—", _ST_NC, "need_calculator.py", "V0-16 renamed", ""),
    "PAC_YEARS": ("years", "—", _ST_NC, "— (new)", "V0-16, agreed V0-18", ""),
    "PAC_COST": ("one-off", "USD", _ST_USD, "— (new)", "V0-16, agreed V0-18", ""),
    "LON_AGE": ("age", "—", _ST_NC, "goal_math.py LIFE_EXPECTANCY_MAX", "V0-21: also the LE cap and the SV path end", ""),
    "spendShareBase": ("% of take-home", "—", _ST_NC, "src/cpf.py spend_share", "", ""),
    "spendSharePerDependant": ("pp per dependant", "—", _ST_NC, "src/cpf.py spend_share", "", ""),
    "spendShareCap": ("% of take-home", "—", _ST_NC, "src/cpf.py spend_share", "", ""),
    "assetsSaveShare": ("% of surplus", "—", _ST_NC, "people_like_you.py", "", ""),
    "workStartAge": ("age", "—", _ST_NC, "people_like_you.py", "", ""),
    "liabilityRatio": ("× assets", "—", _ST_NC, "people_like_you.py", "", ""),
    "CASH_SAVINGS_SHARE": ("% of assets", "—", _ST_NC, "predict.py", "", ""),
    "INVESTMENTS_SHARE": ("% of assets", "—", _ST_NC, "predict.py", "", ""),
    "propertyLow": ("value", "USD", _ST_USD, "predict.py seed_property_value (SGD)", "V0-15", ""),
    "propertyMid": ("value", "USD", _ST_USD, "predict.py seed_property_value (SGD)", "V0-15", ""),
    "propertyHigh": ("value", "USD", _ST_USD, "predict.py seed_property_value (SGD)", "V0-15", ""),
    "propertyIncomeLow": ("per month", "USD", _ST_USD, "predict.py (SGD)", "V0-15", ""),
    "propertyIncomeHigh": ("per month", "USD", _ST_USD, "predict.py (SGD)", "V0-15", ""),
    "PROPERTY_LTV": ("% of property", "—", _ST_NC, "predict.py PROPERTY_LTV", "", ""),
    "lifePremiumRate": ("% of sum", "—", _ST_NC, "predict.py _assumed_life_policy", "", ""),
    "lifeRoundUnit": ("step", "USD", _ST_USD, "predict.py (SGD 100,000)", "V0-15", ""),
    "protectionPremiumRate": ("% of sum", "—", "Placeholder", "planProducts.ts coverPremiumFor", "", "Premium-quote API; too cheap for large covers (N_LTC)"),
    "FREE_BUDGET_SHARE": ("% of surplus", "—", _ST_NC, "planProducts.ts", "", ""),
    "lumpRoundStep": ("step", "USD", _ST_USD, "planProducts.ts (SGD 1,000)", "V0-15", ""),
    "monthlyRoundStep": ("step", "USD", _ST_USD, "planProducts.ts (SGD 50)", "V0-15", ""),
    "coverPremRoundStep": ("step", "USD", _ST_USD, "planProducts.ts (SGD 10)", "V0-15", ""),
    "coverSliderPremFloor": ("per year", "USD", _ST_USD, "planProducts.ts (SGD 200)", "V0-15", ""),
    "annualBudget": ("per year", "USD", _ST_USD, "hu_payload.py (SGD 1,500)", "V0-15", ""),
    "placeholderNeedBudget": ("per year", "USD", _ST_USD, "hu_payload.py (SGD 200)", "V0-15", ""),
    "gfr": ("%", "—", _ST_NC, "hu_payload.py", "", ""),
    "benefitRound": ("step", "USD", _ST_USD, "hu_payload.py (SGD 50,000)", "V0-15", ""),
    "huNumSims": ("count", "—", _ST_NC, "hu_payload.py", "", ""),
    "MIN_EXPENSE_MONTHLY": ("per month", "USD", _ST_USD, "frontend MIN_EXPENSE_MONTHLY (SGD 100)", "V0-21: USD 100 (was S$100)", ""),
    "suggestBand1": ("% p.a.", "—", _ST_NC, "riskCapacity.ts", "", ""),
    "suggestBand2": ("% p.a.", "—", _ST_NC, "riskCapacity.ts", "", ""),
    "suggestBand3": ("% p.a.", "—", _ST_NC, "riskCapacity.ts", "", ""),
    "suggestBand4": ("% p.a.", "—", _ST_NC, "riskCapacity.ts", "", ""),
    "suggestBand5": ("% p.a.", "—", _ST_NC, "riskCapacity.ts", "", ""),
    "defaultRiskTolerance": ("1–5", "—", _ST_NC, "riskCapacity.ts", "", ""),
}
# stress events: code, label, size (value or formula, USD), size unit, timing (value or formula), timing unit,
#                what SV applies, code source, name stem (None = market event, SV override inputs only)
STRESS = [
    ("R_DEA", "Death", round(20000 * SGD_CAL, 2), "one-off USD", 60, "age", "One-off cost; salary and CPF wage → 0 from that age", "stressEvents.ts death", "R_DEA"),
    ("R_CRI", "Critical illness", "=CRI_COST", "one-off USD", 55, "age", "One-off medical cost (= CRI_COST)", "stressEvents.ts ci", "R_CRI"),
    ("R_TPD", "Total & permanent disability", "=TPD_COST", "one-off USD", 50, "age", "One-off cost (= TPD_COST)", "stressEvents.ts tpd", "R_TPD"),
    ("R_PAC", "Personal accident", "=PAC_COST", "one-off USD", 45, "age", "One-off cost (= PAC_COST)", "stressEvents.ts pa", "R_PAC"),
    ("R_HOS", "Hospitalisation", round(120000 * SGD_CAL, 2), "one-off USD", 50, "age", "One-off hospital bill", "stressEvents.ts hosp", "R_HOS"),
    ("R_LTC", "Long-term care", "=LTC_COST", "USD per year", "=LTC_START_AGE", "age → life expectancy", "Care cost every year from that age to the session life expectancy (= N_LTC)", "stressEvents.ts care", "R_LTC"),
    ("R_WED", "Wedding / marriage", round(60000 * SGD_CAL, 2), "one-off USD", 5, "years from today", "One-off cost", "stressEvents.ts wed", "R_WED"),
    ("R_BAB", "Newborn", round(35000 * SGD_CAL, 2), "one-off USD", 3, "years from today", "One-off cost", "stressEvents.ts baby", "R_BAB"),
    ("R_LON", "Longevity", "—", "", "=LON_AGE", "age", "Chart horizon to LON_AGE; N_RET and N_LTC re-sized (display only)", "— (new)", None),
    ("R_MKT", "Market crash", 0.35, "% of assets", 8, "years from today", "Haircut on invested assets", "stressEvents.ts crash", None),
    ("R_CCY", "Currency shock", 0.14, "% (× 2/3 on liquid)", 6, "years from today", "Haircut on liquid assets", "stressEvents.ts ccy", None),
    ("R_INF", "Inflation shock", 0.03, "+ pp", "4–9", "years from today", "inflationRate + extra", "stressEvents.ts infl", None),
    ("R_ICT", "Income cut", -0.2, "% of salary", "5–10", "years from today", "Salary reduced for that span", "stressEvents.ts inc", None),
    ("R_EXP", "Expense shock", 0.15, "% of spend", "6–12", "years from today", "Living spend raised for that span", "stressEvents.ts exp", None),
]
ELSEWHERE = [
    ("CPF rates, OW_CEILING", "CPF tab", "SGD", "Country plug-in (SG-CPF): local by design"),
    ("Income anchors (occupation bands)", "Assumptions J6:L13", "SGD", "Country plug-in: local by design"),
    ("FX rates (152 currencies), PPP price levels (245 countries)", "FX tab; fx_ppp/*.csv", "USD per 1", "Data snapshot; live feed locked per session in the app"),
    ("SV CPF caps, BRS, CPF LIFE tables", "Scenario Visualizer", "SGD", "SG-CPF module inside SV: local by design"),
    ("SV savingsRate, property premium, currency share", "Scenario Visualizer", "—", "SV engine constants"),
    ("HappiU engine constants (whl, beta, cuts, cover age 75, dependent years 10)", "HappiU", "—", "HU engine constants"),
    ("Validation min / max", "Validation", "USD", "USD sanity bands"),
    ("Need Profiler factor weights", "Assumptions A88", "—", "Need_profiler.json"),
]


def build_assumptions(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "Assumptions"
    ws.sheet_properties.tabColor = TEAL
    ws.freeze_panes = "A3"
    _fill(ws, "A1", "Assumptions — every parameter of the model, one place (USD for money)", title_font, paper_fill, border=False)
    ws.merge_cells("A1:G1")
    ws.row_dimensions[1].height = 22
    _fill(
        ws,
        "A2",
        "Yellow cells are editable. Every other tab reads these named cells. "
        "HappiU and Scenario Visualizer still run in HU / SV; this sheet only stores what GP sends them.",
        note_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A2:G2")

    rows = [
        (4, "Economic rates (src/session_rates.py DEFAULTS / ASSUME_DEFAULTS)", None),
        (5, "inflationRate", DEFAULTS["inflationRate"]),
        (6, "interestRate", DEFAULTS["interestRate"]),
        (7, "loanRate", DEFAULTS["loanRate"]),
        (8, "incomeGrowthRate", DEFAULTS["incomeGrowthRate"]),
        (9, "investmentReturn", DEFAULTS["investmentReturn"]),
        (10, "assetReturn", DEFAULTS["assetReturn"]),
        (11, "realReturn (derived)", 0),
        (13, "Life-cycle", None),
        (14, "ageOfRetirement", RETIREMENT_AGE),
        (15, "lifeExpectancyDefault", LIFE_EXPECTANCY),
        (16, "currentYear", CURRENT_YEAR),
        (17, "endAge (chart horizon default)", "=lifeExpectancyDefault"),
        (18, "SAV_TARGET_AGE (N_SAV default target: next car / investment)", 40),
        (19, "PRP_TARGET_AGE (N_PRP default target: 3 years after marriage at 30)", 33),
        (21, "System currency (V0-15) — every calculator runs in USD; fixed amounts below are USD", None),
        (22, "systemCurrency", "USD"),
        (23, "fxMode (A = market rate; B = market rate × price level)", "B"),
        (24, "priceLevelOn (option B)", True),
        (25, "LTC_COST (USD / year, N_LTC nursing home)", 129_000),
        (26, "LTC_START_AGE (N_LTC default; front-end input)", 80),
        (27, "Need parameters (src/pipeline/goal_math.py) — money in USD", None),
        (28, "RET_LIFESTYLE_FRUGAL", 0.75),
        (29, "RET_LIFESTYLE_STRESSFREE", 1.00),
        (30, "RET_LIFESTYLE_ONLYTHEBEST", 1.25),
        (31, "INC_SUPPORT_MIN", INC_SUPPORT_MIN),
        (32, "INC_SUPPORT_MAX", INC_SUPPORT_MAX),
        (33, "INC_SUPPORT_PIVOT_AGE", INC_SUPPORT_PIVOT_AGE),
        (34, "CRI_YEARS", CRI_YEARS),
        (35, "CRI_COST (USD)", round(CRI_COST * SGD_CAL, 2)),
        (36, "TPD_YEARS", TPD_YEARS),
        (37, "TPD_COST (USD)", round(TPD_COST * SGD_CAL, 2)),
        (38, "HOS_MONTHS", HOS_MONTHS),
        (39, "EDU_COST (USD)", round(EDU_COST * SGD_CAL, 2)),
        (40, "EDU_TARGET_AGE (N_EDU default target: children leave home at 20, born at 30)", 50),
        (41, "SAV_INCOME_MULT", 1),
        (42, "PRP_INCOME_MULT", 5),
        (43, "PAC_YEARS", 1),
        (44, "PAC_COST (USD = S$80,000 at the calibration rate)", round(80_000 * SGD_CAL, 2)),
        (45, "LON_AGE (life expectancy cap and R_LON)", 99),
        (46, "Household seeding (src/predict.py spend / assets; CPF is on the CPF tab)", None),
        (47, "spendShareBase", 0.675),
        (48, "spendSharePerDependant", 0.05),
        (49, "spendShareCap", 0.90),
        (50, "assetsSaveShare", 0.5),
        (51, "workStartAge", 21),
        (52, "liabilityRatio (PLU only; not the mortgage)", 0.7),
        (53, "CASH_SAVINGS_SHARE", CASH_SAVINGS_SHARE),
        (54, "INVESTMENTS_SHARE", INVESTMENTS_SHARE),
        (55, "propertyLow (USD)", round(350_000 * SGD_CAL, 2)),
        (56, "propertyMid (USD)", round(650_000 * SGD_CAL, 2)),
        (57, "propertyHigh (USD)", round(850_000 * SGD_CAL, 2)),
        (58, "propertyIncomeLow (USD / month)", round(10_000 * SGD_CAL, 2)),
        (59, "propertyIncomeHigh (USD / month)", round(20_000 * SGD_CAL, 2)),
        (60, "PROPERTY_LTV", PROPERTY_LTV),
        (61, "lifePremiumRate", 0.0031),
        (62, "lifeRoundUnit (USD, before nice step)", round(100_000 * SGD_CAL, 2)),
        (64, "Plan and budget (frontend/src/lib/planProducts.ts)", None),
        (65, "protectionPremiumRate", 0.00078),
        (66, "FREE_BUDGET_SHARE", 0.5),
        (67, "lumpRoundStep (USD, before nice step)", round(1000 * SGD_CAL, 2)),
        (68, "monthlyRoundStep (USD, before nice step)", round(50 * SGD_CAL, 2)),
        (69, "coverPremRoundStep (USD, before nice step)", round(10 * SGD_CAL, 2)),
        (70, "coverSliderPremFloor (USD)", round(200 * SGD_CAL, 2)),
        (72, "HappiU budget envelope (src/hu_payload.py) — not Budget Calculator", None),
        (73, "annualBudget (USD)", round(1500 * SGD_CAL, 2)),
        (74, "placeholderNeedBudget (USD)", round(200 * SGD_CAL, 2)),
        (75, "gfr", 0.05),
        (76, "benefitRound (USD, before nice step)", round(50_000 * SGD_CAL, 2)),
        (77, "huNumSims", 200),
        (78, "PPP_BASE_COUNTRY (price level = 1)", "Singapore"),
        (79, "MIN_EXPENSE_MONTHLY (USD)", 100),
        (81, "Risk → investmentReturn seed (frontend/src/lib/riskCapacity.ts)", None),
        (82, "suggestBand1", 0.030),
        (83, "suggestBand2", 0.035),
        (84, "suggestBand3", 0.042),
        (85, "suggestBand4", 0.050),
        (86, "suggestBand5", 0.055),
        (87, "defaultRiskTolerance", 3),
    ]
    named = {
        "inflationRate": "B5",
        "systemCurrency": "B22",
        "fxMode": "B23",
        "PPP_BASE_COUNTRY": "B78",
        "priceLevelOn": "B24",
        "LTC_COST": "B25",
        "LTC_START_AGE": "B26",
        "interestRate": "B6",
        "loanRate": "B7",
        "incomeGrowthRate": "B8",
        "investmentReturn": "B9",
        "assetReturn": "B10",
        "realReturn": "B11",
        "ageOfRetirement": "B14",
        "lifeExpectancyDefault": "B15",
        "currentYear": "B16",
        "endAge": "B17",
        "RET_LIFESTYLE_FRUGAL": "B28",
        "RET_LIFESTYLE_STRESSFREE": "B29",
        "RET_LIFESTYLE_ONLYTHEBEST": "B30",
        "INC_SUPPORT_MIN": "B31",
        "INC_SUPPORT_MAX": "B32",
        "INC_SUPPORT_PIVOT_AGE": "B33",
        "CRI_YEARS": "B34",
        "CRI_COST": "B35",
        "TPD_YEARS": "B36",
        "TPD_COST": "B37",
        "HOS_MONTHS": "B38",
        "EDU_COST": "B39",
        "EDU_TARGET_AGE": "B40",
        "SAV_TARGET_AGE": "B18",
        "PRP_TARGET_AGE": "B19",
        "SAV_INCOME_MULT": "B41",
        "PRP_INCOME_MULT": "B42",
        "PAC_YEARS": "B43",
        "PAC_COST": "B44",
        "LON_AGE": "B45",
        "spendShareBase": "B47",
        "spendSharePerDependant": "B48",
        "spendShareCap": "B49",
        "assetsSaveShare": "B50",
        "workStartAge": "B51",
        "liabilityRatio": "B52",
        "CASH_SAVINGS_SHARE": "B53",
        "INVESTMENTS_SHARE": "B54",
        "propertyLow": "B55",
        "propertyMid": "B56",
        "propertyHigh": "B57",
        "propertyIncomeLow": "B58",
        "propertyIncomeHigh": "B59",
        "PROPERTY_LTV": "B60",
        "lifePremiumRate": "B61",
        "lifeRoundUnit": "B62",
        "protectionPremiumRate": "B65",
        "FREE_BUDGET_SHARE": "B66",
        "lumpRoundStep": "B67",
        "monthlyRoundStep": "B68",
        "coverPremRoundStep": "B69",
        "coverSliderPremFloor": "B70",
        "annualBudget": "B73",
        "placeholderNeedBudget": "B74",
        "gfr": "B75",
        "benefitRound": "B76",
        "huNumSims": "B77",
        "MIN_EXPENSE_MONTHLY": "B79",
    }
    for row, label, value in rows:
        if value is None:
            _fill(ws, f"A{row}", label, sec_font, sec_fill, border=False)
            ws.merge_cells(f"A{row}:H{row}")
            continue
        _fill(ws, f"A{row}", label)
        editable = row not in (11, 17, 22)
        pct_rows = {
            5, 6, 7, 8, 9, 10, 28, 29, 30,
            47, 48, 49, 50, 52, 53, 54, 60, 61, 65, 66, 75, 82, 83, 84, 85, 86,
        }
        if row in pct_rows:
            num = "0.00%" if row in (61, 65) else "0.0%"
        elif isinstance(value, float) and abs(value) < 10 and value != int(value):
            num = "0.000"
        elif isinstance(value, float) and value != int(value):
            num = "#,##0.00"
        else:
            num = "#,##0"
        _fill(
            ws,
            f"B{row}",
            value,
            fill=input_fill if editable else None,
            num=num,
            align=center,
        )
    ws["B11"] = "=MAX(0,(1+investmentReturn)/(1+inflationRate)-1)"
    ws["B11"].number_format = "0.0000%"
    ws["B11"].font = body_font
    _headers(ws, 3, ["Parameter", "Value", "Unit", "Currency", "Status", "Code source", "Changed in", "Open proposal"])
    stat_fill = {_ST_USD: calc_fill, _ST_NC: paper_fill, _ST_SYS: blue_fill, "Derived": paper_fill, "Placeholder": red_fill}
    for row, label, value in rows:
        if value is None:
            continue
        key = label.split(" ")[0]
        meta = ASSUME_META.get(key)
        if not meta:
            continue
        for j, v in enumerate(meta, 3):
            _fill(ws, f"{get_column_letter(j)}{row}", v, font=note_font if j >= 6 else body_font,
                  fill=stat_fill.get(v) if j == 5 else (input_fill if (j == 8 and v) else None), align=wrap)

    for name, cell in named.items():
        col = "".join(c for c in cell if c.isalpha())
        row = "".join(c for c in cell if c.isdigit())
        # Both column and row must be absolute. `$B45` is row-relative, so
        # =spendShareCap on People Like You row 28 reads Assumptions!B74.
        _name(wb, name, f"Assumptions!${col}${row}")

    # Income bands
    _fill(ws, "J4", "Singapore occupation income bands (income_anchors.json)", sec_font, sec_fill, border=False)
    ws.merge_cells("J4:L4")
    _fill(ws, "J5", "occupation", h_font, header_fill, center)
    _fill(ws, "K5", "min", h_font, header_fill, center)
    _fill(ws, "L5", "max", h_font, header_fill, center)
    band_rows = []
    short_name = {
        "nurse": "Nurse",
        "teacher": "Teacher",
        "accountant": "Accountant",
        "marketing_manager": "Marketing Manager",
        "software_engineer": "Software Engineer",
        "doctor": "Doctor",
        "investment_banker": "Investment Banker",
        "ceo": "CEO",
    }
    r = 6
    for occ in ANCHORS["occupations"]:
        b = (occ.get("bounds") or {}).get("singapore")
        if not b:
            continue
        _fill(ws, f"J{r}", short_name.get(occ["id"], occ["label"]))
        _fill(ws, f"K{r}", float(b["min"]), num="#,##0", align=center)
        _fill(ws, f"L{r}", float(b["max"]), num="#,##0", align=center)
        _fill(ws, f"M{r}", occ["label"], font=note_font)
        r += 1
    _name(wb, "IncomeBands", f"Assumptions!$J$6:$L${r - 1}")

    # Stress events (V0-21): named sizes and timings, all money in USD
    _fill(ws, "J19", "Stress events (stressEvents.ts) — sizes in USD, personal risks by age. Scenario Visualizer applies them when switched on",
          sec_font, sec_fill, border=False)
    ws.merge_cells("J19:Q19")
    _headers_at = ["code", "label", "size", "size unit", "timing", "timing unit", "what SV applies", "code source"]
    for i, h in enumerate(_headers_at):
        _fill(ws, f"{get_column_letter(10 + i)}20", h, h_font, header_fill, center)
    for i, (code, lab, size, su, tim, tu, what, src, stem) in enumerate(STRESS):
        rr = 21 + i
        vals = [code, lab, size, su, tim, tu, what, src]
        for j, v in enumerate(vals):
            col = get_column_letter(10 + j)
            fill = None
            if stem and j in (2, 4) and not (isinstance(v, str) and v.startswith("=")):
                fill = input_fill
            num = None
            if j == 2 and isinstance(v, float) and abs(v) < 1:
                num = "0%"
            elif j == 2:
                num = "#,##0"
            _fill(ws, f"{col}{rr}", v, fill=fill, num=num, align=wrap if j in (6, 7) else center)
        if stem:
            _name(wb, f"{stem}_SIZE", f"Assumptions!$L${rr}")
            _name(wb, f"{stem}_WHEN", f"Assumptions!$N${rr}")
    r_else = 21 + len(STRESS) + 2
    _fill(ws, f"J{r_else}", "Parameters held on other tabs (by design)", sec_font, sec_fill, border=False)
    ws.merge_cells(f"J{r_else}:Q{r_else}")
    for i, h in enumerate(["parameter", "where", "currency", "why there"]):
        _fill(ws, f"{get_column_letter(10 + i)}{r_else + 1}", h, h_font, header_fill, center)
    for i, row in enumerate(ELSEWHERE):
        for j, v in enumerate(row):
            _fill(ws, f"{get_column_letter(10 + j)}{r_else + 2 + i}", v, align=wrap)

    # Profiler factor-weight matrix
    _fill(ws, "A88", "Need Profiler factor weights (Need_profiler.json needs_factor_weights)", sec_font, sec_fill, border=False)
    ws.merge_cells("A88:M88")
    _fill(ws, "A89", "factor \\ need", h_font, header_fill, center)
    for i, lab in enumerate(WB_LABELS, 2):
        _fill(ws, f"{get_column_letter(i)}89", SHOW.get(lab, lab), h_font, header_fill, center)
    for i, factor in enumerate(FACTOR_ROWS):
        rr = 90 + i
        _fill(ws, f"A{rr}", factor)
        for j, lab in enumerate(WB_LABELS, 2):
            _fill(ws, f"{get_column_letter(j)}{rr}", _factor_weight(factor, lab), num="0", align=center)
    lastc = get_column_letter(1 + len(WB_LABELS))
    _name(wb, "ProfilerWeights", f"Assumptions!$B$90:${lastc}${90 + len(FACTOR_ROWS) - 1}")
    for i, factor in enumerate(FACTOR_ROWS):
        _name(wb, f"PW_{i + 1}", f"Assumptions!$B${90 + i}:${lastc}${90 + i}")

    _hu_tables(wb, ws, 90 + len(FACTOR_ROWS) + 3)

    ws["O4"] = (
        "V0-21: this tab is the one parameter list (Parameter review merged). Money is USD; country plug-ins stay local. "
        "Decisions and history: Change log tab."
    )
    ws["O4"].font = note_font
    ws["O4"].alignment = wrap
    ws.merge_cells("O4:Q8")

    _widths(ws, {"A": 46, "B": 14, "C": 16, "D": 10, "E": 14, "F": 30, "G": 26, "H": 30, "I": 3,
                 "J": 30, "K": 24, "L": 16, "M": 16, "N": 12, "O": 18, "P": 40, "Q": 22})
    ws.row_dimensions[2].height = 32
    ws.auto_filter.ref = "A5:B10"


HU_RATE_LABELS = {
    "mort": "mortality",
    "adb": "accidental death",
    "morb": "critical illness (morbidity)",
    "ptd": "total & permanent disability (HU file ptd_rate)",
    "dis": "dismemberment",
    "hosp": "hospitalisation (not on GP's path)",
}
HU_SEX_COLS = ("Male", "MaleSmoker", "Female", "FemaleSmoker")


def _hu_tables(wb: Workbook, ws, top: int) -> None:
    """HU CashflowHandler/Tables q(age) and social-security tables, ages 18–100."""
    tables = load_hu_tables()
    last_col = 1 + 4 * len(HU_RATES) + 3
    _fill(
        ws, f"A{top}",
        "HappiU rate tables (HU/src/CashflowHandler/Tables/*.csv) — q at age, read at age + 1 + year. "
        "Columns per rate: Male, Male smoker, Female, Female smoker.",
        sec_font, sec_fill, border=False,
    )
    ws.merge_cells(f"A{top}:{get_column_letter(last_col)}{top}")
    band, head = top + 1, top + 2
    r0, r1 = head + 1, head + 1 + (HU_AGE1 - HU_AGE0)
    _fill(ws, f"A{band}", "", fill=assume_hdr)
    _fill(ws, f"A{head}", "age", h_font, header_fill, center)
    for i, name in enumerate(HU_RATES):
        c0 = 2 + 4 * i
        _group_band(ws, c0, c0 + 3, band, HU_RATE_LABELS[name], assume_hdr)
        for j, sex in enumerate(HU_SEX_COLS):
            _fill(ws, f"{get_column_letter(c0 + j)}{head}", sex, h_font, header_fill, center)
        _name(wb, f"HU_q_{name}", f"Assumptions!${get_column_letter(c0)}${r0}:${get_column_letter(c0 + 3)}${r1}")
    ss0 = 2 + 4 * len(HU_RATES)
    _group_band(ws, ss0, ss0 + 2, band, "social security (ss_contribution_cap / ss_growth_rate)", assume_hdr)
    for j, h in enumerate(("contribution", "cap", "growth")):
        _fill(ws, f"{get_column_letter(ss0 + j)}{head}", h, h_font, header_fill, center)
    for a in range(HU_AGE0, HU_AGE1 + 1):
        rr = r0 + a - HU_AGE0
        _fill(ws, f"A{rr}", a, align=center)
        for i, name in enumerate(HU_RATES):
            for j, sex in enumerate(HU_SEX_COLS):
                _fill(ws, f"{get_column_letter(2 + 4 * i + j)}{rr}", tables[name][sex][a],
                      fill=assume_fill, num="0.000000", align=center)
        c_, cap = tables["ss_cap"][a]
        _fill(ws, f"{get_column_letter(ss0)}{rr}", c_, fill=assume_fill, num="0.000", align=center)
        _fill(ws, f"{get_column_letter(ss0 + 1)}{rr}", cap, fill=assume_fill, num="#,##0", align=center)
        _fill(ws, f"{get_column_letter(ss0 + 2)}{rr}", tables["ss_growth"][a], fill=assume_fill, num="0.0000", align=center)
    for j, nm in enumerate(("HU_ssC", "HU_ssCap", "HU_ssG")):
        col = get_column_letter(ss0 + j)
        _name(wb, nm, f"Assumptions!${col}${r0}:${col}${r1}")


def build_overview(wb: Workbook) -> None:
    ws = wb.create_sheet("Overview", 0)
    ws.sheet_properties.tabColor = GOLD
    ws.freeze_panes = "A3"
    _fill(ws, "A1", "FinPlan360 calculation components — live code, September 2026", title_font, paper_fill, border=False)
    ws.merge_cells("A1:H1")
    _fill(
        ws,
        "A2",
        "Yellow = type here. Orange = override (leave blank to keep the calculated value). "
        "Pick the persona on the Selected persona tab; every later tab follows that id. "
        "Gold = persona input, blue = LLM, orange = user / Money-page override, green = calculated, purple = assumptions. "
        "FX converts local amounts to USD. Validation applies USD-only rules. "
        "CPF is its own tab and is on only when the country switch says so (Singapore on, others off). "
        "HappiU and Scenario Visualizer are mapped here but scored / projected in HU and SV.",
        note_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A2:H2")
    headers = [
        "Component",
        "Owner",
        "Reads",
        "Writes",
        "How it calculates (code)",
        "Code",
        "Tab",
        "HTTP / UI",
    ]
    _headers(ws, 3, headers)
    rows = [
        (
            "CPF",
            "GP pipeline (Singapore only)",
            "country, residency, age, incomeMonthly. Country switch on the CPF tab.",
            "employee CPF, take-home. 0 / income when CPF is off.",
            "On only when the country table (or orange override) is TRUE. Singapore Citizen/PR: "
            "employee CPF = floor(min(gross, OW_CEILING) × age-band rate). Foreigner → 0. "
            "Any other country → off, take-home = gross. src/cpf.py.",
            "src/cpf.py",
            "CPF",
            "Inside POST /v1/predict (take-home)",
        ),
        (
            "People Like You",
            "GP pipeline",
            "age / DOB, occupation, gender, dependents, residency. CPF box for take-home. Does not read Assumptions.",
            "incomeMonthly, expenseMonthly, cash, investments, property, mortgage, one Life Protection policy, lifeExpectancy, isSmoker.",
            "LLM proposes gross monthly income and lifestyle flags. Income is clamped to the Singapore occupation band. "
            "Employee CPF = floor(min(gross, 8000) × age-band rate); 0 if Foreigner. "
            "expenseMonthly = round(take-home × min(67.5% + 5pp × dependents, 90%), 2). "
            "Liquid assets = max(0, surplus × 12 × 0.5 × (age − 21)), then cash 15% / investments 85%. "
            "If the model says they own a home: property from income band, mortgage = round(property × 55%). "
            "Assumed life cover = max(mortgage rounded up to S$100k, 5 × annual income if dependents > 0); premium = round(sum × 0.31%). "
            "PLU liabilities (= assets × 0.7) is not the mortgage. If this step fails, predict returns 503.",
            "src/pipeline/people_like_you.py, src/cpf.py, src/predict.py _apply_plu",
            "People Like You",
            "POST /v1/predict (first of three)",
        ),
        (
            "Need Profiler",
            "GP pipeline",
            "Age, gender, dependents, occupation, smoker, income, expense, liquid assets, PLU liabilities, hospital/ward/lifestyle/sports, car/home/travel flags. Existing cover is hard-coded 0. No Assumptions. No LLM.",
            "needs[].enabled, needs[].priority, needs[].weightageScore. Four UNIFIED types on: two protection + two growth (retirement always one of the growth pair).",
            "Eleven profiler labels are scored as Σ (factor_weight × option_weight), rounded to 2 dp, then min–max scaled 0–10. "
            "Income / expense / assets / liabilities convert to PPP-USD (market USD ÷ price level). "
            "Personal accident joins the protection pick. Growth is N_EDU vs N_SAV; N_PRP and N_LTC are never auto-picked. "
            "priority = 5 if scaled score > 7 else 3. Home / car / travel are scored as parked coverage. "
            "Orange Enable? columns let you force a need on or off.",
            "src/services/need_profiler/service.py, src/pipeline/prompts/Need_profiler.json",
            "Need Profiler",
            "POST /v1/predict",
        ),
        (
            "Need Calculator",
            "GP pipeline",
            "Money attributes, enabled needs, goal-card sliders (lifestyle, retAge, targetYear, incomeReplaceMonthly, dependYears, bequest, monthlyContribution, tagged existing), Assumptions rates, Need parameters.",
            "For every UNIFIED type: needAmount, have, gap. Copies ageOfRetirement from the retirement row.",
            "realReturn = max(0, (1 + investmentReturn) / (1 + inflationRate) − 1). "
            "N_RET = annualSpend × (1+realReturn)^T × a(realReturn, n), n = min(LE,99) − retAge. "
            "N_INC = bequest + mortgage + ordinary annuity of annual spend over supportYears = min(max(10, 50 − age), 25). "
            "N_CRI / N_TPD = annuity-due of replacement income for 3 / 5 years + S$200,000. N_HOS = income × 6. "
            "N_EDU = 75,000 × (1 + inflation)^(targetYear − thisYear). N_SAV / N_PRP = stored needAmount if > 0, else 1× / 5× annual income. "
            "Protection have = policy sum (life is seeded by PLU). Wealth have = tagged investments only, grown at realReturn; cash is never allocated. "
            "Amounts are computed for all eight types even when a need is off. Orange Enable? and slider columns are the goal-card inputs.",
            "src/pipeline/need_calculator.py evaluate_session, src/pipeline/goal_math.py, src/hu_payload.py need_existing / apply_investment_pot",
            "Need Calculator",
            "POST /v1/predict and POST /v1/needs",
        ),
        (
            "Goal cards",
            "GP UI",
            "Last calculator row (have, gap, stored sliders).",
            "Slider fields on the need; then POST /v1/needs (debounced). Does not recompute amounts in the browser.",
            "fillNeedEdit reads stored fields. patchNeedInputs writes lifestyle / retAge / targetYear / existing / … onto the session. "
            "Retirement stays on. The Score/Plan cap of four needs is UI-only (needEdit.capEnabledNeeds); this workbook lets you switch any need.",
            "frontend/src/lib/needEdit.ts",
            "Need Calculator (slider columns)",
            "Score and Plan screens",
        ),
        (
            "Plan Calculator",
            "GP UI",
            "Enabled needs with gap > 0, take-home surplus, Assumptions inflationRate / investmentReturn / ageOfRetirement.",
            "planSum + planPrem (protection), planMth + planLump (wealth), investMth / investLump totals, plansOff.",
            "Suggested = enabled AND gap > 0. Default planSum = round(gap). "
            "planPrem = dummy indicative round((sum × 0.00078) / 10) × 10 (future: premium-quote API). "
            "Wealth horizon = years to retirement, or targetYear − this year. "
            "Lump / monthly caps = the amount that alone grows to the gap at realReturn (round up to S$1,000 / S$50). "
            "Default monthly = round((max(0, take-home − expense) × 12 − all protection premiums) × 50% / 12 / n_wealth / 50) × 50, then min(share, cap). Default lump = 0. "
            "Orange Include? columns are plansOff.",
            "frontend/src/lib/planProducts.ts, frontend/src/lib/local.ts seedProducts",
            "Plan Calculator",
            "Plan screen (not an HTTP engine)",
        ),
        (
            "Budget Calculator",
            "GP UI",
            "take-home, expenseMonthly, investments, included planPrem / planMth / planLump. Not the economic rates.",
            "Nothing on the session. Plan-screen affordability only.",
            "available = max(0, takeHomeMonthly − expenseMonthly). free = round(available × 0.5). "
            "monthly = round(wealth contributions + protection premiums / 12). monthlyOver = monthly − free. "
            "lumpOver = wealth lumps − investments. Separate from the HappiU envelope (annualBudget 1500).",
            "planAfford in frontend/src/lib/planProducts.ts; availableBudget in types.ts",
            "Budget Calculator",
            "Plan screen",
        ),
        (
            "FX",
            "Workbook only (not an HTTP engine)",
            "Personas currency + effective session money fields from People Like You.",
            "USD per 1 local, and each money field in USD. Validation reads these; engines stay local.",
            "Lookup ISO code in the FX rate table (USD per 1 local unit). "
            "USD = local × rate. Example: 5,000 SGD × 0.78162734 = 3,908 USD; 5,000 VND × 0.0000385 = 0.19 USD. "
            "The Need Profiler divides by the country's relative price level as well (PPP-USD). "
            "Edit the rate table on this tab. People Like You still stores local currency.",
            "Workbook FX tab (no src module — validation helper)",
            "FX",
            "Not in the live pipeline",
        ),
        (
            "HappiU",
            "HU, via GP",
            "Whole session. Assumptions rates, CPF (inside HU), riskProfile, plan fields when set. Need amounts already stored.",
            "preHappiU, postHappiU. GP does not run the Monte Carlo.",
            "GP maps the session (src/hu_payload.py). Salary is gross incomeMonthly. N_HOS is renamed N_HSP. "
            "If retirement is off, GP still sends a synthetic N_RET = expense × 12 × (lifeExpectancy − retAge). "
            "Before a plan: benefitAmount = needAmount rounded to S$50,000, budget 200. With a plan: planSum / planPrem. "
            "This workbook does not score HappiU.",
            "src/hu_payload.py → POST /v1/score → HU",
            "Assumptions (envelope only)",
            "POST /v1/score",
        ),
        (
            "Scenario Visualizer",
            "SV, via GP",
            "Session after Plan, all six rates, ageOfRetirement, endAge, stress chips. CPF inside SV.",
            "Year-by-year wealth path. GP does not run the year step.",
            "preWealth = session without the plan; postWealth = plus included planMth / planLump / planSum / planPrem. "
            "svNumSims defaults to 20. Investment contribution = max(0, take-home − expenseMonthly) once a year. "
            "This workbook does not project the path.",
            "src/sv_payload.py → POST /v1/project → SV",
            "Assumptions (stress catalogue)",
            "POST /v1/project",
        ),
    ]
    for i, row in enumerate(rows):
        rr = 4 + i
        for j, v in enumerate(row, 1):
            _fill(ws, f"{get_column_letter(j)}{rr}", v, align=wrap)
        ws.row_dimensions[rr].height = 78
    ws.row_dimensions[2].height = 36
    _widths(ws, {"A": 22, "B": 14, "C": 36, "D": 36, "E": 62, "F": 42, "G": 28, "H": 24})

    _fill(ws, "A14", "Journey order (one session, each step adds attributes)", sec_font, sec_fill, border=False)
    ws.merge_cells("A14:H14")
    _fill(
        ws,
        "A15",
        "Shared inputs (Assumptions · CPF · Need parameters · Risk · Stress events)  →  "
        "About you  →  CPF (on for Singapore only)  →  People Like You (or the customer edits the same money fields)  →  "
        "Need Profiler  →  Need Calculator  →  HappiU (no plan)  →  Plan Calculator  →  "
        "Budget Calculator  →  Scenario Visualizer  →  HappiU (with plan). "
        "Workbook-only: FX (local → USD) then Validation (USD rules).",
        body_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A15:H15")
    ws.row_dimensions[15].height = 36
    _fill(
        ws,
        "A17",
        "UNIFIED types in code order: N_INC, N_CRI, N_TPD, N_HOS (protection) · N_RET, N_EDU, N_SAV, N_PRP (wealth). "
        "Goal-card sliders live on the Need Calculator tab. Discrepancies lists remaining multi-country / multi-currency work.",
        note_font,
        border=False,
    )
    ws.merge_cells("A17:H17")


def build_personas_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("Personas")
    ws.sheet_properties.tabColor = "8B6914"
    ws.freeze_panes = "C3"
    _group_band(ws, 1, 9, 1, "A · INPUT DATA  —  About you (typed / session)", input_hdr)
    _group_band(
        ws,
        10,
        22,
        1,
        "B · LLM PREDICTED DATA  —  13 fields from people_like_you_all_fields.json",
        llm_hdr,
    )
    _group_band(
        ws,
        23,
        29,
        1,
        "E · USER / FRONTEND OVERRIDE  —  Money page (blank = keep People Like You calculated)",
        override_hdr,
    )
    _group_band(ws, 30, 30, 1, "notes", header_fill)
    _legend(ws, "AF", 1)
    headers = [
        "id", "name", "age", "gender", "residency", "country", "occupation", "dependents", "maritalStatus (blank = infer)",
        "income", "currency", "risk_ability", "price_sensitivity", "property", "car",
        "ward_type", "hospitalization_type", "travelling", "sports", "retirement_lifestyle",
        "is_smoker", "life_expectancy",
        "expenseMonthly", "cash (Cash & Savings)", "investments", "property value",
        "mortgage (loans)", "PLU liabilities", "life sum assured",
        "What this row varies",
    ]
    for i, h in enumerate(headers, 1):
        if i <= 9:
            fill = input_hdr
        elif i <= 22:
            fill = llm_hdr
        elif i <= 29:
            fill = override_hdr
        else:
            fill = header_fill
        _fill(ws, f"{get_column_letter(i)}2", h, font=h_font, fill=fill, align=center)
    yn = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=False)
    res = DataValidation(type="list", formula1='"Citizen,PR,Foreigner"', allow_blank=False)
    gen = DataValidation(type="list", formula1='"Female,Male"', allow_blank=False)
    ctry = DataValidation(
        type="list",
        formula1='"Singapore,Vietnam,Malaysia,Thailand,Philippines,Australia,Germany,Hong Kong,United States"',
        allow_blank=False,
    )
    ccy = DataValidation(type="list", formula1='"SGD,VND,MYR,THB,PHP,AUD,EUR,HKD,USD"', allow_blank=False)
    risk = DataValidation(type="list", formula1='"conservative,moderate,aggressive"', allow_blank=False)
    price = DataValidation(type="list", formula1='"low,medium,high"', allow_blank=False)
    ward = DataValidation(type="list", formula1='"Single,Double,Ward,A,B"', allow_blank=True)
    hosp = DataValidation(type="list", formula1='"Public,Private"', allow_blank=False)
    life = DataValidation(type="list", formula1='"Basic,Comfortable,Luxurious,frugal,stress-free,only the best"', allow_blank=True)
    ws.add_data_validation(yn)
    ws.add_data_validation(res)
    ws.add_data_validation(gen)
    ws.add_data_validation(ctry)
    ws.add_data_validation(ccy)
    ws.add_data_validation(risk)
    ws.add_data_validation(price)
    ws.add_data_validation(ward)
    ws.add_data_validation(hosp)
    ws.add_data_validation(life)
    yn.add(f"N3:O{R1}")
    yn.add(f"R3:R{R1}")
    yn.add(f"U3:U{R1}")
    res.add(f"E3:E{R1}")
    gen.add(f"D3:D{R1}")
    ctry.add(f"F3:F{R1}")
    ccy.add(f"K3:K{R1}")
    risk.add(f"L3:L{R1}")
    price.add(f"M3:M{R1}")
    ward.add(f"P3:P{R1}")
    hosp.add(f"Q3:Q{R1}")
    life.add(f"T3:T{R1}")
    for i, p in enumerate(PERSONAS):
        r = 3 + i
        plu = twin_plu(p)
        vals = [
            p["id"], p["name"], p["age"], p["gender"], p["residency"], p["country"], p["occupation"],
            p["dependents"], p["marital_status"],
            p["llm_income"], p["llm_currency"], p["llm_risk_ability"], p["llm_price_sensitivity"],
            p["llm_property"], p["llm_car"], p["llm_ward_type"], p["llm_hospital_type"],
            p["llm_travelling"], p["llm_sports"], p["llm_retirement_lifestyle"],
            p["llm_smoker"], p["llm_life_expectancy"],
            "", "", "", "", "", "", "",  # V0-24: Money-page overrides cleared; blank = People Like You calculated
            p["varies"],
        ]
        money_cols = {"J", "W", "X", "Y", "Z", "AA", "AB", "AC"}
        for j, v in enumerate(vals, 1):
            col = get_column_letter(j)
            if j <= 9:
                fill = input_fill
            elif j <= 22:
                fill = llm_fill
            elif j <= 29:
                fill = override_fill
            else:
                fill = paper_fill
            num = "#,##0.00" if col in ("W",) else ("#,##0" if col in money_cols else None)
            _fill(ws, f"{col}{r}", v, fill=fill, align=center if j not in (2, 7, 19, 30) else left, num=num)
    _widths(ws, {
        "A": 6, "B": 18, "C": 6, "D": 10, "E": 12, "F": 14, "G": 20, "H": 12, "I": 22,
        "J": 12, "K": 10, "L": 14, "M": 16, "N": 10, "O": 8, "P": 12, "Q": 20,
        "R": 12, "S": 22, "T": 20, "U": 12, "V": 14,
        "W": 16, "X": 20, "Y": 14, "Z": 16, "AA": 16, "AB": 16, "AC": 16, "AD": 52,
    })
    ws.auto_filter.ref = f"A2:AD{R1}"
    ws.row_dimensions[1].height = 22
    _name(wb, "PersonaIDs", "Personas!$A$3:$A$52")


def _px(col: str, sel: str = "$B$2") -> str:
    return (
        f"IFERROR(INDEX(Personas!{col}$3:{col}$52,"
        f"MATCH({sel},Personas!$A$3:$A$52,0)),\"\")"
    )


KIND_META = {
    "A": (input_hdr, input_fill, "A · input"),
    "B": (llm_hdr, llm_fill, "B · LLM predicted"),
    "C": (calc_hdr, calc_fill, "C · calculated"),
    "D": (assume_hdr, assume_fill, "D · assumption / shared"),
    "O": (override_hdr, override_fill, "E · user / frontend override"),
}


def _kv(ws, r: int, label, value, kind: str, note: str = "", num=None) -> int:
    hdr, fill, kind_label = KIND_META[kind]
    _fill(ws, f"A{r}", label, font=h_font, fill=hdr, align=left)
    _fill(ws, f"B{r}", value, fill=fill, num=num, align=center)
    _fill(ws, f"C{r}", kind_label, fill=fill, align=center)
    _fill(ws, f"D{r}", note, font=note_font, fill=paper_fill, align=left)
    return r + 1


def _section(ws, r: int, label: str, fill) -> int:
    _group_band(ws, 1, 4, r, label, fill)
    return r + 1


def _bind(wb: Workbook, sheet: str, mapping: dict[str, int], col: str = "B") -> None:
    quoted = f"'{sheet}'" if " " in sheet else sheet
    for name, row in mapping.items():
        _name(wb, name, f"{quoted}!${col}${row}")


def _add_selector(ws, *, master: bool, title: str) -> None:
    _fill(ws, "A1", title, title_font, paper_fill, border=False)
    ws.merge_cells("A1:D1")
    _fill(ws, "A2", "Selected persona", font=h_font, fill=input_hdr, align=center)
    if master:
        _fill(ws, "B2", "P01", fill=input_fill, align=center)
        dv = DataValidation(type="list", formula1="=PersonaIDs", allow_blank=False)
        ws.add_data_validation(dv)
        dv.add("B2")
        follow = (
            "This is the only picker. CPF, People Like You, Need Profiler, "
            "Need Calculator, Plan, Budget, FX, and Validation follow this cell."
        )
    else:
        _fill(ws, "B2", "=SelectedPersona", fill=input_fill, align=center)
        follow = "Follows the dropdown on the Selected persona tab."
    _fill(ws, "C2", f"={_px('B')}", fill=input_fill)
    _fill(ws, "D2", follow, note_font, paper_fill, border=False)
    _fill(ws, "A3", "Attribute", font=h_font, fill=header_fill, align=center)
    _fill(ws, "B3", "Value", font=h_font, fill=header_fill, align=center)
    _fill(ws, "C3", "Kind", font=h_font, fill=header_fill, align=center)
    _fill(ws, "D3", "Source / formula", font=h_font, fill=header_fill, align=center)


def _dash_widths(ws) -> None:
    _widths(ws, {"A": 36, "B": 22, "C": 34, "D": 78})
    ws.freeze_panes = "A4"
    ws.row_dimensions[1].height = 28


def build_selected(wb: Workbook) -> None:
    """The one persona picker. Other tabs follow SelectedPersona."""
    ws = wb.create_sheet("Selected persona")
    ws.sheet_properties.tabColor = GOLD
    _add_selector(
        ws,
        master=True,
        title="Selected persona — pick one id here. Every calculation tab follows this cell.",
    )
    _legend(ws, "F", 2)
    _name(wb, "SelectedPersona", "'Selected persona'!$B$2")

    r = 4
    r = _section(ws, r, "A · ABOUT YOU  —  from the Personas row (edit there)", input_hdr)
    r = _kv(ws, r, "name", f"={_px('B')}", "A", "Personas B.")
    r = _kv(ws, r, "age", f"={_px('C')}", "A", "Personas C.", "0")
    r = _kv(ws, r, "gender", f"={_px('D')}", "A", "Personas D.")
    r = _kv(ws, r, "residency", f"={_px('E')}", "A", "Personas E.")
    r = _kv(ws, r, "country", f"={_px('F')}", "A", "Personas F. CPF on/off uses this.")
    r = _kv(ws, r, "occupation", f"={_px('G')}", "A", "Personas G. Income clamp band.")
    r = _kv(ws, r, "dependents", f"={_px('H')}", "A", "Personas H.", "0")
    r = _kv(ws, r, "maritalStatus", f"={_px('I')}", "A", "Personas I. Blank = infer on People Like You.")
    r = _kv(ws, r, "what this row varies", f"={_px('AD')}", "A", "Personas AD. Why this persona exists.")

    r += 1
    r = _section(ws, r, "B · LLM PREDICTED  —  from the Personas row (edit there)", llm_hdr)
    r = _kv(ws, r, "incomeMonthly (LLM)", f"={_px('J')}", "B", "Personas J. Before clamp and CPF.", "#,##0.00")
    r = _kv(ws, r, "currency", f"={_px('K')}", "B", "Personas K. FX looks this up.")
    r = _kv(ws, r, "risk ability", f"={_px('L')}", "B", "Personas L.")
    r = _kv(ws, r, "price sensitivity", f"={_px('M')}", "B", "Personas M.")
    r = _kv(ws, r, "owns property", f"={_px('N')}", "B", "Personas N.")
    r = _kv(ws, r, "owns car", f"={_px('O')}", "B", "Personas O.")
    r = _kv(ws, r, "is smoker", f"={_px('U')}", "B", "Personas U.")
    r = _kv(ws, r, "life expectancy", f"={_px('V')}", "B", "Personas V.", "0")
    r = _kv(ws, r, "retirement lifestyle", f"={_px('T')}", "B", "Personas T.")

    r += 1
    r = _section(ws, r, "C · EFFECTIVE SESSION  —  after CPF, People Like You, and Money-page overrides", calc_hdr)
    r = _kv(ws, r, "CPF on", "=CPF_on", "C", "From the CPF tab.")
    r = _kv(ws, r, "incomeMonthly", "=PLU_incomeMonthly", "C", "Clamped LLM income.", "#,##0.00")
    r = _kv(ws, r, "take-home", "=PLU_takeHome", "C", "Gross minus employee CPF when CPF is on.", "#,##0.00")
    r = _kv(ws, r, "expenseMonthly", "=PLU_expenseMonthly", "C", "Override if Personas W is set.", "#,##0.00")
    r = _kv(ws, r, "cash", "=PLU_cash", "C", "Cash & Savings.", "#,##0")
    r = _kv(ws, r, "investments", "=PLU_investments", "C", "", "#,##0")
    r = _kv(ws, r, "property", "=PLU_property", "C", "0 if renter.", "#,##0")
    r = _kv(ws, r, "mortgage", "=PLU_mortgage", "C", "", "#,##0")
    r = _kv(ws, r, "PLU liabilities", "=PLU_liabilities", "C", "Not the mortgage.", "#,##0.00")
    r = _kv(ws, r, "life sum assured", "=PLU_lifeSum", "C", "", "#,##0")

    _dash_widths(ws)
    ws.column_dimensions["F"].width = 42


def build_cpf(wb: Workbook) -> None:
    ws = wb.create_sheet("CPF")
    ws.sheet_properties.tabColor = "C45C26"
    _add_selector(
        ws,
        master=False,
        title="CPF — social-security plug-in. In: gross, age, residency, country. Out: employee contribution, take-home. Runs in user currency.",
    )
    _legend(ws, "F", 2)

    # Country on/off table (right of the form)
    _fill(ws, "I4", "D · MODULE PER COUNTRY  —  TRUE = SG-CPF module; FALSE = default module (no contribution)", font=h_font, fill=assume_hdr, align=center)
    ws.merge_cells("I4:K4")
    _fill(ws, "I5", "country", font=h_font, fill=header_fill, align=center)
    _fill(ws, "J5", "CPF on?", font=h_font, fill=header_fill, align=center)
    _fill(ws, "K5", "note", font=h_font, fill=header_fill, align=center)
    countries = [
        ("Singapore", True, "src/cpf.py applies. Citizen / PR contribute; Foreigner rate 0."),
        ("Vietnam", False, "No CPF. Take-home = gross."),
        ("Malaysia", False, "No CPF. Take-home = gross."),
        ("Thailand", False, "No CPF. Take-home = gross."),
        ("Philippines", False, "No CPF. Take-home = gross."),
        ("Australia", False, "No CPF. Take-home = gross."),
        ("Germany", False, "No CPF. Take-home = gross."),
        ("Hong Kong", False, "No CPF. Take-home = gross."),
        ("United States", False, "No CPF. Take-home = gross."),
    ]
    yn = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=False)
    ws.add_data_validation(yn)
    for i, (name, on, note) in enumerate(countries):
        rr = 6 + i
        _fill(ws, f"I{rr}", name, fill=assume_fill, align=center)
        _fill(ws, f"J{rr}", on, fill=input_fill, align=center)
        _fill(ws, f"K{rr}", note, font=note_font, fill=paper_fill)
    yn.add(f"J6:J{5 + len(countries)}")
    _name(wb, "CpfCountrySwitch", f"CPF!$I$6:$J${5 + len(countries)}")

    r = 4
    r = _section(ws, r, "A · INPUT DATA  —  from the selected Personas row", input_hdr)
    r = _kv(ws, r, "country", f"={_px('F')}", "A", "Personas F. Looks up the country switch.")
    ctry = r - 1
    r = _kv(ws, r, "residency", f"={_px('E')}", "A", "Personas E. When CPF is on, Foreigner → rate 0.")
    res = r - 1
    r = _kv(ws, r, "age", f"={_px('C')}", "A", "Personas C. Age-band rate when CPF is on.", "0")
    age = r - 1
    r = _kv(ws, r, "incomeMonthly", f"={_px('J')}", "A", "Personas J (LLM or user overwrite).", "#,##0.00")
    inc = r - 1

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS  —  src/cpf.py (used only when CPF is on)", assume_hdr)
    r = _kv(ws, r, "OW_CEILING", OW_CEILING, "D", "Ordinary-wage ceiling. Employee CPF is on min(gross, this).", "#,##0")
    _name(wb, "OW_CEILING", f"CPF!$B${r - 1}")
    r = _kv(ws, r, "cpfRate_to55", 0.20, "D", "Employee rate age ≤ 55.", "0.0%")
    _name(wb, "cpfRate_to55", f"CPF!$B${r - 1}")
    r = _kv(ws, r, "cpfRate_to60", 0.18, "D", "Age 56–60.", "0.0%")
    _name(wb, "cpfRate_to60", f"CPF!$B${r - 1}")
    r = _kv(ws, r, "cpfRate_to65", 0.125, "D", "Age 61–65.", "0.0%")
    _name(wb, "cpfRate_to65", f"CPF!$B${r - 1}")
    r = _kv(ws, r, "cpfRate_to70", 0.075, "D", "Age 66–70.", "0.0%")
    _name(wb, "cpfRate_to70", f"CPF!$B${r - 1}")
    r = _kv(ws, r, "cpfRate_over70", 0.05, "D", "Age > 70.", "0.0%")
    _name(wb, "cpfRate_over70", f"CPF!$B${r - 1}")

    r += 1
    r = _section(ws, r, "E · OVERRIDE  —  blank = country switch. TRUE / FALSE forces CPF on or off", override_hdr)
    r = _kv(ws, r, "CPF on? (override)", "", "O", "TRUE / FALSE / blank. Blank uses the country table.")
    ov = r - 1
    ov_dv = DataValidation(type="list", formula1='"TRUE,FALSE,"', allow_blank=True)
    ws.add_data_validation(ov_dv)
    ov_dv.add(f"B{ov}")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  src/cpf.py when on; identity when off", calc_hdr)
    r = _kv(
        ws, r, "CPF on (effective)",
        f'=IF(B{ov}="",IFERROR(VLOOKUP(B{ctry},CpfCountrySwitch,2,FALSE),FALSE),B{ov})',
        "C", "Country table, unless the orange override is set.",
    )
    on = r - 1
    r = _kv(
        ws, r, "module used",
        f'=IF(B{on}=TRUE,"SG-CPF (src/cpf.py)","default: no contribution, take-home = gross")',
        "C", "Plug-in interface. Other countries get their own module later; the rest of the model does not change.",
    )
    r = _kv(
        ws, r, "Singapore age-band rate",
        f'=IF(LOWER(B{res})="foreigner",0,IF(B{age}<=55,cpfRate_to55,IF(B{age}<=60,cpfRate_to60,IF(B{age}<=65,cpfRate_to65,IF(B{age}<=70,cpfRate_to70,cpfRate_over70)))))',
        "C", "employee_cpf_rate. Ignored when CPF is off.",
        "0.0%",
    )
    sg_rate = r - 1
    r = _kv(
        ws, r, "CPF rate used",
        f"=IF(B{on}=TRUE,B{sg_rate},0)",
        "C", "0 when CPF is off for this country.",
        "0.0%",
    )
    rate = r - 1
    r = _kv(
        ws, r, "employee CPF",
        f"=IF(OR(B{on}<>TRUE,B{inc}<=0,B{rate}<=0),0,FLOOR(MIN(B{inc},OW_CEILING)*B{rate},1))",
        "C", "floor(min(gross, ceiling) × rate). 0 if CPF off.",
        "#,##0",
    )
    cpf = r - 1
    r = _kv(
        ws, r, "take-home",
        f"=IF(B{inc}<=0,0,ROUND(MAX(0,B{inc}-B{cpf}),2))",
        "C", "Gross minus employee CPF. Equals income when CPF is off.",
        "#,##0.00",
    )
    take = r - 1

    _bind(wb, "CPF", {
        "CPF_on": on,
        "CPF_rate": rate,
        "CPF_employee": cpf,
        "CPF_takeHome": take,
        "CPF_income": inc,
    })
    _dash_widths(ws)
    _widths(ws, {"F": 42, "I": 16, "J": 12, "K": 56})


def build_plu(wb: Workbook) -> None:
    ws = wb.create_sheet("People Like You")
    ws.sheet_properties.tabColor = "2E7D4F"
    _add_selector(
        ws,
        master=False,
        title="People Like You — selected persona. Spend, assets, home, life cover. Take-home comes from the CPF tab.",
    )
    _legend(ws, "F", 2)

    r = 4
    r = _section(ws, r, "A · INPUT DATA  —  About you from the selected Personas row", input_hdr)
    r = _kv(ws, r, "age", f"={_px('C')}", "A", "Personas C. Working years = age − 21.", "0")
    age = r - 1
    r = _kv(ws, r, "gender", f"={_px('D')}", "A", "Personas D. Not used by this component.")
    r = _kv(ws, r, "residency", f"={_px('E')}", "A", "Personas E. Passed to the CPF tab (Foreigner → 0 when CPF is on).")
    r = _kv(ws, r, "country", f"={_px('F')}", "A", "Personas F. CPF on/off is decided on the CPF tab.")
    r = _kv(ws, r, "occupation", f"={_px('G')}", "A", "Personas G. Looks up income_anchors.json Singapore band.", None)
    occ = r - 1
    r = _kv(ws, r, "dependents", f"={_px('H')}", "A", "Personas H. Spend-share +5 pp each; 5× income life cover if > 0.", "0")
    deps = r - 1
    r = _kv(ws, r, "maritalStatus (typed)", f"={_px('I')}", "A", "Personas I. Blank → infer below.", None)

    r += 1
    r = _section(ws, r, "B · LLM PREDICTED DATA  —  fields this component reads from Personas", llm_hdr)
    r = _kv(ws, r, "income (LLM gross monthly)", f"={_px('J')}", "B", "Personas J. people_like_you_all_fields.json income.", "#,##0")
    inc = r - 1
    r = _kv(ws, r, "currency", f"={_px('K')}", "B", "Personas K. SGD in this workbook.")
    r = _kv(ws, r, "property (owns home)", f"={_px('N')}", "B", "Personas N. seed_property_value if TRUE.", None)
    owns = r - 1
    r = _kv(ws, r, "life_expectancy (raw)", f"={_px('V')}", "B", "Personas V. Capped at 99. Missing or ≤ 0 → 85.", "0")
    le_raw = r - 1

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA  —  named cells on Assumptions (CPF is on the CPF tab)", assume_hdr)
    r = _kv(ws, r, "spendShareBase", "=spendShareBase", "D", "67.5% of take-home.", "0.0%")
    r = _kv(ws, r, "spendSharePerDependant", "=spendSharePerDependant", "D", "+5 pp per dependant.", "0.0%")
    r = _kv(ws, r, "spendShareCap", "=spendShareCap", "D", "90% cap.", "0.0%")
    r = _kv(ws, r, "assetsSaveShare", "=assetsSaveShare", "D", "50% of annual surplus saved.", "0.0%")
    r = _kv(ws, r, "workStartAge", "=workStartAge", "D", "21. Working years = max(0, age − 21).", "0")
    r = _kv(ws, r, "CASH_SAVINGS_SHARE", "=CASH_SAVINGS_SHARE", "D", "src/predict.py 15% cash.", "0.0%")
    r = _kv(ws, r, "INVESTMENTS_SHARE", "=INVESTMENTS_SHARE", "D", "src/predict.py 85%.", "0.0%")
    r = _kv(ws, r, "liabilityRatio", "=liabilityRatio", "D", "PLU liabilities = liquid assets × 0.7 (not the mortgage).", "0.0%")
    r = _kv(ws, r, "propertyLow (USD)", "=propertyLow", "D", "income < propertyIncomeLow (USD).", "#,##0")
    r = _kv(ws, r, "propertyMid (USD)", "=propertyMid", "D", "income between the two USD bands.", "#,##0")
    r = _kv(ws, r, "propertyHigh (USD)", "=propertyHigh", "D", "income > propertyIncomeHigh (USD).", "#,##0")
    r = _kv(ws, r, "propertyIncomeLow (USD)", "=propertyIncomeLow", "D", "Monthly gross income in USD.", "#,##0")
    r = _kv(ws, r, "propertyIncomeHigh (USD)", "=propertyIncomeHigh", "D", "Monthly gross income in USD.", "#,##0")
    r = _kv(ws, r, "PROPERTY_LTV", "=PROPERTY_LTV", "D", "Mortgage = round(property × 55%).", "0.0%")
    r = _kv(ws, r, "lifePremiumRate", "=lifePremiumRate", "D", "0.31% of sum assured.", "0.00%")
    r = _kv(ws, r, "life cover step (user currency)", "=FX_lifeRound", "D", "lifeRoundUnit (USD) as a nice step in user currency (FX tab).", "#,##0")
    r = _kv(ws, r, "lifeExpectancyDefault", "=lifeExpectancyDefault", "D", "Used when raw LE is missing or ≤ 0.", "0")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  _apply_plu. Take-home is read from the CPF tab.", calc_hdr)
    r = _kv(
        ws, r, "band min",
        f'=IFERROR(INDEX(Assumptions!$K$6:$K$13,MATCH(B{occ},Assumptions!$J$6:$J$13,0)),"")',
        "C", "income_anchors.json Singapore min for occupation.", "#,##0",
    )
    bmin = r - 1
    r = _kv(
        ws, r, "band max",
        f'=IFERROR(INDEX(Assumptions!$L$6:$L$13,MATCH(B{occ},Assumptions!$J$6:$J$13,0)),"")',
        "C", "income_anchors.json Singapore max.", "#,##0",
    )
    bmax = r - 1
    r = _kv(
        ws, r, "incomeMonthly (clamped)",
        f'=IF(OR(B{bmin}="",B{inc}=0),B{inc},MIN(MAX(B{inc},B{bmin}),B{bmax}))',
        "C", "Clamp LLM income into the occupation band. 0 stays 0.", "#,##0.00",
    )
    income = r - 1
    r = _kv(ws, r, "CPF on (from CPF tab)", "=CPF_on", "A", "Country switch or orange override on the CPF tab.")
    r = _kv(ws, r, "CPF rate", "=CPF_rate", "C", "0 when CPF is off for this country.", "0.0%")
    rate = r - 1
    r = _kv(ws, r, "employee CPF", "=CPF_employee", "C", "0 when CPF is off.", "#,##0")
    cpf = r - 1
    r = _kv(ws, r, "take-home", "=CPF_takeHome", "C", "Gross minus employee CPF. Equals income when CPF is off.", "#,##0.00")
    take = r - 1
    r = _kv(
        ws, r, "spend share",
        f"=MIN(spendShareBase+spendSharePerDependant*MAX(0,B{deps}),spendShareCap)",
        "C", "min(67.5% + 5pp × dependents, 90%).", "0.0%",
    )
    share = r - 1
    r = _kv(
        ws, r, "expenseMonthly",
        f"=IF(B{take}<=0,0,ROUND(B{take}*B{share},2))",
        "C", "expenses_from_gross / spend of take-home.", "#,##0.00",
    )
    exp = r - 1
    r = _kv(ws, r, "surplus / mo", f"=B{take}-B{exp}", "C", "take-home − expense.", "#,##0.00")
    surplus = r - 1
    r = _kv(ws, r, "working years", f"=MAX(0,B{age}-workStartAge)", "C", "max(0, age − 21).", "0")
    years = r - 1
    r = _kv(
        ws, r, "liquid assets",
        f"=IF(AND(B{inc}>0,B{exp}>0,B{age}>workStartAge),MAX(0,B{surplus}*12*assetsSaveShare*B{years}),0)",
        "C", "surplus × 12 × 0.5 × working years.", "#,##0.00",
    )
    liq = r - 1
    r = _kv(ws, r, "PLU liabilities", f"=B{liq}*liabilityRatio", "C", "liquid × 0.7. Not the mortgage.", "#,##0.00")
    liab = r - 1
    r = _kv(ws, r, "cash (15%)", "=" + _round_even(f"B{liq}*CASH_SAVINGS_SHARE"), "C",
            "CASH_SAVINGS_SHARE. Python round (half to even).", "#,##0")
    cash = r - 1
    r = _kv(ws, r, "investments (85%)", "=" + _round_even(f"B{liq}*INVESTMENTS_SHARE"), "C",
            "INVESTMENTS_SHARE. Python round (half to even).", "#,##0")
    inv = r - 1
    r = _kv(ws, r, "income USD (home seed)", f"=B{inc}*FX_usdPerLocal", "C", "System currency: user currency × USD per 1.", "#,##0.00")
    inc_usd = r - 1
    r = _kv(
        ws, r, "property USD",
        f'=IF(B{owns}=FALSE,0,IF(B{inc_usd}<propertyIncomeLow*FX_priceLevel,propertyLow,'
        f'IF(B{inc_usd}<=propertyIncomeHigh*FX_priceLevel,propertyMid,propertyHigh))*FX_priceLevel)',
        "C", "seed_property_value on USD bands.", "#,##0.00",
    )
    prop_usd = r - 1
    r = _kv(
        ws, r, "property",
        f"=ROUND(B{prop_usd}/FX_usdPerLocal,0)",
        "C", "Back to user currency.", "#,##0",
    )
    prop = r - 1
    r = _kv(ws, r, "mortgage", f"=IF(B{prop}=0,0,{_round_even(f'B{prop}*PROPERTY_LTV')})", "C", "round(property × 55%).", "#,##0")
    mort = r - 1
    r = _kv(
        ws, r, "life sum assured",
        f"=MAX(IF(B{prop}>0,INT((B{mort}+FX_lifeRound/2)/FX_lifeRound)*FX_lifeRound,0),"
        f"IF(B{deps}>0,{_round_even(f'B{inc}*12*5')},0))",
        "C", "_assumed_life_policy: max(mortgage rounded to the life cover step, 5 × annual income if dependents).", "#,##0",
    )
    life = r - 1
    r = _kv(
        ws, r, "life premium",
        f"=IF(B{life}<=0,0,{_round_even(f'B{life}*lifePremiumRate')})",
        "C", "round(sum × 0.31%), half to even like Python (790.5 → 790).", "#,##0",
    )
    prem = r - 1
    r = _kv(
        ws, r, "lifeExpectancy used",
        f"=MIN(LON_AGE,IF(B{le_raw}>0,B{le_raw},lifeExpectancyDefault))",
        "C", "min(raw, 99). Missing or ≤ 0 → 85.", "0",
    )
    le = r - 1
    r = _kv(
        ws, r, "marital (inferred)",
        f'=IF({_px("I")}<>"",LOWER({_px("I")}),IF(B{age}<30,"single","married"))',
        "C", "Typed maritalStatus, else age < 30 → single.", None,
    )
    marital = r - 1

    r += 1
    r = _section(
        ws, r,
        "E · USER / FRONTEND OVERRIDE  —  Personas W–AC (Money page). Blank keeps the green calculated value.",
        override_hdr,
    )
    r = _kv(ws, r, "override expenseMonthly", f"={_px('W')}", "O", "Money page spend. Floor is MIN_EXPENSE_MONTHLY (USD 100) in user currency.", "#,##0.00")
    r = _kv(ws, r, "override cash", f"={_px('X')}", "O", "Cash & Savings. Provenance key cash / savings.", "#,##0")
    r = _kv(ws, r, "override investments", f"={_px('Y')}", "O", "Investments.", "#,##0")
    r = _kv(ws, r, "override property value", f"={_px('Z')}", "O", "Home value. Distinct from owns-home flag N.", "#,##0")
    r = _kv(ws, r, "override mortgage", f"={_px('AA')}", "O", "Money page loans.", "#,##0")
    r = _kv(ws, r, "override PLU liabilities", f"={_px('AB')}", "O", "Need Profiler TotalLiabilities. Not the mortgage.", "#,##0.00")
    r = _kv(ws, r, "override life sum assured", f"={_px('AC')}", "O", "Existing Life Protection cover.", "#,##0")

    r += 1
    r = _section(
        ws, r,
        "C · EFFECTIVE SESSION  —  override if set, else calculated. Downstream and Validation read these.",
        calc_hdr,
    )
    r = _kv(
        ws, r, "incomeMonthly",
        f"=B{inc}",
        "C", "Personas J (LLM or user). The clamp row above is what /predict would force.",
        "#,##0.00",
    )
    eff_inc = r - 1
    r = _kv(ws, r, "expenseMonthly", f'=MAX(ROUND(MIN_EXPENSE_MONTHLY/FX_usdPerLocal,2),IF({_px("W")}="",B{exp},{_px("W")}))', "C",
            "Floor: MIN_EXPENSE_MONTHLY (USD 100) in user currency.", "#,##0.00")
    eff_exp = r - 1
    r = _kv(ws, r, "take-home", f"=B{take}", "C", "From Personas J and CPF.", "#,##0.00")
    eff_take = r - 1
    r = _kv(ws, r, "surplus / mo", f"=B{eff_take}-B{eff_exp}", "C", "", "#,##0.00")
    r = _kv(ws, r, "cash", f'=IF({_px("X")}="",B{cash},{_px("X")})', "C", "", "#,##0")
    eff_cash = r - 1
    r = _kv(ws, r, "investments", f'=IF({_px("Y")}="",B{inv},{_px("Y")})', "C", "", "#,##0")
    eff_inv = r - 1
    r = _kv(ws, r, "liquid assets", f"=B{eff_cash}+B{eff_inv}", "C", "cash + investments.", "#,##0")
    r = _kv(ws, r, "property", f'=IF({_px("Z")}="",B{prop},{_px("Z")})', "C", "", "#,##0")
    eff_prop = r - 1
    r = _kv(ws, r, "mortgage", f'=IF({_px("AA")}="",B{mort},{_px("AA")})', "C", "", "#,##0")
    eff_mort = r - 1
    r = _kv(ws, r, "PLU liabilities", f'=IF({_px("AB")}="",B{liab},{_px("AB")})', "C", "", "#,##0.00")
    eff_liab = r - 1
    r = _kv(ws, r, "life sum assured", f'=IF({_px("AC")}="",B{life},{_px("AC")})', "C", "", "#,##0")
    eff_life = r - 1
    r = _kv(
        ws, r, "life premium",
        f"=IF(B{eff_life}<=0,0,{_round_even(f'B{eff_life}*lifePremiumRate')})",
        "C", "Recomputed from effective sum.",
        "#,##0",
    )
    eff_prem = r - 1
    r = _kv(ws, r, "currency", f"={_px('K')}", "B", "Personas K. FX converts with this ISO code.")
    eff_ccy = r - 1

    _bind(wb, "People Like You", {
        "PLU_age": age,
        "PLU_incomeMonthly": eff_inc,
        "PLU_takeHome": eff_take,
        "PLU_expenseMonthly": eff_exp,
        "PLU_surplus": surplus,
        "PLU_liabilities": eff_liab,
        "PLU_cash": eff_cash,
        "PLU_investments": eff_inv,
        "PLU_property": eff_prop,
        "PLU_mortgage": eff_mort,
        "PLU_lifeSum": eff_life,
        "PLU_lifePrem": eff_prem,
        "PLU_leUsed": le,
        "PLU_marital": marital,
        "PLU_dependents": deps,
        "PLU_ownsProperty": owns,
        "PLU_currency": eff_ccy,
    })
    _dash_widths(ws)
    ws.column_dimensions["F"].width = 42


def build_profiler(wb: Workbook) -> None:
    ws = wb.create_sheet("Need Profiler")
    ws.sheet_properties.tabColor = "6B3FA0"
    _add_selector(
        ws,
        master=False,
        title="Need Profiler — selected persona. Weighted scores → two protection + N_RET + one growth. Parked coverage needs are scored only.",
    )
    _legend(ws, "F", 2)

    r = 4
    r = _section(ws, r, "A · INPUT DATA  —  from selected Personas + People Like You results", input_hdr)
    r = _kv(ws, r, "age", f"={_px('C')}", "A", "Personas C. Bucket <21 / ≤30 / ≤40 / else.", "0")
    age = r - 1
    r = _kv(ws, r, "gender", f"={_px('D')}", "A", "Personas D. male=3, female=2.", None)
    gen = r - 1
    r = _kv(ws, r, "dependents", f"={_px('H')}", "A", "Personas H. 0 / 1 / ≥2 → 0 / 2 / 4.", "0")
    deps = r - 1
    r = _kv(ws, r, "occupation", f"={_px('G')}", "A", "Personas G. Self-employed tokens → 2, else 1.")
    occ = r - 1
    r = _kv(ws, r, "incomeMonthly (from PLU)", "=PLU_incomeMonthly", "A", "People Like You calculated income, used as profiler Income.", "#,##0.00")
    r = _kv(ws, r, "expenseMonthly (from PLU)", "=PLU_expenseMonthly", "A", "People Like You calculated spend.", "#,##0.00")
    r = _kv(ws, r, "liquid assets (from PLU)", "=PLU_cash+PLU_investments", "A", "cash + investments.", "#,##0")
    r = _kv(ws, r, "PLU liabilities (from PLU)", "=PLU_liabilities", "A", "Not the mortgage.", "#,##0.00")

    r += 1
    r = _section(ws, r, "B · LLM PREDICTED DATA  —  lifestyle flags this component reads", llm_hdr)
    r = _kv(ws, r, "is_smoker", f"={_px('U')}", "B", "Personas U. TRUE→3, else 1 (JSON has no Smoking options).")
    smoke = r - 1
    r = _kv(ws, r, "hospitalization_type", f"={_px('Q')}", "B", "Personas Q. private=4, public=2.")
    hosp = r - 1
    r = _kv(ws, r, "ward_type", f"={_px('P')}", "B", "Personas P. A=3, B=2. Single/Double/Ward score 0.")
    ward = r - 1
    r = _kv(ws, r, "retirement_lifestyle", f"={_px('T')}", "B", "Personas T. frugal / stress-free / only the best.")
    life = r - 1
    r = _kv(ws, r, "sports", f"={_px('S')}", "B", "Personas S. Adventurous / I dont do sports / Life style.")
    sports = r - 1
    r = _kv(ws, r, "property (owns home)", f"={_px('N')}", "B", "Personas N. V0-16: no longer swaps N_SAV / N_PRP (not used for selection).")
    owns = r - 1

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA  —  used by this component", assume_hdr)
    r = _kv(ws, r, "Existing hospital cover", 0, "D", "build_profiler_profile hard-codes Existing*Coverage = False → option weight 1.")
    r = _kv(ws, r, "Existing disability cover", 0, "D", "Same. Stored as 0 here; option weight of False is 1.")
    r = _kv(ws, r, "PPP-USD per 1 local (market ÷ price level)", "=FX_pppUsdPerLocal", "D", "From the FX tab. Income / expense / assets / liabilities convert local × this rate (equals the market rate for the base country).", "0.000000")
    r = _kv(ws, r, "Selection rule", "2 prot + N_RET + 1 growth", "D", "V0-16: protection from N_INC/N_CRI/N_TPD/N_HOS/N_PAC; growth N_EDU vs N_SAV. N_PRP is never auto-picked (no profiler label).")
    r = _kv(ws, r, "Profiler weight matrix", "Assumptions!B90:L104", "D", "Need_profiler.json needs_factor_weights. SUMPRODUCT with option weights.")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  local × FX → USD, then 15 option weights", calc_hdr)
    r = _kv(ws, r, "usd Income", "=IF(FX_usdPerLocal=\"\",\"\",PLU_incomeMonthly*FX_pppUsdPerLocal)", "C", "local income × PPP-USD rate (market USD ÷ price level, V0-22). Singapore = market USD.", "0.00")
    usd_inc = r - 1
    r = _kv(ws, r, "usd Expense", "=IF(FX_usdPerLocal=\"\",\"\",PLU_expenseMonthly*FX_pppUsdPerLocal)", "C", "local expense × FX.", "0.00")
    usd_exp = r - 1
    r = _kv(ws, r, "usd Assets", "=IF(FX_usdPerLocal=\"\",\"\",(PLU_cash+PLU_investments)*FX_pppUsdPerLocal)", "C", "cash + investments × FX.", "0.00")
    usd_ast = r - 1
    r = _kv(ws, r, "usd Liab", "=IF(FX_usdPerLocal=\"\",\"\",PLU_liabilities*FX_pppUsdPerLocal)", "C", "PLU liabilities × FX.", "0.00")
    usd_liab = r - 1
    r = _kv(
        ws, r, "ow Age",
        f"=IF(B{age}<21,1,IF(B{age}<=30,2,IF(B{age}<=40,3,4)))",
        "C", "_get_option_weight Date of Birth.", "0",
    )
    ow0 = r - 1
    r = _kv(ws, r, "ow Gender", f'=IF(LOWER(B{gen})="male",3,IF(LOWER(B{gen})="female",2,0))', "C", "male=3, female=2.", "0")
    r = _kv(ws, r, "ow Deps", f"=IF(B{deps}=0,0,IF(B{deps}=1,2,4))", "C", "0 / 1 / else.", "0")
    r = _kv(
        ws, r, "ow Occ",
        f'=IF(OR(ISNUMBER(SEARCH("self",B{occ})),ISNUMBER(SEARCH("entrepreneur",B{occ})),ISNUMBER(SEARCH("own business",B{occ})),ISNUMBER(SEARCH("freelance",B{occ}))),2,1)',
        "C", "Self-employed tokens.", "0",
    )
    r = _kv(ws, r, "ow Smoke", f"=IF(B{smoke}=TRUE,3,1)", "C", "No Smoking options in JSON.", "0")
    r = _kv(
        ws, r, "ow Income",
        f"=IF(B{usd_inc}<1000,4,IF(B{usd_inc}<2500,3,IF(B{usd_inc}<5000,2,IF(B{usd_inc}<10000,1,0))))",
        "C", "Need_profiler.json Income lt bands (USD after FX).", "0",
    )
    r = _kv(
        ws, r, "ow Expense",
        f"=IF(B{usd_exp}<600,4,IF(B{usd_exp}<1500,3,IF(B{usd_exp}<3000,2,IF(B{usd_exp}<6000,1,0))))",
        "C", "Expense USD bands (~0.6× income).", "0",
    )
    r = _kv(
        ws, r, "ow Assets",
        f"=IF(B{usd_ast}<10000,4,IF(B{usd_ast}<50000,3,IF(B{usd_ast}<150000,2,IF(B{usd_ast}<500000,1,0))))",
        "C", "Assets USD bands (stock).", "0",
    )
    r = _kv(
        ws, r, "ow Liab",
        f"=IF(B{usd_liab}<5000,4,IF(B{usd_liab}<25000,3,IF(B{usd_liab}<100000,2,IF(B{usd_liab}<250000,1,0))))",
        "C", "Liabilities USD bands (stock).", "0",
    )
    r = _kv(ws, r, "ow HospExist", 1, "C", "Existing hospital coverage always False → 1.", "0")
    r = _kv(ws, r, "ow DisExist", 1, "C", "Existing disability coverage always False → 1.", "0")
    r = _kv(ws, r, "ow HospType", f'=IF(LOWER(B{hosp})="private",4,IF(LOWER(B{hosp})="public",2,0))', "C", "Hospital Type.", "0")
    r = _kv(ws, r, "ow Ward", f'=IF(OR(UPPER(B{ward})="A",UPPER(B{ward})="SINGLE"),3,IF(OR(UPPER(B{ward})="B",UPPER(B{ward})="DOUBLE",UPPER(B{ward})="WARD"),2,0))',
            "C", "V0-24 map: Single → A (3); Double / Ward → B (2, shared room).", "0")
    r = _kv(
        ws, r, "ow Lifestyle",
        f'=IF(OR(LOWER(B{life})="frugal",LOWER(B{life})="basic"),1,IF(OR(LOWER(B{life})="stress-free",LOWER(B{life})="stress free",LOWER(B{life})="comfortable"),2,IF(OR(LOWER(B{life})="only the best",LOWER(B{life})="luxurious"),4,0)))',
        "C", "V0-24 map: Basic → frugal (1), Comfortable → stress-free (2), Luxurious → only the best (4).", "0",
    )
    r = _kv(
        ws, r, "ow Sports",
        f'=IF(OR(ISNUMBER(SEARCH("adventur",B{sports})),ISNUMBER(SEARCH("diving",B{sports})),ISNUMBER(SEARCH("climb",B{sports})),ISNUMBER(SEARCH("ski",B{sports})),ISNUMBER(SEARCH("surf",B{sports})),ISNUMBER(SEARCH("martial",B{sports})),ISNUMBER(SEARCH("rugby",B{sports})),ISNUMBER(SEARCH("motor",B{sports})),ISNUMBER(SEARCH("extreme",B{sports})),ISNUMBER(SEARCH("parachut",B{sports})),ISNUMBER(SEARCH("boxing",B{sports}))),4,IF(OR(TRIM(B{sports})="",ISNUMBER(SEARCH("dont",B{sports})),ISNUMBER(SEARCH("no sport",B{sports})),LOWER(TRIM(B{sports}))="none"),0,1))',
        "C", "V0-24 map: adventurous / high-risk sports → Adventurous (4); none → 0; any other sport (running, yoga, golf, …) → Life style (1).", "0",
    )
    ow1 = r - 1
    ow_span = f"$B${ow0}:$B${ow1}"

    r += 1
    raw_rows = {}
    sc_rows = {}
    r = _section(ws, r, "C · RESULTS  —  raw Σ (factor × option), then min–max scale 0–10", calc_hdr)
    for i, lab in enumerate(WB_LABELS):
        src_col = get_column_letter(2 + i)
        r = _kv(
            ws, r, f"raw {SHOW.get(lab, lab)}",
            f"=ROUND(SUMPRODUCT({ow_span},Assumptions!{src_col}$90:{src_col}$104),2)",
            "C", f"Need_profiler.json column {lab}." + (" Shown as TPD." if lab in SHOW else ""), "0.00",
        )
        raw_rows[lab] = r - 1
    raw_first = raw_rows[WB_LABELS[0]]
    raw_last = raw_rows[WB_LABELS[-1]]
    r = _kv(ws, r, "min raw", f"=MIN(B{raw_first}:B{raw_last})", "C", "scale_scores min.", "0.00")
    mn = r - 1
    r = _kv(ws, r, "max raw", f"=MAX(B{raw_first}:B{raw_last})", "C", "If max=min, divisor is forced to 1 so every scaled value is 0.", "0.00")
    mx = r - 1
    for lab in WB_LABELS:
        r = _kv(
            ws, r, f"scaled {SHOW.get(lab, lab)}",
            f"=ROUND(((B{raw_rows[lab]}-B{mn})/IF(B{mx}>B{mn},B{mx}-B{mn},1))*10,1)",
            "C", "0–10, 1 decimal.", "0.0",
        )
        sc_rows[lab] = r - 1

    r += 1
    s_inc, s_cri, s_tpd, s_hos = (
        sc_rows["Life Protection"], sc_rows["Critical Illness"],
        sc_rows["Disability"], sc_rows["Hospitalization"],
    )
    s_edu, s_sav = sc_rows["Education"], sc_rows["General Savings"]
    s_pac = sc_rows["Personal Accident"]
    cand = [("N_INC", s_inc, "0.005", "Life Protection first in label order."),
            ("N_CRI", s_cri, "0.004", "Critical Illness second."),
            ("N_TPD", s_tpd, "0.003", "TPD third."),
            ("N_HOS", s_hos, "0.002", "Hospitalization fourth."),
            ("N_PAC", s_pac, "0.001", "Personal Accident last (V0-16).")]
    tb = {}
    for t, srow, bonus, note in cand:
        r = _kv(ws, r, f"tb {t}", f"=B{srow}+{bonus}", "C", "Tie-break bonus. " + note, "0.000")
        tb[t] = r - 1
    def pick(rows_):
        mx_ = "MAX(" + ",".join(f"B{rows_[t]}" for t, *_ in cand) + ")"
        expr = f'"{cand[-1][0]}"'
        for t, *_ in reversed(cand[:-1]):
            expr = f'IF(B{rows_[t]}={mx_},"{t}",{expr})'
        return "=" + expr
    r = _kv(ws, r, "prot1", pick(tb), "C", "Highest protection score after the order bonus.")
    prot1 = r - 1
    tb2 = {}
    for t, srow, bonus, _n in cand:
        r = _kv(ws, r, f"tb2 {t}", f'=IF(B{prot1}="{t}",-1,B{srow}+{bonus})', "C", "Winner of prot1 is excluded.", "0.000")
        tb2[t] = r - 1
    r = _kv(ws, r, "prot2", pick(tb2), "C", "Second protection.")
    prot2 = r - 1
    r = _kv(ws, r, "tb N_EDU", f"=B{s_edu}+0.002", "C", "Education first on a tie.", "0.000")
    tb_edu = r - 1
    r = _kv(ws, r, "tb N_SAV", f"=B{s_sav}+0.001", "C", "General Savings second.", "0.000")
    tb_sav = r - 1
    r = _kv(ws, r, "grow2", f'=IF(B{tb_edu}>=B{tb_sav},"N_EDU","N_SAV")', "C",
            "Second growth after forced N_RET. V0-16: N_EDU vs N_SAV only; no home-ownership swap; N_PRP never auto-picked.")
    grow2 = r - 1

    sc_for = {
        "N_INC": s_inc, "N_CRI": s_cri, "N_TPD": s_tpd, "N_HOS": s_hos, "N_PAC": s_pac, "N_LTC": None,
        "N_RET": sc_rows["Retirement"], "N_EDU": s_edu, "N_SAV": s_sav, "N_PRP": None,
    }
    r += 1
    r = _section(ws, r, "C · RESULTS  —  nine calculator needs, then three parked coverage needs (scored, no calculator)", calc_hdr)
    _fill(ws, f"A{r}", "type", font=h_font, fill=header_fill, align=center)
    _fill(ws, f"B{r}", "calc on", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"C{r}", "Enable?", font=h_font, fill=override_hdr, align=center)
    _fill(ws, f"D{r}", "on (effective)", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"E{r}", "priority", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"F{r}", "scaled score", font=h_font, fill=calc_hdr, align=center)
    r += 1
    dv = DataValidation(type="list", formula1='"TRUE,FALSE,"', allow_blank=True)
    ws.add_data_validation(dv)
    first_en = r
    on_rows = {}
    for t in UNIFIED_X:
        if t == "N_LTC":
            formula = "=FALSE()"
        elif t in PROT_X:
            formula = f'=OR($B${prot1}="{t}",$B${prot2}="{t}")'
        elif t == "N_RET":
            formula = "=TRUE()"
        elif t == "N_PRP":
            formula = "=FALSE()"
        else:
            formula = f'=$B${grow2}="{t}"'
        _fill(ws, f"A{r}", t, font=h_font, fill=calc_hdr, align=center)
        _fill(ws, f"B{r}", formula, fill=calc_fill, align=center)
        _fill(ws, f"C{r}", "", fill=override_fill, align=center)
        _fill(ws, f"D{r}", f'=IF(C{r}="",B{r},C{r})', fill=green_fill, align=center)
        _fill(ws, f"E{r}", f"=IF(B{sc_for[t]}>7,5,3)" if sc_for[t] else 3, fill=calc_fill, align=center)
        _fill(ws, f"F{r}", f"=B{sc_for[t]}" if sc_for[t] else "no label", fill=calc_fill, align=center, num="0.0")
        on_rows[t] = r
        r += 1
    dv.add(f"C{first_en}:C{r - 1}")
    park_rows = {}
    for t, lab in PARKED.items():
        _fill(ws, f"A{r}", t, font=h_font, fill=assume_hdr, align=center)
        _fill(ws, f"B{r}", "parked", fill=paper_fill, align=center)
        _fill(ws, f"C{r}", "", fill=paper_fill, align=center)
        _fill(ws, f"D{r}", "coverage need", fill=paper_fill, align=center)
        _fill(ws, f"E{r}", f"=IF(B{sc_rows[lab]}>7,5,3)", fill=calc_fill, align=center)
        _fill(ws, f"F{r}", f"=B{sc_rows[lab]}", fill=calc_fill, align=center, num="0.0")
        park_rows[t] = r
        r += 1
    _fill(ws, f"A{r}", "N_PRP (home purchase) and N_LTC (long-term care) are never switched on by the profiler: no label. Enable? = TRUE switches them on.",
          font=note_font, fill=paper_fill, border=False)

    _bind(wb, "Need Profiler", {"NP_prot1": prot1, "NP_prot2": prot2, "NP_grow2": grow2})
    for t, row in on_rows.items():
        _name(wb, f"NP_on_{t}", f"'Need Profiler'!$D${row}")
        _name(wb, f"NP_priority_{t}", f"'Need Profiler'!$E${row}")
    for t, row in park_rows.items():
        _name(wb, f"NP_priority_{t}", f"'Need Profiler'!$E${row}")
        _name(wb, f"NP_score_{t}", f"'Need Profiler'!$F${row}")
    _dash_widths(ws)
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["D"].width = 16


def _pv_annuity(pmt: str, rate: str, n: str) -> str:
    return (
        f'IF(OR(({n})<=0,({pmt})<=0),0,IF(ABS({rate})<1E-12,({pmt})*({n}),'
        f'({pmt})*(1-(1+{rate})^(-({n})))/({rate})))'
    )


def _pv_due(pmt: str, rate: str, n: str) -> str:
    return (
        f'IF(OR(({n})<=0,({pmt})<=0),0,IF(ABS({rate})<1E-12,({pmt})*({n}),'
        f'({pmt})*(1-(1/((1+{rate})))^({n}))/(1-(1/((1+{rate}))))))'
    )


def _fv(pv: str, rate: str, n: str) -> str:
    return f'IF(({n})<=0,MAX(0,{pv}),({pv})*(1+{rate})^({n}))'


def _fv_ann(pmt: str, rate: str, n: str) -> str:
    return (
        f'IF(OR(({n})<=0,({pmt})<=0),0,IF(ABS({rate})<1E-12,({pmt})*({n}),'
        f'({pmt})*((1+{rate})^({n})-1)/({rate})))'
    )


def build_need_calc(wb: Workbook) -> None:
    ws = wb.create_sheet("Need Calculator")
    ws.sheet_properties.tabColor = "C45C26"
    _add_selector(
        ws,
        master=False,
        title="Need Calculator — selected persona. Runs in USD (S-block), results back in user currency. Orange cells are goal-card sliders (user currency).",
    )
    _legend(ws, "F", 2)

    r = 4
    r = _section(ws, r, "A · INPUT DATA  —  from Personas, People Like You, and Need Profiler", input_hdr)
    r = _kv(ws, r, "age", f"={_px('C')}", "A", "Personas C.", "0")
    age = r - 1
    r = _kv(ws, r, "incomeMonthly (from PLU)", "=PLU_incomeMonthly", "A", "Clamped gross monthly.", "#,##0.00")
    r = _kv(ws, r, "expenseMonthly (from PLU)", "=PLU_expenseMonthly", "A", "Annual spend = this × 12.", "#,##0.00")
    r = _kv(ws, r, "mortgage (from PLU)", "=PLU_mortgage", "A", "Added to N_INC amount.", "#,##0")
    r = _kv(ws, r, "life sum (from PLU)", "=PLU_lifeSum", "A", "N_INC have.", "#,##0")
    r = _kv(ws, r, "investments (from PLU)", "=PLU_investments", "A", "Tagged wealth pot only. Cash is never allocated.", "#,##0")
    r = _kv(ws, r, "lifeExpectancy used (from PLU)", "=PLU_leUsed", "A", "yearsInRet = max(0, LE − retAge).", "0")

    r += 1
    r = _section(ws, r, "O · GOAL-CARD SLIDERS / OVERRIDES  —  orange. Blank years keep the age rule", override_hdr)
    r = _kv(ws, r, "lifestyle (1/2/3)", 2, "O", "1=frugal, 2=stress-free, 3=only the best. Default 2.", "0")
    life = r - 1
    r = _kv(ws, r, "retAge", "=ageOfRetirement", "O", "Default from Assumptions (65).", "0")
    ret = r - 1
    r = _kv(ws, r, "targetYear N_EDU", f"=currentYear+MAX(1,EDU_TARGET_AGE-B{age})", "O",
            "Default: the year the customer turns EDU_TARGET_AGE (50); next year if older.", "0")
    tgt = r - 1
    r = _kv(ws, r, "targetYear N_SAV", f"=currentYear+MAX(5,SAV_TARGET_AGE-B{age})", "O",
            "Default: the year the customer turns SAV_TARGET_AGE (40); never shorter than 5 years.", "0")
    tgt_sav = r - 1
    r = _kv(ws, r, "targetYear N_PRP", f"=currentYear+MAX(3,PRP_TARGET_AGE-B{age})", "O",
            "Default: the year the customer turns PRP_TARGET_AGE (33); never shorter than 3 years.", "0")
    tgt_prp = r - 1
    r = _kv(ws, r, "bequest", 0, "O", "Added to N_INC amount.", "#,##0")
    beq = r - 1
    r = _kv(ws, r, "dependYears (blank = age rule)", "", "O", "Blank or ≤0 → supportYears.", None)
    dep_y_cell = r - 1
    r = _kv(ws, r, "incomeReplace (blank = income)", "", "O", "Blank → incomeMonthly for CI / TPD.", "#,##0")
    inc_rep_cell = r - 1
    r = _kv(ws, r, "N_SAV stored", 0, "O", "If > 0, this is N_SAV amount; else 1× annual income.", "#,##0")
    sav_st = r - 1
    r = _kv(ws, r, "N_PRP stored", 0, "O", "If > 0, this is N_PRP amount; else 5× annual income.", "#,##0")
    prp_st = r - 1
    r = _kv(ws, r, "tag N_RET", 0, "O", "Investments tagged to retirement, then grown at realReturn.", "#,##0")
    tag_ret = r - 1
    r = _kv(ws, r, "tag N_EDU", 0, "O", "apply_investment_pot walk order: RET, EDU, SAV, PRP.", "#,##0")
    tag_edu = r - 1
    r = _kv(ws, r, "tag N_SAV", 0, "O", "Takes from remaining investments after RET and EDU.", "#,##0")
    tag_sav = r - 1
    r = _kv(ws, r, "tag N_PRP", 0, "O", "Last in the walk.", "#,##0")
    tag_prp = r - 1
    r = _kv(ws, r, "LTC start age", "=LTC_START_AGE", "O", "N_LTC front-end input. Default LTC_START_AGE (80).", "0")
    ltc_age = r - 1

    r += 1
    r = _section(ws, r, "S · SYSTEM CURRENCY (USD)  —  user-currency inputs × USD per 1. The calculator below runs on these", llm_hdr)
    r = _kv(ws, r, "USD per 1 user-currency unit", "=FX_usdPerLocal", "D", "FX tab. #N/A if the currency is unknown.", "0.000000")
    fx = r - 1
    r = _kv(ws, r, "price level (option B)", "=FX_priceLevel", "D", "1 under option A. Scales the USD fixed amounts.", "0.00")
    pl = r - 1
    usd_cells = {}
    for key, label, src in (
        ("inc", "incomeMonthly USD", "PLU_incomeMonthly"),
        ("exp", "expenseMonthly USD", "PLU_expenseMonthly"),
        ("mort", "mortgage USD", "PLU_mortgage"),
        ("life", "life sum USD", "PLU_lifeSum"),
        ("inv", "investments USD", "PLU_investments"),
        ("beq", "bequest USD", f"B{beq}"),
        ("sav", "N_SAV stored USD", f"B{sav_st}"),
        ("prp", "N_PRP stored USD", f"B{prp_st}"),
        ("tret", "tag N_RET USD", f"B{tag_ret}"),
        ("tedu", "tag N_EDU USD", f"B{tag_edu}"),
        ("tsav", "tag N_SAV USD", f"B{tag_sav}"),
        ("tprp", "tag N_PRP USD", f"B{tag_prp}"),
    ):
        r = _kv(ws, r, label, f"={src}*B{fx}", "C", "", "#,##0.00")
        usd_cells[key] = r - 1
    r = _kv(ws, r, "incomeReplace USD", f'=IF(B{inc_rep_cell}="","",B{inc_rep_cell}*B{fx})', "C", "Blank → income.", "#,##0.00")
    usd_cells["rep"] = r - 1
    r = _kv(ws, r, "CRI_COST USD (× price level)", f"=CRI_COST*B{pl}", "C", "Fixed amount, USD.", "#,##0")
    usd_cells["ci"] = r - 1
    r = _kv(ws, r, "TPD_COST USD (× price level)", f"=TPD_COST*B{pl}", "C", "Fixed amount, USD.", "#,##0")
    usd_cells["tpd"] = r - 1
    r = _kv(ws, r, "EDU_COST USD (× price level)", f"=EDU_COST*B{pl}", "C", "Fixed amount, USD.", "#,##0")
    usd_cells["edu"] = r - 1
    r = _kv(ws, r, "PAC_COST USD (× price level)", f"=PAC_COST*B{pl}", "C", "Fixed amount, USD.", "#,##0")
    usd_cells["pac"] = r - 1
    r = _kv(ws, r, "LTC_COST USD / year (× price level)", f"=LTC_COST*B{pl}", "C", "Fixed amount, USD a year.", "#,##0")
    usd_cells["ltc"] = r - 1
    U = {k: f"B{v}" for k, v in usd_cells.items()}

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA  —  rates and need parameters", assume_hdr)
    r = _kv(ws, r, "inflationRate", "=inflationRate", "D", "Grows EDU cost. N_RET grows at realReturn, not inflation.", "0.00%")
    r = _kv(ws, r, "investmentReturn", "=investmentReturn", "D", "Used to form realReturn.", "0.00%")
    r = _kv(ws, r, "realReturn", "=realReturn", "D", "max(0, (1+i)/(1+π) − 1). Discount rate.", "0.00%")
    r = _kv(ws, r, "RET_LIFESTYLE_FRUGAL", "=RET_LIFESTYLE_FRUGAL", "D", "N_RET spend multiple when lifestyle=1.", "0.0%")
    r = _kv(ws, r, "RET_LIFESTYLE_STRESSFREE", "=RET_LIFESTYLE_STRESSFREE", "D", "Default lifestyle=2.", "0.0%")
    r = _kv(ws, r, "RET_LIFESTYLE_ONLYTHEBEST", "=RET_LIFESTYLE_ONLYTHEBEST", "D", "lifestyle=3.", "0.0%")
    r = _kv(ws, r, "INC_SUPPORT_MIN / Max / Pivot", "=INC_SUPPORT_MIN", "D", "supportYears = min(max(10, 50 − age), 25).", "0")
    r = _kv(ws, r, "CRI_YEARS / CRI_COST", "=CRI_YEARS", "D", "3 years annuity-due + CRI_COST (USD, S-block).", "0")
    r = _kv(ws, r, "TPD_YEARS / TPD_COST", "=TPD_YEARS", "D", "5 years annuity-due + TPD_COST (USD, S-block).", "0")
    r = _kv(ws, r, "PAC_YEARS / PAC_COST", "=PAC_YEARS", "D", "1 year annuity-due + PAC_COST (USD, S-block). Agreed V0-18.", "0")
    r = _kv(ws, r, "HOS_MONTHS", "=HOS_MONTHS", "D", "N_HOS = income × 6.", "0")
    r = _kv(ws, r, "EDU_COST (USD)", "=EDU_COST", "D", "USD course cost, grown at inflation.", "#,##0")
    r = _kv(ws, r, "SAV_INCOME_MULT", "=SAV_INCOME_MULT", "D", "1 × annual income if stored is 0.", "0")
    r = _kv(ws, r, "PRP_INCOME_MULT", "=PRP_INCOME_MULT", "D", "5 × annual income if stored is 0.", "0")
    r = _kv(ws, r, "currentYear / ageOfRetirement", "=currentYear", "D", "2026 / 65 in this workbook.", "0")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  horizons", calc_hdr)
    r = _kv(
        ws, r, "supportYears",
        f"=MIN(MAX(INC_SUPPORT_MIN,INC_SUPPORT_PIVOT_AGE-B{age}),INC_SUPPORT_MAX)",
        "C", "life_support_years(age).", "0",
    )
    supp = r - 1
    r = _kv(ws, r, "yearsToRet", f"=MAX(0,B{ret}-B{age})", "C", "years_to_retirement.", "0")
    ytr = r - 1
    r = _kv(ws, r, "yearsInRet", f"=MAX(0,PLU_leUsed-B{ret})", "C", "years_in_retirement(retAge, session LE).", "0")
    yir = r - 1
    r = _kv(ws, r, "eduYears", f"=MAX(0,B{tgt}-currentYear)", "C", "max(0, targetYear N_EDU − thisYear).", "0")
    edu_y = r - 1
    r = _kv(ws, r, "savYears", f"=MAX(0,B{tgt_sav}-currentYear)", "C", "max(0, targetYear N_SAV − thisYear).", "0")
    sav_y = r - 1
    r = _kv(ws, r, "prpYears", f"=MAX(0,B{tgt_prp}-currentYear)", "C", "max(0, targetYear N_PRP − thisYear).", "0")
    prp_y = r - 1
    r = _kv(ws, r, "careYears (N_LTC)", f"=MAX(0,PLU_leUsed-B{ltc_age})", "C", "lifeExpectancy − LTC start age.", "0")
    care_y = r - 1

    rate_l = f"IF(B{life}=1,RET_LIFESTYLE_FRUGAL,IF(B{life}=3,RET_LIFESTYLE_ONLYTHEBEST,RET_LIFESTYLE_STRESSFREE))"
    dep_y = f'IF(OR(B{dep_y_cell}="",B{dep_y_cell}<=0),B{supp},B{dep_y_cell})'
    # V0-15: every money input is USD (S-block). No rounding in USD: results round in user currency.
    inc_rep = f'IF({U["rep"]}="",{U["inc"]},{U["rep"]})'
    annual_ret = f"{U['exp']}*12*({rate_l})"
    grown = _fv(annual_ret, "realReturn", f"B{ytr}")
    ret_amt = f"MAX(0,{_pv_annuity(grown, 'realReturn', f'B{yir}')})"
    pmt_spend = f"{U['exp']}*12"
    inc_amt = f"MAX(0,{U['beq']}+{U['mort']}+{_pv_annuity(pmt_spend, 'realReturn', dep_y)})"
    pmt_rep = f"({inc_rep})*12"
    cri_amt = f"MAX(0,{_pv_due(pmt_rep, 'realReturn', 'CRI_YEARS')}+{U['ci']})"
    tpd_amt = f"MAX(0,{_pv_due(pmt_rep, 'realReturn', 'TPD_YEARS')}+{U['tpd']})"
    hos_amt = f"MAX(0,{U['inc']}*HOS_MONTHS)"
    pac_amt = f"MAX(0,{_pv_due(pmt_rep, 'realReturn', 'PAC_YEARS')}+{U['pac']})"
    edu_amt = f"MAX(0,{U['edu']}*(1+inflationRate)^B{edu_y})"
    sav_amt = f"IF(B{sav_st}>0,{U['sav']},{U['inc']}*12*SAV_INCOME_MULT)"
    prp_amt = f"IF(B{prp_st}>0,{U['prp']},{U['inc']}*12*PRP_INCOME_MULT)"

    rem0 = U["inv"]
    take_ret = f"MIN(MAX(0,{U['tret']}),MAX(0,{rem0}))"
    rem1 = f"MAX(0,{rem0}-{take_ret})"
    take_edu = f"MIN(MAX(0,{U['tedu']}),{rem1})"
    rem2 = f"MAX(0,{rem1}-{take_edu})"
    take_sav = f"MIN(MAX(0,{U['tsav']}),{rem2})"
    rem3 = f"MAX(0,{rem2}-{take_sav})"
    take_prp = f"MIN(MAX(0,{U['tprp']}),{rem3})"

    amounts = {
        "N_INC": inc_amt,
        "N_CRI": cri_amt,
        "N_TPD": tpd_amt,
        "N_HOS": hos_amt,
        "N_PAC": pac_amt,
        "N_LTC": f"MAX(0,{_pv_due(U['ltc'], 'realReturn', f'B{care_y}')})",
        "N_RET": ret_amt,
        "N_EDU": edu_amt,
        "N_SAV": sav_amt,
        "N_PRP": prp_amt,
    }
    haves = {
        "N_INC": U["life"],
        "N_CRI": "0",
        "N_TPD": "0",
        "N_HOS": "0",
        "N_PAC": "0",
        "N_LTC": "0",
        "N_RET": _fv(take_ret, 'realReturn', f'B{ytr}'),
        "N_EDU": _fv(take_edu, 'realReturn', f'B{edu_y}'),
        "N_SAV": _fv(take_sav, 'realReturn', f'B{sav_y}'),
        "N_PRP": _fv(take_prp, 'realReturn', f'B{prp_y}'),
    }

    r += 1
    r = _section(ws, r, "C · RESULTS  —  amount / have / gap for every UNIFIED type (even when off)", calc_hdr)
    _fill(ws, f"A{r}", "type", font=h_font, fill=header_fill, align=center)
    _fill(ws, f"B{r}", "needAmount", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"C{r}", "have", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"D{r}", "gap", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"E{r}", "Enable?", font=h_font, fill=override_hdr, align=center)
    _fill(ws, f"F{r}", "on (effective)", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"H{r}", "needAmount USD", font=h_font, fill=llm_hdr, align=center)
    _fill(ws, f"I{r}", "have USD", font=h_font, fill=llm_hdr, align=center)
    _fill(ws, f"J{r}", "gap USD", font=h_font, fill=llm_hdr, align=center)
    r += 1
    dv = DataValidation(type="list", formula1='"TRUE,FALSE,"', allow_blank=True)
    ws.add_data_validation(dv)
    first = r
    amt_rows, have_rows, gap_rows, on_rows = {}, {}, {}, {}
    notes = {
        "N_INC": "bequest + mortgage + PV of annual spend over dependYears.",
        "N_CRI": "Annuity-due of replacement income for CRI_YEARS + CRI_COST.",
        "N_TPD": "Annuity-due of replacement income for TPD_YEARS + TPD_COST.",
        "N_HOS": "incomeMonthly × HOS_MONTHS.",
        "N_PAC": "Annuity-due of replacement income for PAC_YEARS + PAC_COST.",
        "N_LTC": "Annuity-due of LTC_COST over careYears (LTC start age → life expectancy), today's money.",
        "N_RET": "annualSpend × (1+realReturn)^T × a(realReturn, yearsInRet).",
        "N_EDU": "EDU_COST (USD) × (1+inflation)^eduYears.",
        "N_SAV": "Stored or 1× annual income.",
        "N_PRP": "Stored or 5× annual income.",
    }
    for t in UNIFIED_X:
        _fill(ws, f"A{r}", t, font=h_font, fill=calc_hdr, align=center)
        _fill(ws, f"H{r}", f"={amounts[t]}", fill=blue_fill, num="#,##0.00", align=center)
        _fill(ws, f"I{r}", f"={haves[t]}", fill=blue_fill, num="#,##0.00", align=center)
        _fill(ws, f"J{r}", f"=MAX(0,H{r}-I{r})", fill=blue_fill, num="#,##0.00", align=center)
        _fill(ws, f"B{r}", f"=ROUND(H{r}/$B${fx},0)", fill=calc_fill, num="#,##0", align=center)
        _fill(ws, f"C{r}", f"=ROUND(I{r}/$B${fx},0)", fill=calc_fill, num="#,##0", align=center)
        _fill(ws, f"D{r}", f"=MAX(0,B{r}-C{r})", fill=calc_fill, num="#,##0", align=center)
        _fill(ws, f"E{r}", "", fill=override_fill, align=center)
        _fill(ws, f"F{r}", f'=IF(E{r}="",NP_on_{t},E{r})', fill=green_fill, align=center)
        _fill(ws, f"G{r}", notes[t], font=note_font, fill=paper_fill, align=left)
        amt_rows[t] = r
        have_rows[t] = r
        gap_rows[t] = r
        on_rows[t] = r
        r += 1
    dv.add(f"E{first}:E{r - 1}")

    r += 1
    r = _section(ws, r, "C · STRESS R_LON  —  longevity: N_RET and N_LTC if the customer lives until LON_AGE (99). Does not change the plan", calc_hdr)
    r = _kv(ws, r, "LON_AGE", "=LON_AGE", "D", "Assumptions. Life expectancy under R_LON.", "0")
    r = _kv(ws, r, "yearsInRet at LON_AGE", f"=MAX(0,LON_AGE-B{ret})", "C", "LON_AGE − retAge.", "0")
    lon_y = r - 1
    lon_usd = f"MAX(0,{_pv_annuity(grown, 'realReturn', f'B{lon_y}')})"
    r = _kv(ws, r, "N_RET need at LON_AGE USD", f"={lon_usd}", "C", "Same formula as N_RET, years to LON_AGE.", "#,##0.00")
    lon_amt_usd = r - 1
    r = _kv(ws, r, "N_RET need at LON_AGE", f"=ROUND(B{lon_amt_usd}/$B${fx},0)", "C", "User currency.", "#,##0")
    lon_amt = r - 1
    r = _kv(ws, r, "N_RET gap at LON_AGE", f"=MAX(0,B{lon_amt}-C{amt_rows['N_RET']})", "C", "Need at 99 − have.", "#,##0")
    lon_gap = r - 1
    r = _kv(ws, r, "extra need from longevity", f"=MAX(0,B{lon_amt}-B{amt_rows['N_RET']})", "C", "Need at 99 − base need.", "#,##0")
    lon_x = r - 1
    r = _kv(ws, r, "careYears at LON_AGE", f"=MAX(0,LON_AGE-B{ltc_age})", "C", "LON_AGE − LTC start age.", "0")
    lon_cy = r - 1
    r = _kv(ws, r, "N_LTC need at LON_AGE", f"=ROUND(MAX(0,{_pv_due(U['ltc'], 'realReturn', f'B{lon_cy}')})/$B${fx},0)",
            "C", "Same formula as N_LTC, care until LON_AGE. User currency.", "#,##0")
    lon_ltc = r - 1

    _bind(wb, "Need Calculator", {"NC_age": age, "NC_yearsToRet": ytr, "NC_eduYears": edu_y, "NC_yearsInRet": yir,
                                   "NC_savYears": sav_y, "NC_prpYears": prp_y,
                                   "NC_lonYearsInRet": lon_y, "NC_lonAmount_N_RET": lon_amt, "NC_lonGap_N_RET": lon_gap,
                                   "NC_lonExtra_N_RET": lon_x, "NC_careYears": care_y, "NC_ltcStartAge": ltc_age,
                                   "NC_lonAmount_N_LTC": lon_ltc})
    for t in UNIFIED_X:
        _name(wb, f"NC_amount_{t}", f"'Need Calculator'!$B${amt_rows[t]}")
        _name(wb, f"NC_have_{t}", f"'Need Calculator'!$C${have_rows[t]}")
        _name(wb, f"NC_gap_{t}", f"'Need Calculator'!$D${gap_rows[t]}")
        _name(wb, f"NC_on_{t}", f"'Need Calculator'!$F${on_rows[t]}")
        _name(wb, f"NC_amountUSD_{t}", f"'Need Calculator'!$H${amt_rows[t]}")
        _name(wb, f"NC_gapUSD_{t}", f"'Need Calculator'!$J${gap_rows[t]}")
    _dash_widths(ws)
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 16
    ws.column_dimensions["G"].width = 56
    for col in ("H", "I", "J"):
        ws.column_dimensions[col].width = 16


def build_plan(wb: Workbook) -> None:
    ws = wb.create_sheet("Plan Calculator")
    ws.sheet_properties.tabColor = "1D4E89"
    _add_selector(
        ws,
        master=False,
        title="Plan Calculator — selected persona. seedProducts / planProducts.ts. Suggested = enabled AND gap > 0.",
    )
    _legend(ws, "F", 2)

    r = 4
    r = _section(ws, r, "A · INPUT DATA  —  from People Like You and Need Calculator", input_hdr)
    r = _kv(ws, r, "take-home (from PLU)", "=PLU_takeHome", "A", "Surplus uses take-home, not gross income.", "#,##0.00")
    r = _kv(ws, r, "expenseMonthly (from PLU)", "=PLU_expenseMonthly", "A", "types.ts availableBudget.", "#,##0.00")
    for t in UNIFIED_X:
        r = _kv(ws, r, f"{t} on (from Need Calculator)", f"=NC_on_{t}", "A", "Effective enable after Need Calculator override.")
        r = _kv(ws, r, f"{t} gap (from Need Calculator)", f"=NC_gap_{t}", "A", "remaining_gap.", "#,##0")
    r = _kv(ws, r, "yearsToRet (from Need Calculator)", "=NC_yearsToRet", "A", "Retirement contribution horizon.", "0")
    r = _kv(ws, r, "eduYears (from Need Calculator)", "=NC_eduYears", "A", "N_EDU contribution horizon.", "0")
    r = _kv(ws, r, "savYears (from Need Calculator)", "=NC_savYears", "A", "N_SAV contribution horizon.", "0")
    r = _kv(ws, r, "prpYears (from Need Calculator)", "=NC_prpYears", "A", "N_PRP contribution horizon.", "0")

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA", assume_hdr)
    r = _kv(ws, r, "protectionPremiumRate", "=protectionPremiumRate", "D", "Dummy 0.00078. Future: premium-quote calculator API.", "0.00%")
    r = _kv(ws, r, "FREE_BUDGET_SHARE", "=FREE_BUDGET_SHARE", "D", "Half of leftover surplus split across wealth needs.", "0.0%")
    r = _kv(ws, r, "monthly step (user currency)", "=FX_monthlyStep", "D", "monthlyRoundStep (USD) as a nice step in user currency. SGD: 50.", "#,##0.##")
    r = _kv(ws, r, "premium step (user currency)", "=FX_coverPremStep", "D", "coverPremRoundStep (USD) as a nice step in user currency. SGD: 10.", "#,##0.##")
    r = _kv(ws, r, "realReturn", "=realReturn", "D", "annualPmtToHitFv for the wealth cap.", "0.00%")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  suggested flags and protection sizing", calc_hdr)
    sug_rows = {}
    for t in UNIFIED_X:
        r = _kv(
            ws, r, f"sug {t}",
            f"=AND(NC_on_{t},NC_gap_{t}>0)",
            "C", "enabled AND gap > 0.",
        )
        sug_rows[t] = r - 1
    r = _kv(
        ws, r, "n wealth suggested",
        f"=(B{sug_rows['N_RET']}*1)+(B{sug_rows['N_EDU']}*1)+(B{sug_rows['N_SAV']}*1)+(B{sug_rows['N_PRP']}*1)",
        "C", "Count of suggested wealth needs.", "0",
    )
    n_w = r - 1

    sum_rows, prem_rows = {}, {}
    for t in PROT_X:
        r = _kv(
            ws, r, f"planSum {t}",
            f"=IF(B{sug_rows[t]},MAX(0,ROUND(NC_gap_{t},0)),0)",
            "C", "Suggested protection sum = gap.", "#,##0",
        )
        sum_rows[t] = r - 1
        r = _kv(
            ws, r, f"planPrem {t}",
            f"=IF(B{sum_rows[t]}<=0,0,MAX(0,ROUND((B{sum_rows[t]}*protectionPremiumRate)/FX_coverPremStep,0)*FX_coverPremStep))",
            "C", "coverPremiumFor(sum). Indicative, not half of slider max.", "#,##0",
        )
        prem_rows[t] = r - 1
    r = _kv(
        ws, r, "prot prem / yr",
        "=" + "+".join(f"B{prem_rows[t]}" for t in PROT_X),
        "C", "Sum of suggested protection premiums (before Include?).", "#,##0",
    )
    prot_yr = r - 1
    r = _kv(
        ws, r, "default wealth mth share",
        f"=IF(B{n_w}=0,0,MAX(0,ROUNDDOWN((MAX(0,PLU_takeHome-PLU_expenseMonthly)*FREE_BUDGET_SHARE-B{prot_yr}/12)"
        f"/B{n_w}/FX_monthlyStep,0)*FX_monthlyStep))",
        "C", "V0-24: (free budget − protection premiums / 12) ÷ n wealth, rounded DOWN to the monthly step. "
        "Free budget = 50% of monthly surplus, as in the Budget Calculator, so the default plan always fits.", "#,##0",
    )
    share = r - 1

    cap_rows, mth_rows, lump_rows = {}, {}, {}
    for t in WEALTH:
        n_yrs = {"N_RET": "NC_yearsToRet", "N_EDU": "NC_eduYears", "N_SAV": "NC_savYears", "N_PRP": "NC_prpYears"}[t]
        gap = f"NC_gap_{t}"
        annual = (
            f"IF(OR(({gap})<=0,({n_yrs})<=0),0,"
            f"IF(ABS(realReturn)<1E-12,({gap})/({n_yrs}),({gap})*realReturn/((1+realReturn)^({n_yrs})-1)))"
        )
        r = _kv(
            ws, r, f"cap mth {t}",
            f"=IF(({annual})<=0,0,ROUNDUP(({annual})/12/FX_monthlyStep,0)*FX_monthlyStep)",
            "C", "annualPmtToHitFv / 12, rounded up to the monthly step.", "#,##0",
        )
        cap_rows[t] = r - 1
        r = _kv(
            ws, r, f"planMth {t}",
            f"=IF(B{sug_rows[t]},MIN(B{share},B{cap_rows[t]}),0)",
            "C", "min(default share, cap).", "#,##0",
        )
        mth_rows[t] = r - 1
        r = _kv(ws, r, f"planLump {t}", 0, "C", "Default lump is 0.", "#,##0")
        lump_rows[t] = r - 1

    r += 1
    r = _section(ws, r, "C · RESULTS  —  Include? blank keeps the suggested product", calc_hdr)
    _fill(ws, f"A{r}", "type", font=h_font, fill=header_fill, align=center)
    _fill(ws, f"B{r}", "suggested", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"C{r}", "Include?", font=h_font, fill=override_hdr, align=center)
    _fill(ws, f"D{r}", "included", font=h_font, fill=calc_hdr, align=center)
    r += 1
    dv = DataValidation(type="list", formula1='"TRUE,FALSE,"', allow_blank=True)
    ws.add_data_validation(dv)
    first = r
    inc_rows = {}
    for t in UNIFIED_X:
        _fill(ws, f"A{r}", t, font=h_font, fill=calc_hdr, align=center)
        _fill(ws, f"B{r}", f"=B{sug_rows[t]}", fill=calc_fill, align=center)
        _fill(ws, f"C{r}", "", fill=override_fill, align=center)
        _fill(ws, f"D{r}", f'=AND(B{r},IF(C{r}="",TRUE,C{r}))', fill=green_fill, align=center)
        inc_rows[t] = r
        r += 1
    dv.add(f"C{first}:C{r - 1}")

    r += 1
    r = _kv(
        ws, r, "investMth",
        f"=(D{inc_rows['N_RET']}*B{mth_rows['N_RET']})+(D{inc_rows['N_EDU']}*B{mth_rows['N_EDU']})+"
        f"(D{inc_rows['N_SAV']}*B{mth_rows['N_SAV']})+(D{inc_rows['N_PRP']}*B{mth_rows['N_PRP']})",
        "C", "Sum of included wealth monthly contributions.", "#,##0",
    )
    inv_m = r - 1
    r = _kv(
        ws, r, "investLump",
        f"=(D{inc_rows['N_RET']}*B{lump_rows['N_RET']})+(D{inc_rows['N_EDU']}*B{lump_rows['N_EDU']})+"
        f"(D{inc_rows['N_SAV']}*B{lump_rows['N_SAV']})+(D{inc_rows['N_PRP']}*B{lump_rows['N_PRP']})",
        "C", "Sum of included wealth lumps (default 0).", "#,##0",
    )
    inv_l = r - 1

    names = {
        "PLAN_nWealth": n_w,
        "PLAN_protPremYr": prot_yr,
        "PLAN_wealthShare": share,
        "PLAN_investMth": inv_m,
        "PLAN_investLump": inv_l,
    }
    _bind(wb, "Plan Calculator", names)
    for t, row in prem_rows.items():
        _name(wb, f"PLAN_prem_{t}", f"'Plan Calculator'!$B${row}")
    for t, row in inc_rows.items():
        _name(wb, f"PLAN_included_{t}", f"'Plan Calculator'!$D${row}")
        _name(wb, f"PLAN_sug_{t}", f"'Plan Calculator'!$B${row}")
    for t, row in sum_rows.items():
        _name(wb, f"PLAN_sum_{t}", f"'Plan Calculator'!$B${row}")
    for t in WEALTH:
        _name(wb, f"PLAN_mth_{t}", f"'Plan Calculator'!$B${mth_rows[t]}")
        _name(wb, f"PLAN_lump_{t}", f"'Plan Calculator'!$B${lump_rows[t]}")
    _dash_widths(ws)
    ws.column_dimensions["F"].width = 42


def build_budget(wb: Workbook) -> None:
    ws = wb.create_sheet("Budget Calculator")
    ws.sheet_properties.tabColor = "8A1C1C"
    _add_selector(
        ws,
        master=False,
        title="Budget Calculator — selected persona. planAfford. Surplus is take-home minus expense.",
    )
    _legend(ws, "F", 2)

    r = 4
    r = _section(ws, r, "A · INPUT DATA  —  from People Like You and Plan Calculator", input_hdr)
    r = _kv(ws, r, "take-home (from PLU)", "=PLU_takeHome", "A", "types.ts availableBudget uses take-home.", "#,##0.00")
    r = _kv(ws, r, "expenseMonthly (from PLU)", "=PLU_expenseMonthly", "A", "Not gross income.", "#,##0.00")
    r = _kv(ws, r, "investments (from PLU)", "=PLU_investments", "A", "Cap for lumps.", "#,##0")
    r = _kv(ws, r, "included N_INC premium", "=IF(PLAN_included_N_INC,PLAN_prem_N_INC,0)", "A", "Only included protection.", "#,##0")
    r = _kv(ws, r, "included N_CRI premium", "=IF(PLAN_included_N_CRI,PLAN_prem_N_CRI,0)", "A", "", "#,##0")
    r = _kv(ws, r, "included N_TPD premium", "=IF(PLAN_included_N_TPD,PLAN_prem_N_TPD,0)", "A", "", "#,##0")
    r = _kv(ws, r, "included N_HOS premium", "=IF(PLAN_included_N_HOS,PLAN_prem_N_HOS,0)", "A", "", "#,##0")
    r = _kv(ws, r, "included N_PAC premium", "=IF(PLAN_included_N_PAC,PLAN_prem_N_PAC,0)", "A", "V0-16.", "#,##0")
    r = _kv(ws, r, "included N_LTC premium", "=IF(PLAN_included_N_LTC,PLAN_prem_N_LTC,0)", "A", "V0-19.", "#,##0")
    r = _kv(ws, r, "investMth (from Plan)", "=PLAN_investMth", "A", "Included wealth contributions.", "#,##0")
    r = _kv(ws, r, "investLump (from Plan)", "=PLAN_investLump", "A", "Included wealth lumps.", "#,##0")

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA", assume_hdr)
    r = _kv(ws, r, "FREE_BUDGET_SHARE", "=FREE_BUDGET_SHARE", "D", "Half of monthly surplus is the free budget.", "0.0%")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  planAfford", calc_hdr)
    r = _kv(ws, r, "available", "=MAX(0,PLU_takeHome-PLU_expenseMonthly)", "C", "max(0, take-home − expense).", "#,##0.00")
    avail = r - 1
    r = _kv(ws, r, "free (50%)", f"=ROUND(B{avail}*FREE_BUDGET_SHARE,0)", "C", "available × 50%, rounded.", "#,##0")
    free = r - 1
    r = _kv(
        ws, r, "included prot prem / yr",
        "=IF(PLAN_included_N_INC,PLAN_prem_N_INC,0)+IF(PLAN_included_N_CRI,PLAN_prem_N_CRI,0)"
        "+IF(PLAN_included_N_TPD,PLAN_prem_N_TPD,0)+IF(PLAN_included_N_HOS,PLAN_prem_N_HOS,0)"
        "+IF(PLAN_included_N_PAC,PLAN_prem_N_PAC,0)+IF(PLAN_included_N_LTC,PLAN_prem_N_LTC,0)",
        "C", "Sum of included protection premiums.", "#,##0",
    )
    prem = r - 1
    r = _kv(ws, r, "premMth (display)", f"=ROUND(B{prem}/12,0)", "C", "Annual premiums / 12.", "#,##0")
    r = _kv(ws, r, "contribMth", "=PLAN_investMth", "C", "Same as investMth.", "#,##0")
    r = _kv(ws, r, "monthly", f"=ROUND(PLAN_investMth+B{prem}/12,0)", "C", "contrib + prem/12.", "#,##0")
    monthly = r - 1
    r = _kv(ws, r, "monthlyOver", f"=B{monthly}-B{free}", "C", "> 0 means the plan exceeds the free budget.", "#,##0")
    over = r - 1
    r = _kv(ws, r, "lumps", "=PLAN_investLump", "C", "Included lumps.", "#,##0")
    lumps = r - 1
    r = _kv(ws, r, "lumpOver", f"=B{lumps}-PLU_investments", "C", "> 0 means lumps exceed current investments.", "#,##0")
    lump_over = r - 1

    ws.conditional_formatting.add(f"B{over}", FormulaRule(formula=[f"B{over}>0"], fill=red_fill))
    ws.conditional_formatting.add(f"B{over}", FormulaRule(formula=[f"B{over}<=0"], fill=green_fill))
    ws.conditional_formatting.add(f"B{lump_over}", FormulaRule(formula=[f"B{lump_over}>0"], fill=red_fill))
    ws.conditional_formatting.add(f"B{lump_over}", FormulaRule(formula=[f"B{lump_over}<=0"], fill=green_fill))

    _dash_widths(ws)
    ws.column_dimensions["F"].width = 42


NICE_STEP = 'IF(({x})<=0,0,10^INT(LOG10({x}))*IF(({x})/10^INT(LOG10({x}))<1.5,1,IF(({x})/10^INT(LOG10({x}))<3.5,2,IF(({x})/10^INT(LOG10({x}))<7.5,5,10))))'


def build_fx(wb: Workbook) -> None:
    """Local → USD conversion. Rate table and converted amounts live here."""
    ws = wb.create_sheet("FX")
    ws.sheet_properties.tabColor = "1D6F42"
    _add_selector(
        ws,
        master=False,
        title="FX — selected persona. Convert local currency to USD. Validation reads these amounts.",
    )
    _legend(ws, "F", 2)

    _fill(ws, "I4", f"D · RATE TABLE  —  {len(FX_CCY)} currencies, market rate {FX_CCY[0]['date']} (fx_ppp/currencies_fx.csv). App: live feed, locked on the session",
          font=h_font, fill=assume_hdr, align=left)
    ws.merge_cells("I4:L4")
    for col, h in zip("IJKL", ["currency", "USD per 1 unit", "units per USD", "date"]):
        _fill(ws, f"{col}5", h, font=h_font, fill=header_fill, align=center)
    for i, row in enumerate(FX_CCY):
        rr = 6 + i
        _fill(ws, f"I{rr}", row["currency"], fill=input_fill, align=center)
        _fill(ws, f"J{rr}", float(row["usd_per_1"]), fill=input_fill, align=center, num="0.000000000")
        _fill(ws, f"K{rr}", float(row["local_per_usd"]), align=center, num="#,##0.0000")
        _fill(ws, f"L{rr}", row["date"], font=note_font, align=center)
    _name(wb, "FxTable", f"FX!$I$6:$J${5 + len(FX_CCY)}")

    _fill(ws, "N4", f"D · PPP TABLE  —  {len(FX_CTRY)} countries. Price level = World Bank PPP ÷ 2024 average market rate (US = 1). fx_ppp/countries_ppp.csv",
          font=h_font, fill=assume_hdr, align=left)
    ws.merge_cells("N4:U4")
    heads = ["country", "ISO3", "currency", "PPP year", "PPP (LCU per int. $)", "2024 avg (LCU per USD)", "price level (US = 1)", "flag"]
    for j, h in enumerate(heads):
        _fill(ws, f"{get_column_letter(14 + j)}5", h, font=h_font, fill=header_fill, align=center)
    for i, row in enumerate(FX_CTRY):
        rr = 6 + i
        vals = [row["country"], row["iso3"], row["currency"],
                int(row["ppp_year"]) if row["ppp_year"] else "",
                float(row["ppp"]) if row["ppp"] else "",
                float(row["fx2024"]) if row["fx2024"] else "",
                float(row["price_level"]) if row["price_level"] else "",
                row["flag"]]
        for j, v in enumerate(vals):
            _fill(ws, f"{get_column_letter(14 + j)}{rr}", v, fill=input_fill if j == 6 and v != "" else None,
                  font=note_font if j == 7 else body_font, align=center if j else left,
                  num={4: "#,##0.0000", 5: "#,##0.0000", 6: "0.0000"}.get(j))
    _name(wb, "CountryPPP", f"FX!$N$6:$U${5 + len(FX_CTRY)}")

    r = 4
    r = _section(ws, r, "A · INPUT DATA  —  currency and effective session (local)", input_hdr)
    r = _kv(ws, r, "currency", "=PLU_currency", "A", "Personas K via People Like You. Lookup key for the rate table.")
    r = _kv(ws, r, "incomeMonthly (local)", "=PLU_incomeMonthly", "A", "Effective session.", "#,##0.00")
    loc_inc = r - 1
    r = _kv(ws, r, "expenseMonthly (local)", "=PLU_expenseMonthly", "A", "", "#,##0.00")
    loc_exp = r - 1
    r = _kv(ws, r, "cash (local)", "=PLU_cash", "A", "", "#,##0.00")
    loc_cash = r - 1
    r = _kv(ws, r, "investments (local)", "=PLU_investments", "A", "", "#,##0")
    loc_inv = r - 1
    r = _kv(ws, r, "property (local)", "=PLU_property", "A", "", "#,##0")
    loc_prop = r - 1
    r = _kv(ws, r, "mortgage (local)", "=PLU_mortgage", "A", "", "#,##0")
    loc_mort = r - 1
    r = _kv(ws, r, "PLU liabilities (local)", "=PLU_liabilities", "A", "", "#,##0.00")
    loc_liab = r - 1
    r = _kv(ws, r, "life sum assured (local)", "=PLU_lifeSum", "A", "", "#,##0")
    loc_life = r - 1

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS  —  rate from the table on the right", assume_hdr)
    r = _kv(
        ws, r, "USD per 1 local",
        '=IFERROR(VLOOKUP(PLU_currency,FxTable,2,FALSE),NA())',
        "D",
        "#N/A if the currency is not in the table: every calculator then fails loudly (no SGD fallback).",
        "0.000000",
    )
    rate = r - 1
    r = _kv(ws, r, "country", f"={_px('F')}", "A", "Personas F. Lookup key for the PPP table (price level is per country, not per currency).")
    ctry = r - 1
    r = _kv(ws, r, "currency of that country", f'=IFERROR(VLOOKUP(B{ctry},CountryPPP,3,FALSE),"country not in table")', "D",
            "Check: should equal the session currency.")
    r = _kv(ws, r, "currency matches country", f'=IFERROR(B{r - 1}=PLU_currency,FALSE)', "C", "FALSE = persona currency differs from the country's currency.")
    r = _kv(ws, r, "price level country (US = 1)", f'=IFERROR(VLOOKUP(B{ctry},CountryPPP,7,FALSE),"")', "D",
            "PPP ÷ 2024 market rate. Blank if the country has no usable PPP.", "0.0000")
    pl_c = r - 1
    r = _kv(ws, r, "price level base (PPP_BASE_COUNTRY)", '=IFERROR(VLOOKUP(PPP_BASE_COUNTRY,CountryPPP,7,FALSE),"")', "D",
            "Singapore: the USD fixed amounts were calibrated there.", "0.0000")
    pl_b = r - 1
    r = _kv(ws, r, "relative price level", f'=IF(OR(B{pl_c}="",B{pl_b}=""),1,B{pl_c}/B{pl_b})', "C",
            "Country ÷ base. 1 when the country has no PPP (falls back to market rate).", "0.0000")
    pl_r = r - 1
    r = _kv(ws, r, "price level (effective)", f'=IF(priceLevelOn=TRUE,B{pl_r},1)', "C",
            "Option B: multiplies every USD fixed amount (costs, home seed, bands). 1 under option A.", "0.0000")
    plev = r - 1
    r = _kv(ws, r, "PPP-USD per 1 local", f"=B{rate}/B{plev}", "C",
            "Market USD ÷ price level: what the local amount buys, in base-country USD. Need Profiler bands read this.", "0.000000000")
    ppp_rate = r - 1

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  local × USD per 1", calc_hdr)
    usd = f'=B{{loc}}*$B${rate}'
    r = _kv(ws, r, "incomeMonthly USD", usd.format(loc=loc_inc), "C", "5,000 SGD → 3,700. 5,000 VND → 0.19.", "#,##0.00")
    usd_inc = r - 1
    r = _kv(ws, r, "expenseMonthly USD", usd.format(loc=loc_exp), "C", "", "#,##0.00")
    usd_exp = r - 1
    r = _kv(ws, r, "cash USD", usd.format(loc=loc_cash), "C", "", "#,##0.00")
    usd_cash = r - 1
    r = _kv(ws, r, "investments USD", usd.format(loc=loc_inv), "C", "", "#,##0.00")
    usd_inv = r - 1
    r = _kv(ws, r, "property USD", usd.format(loc=loc_prop), "C", "", "#,##0.00")
    usd_prop = r - 1
    r = _kv(ws, r, "mortgage USD", usd.format(loc=loc_mort), "C", "", "#,##0.00")
    usd_mort = r - 1
    r = _kv(ws, r, "PLU liabilities USD", usd.format(loc=loc_liab), "C", "", "#,##0.00")
    usd_liab = r - 1
    r = _kv(ws, r, "life sum assured USD", usd.format(loc=loc_life), "C", "", "#,##0.00")
    usd_life = r - 1

    r += 1
    r = _section(ws, r, "C · ROUNDING STEPS IN USER CURRENCY  —  USD step ÷ rate, then the nearest 1 / 2 / 5 × 10^k", calc_hdr)
    nice = NICE_STEP
    steps = {}
    for key, label, src_name in (
        ("FX_lumpStep", "lump step", "lumpRoundStep"),
        ("FX_monthlyStep", "monthly step", "monthlyRoundStep"),
        ("FX_coverPremStep", "premium step", "coverPremRoundStep"),
        ("FX_lifeRound", "life cover step", "lifeRoundUnit"),
        ("FX_benefitRound", "HappiU benefit step", "benefitRound"),
    ):
        x = f"({src_name}/$B${rate})"
        r = _kv(ws, r, label, "=" + nice.format(x=x), "C",
                f"{src_name} (USD) in user currency. SGD gives the V0-14 step.", "#,##0.##")
        steps[key] = r - 1

    _bind(wb, "FX", {
        **steps,
        "FX_priceLevel": plev,
        "FX_pppUsdPerLocal": ppp_rate,
        "FX_usdPerLocal": rate,
        "FX_incomeMonthly": usd_inc,
        "FX_expenseMonthly": usd_exp,
        "FX_cash": usd_cash,
        "FX_investments": usd_inv,
        "FX_property": usd_prop,
        "FX_mortgage": usd_mort,
        "FX_liabilities": usd_liab,
        "FX_lifeSum": usd_life,
    })
    _dash_widths(ws)
    ws.column_dimensions["F"].width = 42
    ws.column_dimensions["I"].width = 14
    ws.column_dimensions["J"].width = 16
    ws.column_dimensions["K"].width = 16
    ws.column_dimensions["L"].width = 12
    for col, wdt in zip("NOPQRSTU", (28, 8, 10, 9, 16, 18, 16, 40)):
        ws.column_dimensions[col].width = wdt


def build_validation(wb: Workbook) -> None:
    """USD-only sanity rules. Amounts in USD come from the FX tab."""
    ws = wb.create_sheet("Validation")
    ws.sheet_properties.tabColor = "C45C26"
    _fill(
        ws,
        "A1",
        "Validation — USD-only min / max on the selected persona. "
        "Conversion lives on the FX tab. People Like You still stores local currency.",
        title_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A1:G1")
    _fill(
        ws,
        "A2",
        "Example: 5,000 SGD → FX 3,700 USD (pass). 5,000 VND → FX 0.19 USD (fail min income). "
        "Change Personas currency to VND and keep income 5,000 to see the fail. Yellow cells are editable.",
        note_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A2:G2")

    _fill(ws, "A4", "USD validation rules (edit these)", font=h_font, fill=override_hdr, align=center)
    ws.merge_cells("A4:E4")
    for i, h in enumerate(["field", "min USD", "max USD", "source / why", "fail if"], 1):
        _fill(ws, f"{get_column_letter(i)}5", h, font=h_font, fill=header_fill, align=center)
    rules = [
        ("incomeMonthly", 200, 100_000, "InsApi rejects below ~USD 1,000. Workbook floor 200 so a junior US wage still passes; 5,000 VND does not.", "USD < min or > max"),
        ("expenseMonthly", 80, 80_000, "Frontend MIN_EXPENSE_MONTHLY = 100 SGD ≈ 74 USD. Floor 80 USD.", "USD < min or > max"),
        ("cash", 0, 20_000_000, "Cash & Savings stock, not a monthly flow.", "USD < 0 or > max"),
        ("investments", 0, 20_000_000, "Investment stock.", "USD < 0 or > max"),
        ("property", 0, 50_000_000, "Home value. 0 is valid (renter).", "USD < 0 or > max"),
        ("mortgage", 0, 50_000_000, "Loans. Also fail if USD mortgage > USD property when property > 0.", "USD < 0, > max, or > property"),
        ("PLU liabilities", 0, 20_000_000, "Profiler TotalLiabilities (liquid × 0.7 unless overridden).", "USD < 0 or > max"),
        ("life sum assured", 0, 20_000_000, "Existing life cover. 0 is valid.", "USD < 0 or > max"),
    ]
    rule_row = {}
    for i, (field, lo, hi, why, fail) in enumerate(rules):
        rr = 6 + i
        _fill(ws, f"A{rr}", field, fill=input_fill)
        _fill(ws, f"B{rr}", lo, fill=input_fill, align=center, num="#,##0")
        _fill(ws, f"C{rr}", hi, fill=input_fill, align=center, num="#,##0")
        _fill(ws, f"D{rr}", why, font=note_font, fill=paper_fill)
        _fill(ws, f"E{rr}", fail, font=note_font, fill=paper_fill)
        rule_row[field] = rr
    _name(wb, "UsdRules", f"Validation!$A$6:$C${5 + len(rules)}")

    _fill(ws, "A15", "Selected persona — pass / fail against USD rules", font=h_font, fill=calc_hdr, align=center)
    ws.merge_cells("A15:G15")
    _fill(ws, "A16", "Selected persona", font=h_font, fill=input_hdr)
    _fill(ws, "B16", "=SelectedPersona", fill=input_fill, align=center)
    _fill(ws, "C16", f"={_px('B', '$B$16')}", fill=input_fill)
    _fill(ws, "D16", f"={_px('F', '$B$16')}&\" / \"&PLU_currency", fill=input_fill)
    _fill(ws, "E16", "Follows the Selected persona tab. Change the id there.", font=note_font, fill=paper_fill, border=False)
    _fill(ws, "A17", "USD per 1 local", font=h_font, fill=assume_hdr)
    _fill(ws, "B17", "=FX_usdPerLocal", fill=assume_fill, align=center, num="0.000000")
    _fill(ws, "C17", "Pointer to the FX tab. Edit rates there, not here.", font=note_font, fill=paper_fill, border=False)

    for i, h in enumerate(
        ["field", "local (effective)", "USD (from FX)", "min USD", "max USD", "status", "detail"],
        1,
    ):
        _fill(ws, f"{get_column_letter(i)}19", h, font=h_font, fill=header_fill, align=center)

    checks = [
        ("incomeMonthly", "PLU_incomeMonthly", "FX_incomeMonthly", "incomeMonthly", False),
        ("expenseMonthly", "PLU_expenseMonthly", "FX_expenseMonthly", "expenseMonthly", False),
        ("cash", "PLU_cash", "FX_cash", "cash", False),
        ("investments", "PLU_investments", "FX_investments", "investments", False),
        ("property", "PLU_property", "FX_property", "property", False),
        ("mortgage", "PLU_mortgage", "FX_mortgage", "mortgage", True),
        ("PLU liabilities", "PLU_liabilities", "FX_liabilities", "PLU liabilities", False),
        ("life sum assured", "PLU_lifeSum", "FX_lifeSum", "life sum assured", False),
    ]
    first_check = 20
    prop_usd_row = first_check + 4  # property
    for i, (label, local_name, usd_name, rule_name, vs_prop) in enumerate(checks):
        rr = first_check + i
        rr_rule = rule_row[rule_name]
        _fill(ws, f"A{rr}", label, fill=calc_fill)
        _fill(ws, f"B{rr}", f"={local_name}", fill=calc_fill, num="#,##0.00", align=center)
        _fill(ws, f"C{rr}", f"={usd_name}", fill=calc_fill, num="#,##0.00", align=center)
        _fill(ws, f"D{rr}", f"=B{rr_rule}", fill=assume_fill, num="#,##0", align=center)
        _fill(ws, f"E{rr}", f"=C{rr_rule}", fill=assume_fill, num="#,##0", align=center)
        if vs_prop:
            status = (
                f'=IF(FX_usdPerLocal="","no FX",'
                f'IF(OR(C{rr}<D{rr},C{rr}>E{rr},AND(C{rr}>C{prop_usd_row},C{prop_usd_row}>0)),"FAIL","OK"))'
            )
            detail = (
                f'=IF(FX_usdPerLocal="","Set Personas currency to a row on the FX tab.",'
                f'IF(AND(C{rr}>C{prop_usd_row},C{prop_usd_row}>0),"mortgage USD > property USD",'
                f'IF(C{rr}<D{rr},"below min USD",IF(C{rr}>E{rr},"above max USD","inside USD band"))))'
            )
        else:
            status = (
                f'=IF(FX_usdPerLocal="","no FX",IF(OR(C{rr}<D{rr},C{rr}>E{rr}),"FAIL","OK"))'
            )
            detail = (
                f'=IF(FX_usdPerLocal="","Set Personas currency to a row on the FX tab.",'
                f'IF(C{rr}<D{rr},"below min USD",IF(C{rr}>E{rr},"above max USD","inside USD band")))'
            )
        _fill(ws, f"F{rr}", status, fill=green_fill, align=center)
        _fill(ws, f"G{rr}", detail, font=note_font, fill=paper_fill)
        ws.conditional_formatting.add(f"F{rr}", FormulaRule(formula=[f'F{rr}="FAIL"'], fill=red_fill))
        ws.conditional_formatting.add(f"F{rr}", FormulaRule(formula=[f'F{rr}="OK"'], fill=green_fill))

    last_check = first_check + len(checks) - 1
    overall = last_check + 2
    _fill(ws, f"A{overall}", "Overall", font=h_font, fill=header_fill)
    _fill(
        ws,
        f"B{overall}",
        f'=IF(COUNTIF(F{first_check}:F{last_check},"FAIL")>0,"FAIL",'
        f'IF(COUNTIF(F{first_check}:F{last_check},"no FX")>0,"no FX","OK"))',
        fill=green_fill,
        align=center,
    )
    ws.conditional_formatting.add(f"B{overall}", FormulaRule(formula=[f'B{overall}="FAIL"'], fill=red_fill))
    ws.conditional_formatting.add(f"B{overall}", FormulaRule(formula=[f'B{overall}="OK"'], fill=green_fill))

    _widths(ws, {
        "A": 22, "B": 20, "C": 18, "D": 72, "E": 28, "F": 10, "G": 42,
    })
    ws.row_dimensions[1].height = 32
    ws.row_dimensions[2].height = 32
    ws.freeze_panes = "A4"


# ---------------------------------------------------------------------------
# Scenario Visualizer and HappiU — one deterministic path each
# (Python twins: deterministic_engines.twin_sv / twin_hu)
# ---------------------------------------------------------------------------

YEAR_ROWS = 83  # year 0..82 covers age 18 → 100
grey_fill = PatternFill("solid", fgColor="E7E6E6")
HU_AGE0, HU_AGE1 = 18, 100


class _Cols:
    """Year-table column letters by key; c(key, row) → A1 reference."""

    def __init__(self, keys: list[str], first_col: int = 1):
        self.letter = {k: get_column_letter(first_col + i) for i, k in enumerate(keys)}

    def __call__(self, key: str, row: int) -> str:
        return f"{self.letter[key]}{row}"

    def rng(self, key: str, r0: int, r1: int) -> str:
        c = self.letter[key]
        return f"${c}${r0}:${c}${r1}"


def _write_year_table(ws, top: int, specs: list[tuple], cols: _Cols, groups: list[tuple]) -> tuple[int, int]:
    """specs: (key, header, fill, first-row formula or None, formula(r) for later rows, num)."""
    for label, k0, k1, fill in groups:
        _group_band(ws, column_index_from_string(cols.letter[k0]), column_index_from_string(cols.letter[k1]),
                    top - 1, label, fill)
    first, last = top + 1, top + YEAR_ROWS
    for key, header, fill, f0, fr, num in specs:
        _fill(ws, cols(key, top), header, font=h_font, fill=header_fill, align=center)
        for i in range(YEAR_ROWS):
            r = first + i
            v = f0 if (i == 0 and f0 is not None) else fr(r)
            _fill(ws, cols(key, r), v, fill=fill, num=num, align=center)
    return first, last


def _round_even(x: str) -> str:
    """Python round(x) (half to even) for x ≥ 0; Excel ROUND rounds halves up."""
    return f"IF(MOD({x},1)=0.5,2*ROUND(({x})/2,0),ROUND({x},0))"


def _grey_rows(ws, first: int, last: int, last_col: str, in_col: str, age_col: str) -> None:
    ws.conditional_formatting.add(
        f"A{first}:{last_col}{last}",
        FormulaRule(formula=[f"OR(${in_col}{first}=FALSE,${age_col}{first}>IFERROR(SV_end,endAge))"], fill=grey_fill),
    )


def build_sv(wb: Workbook) -> None:
    ws = wb.create_sheet("Scenario Visualizer")
    ws.sheet_properties.tabColor = "2F5597"
    _add_selector(
        ws,
        master=False,
        title="Scenario Visualizer — selected persona. One deterministic path of SV CashFlowGeneratorV2 on GP's payload.",
    )
    _legend(ws, "F", 2)
    names: dict[str, int] = {}
    r = 4

    def kv(name: str, label: str, value, kind: str, note: str = "", num=None) -> None:
        nonlocal r
        r = _kv(ws, r, label, value, kind, note, num)
        names[name] = r - 1

    r = _section(ws, r, "A · INPUT DATA  —  effective session (People Like You, Need Calculator, Plan Calculator)", input_hdr)
    kv("SV_age", "age", f"={_px('C')}", "A", "Personas C.", "0")
    kv("SV_residency", "residency", f"={_px('E')}", "A", "Personas E. sv_payload.py sends CPF region R_SGP unless Foreigner.")
    kv("SV_income", "incomeMonthly", "=PLU_incomeMonthly", "A", "Salary I_SAL = round(× 12).", "#,##0.00")
    kv("SV_takeHome", "take-home", "=PLU_takeHome", "A", "Investment contribution = take-home − spend.", "#,##0.00")
    kv("SV_expense", "expenseMonthly", "=PLU_expenseMonthly", "A", "PERSONAL_EXPENSE = round(× 12).", "#,##0.00")
    kv("SV_cash", "cash", "=PLU_cash", "A", "A_SAV, grows at interestRate.", "#,##0")
    kv("SV_investments", "investments", "=PLU_investments", "A", "INVESTMENT_PORTFOLIO, grows at investmentReturn.", "#,##0")
    kv("SV_property", "property", "=PLU_property", "A", "RESIDENTIAL_PROPERTY (illiquid).", "#,##0")
    kv("SV_mortgage", "mortgage", "=PLU_mortgage", "A", "Mortgage loan, 20-year annuity at loanRate.", "#,##0")
    kv("SV_lifeSum", "life sum assured", "=PLU_lifeSum", "A", "Existing life policy (only when > 0).", "#,##0")
    kv("SV_lifePrem", "life premium / yr", "=PLU_lifePrem", "A", "regularPremium of the existing policy.", "#,##0")

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS  —  SV helium tenant conf.ini and SocialSecurityR_SGP", assume_hdr)
    kv("SV_LE", "path end age (sent: LON_AGE)", "=LON_AGE", "D", "V0-21: GP sends the cap (99); was SV tenant 100.", "0")
    kv("SV_savRate", "savingsRate", 0.01, "D", "helium conf.ini. Savings account growth; also the premium load (× 1.01).", "0.00%")
    kv("SV_ret", "ageOfRetirement", "=ageOfRetirement", "D", "Assumptions.", "0")
    kv("SV_loanYears", "loan / premium term (years)", 20, "D", "Mortgage remainingYears and existing policyTerm in sv_payload.py.", "0")
    kv("SV_propPremium", "property rate premium", 0.004, "D", "Property grows at max(0, assetReturn + 0.4%).", "0.00%")
    kv("SV_fxShare", "currency shock share", 2 / 3, "D", "Liquid assets fall by 2/3 of the slider.", "0.0000")
    kv("SV_owCap", "CPF ordinary-wage cap / yr", 96_000, "D", "SocialSecurityR_SGP.", "#,##0")
    kv("SV_maCap", "CPF MA cap", 63_000, "D", "Medisave excess moves to RA at payout age; MA is capped from then.", "#,##0")
    kv("SV_oaRate", "CPF OA rate", 0.025, "D", "", "0.0%")
    kv("SV_saRate", "CPF SA / MA rate", 0.04, "D", "", "0.0%")
    kv("SV_lifeGrowth", "CPF RA / LIFE growth factor", 1.04, "D", "RA and the CPF LIFE pot grow × 1.04 a year.", "0.00")
    kv("SV_brsGrowth", "BRS / payout growth", 0.03, "D", "Past the 2027 row, and per year of payout age past 55.", "0.0%")
    kv("SV_deferBonus", "payout bonus per deferral year", 0.07, "D", "× (1 + 7% × (payout age − 65)).", "0.0%")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  sv_payload.py values as SV reads them", calc_hdr)
    kv("SV_T", "years on the path (T)", "=MAX(SV_LE-SV_age,0)", "C", "SV numYears = 100 − age.", "0")
    kv("SV_L", "array length (T + 1)", "=SV_T+1", "C", "Asset / CPF columns run 0..T.", "0")
    kv("SV_dtr", "years to retirement", "=MAX(SV_ret-SV_age,0)", "C", "", "0")
    kv("SV_salCut", "salary zero from index", "=IF(SV_dtr>=1,SV_dtr-1,SV_T-1)",
       "C", "numpy arr[dtr−1:] = 0. When dtr = 0 only the last year is zeroed (SV keeps salary for retirees).", "0")
    even = "Python round (half to even)."
    kv("SV_sal0", "salary / yr", "=" + _round_even("SV_income*12"), "C", f"I_SAL absoluteValue. {even}", "#,##0")
    kv("SV_exp0", "spend / yr", "=" + _round_even("SV_expense*12"), "C", f"PERSONAL_EXPENSE absoluteValue. {even}", "#,##0")
    kv("SV_mortP", "mortgage principal", "=INT(SV_mortgage)", "C", "int(mortgage).", "#,##0")
    kv("SV_inst", "mortgage instalment / yr",
       "=IF(SV_mortgage>0,"
       + _round_even("IF(loanRate=0,SV_mortgage/SV_loanYears,SV_mortgage*loanRate/(1-(1+loanRate)^(-SV_loanYears)))")
       + ",0)",
       "C", "Level annual annuity that clears the loan in 20 years, interest included "
       f"(goal_math.annual_loan_payment). rate 0 → mortgage / 20. Paid from spend for 20 years. {even}", "#,##0")
    kv("SV_contrib", "investment contribution / yr", "=" + _round_even("MAX(0,SV_takeHome-SV_expense)"),
       "C", f"sv_payload.py sends the MONTHLY surplus; SV adds it once a year. {even}", "#,##0")
    kv("SV_lifePremYr", "existing life premium / yr", "=IF(SV_lifeSum>0,SV_lifePrem,0)*(1+SV_savRate)",
       "C", "InsuranceBaseClass premium × (1 + savingsRate), first 20 years.", "#,##0.00")
    kv("SV_propRate", "property growth", "=MAX(0,assetReturn+SV_propPremium)", "C", "", "0.00%")
    for g, yrs in (("EDU", "NC_eduYears"), ("SAV", "NC_savYears"), ("PRP", "NC_prpYears")):
        kv(f"SV_wd{g}Year", f"N_{g} withdrawal year", f"=IF({yrs}>=1,{yrs},SV_T)", "C", "fundsNeededYear − now (V0-24: own target year).", "0")
        kv(f"SV_wd{g}Amt", f"N_{g} withdrawal amount", f"=IF({yrs}<=SV_T,NC_on_N_{g}*NC_amount_N_{g},0)", "C",
           "capitalSumRequired, not inflated. Leaves savings in that year.", "#,##0")
    kv("SV_retMth", "plan RET monthly", "=IF(PLAN_included_N_RET,PLAN_mth_N_RET,0)", "C", "plan_benefit_visualizer pot.", "#,##0")
    kv("SV_retLump", "plan RET lump", "=IF(PLAN_included_N_RET,PLAN_lump_N_RET,0)", "C", "", "#,##0")
    kv("SV_retPay", "plan RET pay years", "=MAX(1,SV_ret-SV_age)", "C", "", "0")
    for g, yrs in (("EDU", "NC_eduYears"), ("SAV", "NC_savYears"), ("PRP", "NC_prpYears")):
        kv(f"SV_{g}Mth", f"plan N_{g} monthly", f"=IF(PLAN_included_N_{g},PLAN_mth_N_{g},0)", "C", "One pot column for the three goals.", "#,##0")
        kv(f"SV_{g}Lump", f"plan N_{g} lump", f"=IF(PLAN_included_N_{g},PLAN_lump_N_{g},0)", "C", "", "#,##0")
        kv(f"SV_{g}Pay", f"plan N_{g} pay years", f"=MAX(1,{yrs})", "C", "V0-24: own target year.", "0")
    kv("SV_protPrem", "plan protection premium / yr",
       "=IF(PLAN_included_N_INC,PLAN_prem_N_INC,0)+IF(PLAN_included_N_CRI,PLAN_prem_N_CRI,0)"
       "+IF(PLAN_included_N_TPD,PLAN_prem_N_TPD,0)+IF(PLAN_included_N_HOS,PLAN_prem_N_HOS,0)"
       "+IF(PLAN_included_N_PAC,PLAN_prem_N_PAC,0)+IF(PLAN_included_N_LTC,PLAN_prem_N_LTC,0)",
       "C", "Premiums only: protection pots have no account value on SV's no-death path. Includes N_PAC and N_LTC.", "#,##0")
    kv("SV_protPay", "plan protection pay years", "=MAX(1,SV_ret-SV_age)", "C", "", "0")

    r += 1
    r = _section(ws, r, "E · OVERRIDE  —  stress events (blank size = off). Slider years as on the SV screen", override_hdr)
    kv("SV_crashY", "R_MKT market crash: year", "", "O", "Slider year; SV applies it at year + 1.", "0")
    kv("SV_crashV", "R_MKT market crash: size", "", "O", "e.g. 0.35. Every asset × (1 − size).", "0%")
    kv("SV_ccyY", "R_CCY currency shock: year", "", "O", "", "0")
    kv("SV_ccyV", "R_CCY currency shock: size", "", "O", "Liquid assets × (1 − size × 2/3).", "0%")
    kv("SV_inflFrom", "R_INF inflation shock: from", "", "O", "", "0")
    kv("SV_inflTo", "R_INF inflation shock: to", "", "O", "", "0")
    kv("SV_inflV", "R_INF inflation shock: extra", "", "O", "Added to inflationRate for the window.", "0.0%")
    kv("SV_incFrom", "R_ICT income impact: from", "", "O", "", "0")
    kv("SV_incTo", "R_ICT income impact: to", "", "O", "", "0")
    kv("SV_incV", "R_ICT income impact: size", "", "O", "−0.2 = salary × 0.8 (also the CPF wage).", "0%")
    kv("SV_expFrom", "R_EXP expense impact: from", "", "O", "", "0")
    kv("SV_expTo", "R_EXP expense impact: to", "", "O", "", "0")
    kv("SV_expV", "R_EXP expense impact: size", "", "O", "Scales spend, instalment and goal withdrawals.", "0%")
    kv("SV_crashOn", "crash on", '=SV_crashV<>""', "C", "")
    kv("SV_crashYr", "crash year (SV)", "=MAX(1,N(SV_crashY)+1)", "C", "", "0")
    kv("SV_crashF", "crash factor", "=1-ABS(N(SV_crashV))", "C", "", "0.0000")
    kv("SV_ccyOn", "currency on", '=SV_ccyV<>""', "C", "")
    kv("SV_ccyYr", "currency year (SV)", "=MAX(1,N(SV_ccyY)+1)", "C", "", "0")
    kv("SV_ccyF", "currency factor", "=1-ABS(N(SV_ccyV))*SV_fxShare", "C", "", "0.0000")
    for key, label in (("infl", "inflation"), ("inc", "income"), ("exp", "expense")):
        kv(f"SV_{key}On", f"{label} on", f'=SV_{key}V<>""', "C", "")
        kv(f"SV_{key}S", f"{label} first year (SV)", f"=MAX(1,N(SV_{key}From)+1)", "C", "", "0")
        kv(f"SV_{key}E", f"{label} last year (SV)", f"=MAX(SV_{key}S,N(SV_{key}To)+1)", "C", "", "0")
    kv("SV_inflRate", "shock inflation rate", "=inflationRate+ABS(N(SV_inflV))", "C", "", "0.00%")
    kv("SV_incImp", "income impact", "=IF(N(SV_incV)<=0,N(SV_incV),-ABS(N(SV_incV)))", "C", "", "0.0%")
    kv("SV_expImp", "expense impact", "=ABS(N(SV_expV))", "C", "", "0.0%")
    kv("SV_lonV", "R_LON longevity: on (TRUE / blank)", "", "O", "Chart horizon to LON_AGE (99). SV already runs the path to 100.")
    kv("SV_lonOn", "R_LON on", "=SV_lonV=TRUE", "C", "")
    kv("SV_end", "chart horizon (age)", "=IF(SV_lonOn,LON_AGE,PLU_leUsed)", "C", "Session life expectancy, or LON_AGE under R_LON.", "0")
    for k, K, lab in (("dea", "R_DEA", "death"), ("cri", "R_CRI", "critical illness"), ("tpd", "R_TPD", "TPD"),
                      ("pac", "R_PAC", "personal accident"), ("hos", "R_HOS", "hospitalisation"),
                      ("ltc", "R_LTC", "long-term care"), ("wed", "R_WED", "wedding"), ("bab", "R_BAB", "newborn")):
        kv(f"SV_{k}V", f"{K} {lab}: on (TRUE / blank)", "", "O", f"Size and timing from Assumptions ({K}_SIZE, {K}_WHEN).")
        kv(f"SV_{k}On", f"{K} on", f"=SV_{k}V=TRUE", "C", "")
        if k in ("wed", "bab"):
            kv(f"SV_{k}M", f"{K} engine year", f"=MAX(1,N({K}_WHEN)+1)", "C", "Years from today; SV applies at year + 1.", "0")
        elif k == "ltc":
            kv("SV_ltcM", "R_LTC first year", "=MAX(1,NC_ltcStartAge-SV_age)", "C", "LTC start age (Need Calculator input).", "0")
            kv("SV_ltcE", "R_LTC last year", "=MAX(SV_ltcM,PLU_leUsed-SV_age-1)", "C", "Last year before the session life expectancy (same years as N_LTC).", "0")
        else:
            kv(f"SV_{k}M", f"{K} engine year", f"=MAX(1,{K}_WHEN-SV_age)", "C", "Age-based; if already older, next year.", "0")
        kv(f"SV_{k}Amt", f"{K} cost (user currency)", f"={K}_SIZE/FX_usdPerLocal", "C", "USD size ÷ rate. Grown with the spend index.", "#,##0")

    # CPF tables (right of the form)
    _fill(ws, "H4", "D · SV CPF TABLES  —  SocialSecurityR_SGP (by age at contribution)", font=h_font, fill=assume_hdr, align=center)
    ws.merge_cells("H4:N4")
    for i, h in enumerate(["from age", "to age", "total rate", "employee rate", "OA share", "SA share", "MA share"]):
        _fill(ws, f"{get_column_letter(8 + i)}5", h, font=h_font, fill=header_fill, align=center)
    lowers = (0, 36, 46, 51, 56, 61, 66, 71)
    tops = (35, 45, 50, 55, 60, 65, 70, 999)
    for i in range(8):
        rr = 6 + i
        vals = [lowers[i], tops[i], _band(tops[i], CPF_TOTAL), _band(tops[i], CPF_EMP), CPF_OA[i], CPF_SA[i], CPF_MA[i]]
        for j, v in enumerate(vals):
            _fill(ws, f"{get_column_letter(8 + j)}{rr}", v, fill=assume_fill, align=center,
                  num="0" if j < 2 else "0.00%")
    for key, col in (("Lower", "H"), ("Tot", "J"), ("Emp", "K"), ("OA", "L"), ("SA", "M"), ("MA", "N")):
        _name(wb, f"SV_cpf{key}", f"'Scenario Visualizer'!${col}$6:${col}$13")
    _fill(ws, "H15", "D · CPF LIFE  —  BRS and monthly payout by (55 − age)+ + year − 2023", font=h_font, fill=assume_hdr, align=center)
    ws.merge_cells("H15:L15")
    for i, h in enumerate(["row", "BRS", "payout × 1", "payout × 2", "payout × 3"]):
        _fill(ws, f"{get_column_letter(8 + i)}16", h, font=h_font, fill=header_fill, align=center)
    for i in range(5):
        rr = 17 + i
        vals = [i, BRS[i], *CPF_LIFE_PAY[i]]
        for j, v in enumerate(vals):
            _fill(ws, f"{get_column_letter(8 + j)}{rr}", v, fill=assume_fill, align=center, num="#,##0")
    _name(wb, "SV_brsTbl", "'Scenario Visualizer'!$I$17:$I$21")
    _name(wb, "SV_payTbl", "'Scenario Visualizer'!$J$17:$L$21")

    keys = [
        "m", "age", "year", "in",
        "F", "C", "incF", "sal", "spend", "evt", "prem", "invNeg",
        "crashF", "ccyF", "cash", "inv", "home",
        "band", "ow", "oaRaw", "saRaw", "maRaw", "emp", "oa", "sa", "ma", "pay", "ra", "life", "cpf", "cpfCf",
        "loan", "savPre", "wPre", "spPre",
        "retC", "retAcc", "goalC", "goalAcc", "protP", "pot", "insCf", "savPost", "wPost", "spPost",
    ]
    c = _Cols(keys)
    top = r + 38  # room for the two sections below (+2 V0-14 spendable, +1 V0-18 horizon)
    first, last = top + 1, top + YEAR_ROWS

    def rng(k: str) -> str:
        return c.rng(k, first, last)

    # CPF payout-age scalars need the year table, so they sit after it is laid out.
    r += 1
    r = _section(ws, r, "C · CPF AT PAYOUT AGE  —  numpy indexing as SV runs it (negative index counts from the end)", calc_hdr)
    sp_note = "Past age 66 the payout index is negative, so SV wraps RA into year 0 (Discrepancies)."
    kv("SV_cpfOn", "CPF on", '=SV_residency<>"Foreigner"', "C", "sv_payload.py: region R_SGP unless Foreigner (not the CPF tab country switch).")
    kv("SV_asp", "payout age", "=MAX(65,SV_ret)", "C", "ageStartPayout.", "0")
    kv("SV_stop", "contribution stop index", "=MIN(70,SV_ret)-SV_age+1", "C", "Contributions zero from here.", "0")
    kv("SV_sp", "payout index", "=SV_asp-SV_age+1", "C", sp_note, "0")
    eff = "IF({k}>=0,MIN({k},SV_L),MAX(0,SV_L+({k})))"
    kv("SV_effStop", "contributions zero from (effective)", "=" + eff.format(k="SV_stop"), "C", "", "0")
    kv("SV_effNeg", "employee CPF zero from (effective)", "=" + eff.format(k="SV_stop-1"), "C", "", "0")
    kv("SV_sIdx", "payout column (effective)", "=" + eff.format(k="SV_sp"), "C", "", "0")
    kv("SV_pIdx", "column before payout (effective)", "=" + eff.format(k="SV_sp-1"), "C", "", "0")
    kv("SV_brsIdx", "BRS row", "=MAX(55-SV_age,0)+currentYear-2023", "C", "", "0")
    kv("SV_brs", "BRS at payout age",
       "=IF(SV_brsIdx<5,INDEX(SV_brsTbl,SV_brsIdx+1),INDEX(SV_brsTbl,5)*(1+SV_brsGrowth)^(SV_brsIdx-4))*(1+SV_brsGrowth)^(SV_asp-55)",
       "C", "", "#,##0")
    kv("SV_raS", "RA at payout (before CPF LIFE)",
       f"=INDEX({rng('oa')},SV_pIdx+1)+INDEX({rng('sa')},SV_pIdx+1)+MAX(INDEX({rng('maRaw')},SV_pIdx+1)-SV_maCap,0)",
       "C", "OA + SA + MA above the cap, one column before payout.", "#,##0")
    kv("SV_mult", "BRS multiple (max 3)", "=IF(SV_brs>0,MIN(3,INT(SV_raS/SV_brs)),0)", "C", "", "0")
    kv("SV_wd", "CPF LIFE premium (withdrawn from RA)", "=IF(SV_mult<=0,0,SV_brs*SV_mult)", "C", "", "#,##0")
    kv("SV_pay", "CPF LIFE monthly payout",
       "=IF(SV_mult<=0,0,IF(SV_brsIdx<5,INDEX(SV_payTbl,SV_brsIdx+1,SV_mult),"
       "INDEX(SV_payTbl,5,SV_mult)*(1+SV_brsGrowth)^(SV_brsIdx-4))*(1+SV_deferBonus*(SV_asp-65)))",
       "C", "", "#,##0.00")
    kv("SV_L0", "CPF LIFE pot at payout column", "=SV_lifeGrowth*(SV_wd-12*SV_pay)", "C", "", "#,##0")
    kv("SV_R0", "RA at payout column", "=SV_lifeGrowth*(SV_raS-SV_wd)", "C", "", "#,##0")
    kv("SV_n1", "wrap steps (payout index < 0)", "=MAX(0,-SV_sp-1)", "C", "SV's loop starts at a negative year.", "0")
    kv("SV_seedLife", "CPF LIFE carried into year 0 (wrap)",
       "=SV_L0*SV_lifeGrowth^SV_n1-12*SV_pay*SV_lifeGrowth*(SV_lifeGrowth^SV_n1-1)/(SV_lifeGrowth-1)", "C", "", "#,##0")
    kv("SV_seedRA", "RA carried into year 0 (wrap)", "=SV_R0*SV_lifeGrowth^SV_n1", "C", "", "#,##0")

    r += 1
    r = _section(ws, r, "C · RESULTS  —  wealth (pre = today, post = with the plan)", calc_hdr)
    for lab, col, nm in (("pre", "wPre", "Pre"), ("post", "wPost", "Post")):
        for a in (65, 85):
            kv(f"SV_w{nm}{a}", f"{lab} wealth at age {a}",
               f'=IF(AND({a}-SV_age>=0,{a}-SV_age<=SV_T),INDEX({rng(col)},{a}-SV_age+1),"")', "C", "", "#,##0")
    kv("SV_wPreEnd", "pre wealth at horizon", f'=IF(SV_end-SV_age<=SV_T,INDEX({rng("wPre")},MAX(0,SV_end-SV_age)+1),"")', "C", "endAge, or 99 under R_LON.", "#,##0")
    kv("SV_wPostEnd", "post wealth at horizon", f'=IF(SV_end-SV_age<=SV_T,INDEX({rng("wPost")},MAX(0,SV_end-SV_age)+1),"")', "C", "", "#,##0")
    kv("SV_spPostEnd", "post spendable at horizon", f'=IF(SV_end-SV_age<=SV_T,INDEX({rng("spPost")},MAX(0,SV_end-SV_age)+1),"")', "C",
       "Below 0 = liquid money runs out before the horizon.", "#,##0")
    for lab, col, nm in (("pre", "spPre", "Pre"), ("post", "spPost", "Post")):
        kv(f"SV_spOut{nm}", f"{lab}: first age spendable wealth < 0",
           f'=IFERROR(SV_age+MATCH(1,INDEX(--({rng(col)}<0),0),0)-1,"never")', "C",
           "Expense-funding panel: shortfall starts here even if the chart line is above 0.", "0")
    _bind(wb, "Scenario Visualizer", names)

    assert r + 2 <= top - 1, "year table overlaps the form"
    m = lambda rr: c("m", rr)  # noqa: E731
    live = lambda rr: f"OR({m(rr)}<1,{m(rr)}>SV_T)"  # noqa: E731
    prev = lambda k, rr: c(k, rr - 1)  # noqa: E731
    money, pct = "#,##0", "0.0000"

    def band(k: str, rr: int) -> str:
        return f"INDEX(SV_cpf{k},{c('band', rr)})"

    def acc(k: str, share: str, rate: str):
        return lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{prev(k, rr)}*(1+{rate})+IF({m(rr)}>=SV_effStop,0,"
            f"{band(share, rr)}*{band('Tot', rr)}*{c('ow', rr)}))"
        )

    specs = [
        ("m", "year", paper_fill, None, lambda rr: rr - first, "0"),
        ("age", "age", paper_fill, None, lambda rr: f"=SV_age+{m(rr)}", "0"),
        ("year", "calendar", paper_fill, None, lambda rr: f"=currentYear+{m(rr)}", "0"),
        ("in", "on path", paper_fill, None, lambda rr: f"={m(rr)}<=SV_T", None),
        ("F", "inflation factor", calc_fill, 1, lambda rr: (
            f"=IF(AND(SV_inflOn,{m(rr)}>=SV_inflS,{m(rr)}<=SV_inflE),1+SV_inflRate,1+inflationRate)"), pct),
        ("C", "spend index", calc_fill, 1, lambda rr: f"=IF({m(rr)}<=1,1,{prev('C', rr)}*{c('F', rr)})", pct),
        ("incF", "income factor", calc_fill, 1, lambda rr: (
            f"=IF(AND(SV_incOn,{m(rr)}>=SV_incS,{m(rr)}<=SV_incE),1+SV_incImp,1)"), pct),
        ("sal", "salary", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{m(rr)}-1>=SV_salCut,AND(SV_deaOn,{m(rr)}>=SV_deaM)),0,SV_sal0*(1+incomeGrowthRate)^({m(rr)}-1)*{c('incF', rr)})"), money),
        ("spend", "spend + instalment + goals", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,(-SV_exp0*{c('C', rr)}-IF({m(rr)}<=SV_loanYears,SV_inst,0)"
            + "".join(f"-IF(AND(SV_wd{g}Amt>0,{m(rr)}=SV_wd{g}Year),SV_wd{g}Amt,0)" for g in ("EDU", "SAV", "PRP")) + ")"
            f"*IF(AND(SV_expOn,{m(rr)}>=SV_expS,{m(rr)}<=SV_expE),1+SV_expImp,1))"), money),
        ("evt", "stress events cost", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,-{c('C', rr)}*("
            + "+".join(f"IF(AND(SV_{k}On,{m(rr)}=SV_{k}M),SV_{k}Amt,0)" for k in ("dea", "cri", "tpd", "pac", "hos", "wed", "bab"))
            + f"+IF(AND(SV_ltcOn,{m(rr)}>=SV_ltcM,{m(rr)}<=SV_ltcE),SV_ltcAmt,0)))"), money),
        ("prem", "existing life premium", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{m(rr)}>SV_loanYears),0,-SV_lifePremYr)"), money),
        ("invNeg", "to investments", calc_fill, 0, lambda rr: f"=IF({live(rr)},0,-SV_contrib)", money),
        ("crashF", "crash", calc_fill, 1, lambda rr: f"=IF(AND(SV_crashOn,{m(rr)}=SV_crashYr),SV_crashF,1)", pct),
        ("ccyF", "currency", calc_fill, 1, lambda rr: f"=IF(AND(SV_ccyOn,{m(rr)}=SV_ccyYr),SV_ccyF,1)", pct),
        ("cash", "cash", calc_fill, "=" + _round_even("SV_cash"), lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{prev('cash', rr)}*(1+interestRate)*{c('crashF', rr)}*{c('ccyF', rr)})"), money),
        ("inv", "investments", calc_fill, "=" + _round_even("SV_investments"), lambda rr: (
            f"=IF({m(rr)}>SV_T,0,({prev('inv', rr)}+SV_contrib)*(1+investmentReturn)*{c('crashF', rr)}*{c('ccyF', rr)})"), money),
        ("home", "home", calc_fill, "=" + _round_even("SV_property"), lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{prev('home', rr)}*(1+SV_propRate)*{c('crashF', rr)})"), money),
        ("band", "CPF band", calc_fill, "", lambda rr: f"=MATCH(SV_age+{m(rr)}-1,SV_cpfLower,1)", "0"),
        ("ow", "CPF wage", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},NOT(SV_cpfOn),AND(SV_deaOn,{m(rr)}>=SV_deaM)),0,MIN(SV_sal0*(1+incomeGrowthRate)^({m(rr)}-1)*{c('incF', rr)},SV_owCap))"), money),
        ("oaRaw", "OA (running)", calc_fill, 0, acc("oaRaw", "OA", "SV_oaRate"), money),
        ("saRaw", "SA (running)", calc_fill, 0, acc("saRaw", "SA", "SV_saRate"), money),
        ("maRaw", "MA (running)", calc_fill, 0, acc("maRaw", "MA", "SV_saRate"), money),
        ("emp", "employee CPF", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{m(rr)}>=SV_effNeg),0,-({band('OA', rr)}+{band('SA', rr)}+{band('MA', rr)})"
            f"*{band('Emp', rr)}*{c('ow', rr)})"), money),
        ("oa", "OA", calc_fill, None, lambda rr: f"=IF({m(rr)}>=SV_sIdx,0,{c('oaRaw', rr)})", money),
        ("sa", "SA", calc_fill, None, lambda rr: f"=IF({m(rr)}>=SV_sIdx,0,{c('saRaw', rr)})", money),
        ("ma", "MA", calc_fill, None, lambda rr: f"=IF({m(rr)}>=SV_sIdx,MIN({c('maRaw', rr)},SV_maCap),{c('maRaw', rr)})", money),
        ("pay", "CPF LIFE payout", calc_fill, None, lambda rr: (
            f"=IF(AND(SV_cpfOn,{m(rr)}>=SV_pIdx,{m(rr)}<=SV_T),12*SV_pay,0)"), money),
        ("ra", "RA", calc_fill, "=IF(SV_sp>=0,IF(SV_sIdx=0,SV_R0,0),SV_lifeGrowth*SV_seedRA)", lambda rr: (
            f"=IF({m(rr)}>SV_T,0,IF(SV_sp>=0,IF({m(rr)}<SV_sIdx,0,IF({m(rr)}=SV_sIdx,SV_R0,"
            f"SV_lifeGrowth*{prev('ra', rr)})),SV_lifeGrowth*{prev('ra', rr)}))"), money),
        ("life", "CPF LIFE pot", calc_fill, None, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,IF(AND(SV_sp>=0,{m(rr)}<SV_sIdx),0,IF(AND(SV_sp>=0,{m(rr)}=SV_sIdx),SV_L0,"
            f"SV_lifeGrowth*({prev('life', rr) if rr > first else 'SV_seedLife'}-{c('pay', rr)}))))"), money),
        ("cpf", "CPF total", calc_fill, None, lambda rr: (
            f"={c('oa', rr)}+{c('sa', rr)}+{c('ra', rr)}+{c('ma', rr)}+IF({c('ra', rr)}<0,0,{c('life', rr)})"), money),
        ("cpfCf", "CPF cash flow", calc_fill, None, lambda rr: f"={c('pay', rr)}+{c('emp', rr)}", money),
        ("loan", "mortgage balance (annuity → 0 at year 20)", calc_fill, "=IF(SV_mortP>0,SV_mortP,0)", lambda rr: (
            f"=IF(OR({m(rr)}>SV_T,{m(rr)}>=SV_loanYears),0,MAX(0,{prev('loan', rr)}*(1+loanRate)-SV_inst))"), money),
        ("savPre", "savings (pre)", calc_fill, 0, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{prev('savPre', rr)}*(1+SV_savRate)+{c('sal', rr)}+{c('spend', rr)}+{c('evt', rr)}+{c('prem', rr)}"
            f"+{c('invNeg', rr)}+{c('cpfCf', rr)})"), money),
        ("wPre", "WEALTH pre", green_fill, None, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,MAX(0,{c('cash', rr)}+{c('inv', rr)}+{c('home', rr)}+{c('cpf', rr)}"
            f"+{c('savPre', rr)}-{c('loan', rr)}))"), money),
        ("spPre", "SPENDABLE pre", green_fill, None, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{c('cash', rr)}+{c('inv', rr)}+{c('savPre', rr)}"
            f"-MAX(0,{c('loan', rr)}-({c('home', rr)}+{c('cpf', rr)})))"), money),
        ("retC", "RET paid in", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{m(rr)}-1>=SV_retPay),0,SV_retMth*12+IF({m(rr)}=1,SV_retLump,0))"), money),
        ("retAcc", "RET pot", calc_fill, 0, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,({prev('retAcc', rr)}+{c('retC', rr)})*(1+investmentReturn))"), money),
        ("goalC", "goal pots paid in", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,"
            + "+".join(f"IF({m(rr)}-1>=SV_{g}Pay,0,SV_{g}Mth*12+IF({m(rr)}=1,SV_{g}Lump,0))" for g in ("EDU", "SAV", "PRP")) + ")"), money),
        ("goalAcc", "goal pots", calc_fill, 0, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,({prev('goalAcc', rr)}+{c('goalC', rr)})*(1+investmentReturn))"), money),
        ("protP", "protection premium", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{m(rr)}-1>=SV_protPay),0,SV_protPrem)"), money),
        ("pot", "plan account value", calc_fill, None, lambda rr: (
            f"=IF(OR({m(rr)}=0,{m(rr)}>=SV_T),0,ROUND(MAX(0,{c('retAcc', rr)}),2)+ROUND(MAX(0,{c('goalAcc', rr)}),2))"), money),
        ("insCf", "plan cash flow", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,-({c('retC', rr)}+{c('goalC', rr)}+{c('protP', rr)})"
            f"+IF({m(rr)}=SV_T,ROUND(MAX(0,{c('retAcc', rr)}),2)+ROUND(MAX(0,{c('goalAcc', rr)}),2),0))"), money),
        ("savPost", "savings (post)", calc_fill, 0, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{prev('savPost', rr)}*(1+SV_savRate)+{c('sal', rr)}+{c('spend', rr)}+{c('evt', rr)}+{c('prem', rr)}"
            f"+{c('invNeg', rr)}+{c('cpfCf', rr)}+{c('insCf', rr)})"), money),
        ("wPost", "WEALTH post", green_fill, None, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,MAX(0,{c('cash', rr)}+{c('inv', rr)}+{c('home', rr)}+{c('cpf', rr)}"
            f"+{c('savPost', rr)}+{c('pot', rr)}-{c('loan', rr)}))"), money),
        ("spPost", "SPENDABLE post", green_fill, None, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{c('cash', rr)}+{c('inv', rr)}+{c('savPost', rr)}+{c('pot', rr)}"
            f"-MAX(0,{c('loan', rr)}-({c('home', rr)}+{c('cpf', rr)})))"), money),
    ]
    groups = [
        ("year", "m", "in", header_fill),
        ("C · HUMAN CAPITAL  —  salary, spend, premiums (flows land in the year shown)", "F", "invNeg", calc_hdr),
        ("C · ASSETS", "crashF", "home", calc_hdr),
        ("C · CPF  —  SocialSecurityR_SGP", "band", "cpfCf", calc_hdr),
        ("C · PRE (today)", "loan", "spPre", calc_hdr),
        ("C · POST (with the plan)  —  plan_benefit_visualizer pots", "retC", "spPost", calc_hdr),
    ]
    _write_year_table(ws, top, specs, c, groups)
    _grey_rows(ws, first, last, c.letter["spPost"], c.letter["in"], c.letter["age"])
    for k in ("wPre", "wPost", "spPre", "spPost", "cpf", "savPre", "savPost", "sal", "spend", "evt", "cash", "inv", "home", "loan", "pot", "insCf"):
        _name(wb, f"SV_Y_{k}", f"'Scenario Visualizer'!{rng(k)}")
    _dash_widths(ws)
    for k, L in c.letter.items():
        if k not in ("m", "age", "year", "in") and L not in ("A", "B", "C", "D"):
            ws.column_dimensions[L].width = 14
    _widths(ws, {"F": 42, "H": 12, "I": 12})


HU_W_PATH = ("N_INC", "N_RET")  # scored on wealth; the rest on consumption wealth
HU_PRIORITY_FLOOR = ("N_INC", "N_RET", "N_CRI")


def build_hu(wb: Workbook) -> None:
    ws = wb.create_sheet("HappiU")
    ws.sheet_properties.tabColor = "7A3E9D"
    _add_selector(
        ws,
        master=False,
        title="HappiU — selected persona. Deterministic HU score: expected values weighted by survival, on HU's cashflow rules.",
    )
    _legend(ws, "F", 2)
    names: dict[str, int] = {}
    r = 4

    def kv(name: str, label: str, value, kind: str, note: str = "", num=None) -> None:
        nonlocal r
        r = _kv(ws, r, label, value, kind, note, num)
        names[name] = r - 1

    r = _section(ws, r, "A · INPUT DATA  —  effective session (what hu_payload.py sends)", input_hdr)
    kv("HU_age", "age", f"={_px('C')}", "A", "Personas C. HU needs 18–83.", "0")
    kv("HU_gender", "gender", f"={_px('D')}", "A", "Personas D. Picks the q(age) column.")
    kv("HU_smoker", "is smoker", f"={_px('U')}", "A", "Personas U.")
    kv("HU_income", "incomeMonthly", "=PLU_incomeMonthly", "A", "", "#,##0.00")
    kv("HU_expense", "expenseMonthly", "=PLU_expenseMonthly", "A", "", "#,##0.00")
    kv("HU_cash", "cash", "=PLU_cash", "A", "A_SAV. HU starts savings at 1 when cash is 0.", "#,##0")
    kv("HU_inv", "investments", "=PLU_investments", "A", "A_INV. Deterministic growth e^(mu·t).", "#,##0")
    kv("HU_lifeSum", "life sum assured", "=PLU_lifeSum", "A", "N_INC existing cover.", "#,##0")
    kv("HU_leS", "session life expectancy", "=MIN(PLU_leUsed,LON_AGE)", "A", "Sent by GP, capped at LON_AGE (99).", "0")

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS  —  HU conf.json / config/default/conf.ini / hu_payload.py", assume_hdr)
    kv("HU_ret", "ageOfRetirement", "=ageOfRetirement", "D", "", "0")
    kv("HU_defaultLE", "default life expectancy", "=lifeExpectancyDefault", "D", "V0-21: GP sends the one default (85); was HU 83.", "0")
    kv("HU_ciYearsGP", "CI income years (N_CRI on)", "=CRI_YEARS", "D", "numYearsIncomeNeeded from GP.", "0")
    kv("HU_ciDefaultYears", "CI income years (N_CRI off)", 5, "D", "HU ciAssumptions default.", "0")
    kv("HU_medCost", "CI medical cost (sent: CRI_COST)", "=CRI_COST/FX_usdPerLocal", "D", "V0-21: GP sends CRI_COST in user currency; was HU 200,000.", "#,##0")
    kv("HU_tpdCost", "TPD medical cost (sent: TPD_COST)", "=TPD_COST/FX_usdPerLocal", "D", "V0-21: GP sends TPD_COST in user currency; was HU 444,000.", "#,##0")
    kv("HU_tpdCut", "TPD income cut", 0.5, "D", "", "0%")
    kv("HU_disCut", "dismemberment income cut", 1.0, "D", "From the year after.", "0%")
    kv("HU_ciMaxAge", "cover age (off-plan CI / TPD / HSP)", 75, "D", "Off-plan protection runs to age 75.", "0")
    kv("HU_depYears", "dependent years (N_INC)", 10, "D", "numYearDependents default.", "0")
    kv("HU_term", "plan policy term", 10, "D", "segregatedBudget policyTerm in hu_payload.py.", "0")
    kv("HU_whl", "wealth high-loss factor", 0.25, "D", "conf.ini wealth_hight_loss_factor.", "0.00")
    kv("HU_beta", "beta", 1, "D", "conf.ini beta.", "0.00")
    kv("HU_minMu", "minimum equity drift", 0.01, "D", "ProductEquity mu floor.", "0.00%")
    kv("HU_riskProfile", "riskProfile", 4, "D", "hu_payload.py default.", "0")
    kv("HU_retLifestyle", "retirement lifestyle rate", "=RET_LIFESTYLE_STRESSFREE", "D", "N_RET lifestyle 2.", "0.00")
    kv("HU_retShare", "retirement spend share", 0.75, "D", "expectedLivingExpenseInTheCountry = living × 0.75.", "0.00")
    kv("HU_benefitRound", "benefit round (user currency)", "=FX_benefitRound", "D", "benefitRound (USD) as a nice step in user currency. SGD: 50,000.", "#,##0")
    kv("HU_calRet", "N_RET calibration", 2, "D", "N_INC 1, N_RET 2, consumption goals 1 / count.", "0")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  HU input mapping", calc_hdr)
    kv("HU_le", "life expectancy (HU)", "=IF(HU_leS>HU_ret,HU_leS,HU_defaultLE)", "C", "durationOfRetirement + 65, or the default (85).", "0")
    kv("HU_T", "years on the path (T)", "=MAX(HU_le-HU_age,0)", "C", "", "0")
    kv("HU_dtr", "years to retirement", "=MAX(HU_ret-HU_age,0)", "C", "", "0")
    kv("HU_col", "q(age) column", '=IF(HU_gender="Male",1,3)+IF(HU_smoker=TRUE,1,0)',
       "C", "1 Male, 2 Male smoker, 3 Female, 4 Female smoker.", "0")
    kv("HU_inc0", "income / yr (HU)", "=1+HU_income*12", "C", "HU adds 1 to the salary.", "#,##0")
    kv("HU_exp0", "spend / yr", "=HU_expense*12", "C", "", "#,##0")
    kv("HU_retExp", "retirement spend / yr", "=HU_exp0*HU_retLifestyle*HU_retShare", "C", "Replaces spend after retirement.", "#,##0")
    kv("HU_ciYears", "CI income years", "=IF(NC_on_N_CRI,HU_ciYearsGP,HU_ciDefaultYears)", "C", "", "0")
    kv("HU_ciProp", "CI income share", "=MAX(0,MIN(1,HU_exp0/HU_inc0))", "C", "Share of income lost while ill.", "0.0000")
    kv("HU_cash0", "savings at t = 0", "=IF(N(HU_cash)=0,1,HU_cash)", "C", "", "#,##0")
    kv("HU_mu", "equity drift", "=IF(HU_inv>0,MAX(HU_minMu,investmentReturn),0)", "C", "", "0.00%")
    kv("HU_nanEquity", "HU errors (retiree with investments)", "=AND(HU_inv>0,HU_dtr=0)",
       "C", "Live HU returns NaN here; this tab still scores (Discrepancies).")
    kv("HU_alpha", "alpha", "=1+(HU_riskProfile-1)*0.5", "C", "Value-function curvature from riskProfile.", "0.00")
    for g, yrs in (("EDU", "NC_eduYears"), ("SAV", "NC_savYears"), ("PRP", "NC_prpYears")):
        kv(f"HU_wd{g}On", f"N_{g} withdrawal on the path", f"=AND(HU_T>0,{yrs}<=HU_T)", "C", "V0-24: own target year.")
        kv(f"HU_wd{g}Year", f"N_{g} withdrawal year", f"=IF(HU_T>0,MOD({yrs}-1,HU_T)+1,0)", "C", "fundsNeededYear − now.", "0")
        kv(f"HU_wd{g}Amt", f"N_{g} amount", f"=NC_on_N_{g}*NC_amount_N_{g}", "C",
           "SAV / PRP: booked as income in the target year and spent again (net 0). EDU: spent.", "#,##0")

    # Layout: year table below the form, goal table to the right of the form.
    base_keys = [
        "t", "age", "in", "qm", "qa", "qc", "qp", "qd", "S", "survW", "noPtd", "pPtd", "pPtdF", "noDis", "pDis",
        "ciCum", "pCi", "infl", "x", "ssG", "ss", "base", "cut", "pos", "spend", "neg", "med", "sav", "eq", "W", "Cw",
    ]
    goal_keys = [f"{p}_{t}" for t in UNIFIED for p in ("wt", "vp", "vr", "vf")]
    c = _Cols(base_keys + goal_keys)
    top = r + 13
    first, last = top + 1, top + YEAR_ROWS

    def rng(k: str) -> str:
        return c.rng(k, first, last)

    gcols = [
        "type", "code", "in list", "need", "existing", "in plan", "benefit", "priority", "duration", "D", "path",
        "w0", "whl", "v(0)", "U base", "U pre", "U rec", "U full", "denominator", "pre", "post", "flag",
        "log priority", "calibration", "weight",
    ]
    g = _Cols(gcols, first_col=column_index_from_string("H"))
    g_hdr, g0 = 5, 6
    g1 = g0 + len(UNIFIED) - 1
    _fill(ws, "H4", "C · GOALS  —  enabled needs plus N_RET (GP always sends it)", font=h_font, fill=calc_hdr, align=center)
    ws.merge_cells(f"H4:{g.letter['weight']}4")
    for k in gcols:
        _fill(ws, g(k, g_hdr), k, font=h_font, fill=header_fill, align=center)

    def gc(k: str, gr: int) -> str:
        col = g.letter[k]
        return f"${col}${gr}"

    def vfn(w: str, gr: int) -> str:
        n, w0, whl = gc("need", gr), gc("w0", gr), gc("whl", gr)
        return (
            f"IF({w}>{w0}/HU_alpha+{n},0.5*{w0}/HU_alpha,IF({w}>={n},({w}-{n})-0.5*HU_alpha/{w0}*({w}-{n})^2,"
            f"IF({w}>={whl},HU_beta*({w}-{n}),HU_beta*({whl}-{n}))))"
        )

    grow = {}
    for i, t in enumerate(UNIFIED):
        gr = g0 + i
        grow[t] = gr
        on = gc("in list", gr)
        need, plan_ok = gc("need", gr), gc("in plan", gr)
        is_w = t in HU_W_PATH
        cells = {
            "type": t,
            "code": "N_HSP" if t == "N_HOS" else t,
            "in list": "=TRUE" if t == "N_RET" else f"=NC_on_{t}",
            "need": ("=IF(NC_on_N_RET,NC_amount_N_RET,HU_expense*12*MAX(0,HU_leS-HU_ret))" if t == "N_RET"
                     else f"=NC_amount_{t}"),
            "existing": "=HU_lifeSum" if t == "N_INC" else 0,
            "in plan": f"=NOT(AND(PLAN_sug_{t},NOT(PLAN_included_{t})))",
            "benefit": (
                f"=IF(NOT({plan_ok}),0,IF(PLAN_sug_{t},MAX(0,PLAN_sum_{t}),MAX(0,ROUND({need}/HU_benefitRound,0)*HU_benefitRound)))"
                if t in PROT else
                f"=IF(NOT({plan_ok}),0,MAX(0,ROUND({need}/HU_benefitRound,0)*HU_benefitRound))"
            ),
            "priority": "=IF(NC_on_N_RET,NP_priority_N_RET,5)" if t == "N_RET" else f"=NP_priority_{t}",
            "duration": {
                "N_INC": f"=IF({plan_ok},MIN(HU_term,HU_depYears),HU_depYears)+1",
                "N_RET": "=MAX(0,HU_ret-HU_age)",
            }.get(t, f"=IF({plan_ok},HU_term,HU_ciMaxAge-HU_age)+1" if t in PROT else
                  {"N_EDU": "=MAX(0,NC_eduYears)", "N_SAV": "=MAX(0,NC_savYears)", "N_PRP": "=MAX(0,NC_prpYears)"}.get(t, "")),
            "D": f"=MIN({gc('duration', gr)},HU_T)",
            "path": "W" if is_w else "C",
            "w0": f"=INDEX({rng('W')},IF(HU_T>=1,2,1))+{need}" if is_w else f"={need}",
            "whl": f"=HU_whl*{need}",
            "v(0)": f"=IF({gc('w0', gr)}=0,0,{vfn('0', gr)})",
            "U base": f"={gc('v(0)', gr)}*SUM({rng('wt_' + t)})",
            "U pre": f"=SUMPRODUCT({rng('wt_' + t)},{rng('vp_' + t)})",
            "U rec": f"=SUMPRODUCT({rng('wt_' + t)},{rng('vr_' + t)})",
            "U full": f"=SUMPRODUCT({rng('wt_' + t)},{rng('vf_' + t)})",
            "denominator": f"={gc('U full', gr)}-{gc('U base', gr)}",
            "flag": (f'=IF(NOT({on}),"",IF({gc("w0", gr)}=0,"w0 = 0 (HU raises an error)",'
                     f'IF({gc("denominator", gr)}=0,"denominator 0","")))'),
            "log priority": (f"=IF({on},MAX(LN({gc('priority', gr)}+1),LN({1 if t in HU_PRIORITY_FLOOR else 0}+1)),0)"),
            "calibration": (f"=IF({on},1,0)" if t == "N_INC" else f"=IF({on},HU_calRet,0)" if t == "N_RET"
                            else f"=IF({on},1/HU_nCons,0)"),
            "weight": (f"=IF({on},{gc('log priority', gr)}*{gc('calibration', gr)}/"
                       f"SUMPRODUCT({g.rng('log priority', g0, g1)},{g.rng('calibration', g0, g1)}),0)"),
        }
        for pic, u in (("pre", "U pre"), ("post", "U rec")):
            dn, ub, uu = gc("denominator", gr), gc("U base", gr), gc(u, gr)
            cells[pic] = (f'=IF(NOT({on}),"",IF({gc("w0", gr)}=0,1,IF({dn}=0,1,IF(AND({dn}={uu}-{ub},{uu}>0),1,'
                          f"MAX(0,MIN(1,({uu}-{ub})/{dn}))))))")
        for k in gcols:
            v = cells[k]
            num = ("0" if k in ("priority", "duration", "D") else "0.0000" if k in ("pre", "post", "weight", "log priority", "calibration")
                   else None if k in ("type", "code", "in list", "in plan", "path", "flag") else "#,##0")
            fill = header_fill if k == "type" else green_fill if k in ("pre", "post") else calc_fill
            _fill(ws, g(k, gr), v, font=h_font if k == "type" else body_font, fill=fill, num=num, align=center)

    r += 1
    r = _section(ws, r, "C · RESULTS  —  weights, sigmoid, HappiU (0–100)", calc_hdr)
    kv("HU_nGoals", "goals scored", f"=COUNTIF({g.rng('in list', g0, g1)},TRUE)", "C", "", "0")
    kv("HU_nCons", "consumption goals", f'=COUNTIFS({g.rng("in list", g0, g1)},TRUE,{g.rng("path", g0, g1)},"C")',
       "C", "Everything except N_INC / N_ADB / N_RET.", "0")
    kv("HU_sig", "sigmoid divisor", "=1+EXP(-HU_nGoals)", "C", "Weighted sum ÷ (1 + e^(−number of goals)).", "0.0000")
    kv("HU_preRaw", "pre (0–1)", f"=SUMPRODUCT({g.rng('pre', g0, g1)},{g.rng('weight', g0, g1)})/HU_sig", "C", "", "0.0000")
    kv("HU_postRaw", "post (0–1)", f"=SUMPRODUCT({g.rng('post', g0, g1)},{g.rng('weight', g0, g1)})/HU_sig", "C", "", "0.0000")
    kv("HU_preHappiU", "preHappiU", "=ROUND(HU_preRaw*100,0)", "C", "Today's cover.", "0")
    kv("HU_postHappiU", "postHappiU", "=ROUND(HU_postRaw*100,0)", "C", "With the plan's benefits.", "0")
    _bind(wb, "HappiU", names)
    assert r + 2 <= top - 1, "year table overlaps the form"

    t_ = lambda rr: c("t", rr)  # noqa: E731
    live = lambda rr: f"OR({t_(rr)}<1,{t_(rr)}>HU_T)"  # noqa: E731
    prev = lambda k, rr: c(k, rr - 1)  # noqa: E731
    money, prob = "#,##0", "0.000000"

    def q(name: str):
        return lambda rr: f"=IF({live(rr)},0,INDEX(HU_q_{name},HU_age+{t_(rr)}-{HU_AGE0 - 1},HU_col))"

    ss_at = lambda nm, rr: f"INDEX({nm},HU_age+{t_(rr)}-{HU_AGE0 - 1})"  # noqa: E731
    specs = [
        ("t", "year", paper_fill, None, lambda rr: rr - first, "0"),
        ("age", "age", paper_fill, None, lambda rr: f"=HU_age+{t_(rr)}", "0"),
        ("in", "on path", paper_fill, None, lambda rr: f"={t_(rr)}<=HU_T", None),
        ("qm", "q mortality", calc_fill, None, q("mort"), prob),
        ("qa", "q accidental death", calc_fill, None, q("adb"), prob),
        ("qc", "q critical illness", calc_fill, None, q("morb"), prob),
        ("qp", "q TPD", calc_fill, None, q("ptd"), prob),
        ("qd", "q dismemberment", calc_fill, None, q("dis"), prob),
        ("S", "alive", calc_fill, 1, lambda rr: f"=IF({t_(rr)}>HU_T,0,{prev('S', rr)}*(1-{c('qm', rr)})*(1-{c('qa', rr)}))", prob),
        ("survW", "score weight", calc_fill, None, lambda rr: f"=IF({t_(rr)}>=HU_T,0,N({c('S', rr + 1)}))", prob),
        ("noPtd", "no TPD yet", calc_fill, 1, lambda rr: f"={prev('noPtd', rr)}*(1-{c('qp', rr)})", prob),
        ("pPtd", "P(TPD so far)", calc_fill, 0, lambda rr: f"=1-{c('noPtd', rr)}", prob),
        ("pPtdF", "P(first TPD)", calc_fill, 0, lambda rr: f"={prev('noPtd', rr)}*{c('qp', rr)}", prob),
        ("noDis", "no dismemberment", calc_fill, 1, lambda rr: f"={prev('noDis', rr)}*(1-{c('qd', rr)})", prob),
        ("pDis", "P(dismembered before)", calc_fill, 0, lambda rr: f"=1-{prev('noDis', rr)}", prob),
        ("ciCum", "no CI (running)", calc_fill, 1, lambda rr: f"={prev('ciCum', rr)}*(1-{c('qc', rr)})", prob),
        ("pCi", "P(CI in window)", calc_fill, 0, lambda rr: (
            f"=1-{prev('ciCum', rr)}/INDEX({rng('ciCum')},MAX(1,{t_(rr)}-HU_ciYears))"), prob),
        ("infl", "inflation index", calc_fill, None, lambda rr: f"=(1+inflationRate)^{t_(rr)}", "0.0000"),
        ("x", "salary", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{t_(rr)}-1>=HU_dtr),0,HU_inc0*(1+incomeGrowthRate)^{t_(rr)})"), money),
        ("ssG", "ss growth index", calc_fill, 1, lambda rr: (
            f"=IF({t_(rr)}>HU_T,{prev('ssG', rr)},{prev('ssG', rr)}*(1+{ss_at('HU_ssG', rr)}))"), "0.0000"),
        ("ss", "social-security lump", calc_fill, 0, lambda rr: (
            f"=IF(AND(HU_dtr>=1,{t_(rr)}=HU_dtr,{t_(rr)}<=HU_T),MIN({c('x', rr)}*{ss_at('HU_ssC', rr)}/(1-{ss_at('HU_ssC', rr)}),"
            f"{ss_at('HU_ssCap', rr)})*{c('ssG', rr)},0)"), money),
        ("base", "income + lump + SAV/PRP", calc_fill, 0, lambda rr: (
            f"={c('x', rr)}+{c('ss', rr)}"
            + "".join(f"+IF(AND(HU_wd{g}On,{t_(rr)}=HU_wd{g}Year),HU_wd{g}Amt,0)" for g in ("SAV", "PRP"))), money),
        ("cut", "expected income cut", calc_fill, 0, lambda rr: (
            f"=HU_ciProp*{c('pCi', rr)}+HU_tpdCut*{c('pPtd', rr)}+HU_disCut*{c('pDis', rr)}"), "0.0000"),
        ("pos", "income after cut", calc_fill, 0, lambda rr: f"=IF({live(rr)},0,{c('base', rr)}*(1-{c('cut', rr)}))", money),
        ("spend", "spend", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,IF(AND(HU_retExp>0,{t_(rr)}-1>=HU_dtr),HU_retExp,HU_exp0)*{c('infl', rr)})"), money),
        ("neg", "spend + goals", calc_fill, 0, lambda rr: (
            f"=-{c('spend', rr)}"
            + "".join(f"-IF(AND(HU_wd{g}On,{t_(rr)}=HU_wd{g}Year),HU_wd{g}Amt,0)" for g in ("EDU", "SAV", "PRP"))), money),
        ("med", "expected medical", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,-HU_medCost*{c('infl', rr)}*{c('qc', rr)}-HU_tpdCost*{c('infl', rr)}*{c('pPtdF', rr)})"), money),
        ("sav", "savings", calc_fill, "=HU_cash0", lambda rr: (
            f"=IF({t_(rr)}>HU_T,0,{prev('sav', rr)}*(1+interestRate)+{c('pos', rr)}+{c('neg', rr)}+{c('med', rr)})"), money),
        ("eq", "equity", calc_fill, None, lambda rr: f"=IF({t_(rr)}>HU_T,0,HU_inv*EXP(HU_mu*{t_(rr)}))", money),
        ("W", "WEALTH", green_fill, None, lambda rr: f"=IF({t_(rr)}>HU_T,0,MAX(0,{c('eq', rr)}+{c('sav', rr)}))", money),
        ("Cw", "CONSUMPTION WEALTH", green_fill, 0, lambda rr: (
            f"=IF({t_(rr)}>HU_T,0,MAX(0,{c('pos', rr)}-{c('spend', rr)}))"), money),
    ]
    groups = [
        ("year", "t", "in", header_fill),
        ("D · q(age + year) from Assumptions", "qm", "qd", assume_hdr),
        ("C · PROBABILITIES", "S", "pCi", calc_hdr),
        ("C · EXPECTED CASH FLOWS AND PATHS (alive)", "infl", "Cw", calc_hdr),
    ]
    for t in UNIFIED:
        gr = grow[t]
        on, dd = gc("in list", gr), gc("D", gr)
        path = "W" if t in HU_W_PATH else "Cw"
        if t in PROT:
            wt = lambda rr, on=on, dd=dd: f"=IF(AND({on},{t_(rr)}>=1,{t_(rr)}<={dd}-1),{c('survW', rr)},0)"  # noqa: E731
        else:
            wt = lambda rr, on=on, dd=dd: f"=IF(AND({on},{t_(rr)}={dd}),{c('survW', rr)},0)"  # noqa: E731
        specs.append((f"wt_{t}", f"{t} weight", calc_fill, None, wt, prob))
        for key, lab, add in (("vp", "v pre", gc("existing", gr)),
                              ("vr", "v rec", f"{gc('existing', gr)}+{gc('benefit', gr)}"),
                              ("vf", "v full", gc("need", gr))):
            def vf(rr, t=t, gr=gr, add=add, path=path):
                w = f"({c(path, rr)}+{add})"
                return f"=IF(OR({c('wt_' + t, rr)}=0,{gc('w0', gr)}=0),0,{vfn(w, gr)})"
            specs.append((f"{key}_{t}", f"{t} {lab}", calc_fill, None, vf, money))
        groups.append((f"C · {t}  ({'W' if path == 'W' else 'consumption'} path)", f"wt_{t}", f"vf_{t}", calc_hdr))
    _write_year_table(ws, top, specs, c, groups)
    _grey_rows(ws, first, last, c.letter[goal_keys[-1]], c.letter["in"], c.letter["age"])
    for k in ("W", "Cw", "sav", "S", "pos", "spend"):
        _name(wb, f"HU_Y_{k}", f"'HappiU'!{rng(k)}")
    _dash_widths(ws)
    for k, L in c.letter.items():
        if L not in ("A", "B", "C", "D"):
            ws.column_dimensions[L].width = 13
    ws.column_dimensions["F"].width = 42


# ---------------------------------------------------------------------------
# V0-16 dictionary: one code per need (N_), risk (R_) and parameter prefix.
# ---------------------------------------------------------------------------
NEED_DICT = [
    # code, risk, prefix, category, app label, profiler label (key), HappiU code, SV, calculator, parameters, status
    ("N_INC", "R_DEA", "INC", "Protection · calculator", "Income & family protection", "Life Protection (life_protection)",
     "N_INC", "premium", "bequest + mortgage + PV of annual spend over support years",
     "INC_SUPPORT_MIN / MAX / PIVOT_AGE", "Live"),
    ("N_CRI", "R_CRI", "CRI", "Protection · calculator", "Critical illness", "Critical Illness (critical_illness)",
     "N_CRI", "premium", "annuity-due of income for CRI_YEARS + CRI_COST", "CRI_YEARS, CRI_COST", "Live"),
    ("N_TPD", "R_TPD", "TPD", "Protection · calculator", "Total & permanent disability (TPD)", "TPD (JSON key: disability)",
     "N_TPD (HU engine internals still say PTD: rename there)", "premium", "annuity-due of income for TPD_YEARS + TPD_COST", "TPD_YEARS, TPD_COST", "Live"),
    ("N_HOS", "R_HOS", "HOS", "Protection · calculator", "Hospitalisation", "Hospitalization (hospitalization)",
     "N_HSP: GP renames N_HOS → N_HSP in hu_payload.py because the HU engine only knows N_HSP", "premium", "incomeMonthly × HOS_MONTHS", "HOS_MONTHS",
     "Live. Open: one code (N_HOS) in GP and HU"),
    ("N_PAC", "R_PAC", "PAC", "Protection · calculator", "Personal accident (new)", "Personal Accident (personal_accident)",
     "N_PAC (HU engine supports it; GP does not send it yet)", "premium", "annuity-due of income for PAC_YEARS + PAC_COST", "PAC_YEARS, PAC_COST",
     "Agreed V0-18 (Excel). Code and HappiU payload to follow"),
    ("N_ADB", "R_ADB", "ADB", "Protection · candidate", "Accidental death", "none (no profiler label)",
     "N_ADB (HU engine supports it, death-type goal like N_INC)", "—", "not defined yet (proposal: lump like N_INC, paid only on accidental death)",
     "ADB_* (to define)", "Added V0-17 to the dictionary. No calculator, not scored"),
    ("N_LTC", "R_LTC", "LTC", "Protection · calculator", "Long-term care", "none (no profiler label)",
     "not sent (HU engine has no LTC)", "premium", "annuity-due of LTC_COST over care years (LTC start age → life expectancy)",
     "LTC_COST, LTC_START_AGE (front-end input)", "New V0-19. Off unless the customer switches it on"),
    ("N_RET", "R_LON", "RET", "Wealth · calculator", "Private retirement", "Retirement (retirement)",
     "N_RET", "RET pot", "annual spend × lifestyle, grown to retirement, × annuity over years in retirement",
     "RET_LIFESTYLE_FRUGAL / STRESSFREE / ONLYTHEBEST; LON_AGE (R_LON)", "Live. R_LON stress: need re-sized to LON_AGE 99"),
    ("N_EDU", "—", "EDU", "Wealth · calculator", "Child's university education", "Education (education)",
     "N_EDU", "goal pot", "EDU_COST grown at inflation to target year", "EDU_COST, EDU_TARGET_AGE (50)", "Live"),
    ("N_SAV", "—", "SAV", "Wealth · calculator", "Savings goal", "General Savings (general_savings)",
     "N_SAV", "goal pot", "stored amount, else SAV_INCOME_MULT × annual income", "SAV_INCOME_MULT, SAV_TARGET_AGE (40, min 5y)", "Live. No longer swapped with N_PRP"),
    ("N_PRP", "—", "PRP", "Wealth · calculator", "Home purchase", "none (no home-purchase label)",
     "N_PRP", "goal pot", "stored amount, else PRP_INCOME_MULT × annual income", "PRP_INCOME_MULT, PRP_TARGET_AGE (33, min 3y)",
     "Separated from Home Protection. Off unless the customer switches it on"),
    ("N_HOM", "—", "HOM", "Coverage · parked", "Home protection", "Home Protection (home)",
     "—", "—", "no calculator", "—", "Scored and prioritised only"),
    ("N_CAR", "—", "CAR", "Coverage · parked", "Car protection", "Car Protection (motor)",
     "—", "—", "no calculator", "—", "Scored and prioritised only"),
    ("N_TRV", "—", "TRV", "Coverage · parked", "Travel protection", "Travel Protection (travel)",
     "—", "—", "no calculator", "—", "Scored and prioritised only"),
    ("—", "—", "—", "Dropped", "Farewell", "Farewell (farewell)",
     "funeral lump dropped", "—", "—", "funeralLump removed", "Dropped V0-16"),
]
RISK_DICT = [
    # code, old id, label, linked need, kind
    ("R_DEA", "death", "Death", "N_INC", "Need risk"),
    ("R_CRI", "ci", "Critical illness", "N_CRI", "Need risk"),
    ("R_TPD", "tpd", "Total & permanent disability", "N_TPD", "Need risk"),
    ("R_HOS", "hosp", "Hospitalisation", "N_HOS", "Need risk"),
    ("R_PAC", "pa", "Personal accident", "N_PAC", "Need risk"),
    ("R_ADB", "—", "Accidental death", "N_ADB", "Need risk (no stress event yet)"),
    ("R_LON", "— (new V0-18)", "Longevity: live until LON_AGE (99)", "N_RET", "Need risk · stress event"),
    ("R_LTC", "care", "Long-term care", "N_LTC", "Need risk · stress event"),
    ("R_MKT", "crash", "Market crash", "—", "Market event"),
    ("R_CCY", "ccy", "Currency shock", "—", "Market event"),
    ("R_INF", "infl", "Inflation shock", "—", "Market event"),
    ("R_ICT", "inc", "Income cut", "—", "Household event"),
    ("R_EXP", "exp", "Expense shock", "—", "Household event"),
    ("R_WED", "wed", "Wedding / marriage", "—", "Life event"),
    ("R_BAB", "baby", "Newborn", "—", "Life event"),
]
PARAM_DICT = [
    # new, old, need
    ("INC_SUPPORT_MIN", "lifeSupportMin", "N_INC"), ("INC_SUPPORT_MAX", "lifeSupportMax", "N_INC"),
    ("INC_SUPPORT_PIVOT_AGE", "lifeSupportPivotAge", "N_INC"),
    ("CRI_YEARS", "CI_YEARS", "N_CRI"), ("CRI_COST", "CI_COST", "N_CRI"),
    ("TPD_YEARS", "TPD_YEARS", "N_TPD"), ("TPD_COST", "TPD_COST", "N_TPD"),
    ("HOS_MONTHS", "HOSP_MONTHS", "N_HOS"),
    ("PAC_YEARS", "(new)", "N_PAC"), ("PAC_COST", "(new)", "N_PAC"), ("LON_AGE", "(new)", "N_RET · R_LON"),
    ("LTC_COST", "(new)", "N_LTC"), ("LTC_START_AGE", "(new)", "N_LTC"),
    ("RET_LIFESTYLE_FRUGAL", "lifestyleFrugal", "N_RET"), ("RET_LIFESTYLE_STRESSFREE", "lifestyleStressFree", "N_RET"),
    ("RET_LIFESTYLE_ONLYTHEBEST", "lifestyleOnlyTheBest", "N_RET"),
    ("EDU_COST", "EDU_TOTAL_COST", "N_EDU"), ("EDU_TARGET_AGE", "eduYearsDefault (+10 years)", "N_EDU"),
    ("SAV_TARGET_AGE", "(new; was +10 years)", "N_SAV"), ("PRP_TARGET_AGE", "(new; was +10 years)", "N_PRP"),
    ("SAV_INCOME_MULT", "savIncomeMultiple", "N_SAV"), ("PRP_INCOME_MULT", "prpIncomeMultiple", "N_PRP"),
    ("(merged into CRI_COST)", "criMedicalPlaceholder / CRI_MEDICAL_HU", "N_CRI (HappiU payload)"),
    ("MIN_EXPENSE_MONTHLY", "MIN_EXPENSE_MONTHLY (SGD 100)", "all (spend floor, USD 100)"),
    ("R_xxx_SIZE / R_xxx_WHEN", "stress-event text table", "R_DEA, R_CRI, R_TPD, R_PAC, R_HOS, R_LTC, R_WED, R_BAB"),
    ("(removed)", "funeralLump", "Farewell (dropped)"),
]
RULES = [
    "N_xxx = need. R_xxx = the risk or event that triggers it (N_CRI ↔ R_CRI; N_INC ↔ R_DEA).",
    "Parameters are named <PREFIX>_<WHAT> in upper case, with the need's 3-letter prefix (CRI_COST, HOS_MONTHS).",
    "Protection · calculator and Wealth · calculator needs get amount / have / gap. Coverage · parked needs are scored only.",
    "One name per need in every component (e.g. TPD, never Disability or PTD). Where an engine still differs (HU: N_HSP, PTD) it is listed as open.",
    "Code (src/, frontend/) still uses the old parameter names and 8 needs until the code follows V0-16.",
]


def _dict_md() -> str:
    out = ["# Dictionary — needs, risks and parameters", "",
           "*Model V0-24. Generated by `build_calculations_workbook.py`; same content as the Dictionary tab.*", ""]
    out += ["## Rules", ""] + [f"- {x}" for x in RULES] + [""]
    out += ["## Needs", "",
            "| Code | Risk | Prefix | Category | App label | Profiler label (key) | HappiU | Scenario Visualizer | Calculator | Parameters | Status |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    out += ["| " + " | ".join(r) + " |" for r in NEED_DICT] + [""]
    out += ["## Risks and stress events", "", "| Code | Was | Label | Need | Kind |", "|---|---|---|---|---|"]
    out += ["| " + " | ".join(r) + " |" for r in RISK_DICT] + [""]
    out += ["## Parameter names", "", "| New | Was | Need |", "|---|---|---|"]
    out += ["| " + " | ".join(r) + " |" for r in PARAM_DICT] + [""]
    return "\n".join(out)


NEED_DETAIL = {
    "N_INC": ("Income & family protection",
              "Money the family needs if the earner dies: debts are cleared and today's spending continues for the support years.",
              "INC_SUPPORT_MIN 10, INC_SUPPORT_MAX 25, INC_SUPPORT_PIVOT_AGE 50; slider bequest, dependYears. Have = life sum assured."),
    "N_CRI": ("Critical illness",
              "Income replacement while seriously ill plus the treatment cost.",
              "CRI_YEARS 3, CRI_COST (USD, × price level). Have = 0 (existing CI cover not read yet)."),
    "N_TPD": ("Total & permanent disability (TPD)",
              "Income replacement after permanent disability plus the care / adaptation cost.",
              "TPD_YEARS 5, TPD_COST (USD, × price level)."),
    "N_HOS": ("Hospitalisation",
              "Hospital bills, sized as months of income.",
              "HOS_MONTHS 6."),
    "N_PAC": ("Personal accident",
              "Income replacement and treatment after an accidental injury (non-fatal).",
              "PAC_YEARS 1, PAC_COST (USD, × price level; calibrated from S$80,000). Agreed V0-18."),
    "N_ADB": ("Accidental death",
              "Extra lump paid only when death is accidental (on top of N_INC). HappiU already scores N_ADB like N_INC.",
              "None yet. To define: ADB_* parameters and whether it is a calculator or a rider on N_INC."),
    "N_LTC": ("Long-term care",
              "Nursing-home cost from the care start age until life expectancy, in today's money.",
              "LTC_COST USD 129,000 a year (× price level); LTC_START_AGE 80 (front-end input); care years = lifeExpectancy − start age. "
              "Stress R_LON: care until 99. Have = 0 (no existing LTC cover or social scheme yet)."),
    "N_RET": ("Private retirement",
              "The lump needed at retirement to pay today's spending × lifestyle for the years in retirement. CPF is not counted.",
              "RET_LIFESTYLE_FRUGAL 75%, RET_LIFESTYLE_STRESSFREE 100%, RET_LIFESTYLE_ONLYTHEBEST 125%; ageOfRetirement 65; lifeExpectancy (cap 99). Stress R_LON: LON_AGE 99."),
    "N_EDU": ("Child's university education",
              "One total course cost at the target year.",
              "EDU_COST (USD, × price level), target year when the customer turns EDU_TARGET_AGE 50, grown at inflation."),
    "N_SAV": ("Savings goal",
              "A general savings target set by the customer.",
              "SAV_INCOME_MULT 1 × annual income if the customer sets no amount; target year at SAV_TARGET_AGE 40, never shorter than 5 years."),
    "N_PRP": ("Home purchase",
              "Deposit / purchase money for a home. Separate from home protection.",
              "PRP_INCOME_MULT 5 × annual income if the customer sets no amount; target year at PRP_TARGET_AGE 33, never shorter than 3 years. Not proposed by the profiler (no label)."),
    "N_HOM": ("Home protection", "Insurance for a home the customer owns (building / contents).", "Parked: scored only."),
    "N_CAR": ("Car protection", "Motor insurance.", "Parked: scored only."),
    "N_TRV": ("Travel protection", "Travel insurance.", "Parked: scored only."),
}


def _need_md() -> str:
    by = {r[0]: r for r in NEED_DICT}
    out = ["# Need dictionary", "",
           "*Model V0-24. Generated by `build_calculations_workbook.py` from the same data as the Dictionary tab "
           "and [Dictionary.md](Dictionary.md). Edit the data in the build script, not this file.*", "",
           "Naming: need `N_xxx`, risk `R_xxx`, parameters `XXX_WHAT`. The code (src/, frontend/) still uses the eight "
           "V0-14 needs and the old parameter names until it follows the model.", "",
           "## Overview", "",
           "| Code | Need | Category | Risk | Status |", "|---|---|---|---|---|"]
    for code in NEED_DETAIL:
        r = by[code]
        out.append(f"| `{code}` | {NEED_DETAIL[code][0]} | {r[3]} | `{r[1]}` | {r[10]} |" if r[1] != "—"
                   else f"| `{code}` | {NEED_DETAIL[code][0]} | {r[3]} | — | {r[10]} |")
    out += ["| — | Farewell | Dropped (V0-16) | — | Not scored; funeral lump removed |", ""]
    for code, (name, what, params) in NEED_DETAIL.items():
        r = by[code]
        out += [f"## {code} · {name}", "",
                f"{what}", "",
                "| | |", "|---|---|",
                f"| Category | {r[3]} |",
                f"| Risk / trigger | {r[1]} |",
                f"| Parameter prefix | {r[2]} |",
                f"| Calculator | {r[8]} |",
                f"| Parameters | {params} |",
                f"| App label | {r[4]} |",
                f"| Need Profiler label (key) | {r[5]} |",
                f"| HappiU | {r[6]} |",
                f"| Scenario Visualizer | {r[7]} |",
                f"| Status | {r[10]} |", ""]
    return "\n".join(out)


def build_dictionary(wb: Workbook) -> None:
    ws = wb.create_sheet("Dictionary")
    ws.sheet_properties.tabColor = GOLD
    ws.freeze_panes = "A3"
    _fill(ws, "A1", "Dictionary — needs (N_), risks (R_) and parameter prefixes", title_font, paper_fill, border=False)
    ws.merge_cells("A1:K1")
    _fill(ws, "A2", " · ".join(RULES), note_font, paper_fill, border=False)
    ws.merge_cells("A2:K2")
    ws.row_dimensions[2].height = 48
    ws["A2"].alignment = wrap
    r = 4
    _fill(ws, f"A{r}", "NEEDS", sec_font, sec_fill, border=False)
    r += 1
    _headers(ws, r, ["Code", "Risk", "Prefix", "Category", "App label", "Profiler label (key)", "HappiU",
                     "Scenario Visualizer", "Calculator", "Parameters", "Status"])
    cat_fill = {"Protection": calc_fill, "Wealth": blue_fill, "Coverage": assume_fill, "Dropped": red_fill}
    for row in NEED_DICT:
        r += 1
        f = cat_fill[row[3].split(" ")[0]]
        for j, v in enumerate(row, 1):
            _fill(ws, f"{get_column_letter(j)}{r}", v, fill=f if j <= 4 else None, align=wrap)
    r += 2
    _fill(ws, f"A{r}", "RISKS AND STRESS EVENTS", sec_font, sec_fill, border=False)
    r += 1
    _headers(ws, r, ["Code", "Was (id)", "Label", "Need", "Kind"])
    for row in RISK_DICT:
        r += 1
        for j, v in enumerate(row, 1):
            _fill(ws, f"{get_column_letter(j)}{r}", v, align=wrap)
    r += 2
    _fill(ws, f"A{r}", "PARAMETER NAMES (Assumptions named cells)", sec_font, sec_fill, border=False)
    r += 1
    _headers(ws, r, ["New name", "Was", "Need"])
    for row in PARAM_DICT:
        r += 1
        for j, v in enumerate(row, 1):
            _fill(ws, f"{get_column_letter(j)}{r}", v, align=wrap)
    _widths(ws, {"A": 22, "B": 16, "C": 26, "D": 22, "E": 26, "F": 30, "G": 20, "H": 16, "I": 44, "J": 34, "K": 40})
    (Path(__file__).resolve().parent / "Dictionary.md").write_text(_dict_md(), encoding="utf-8")
    (Path(__file__).resolve().parent / "Need-dictionary.md").write_text(_need_md(), encoding="utf-8")


# ---------------------------------------------------------------------------
# V0-20 parameter review list (review only: proposals are not wired into formulas yet)
# columns: group, parameter, where, current (value or formula), unit, currency today, status,
#          proposed value, proposed unit / timing, why, code source
# ---------------------------------------------------------------------------
_U, _S, _L, _N = "USD done", "SGD → convert", "Local by design (country plug-in)", "No currency"
PARAM_REVIEW = [
    # 1 Need parameters
    ("1 Need parameters", "CRI_COST", "Assumptions", "=CRI_COST", "USD", "USD", _U, "", "", "V0-15: S$200,000 × 0.74.", "goal_math.py CI_COST (still SGD 200,000)"),
    ("1 Need parameters", "CRI_YEARS", "Assumptions", "=CRI_YEARS", "years", "—", _N, "", "", "", "goal_math.py CI_YEARS"),
    ("1 Need parameters", "TPD_COST", "Assumptions", "=TPD_COST", "USD", "USD", _U, "", "", "", "goal_math.py TPD_COST"),
    ("1 Need parameters", "TPD_YEARS", "Assumptions", "=TPD_YEARS", "years", "—", _N, "", "", "", "goal_math.py TPD_YEARS"),
    ("1 Need parameters", "HOS_MONTHS", "Assumptions", "=HOS_MONTHS", "months of income", "—", _N, "", "", "", "goal_math.py HOSP_MONTHS"),
    ("1 Need parameters", "PAC_COST", "Assumptions", "=PAC_COST", "USD", "USD", _U, "", "", "V0-18 agreed.", "— (new)"),
    ("1 Need parameters", "PAC_YEARS", "Assumptions", "=PAC_YEARS", "years", "—", _N, "", "", "", "— (new)"),
    ("1 Need parameters", "LTC_COST", "Assumptions", "=LTC_COST", "USD / year", "USD", _U, "", "", "V0-19: nursing home.", "— (new)"),
    ("1 Need parameters", "LTC_START_AGE", "Assumptions", "=LTC_START_AGE", "age", "—", _N, "", "", "Front-end input.", "— (new)"),
    ("1 Need parameters", "EDU_COST", "Assumptions", "=EDU_COST", "USD", "USD", _U, "", "", "V0-15: S$75,000 × 0.74.", "goal_math.py EDU_TOTAL_COST"),
    ("1 Need parameters", "EDU_YEARS_DEFAULT", "Assumptions", "=EDU_YEARS_DEFAULT", "years", "—", _N, "", "", "", "needEdit.ts"),
    ("1 Need parameters", "SAV_INCOME_MULT / PRP_INCOME_MULT", "Assumptions", "=SAV_INCOME_MULT&\" / \"&PRP_INCOME_MULT", "× annual income", "—", _N, "", "", "", "need_calculator.py"),
    ("1 Need parameters", "INC_SUPPORT_MIN / MAX / PIVOT_AGE", "Assumptions", "=INC_SUPPORT_MIN&\" / \"&INC_SUPPORT_MAX&\" / \"&INC_SUPPORT_PIVOT_AGE", "years / age", "—", _N, "", "", "", "goal_math.py LIFE_SUPPORT_*"),
    ("1 Need parameters", "RET_LIFESTYLE_*", "Assumptions", "=RET_LIFESTYLE_FRUGAL&\" / \"&RET_LIFESTYLE_STRESSFREE&\" / \"&RET_LIFESTYLE_ONLYTHEBEST", "× today's spend", "—", _N, "", "", "", "goal_math.py LIFESTYLE_RATES"),
    # 2 Stress events: money
    ("2 Stress events · size", "R_DEA death cost", "Assumptions stress table", "S$20,000", "one-off", "SGD", _S, "USD 14,800", "one-off", "× 0.74. Funeral / final costs (Farewell need is dropped, the event cost stays).", "stressEvents.ts death; sv_payload.py"),
    ("2 Stress events · size", "R_CRI critical illness cost", "Assumptions stress table", "S$150,000", "one-off", "SGD", _S, "link → CRI_COST (USD 148,000)", "one-off", "Link to the need parameter: one number for need and stress.", "stressEvents.ts ci"),
    ("2 Stress events · size", "R_TPD disability cost", "Assumptions stress table", "S$200,000", "one-off", "SGD", _S, "link → TPD_COST (USD 148,000)", "one-off", "Link to the need parameter.", "stressEvents.ts tpd"),
    ("2 Stress events · size", "R_PAC accident cost", "Assumptions stress table", "S$80,000", "one-off", "SGD", _S, "link → PAC_COST (USD 59,200)", "one-off", "Link to the need parameter.", "stressEvents.ts pa"),
    ("2 Stress events · size", "R_HOS hospital bill", "Assumptions stress table", "S$120,000", "one-off", "SGD", _S, "USD 88,800 (new HOS_COST)", "one-off", "× 0.74. N_HOS is sized in months of income, so the bill needs its own parameter.", "stressEvents.ts hosp"),
    ("2 Stress events · size", "R_LTC care cost", "Assumptions stress table", "S$90,000 / year", "per year", "SGD", _S, "link → LTC_COST (USD 129,000 / year)", "per year", "Link to the need parameter.", "stressEvents.ts care"),
    ("2 Stress events · size", "R_WED wedding", "Assumptions stress table", "S$60,000", "one-off", "SGD", _S, "USD 44,400", "one-off", "× 0.74.", "stressEvents.ts wed"),
    ("2 Stress events · size", "R_BAB newborn", "Assumptions stress table", "S$35,000", "one-off", "SGD", _S, "USD 25,900", "one-off", "× 0.74.", "stressEvents.ts baby"),
    ("2 Stress events · size", "R_MKT / R_CCY / R_INF / R_ICT / R_EXP", "Assumptions stress table", "35% / 14% / +3 pp / −20% / +15%", "%", "—", _N, "", "", "Percentages: no conversion.", "stressEvents.ts"),
    # 3 Stress events: timing
    ("3 Stress events · timing", "R_DEA", "Assumptions stress table", "year 17", "years from today", "—", "Year offset → age", "age 60", "age", "Personal risks by age, so every persona is hit at the same life stage. If the persona is older, apply next year.", "stressEvents.ts"),
    ("3 Stress events · timing", "R_CRI", "Assumptions stress table", "year 12", "years from today", "—", "Year offset → age", "age 55", "age", "", "stressEvents.ts"),
    ("3 Stress events · timing", "R_TPD", "Assumptions stress table", "year 15", "years from today", "—", "Year offset → age", "age 50", "age", "", "stressEvents.ts"),
    ("3 Stress events · timing", "R_PAC", "Assumptions stress table", "year 10", "years from today", "—", "Year offset → age", "age 45", "age", "", "stressEvents.ts"),
    ("3 Stress events · timing", "R_HOS", "Assumptions stress table", "year 9", "years from today", "—", "Year offset → age", "age 50", "age", "", "stressEvents.ts"),
    ("3 Stress events · timing", "R_LTC", "Assumptions stress table", "years 30–35", "years from today", "—", "Year offset → age", "LTC_START_AGE (80) → life expectancy", "age span", "Same span as the N_LTC need.", "stressEvents.ts"),
    ("3 Stress events · timing", "R_LON", "Assumptions stress table", "=LON_AGE", "age", "—", _N, "", "", "Already age-based.", "— (new)"),
    ("3 Stress events · timing", "R_WED / R_BAB", "Assumptions stress table", "year 5 / year 3", "years from today", "—", "Keep year offset", "", "", "Near-term life events: a year from today fits.", "stressEvents.ts"),
    ("3 Stress events · timing", "R_MKT / R_CCY / R_INF / R_ICT / R_EXP", "Assumptions stress table", "year 8 / 6 / 4–9 / 5–10 / 6–12", "years from today", "—", "Keep year offset", "", "", "Market and household shocks are calendar events, not life stages.", "stressEvents.ts"),
    # 4 Ages that should agree
    ("4 Life expectancy and ages", "lifeExpectancyDefault", "Assumptions", "=lifeExpectancyDefault", "age", "—", "Harmonise", "85", "age", "GP default when People Like You gives none.", "goal_math.py LIFE_EXPECTANCY"),
    ("4 Life expectancy and ages", "life expectancy cap", "Need Calculator / PLU", "99", "age", "—", "Harmonise", "link → LON_AGE (99)", "age", "One number for the cap and the longevity stress.", "goal_math.py LIFE_EXPECTANCY_MAX"),
    ("4 Life expectancy and ages", "endAge (chart horizon)", "Assumptions", "=endAge", "age", "—", "Harmonise", "link → life expectancy of the session", "age", "Chart stops at 85 even if the persona's LE is 88.", "sv_payload.py endAge"),
    ("4 Life expectancy and ages", "HappiU default life expectancy", "HappiU", "83", "age", "—", "Harmonise", "link → lifeExpectancyDefault (85)", "age", "HU engine uses 83 when retirement duration is 0.", "HU engine"),
    ("4 Life expectancy and ages", "SV tenant life expectancy", "Scenario Visualizer", "100", "age", "—", "Harmonise", "link → LON_AGE (99) or keep 100", "age", "SV path length.", "SV helium conf.ini"),
    ("4 Life expectancy and ages", "ageOfRetirement", "Assumptions", "=ageOfRetirement", "age", "—", _N, "", "", "", "goal_math.py RETIREMENT_AGE"),
    ("4 Life expectancy and ages", "HappiU off-plan cover age", "HappiU", "75", "age", "—", "Review", "", "age", "CI / TPD / HSP cover runs to 75 in HU.", "HU engine"),
    ("4 Life expectancy and ages", "HappiU dependent years", "HappiU", "10", "years", "—", "Harmonise", "link → INC_SUPPORT years (10–25 by age)", "years", "HU uses 10; GP uses the age rule.", "HU engine"),
    # 5 Household seeding
    ("5 Household seeding", "propertyLow / Mid / High", "Assumptions", "=TEXT(propertyLow,\"#,##0\")&\" / \"&TEXT(propertyMid,\"#,##0\")&\" / \"&TEXT(propertyHigh,\"#,##0\")", "USD", "USD", _U, "", "", "V0-15.", "predict.py seed_property_value (SGD)"),
    ("5 Household seeding", "propertyIncomeLow / High", "Assumptions", "=TEXT(propertyIncomeLow,\"#,##0\")&\" / \"&TEXT(propertyIncomeHigh,\"#,##0\")", "USD / month", "USD", _U, "", "", "", "predict.py (SGD)"),
    ("5 Household seeding", "lifeRoundUnit", "Assumptions", "=lifeRoundUnit", "USD step", "USD", _U, "", "", "", "predict.py (SGD 100,000)"),
    ("5 Household seeding", "MIN_EXPENSE_MONTHLY", "People Like You note", "100", "per month", "SGD", _S, "USD 74", "per month", "× 0.74. Frontend floor for spend.", "frontend MIN_EXPENSE_MONTHLY"),
    ("5 Household seeding", "spend / save / split / LTV shares", "Assumptions", "67.5% +5 pp, 50%, 15/85, 55%", "%", "—", _N, "", "", "", "predict.py"),
    # 6 Plan and budget
    ("6 Plan and budget", "lump / monthly / premium steps", "Assumptions", "=lumpRoundStep&\" / \"&monthlyRoundStep&\" / \"&coverPremRoundStep", "USD step", "USD", _U, "", "", "Nice-rounded in user currency.", "planProducts.ts (SGD)"),
    ("6 Plan and budget", "coverSliderPremFloor", "Assumptions", "=coverSliderPremFloor", "USD", "USD", _U, "", "", "", "planProducts.ts (SGD 200)"),
    ("6 Plan and budget", "protectionPremiumRate", "Assumptions", "=protectionPremiumRate", "% of sum", "—", "Placeholder", "premium-quote API", "", "Too cheap for large covers (e.g. N_LTC).", "planProducts.ts"),
    # 7 HappiU payload / engine
    ("7 HappiU", "annualBudget / placeholderNeedBudget", "Assumptions", "=annualBudget&\" / \"&placeholderNeedBudget", "USD", "USD", _U, "", "", "", "hu_payload.py (SGD)"),
    ("7 HappiU", "benefitRound", "Assumptions", "=benefitRound", "USD step", "USD", _U, "", "", "", "hu_payload.py (SGD 50,000)"),
    ("7 HappiU", "CRI_MEDICAL_HU", "Assumptions", "=CRI_MEDICAL_HU", "USD", "USD", _U, "link → CRI_COST", "", "Same number as CRI_COST: merge.", "hu_payload.py"),
    ("7 HappiU", "HU CI medical cost (engine default)", "HappiU", "200,000", "one-off", "SGD", _S, "GP sends CRI_COST", "", "Engine default when N_CRI is off.", "HU ciAssumptions"),
    ("7 HappiU", "HU TPD medical cost (engine)", "HappiU", "444,000", "one-off", "SGD", _S, "GP sends TPD_COST (USD 148,000) or USD 328,560", "", "Decide: link to TPD_COST, or keep HU's own value converted (× 0.74).", "HU ProductPTD"),
    # 8 Country plug-ins
    ("8 Country plug-ins", "CPF OW_CEILING and rates", "CPF", "=OW_CEILING", "SGD / month", "SGD", _L, "", "", "Singapore social security. Stays in SGD inside the SG-CPF module.", "src/cpf.py"),
    ("8 Country plug-ins", "SV CPF caps, BRS and payout tables", "Scenario Visualizer", "96,000 / 63,000 / BRS table", "SGD", "SGD", _L, "", "", "Same SG-CPF module inside SV.", "SV SocialSecurityR_SGP"),
    ("8 Country plug-ins", "Income anchors (occupation bands)", "Assumptions", "Singapore bands", "per month", "SGD", _L, "", "", "Per country and occupation, local currency.", "income_anchors.json"),
    ("8 Country plug-ins", "FX rate table", "FX", "9 currencies", "USD per 1", "—", "Data feed", "live feed, locked per session", "", "", "src/fx.py"),
    # 9 Rates
    ("9 Rates", "inflation / interest / loan / growth / return / asset", "Assumptions", "=TEXT(inflationRate,\"0.0%\")&\" / \"&TEXT(interestRate,\"0.0%\")&\" / \"&TEXT(loanRate,\"0.0%\")&\" / \"&TEXT(incomeGrowthRate,\"0.0%\")&\" / \"&TEXT(investmentReturn,\"0.0%\")&\" / \"&TEXT(assetReturn,\"0.0%\")", "% p.a.", "—", "Review", "", "", "Singapore-flavoured defaults; per-country rates would be a plug-in or data feed.", "session_rates.py"),
]


def build_param_review(wb: Workbook) -> None:
    ws = wb.create_sheet("Parameter review")
    ws.sheet_properties.tabColor = "B8860B"
    ws.freeze_panes = "D4"
    _fill(ws, "A1", "Parameter review — every fixed amount, age and timing. Goal: all money in USD, personal risks by age", title_font, paper_fill, border=False)
    ws.merge_cells("A1:M1")
    _fill(ws, "A2", "Review list only: 'Proposed' values are not used by the formulas yet. Write your decision in column L "
          "(agree / change to … / keep). Status: USD done · SGD → convert · Year offset → age · Harmonise · Local by design (country plug-in) · No currency.",
          note_font, paper_fill, border=False)
    ws.merge_cells("A2:M2")
    ws.row_dimensions[2].height = 30
    _headers(ws, 3, ["#", "Group", "Parameter", "Where", "Current", "Unit", "Currency today", "Status",
                     "Proposed", "Proposed unit / timing", "Why", "Decision", "Code source"])
    st_fill = {_U: calc_fill, _S: red_fill, _L: assume_fill, _N: paper_fill}
    for i, row in enumerate(PARAM_REVIEW, 1):
        rr = 3 + i
        grp, name, where, cur, unit, ccy, status, prop, prop_u, why, src = row
        vals = [i, grp, name, where, cur, unit, ccy, status, prop, prop_u, why, "", src]
        for j, v in enumerate(vals, 1):
            f = None
            if j == 8:
                f = st_fill.get(status, blue_fill)
            if j == 12:
                f = input_fill
            _fill(ws, f"{get_column_letter(j)}{rr}", v, fill=f, align=wrap,
                  num="#,##0.####" if j == 5 else None)
    last = 3 + len(PARAM_REVIEW)
    ws.auto_filter.ref = f"A3:M{last}"
    _widths(ws, {"A": 5, "B": 22, "C": 30, "D": 20, "E": 18, "F": 14, "G": 10, "H": 20, "I": 26, "J": 16, "K": 46, "L": 24, "M": 30})
    counts = {}
    for row in PARAM_REVIEW:
        counts[row[6]] = counts.get(row[6], 0) + 1
    r = last + 2
    _fill(ws, f"B{r}", "Count by status", sec_font, sec_fill, border=False)
    for k, v in counts.items():
        r += 1
        _fill(ws, f"B{r}", k, fill=st_fill.get(k, blue_fill))
        _fill(ws, f"C{r}", v, align=center)


CODE_BACKLOG = []


def build_discrepancies(wb: Workbook) -> None:
    ws = wb.create_sheet("Discrepancies")
    ws.sheet_properties.tabColor = "9B1D20"
    ws.freeze_panes = "A4"
    _fill(ws, "A1", "Code implementation backlog — empty as of V0-25", title_font, paper_fill, border=False)
    ws.merge_cells("A1:F1")
    _fill(ws, "A2", "V0-25: the code follows V0-24. Parked ideas (mock premium, existing-cover wiring, HU/SV CPF engines) "
          "live in Calculations.md (Open issues). No backlog rows.", note_font, paper_fill, border=False)
    ws.merge_cells("A2:F2")
    _headers(ws, 3, ["#", "Component", "Model (Excel)", "Code today", "Change in code", "Files"])
    _fill(ws, "A4", "—", align=center)
    _fill(ws, "B4", "(none)", align=wrap)
    _fill(ws, "C4", "Code follows the V0-24 model.", align=wrap)
    _fill(ws, "D4", "—", align=wrap)
    _fill(ws, "E4", "—", align=wrap)
    _fill(ws, "F4", "—", align=wrap)
    _widths(ws, {"A": 4, "B": 24, "C": 52, "D": 36, "E": 44, "F": 40})


def build_code_check(wb: Workbook) -> None:
    """Python values from the live modules, for the first-open compare."""
    ws = wb.create_sheet("Code check")
    ws.sheet_properties.tabColor = "44546A"
    ws.freeze_panes = "C3"
    _fill(
        ws,
        "A1",
        "Values computed by importing the GP modules at workbook build time. "
        "After Excel recalculates, pick that id on People Like You and compare the single-persona results. "
        "This sheet is a snapshot — it does not follow yellow-cell edits.",
        title_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A1:R1")
    headers = [
        "id", "incomeMonthly", "expenseMonthly", "cash", "investments", "property", "mortgage",
        "life sum", "on N_INC", "on N_CRI", "on N_TPD", "on N_HOS", "on N_PAC", "on N_LTC",
        "on N_RET", "on N_EDU", "on N_SAV", "on N_PRP",
        "N_INC amount", "N_RET amount",
    ]
    _headers(ws, 2, headers)
    for i, p in enumerate(PERSONAS):
        r = 3 + i
        plu = twin_plu(p)
        prof = twin_profiler(p, plu)
        needs = twin_needs(p, plu, prof["enabled"])
        vals = [
            p["id"],
            plu["income"],
            plu["expense"],
            plu["cash"],
            plu["investments"],
            plu["property"],
            plu["mortgage"],
            plu["life_sum"],
        ]
        for t in UNIFIED_X:
            vals.append(t in prof["enabled"])
        vals.append(needs["N_INC"]["needAmount"])
        vals.append(needs["N_RET"]["needAmount"])
        for j, v in enumerate(vals, 1):
            num = "#,##0.00" if j in (2, 3) else ("#,##0" if j in (4, 5, 6, 7, 8, 19, 20) else None)
            _fill(ws, f"{get_column_letter(j)}{r}", v, num=num, align=center if j != 1 else left)
    _widths(ws, {get_column_letter(i): 14 for i in range(1, 21)})
    ws.column_dimensions["A"].width = 8
    ws.auto_filter.ref = f"A2:T{R1}"
    ws.row_dimensions[1].height = 36


# One row per model change. Newest first. Keep in step with CHANGELOG.md in this folder.
# Status: "Excel + docs" = spec only, code still to follow; "In code" = code already matches.
CHANGELOG = [
    (
        "V0-26", "2026-09-28", "Goal horizons",
        "N_SAV and N_PRP keep a remaining horizon once the customer is at or past the milestone age: "
        "max(5, SAV_TARGET_AGE − age) and max(3, PRP_TARGET_AGE − age). Education still aims at next year "
        "once past EDU_TARGET_AGE 50. Under 30 / 35 the defaults are unchanged (still 33 / 40).",
        "Need Calculator targetYear N_SAV / N_PRP; config session-defaults; Need Calculator service.",
        "In code.",
    ),
    (
        "V0-25", "2026-09-28", "Code follows V0-24",
        "Work packages WP0–WP15: GP calculators, FX lock, PPP, N_PAC / N_LTC, plan / budget BFF, HappiU and SV payloads, "
        "and the frontend spend floor (USD 100 via FxLock) now follow V0-24. The leftover pipeline no longer swaps N_SAV "
        "for N_PRP; twins call the live Need Profiler. Discrepancies tab is empty. Parked (not in this model): real premium "
        "API, wiring policies into profiler Existing*Coverage, and unifying HU/SV CPF with GP.",
        "Discrepancies; Need Profiler twins; frontend minExpenseMonthly; leftover select_unified_top.",
        "In code.",
    ),
    (
        "V0-24", "2026-09-27", "Pre-code clean-up",
        "A1 Money-page overrides (Personas W–AC) cleared. A2 Plan default contribution = (free budget − premiums / 12) ÷ n wealth, "
        "rounded down, so it never exceeds the Budget Calculator. A3 Goal target years by age: N_EDU 50, N_SAV 40, N_PRP 33; "
        "own horizon per goal in Need Calculator, Plan, SV and HappiU. A4 People Like You vocabulary mapped to profiler options "
        "(lifestyle, ward, sports). A6 USD fixed amounts recalibrated at today's SGD rate, so Singapore amounts are unchanged in SGD. "
        "A7 Discrepancies tab is now the code implementation backlog only.",
        "Personas; Plan; Need Calculator; SV; HappiU; Need Profiler; Assumptions; Discrepancies.",
        "Not in code (see Discrepancies).",
    ),
    (
        "V0-23", "2026-09-27", "Need Profiler",
        "Section D row 'USD per 1 local' now shows the rate the profiler actually uses: PPP-USD per 1 local "
        "(market ÷ price level, =FX_pppUsdPerLocal). Display only; no result changes.",
        "Need Profiler D-block.",
        "—",
    ),
    (
        "V0-22", "2026-09-26", "FX and PPP",
        "Rate table extended to 152 currencies (market rate 2026-09-25) and a PPP table for 245 countries (World Bank PPP, "
        "2024 average market rate, price level US = 1; 186 usable). Price level is per country, relative to PPP_BASE_COUNTRY "
        "(Singapore). Option B switched on: USD fixed amounts × relative price level; Need Profiler compares PPP-USD. "
        "Singapore is unchanged by PPP, but the new SGD rate (0.7816, was 0.74) lowers SGD fixed amounts by 5.3%.",
        "FX tab; fx_ppp/*.csv; Assumptions priceLevelOn, fxMode, PPP_BASE_COUNTRY; Need Profiler usd rows.",
        "Not in code (src/fx.py 9 currencies).",
    ),
    (
        "V0-21", "2026-09-26", "Assumptions / stress events / HappiU / SV",
        "Parameter review merged into Assumptions (unit, currency, status, code source, changed in, open proposal); review tab removed. "
        "Life expectancy: one default (85), cap LON_AGE 99; GP sends them to HappiU (default was 83) and SV (path now ends at 99, was 100); "
        "chart horizon = session life expectancy. GP sends CRI_COST and TPD_COST to HappiU (were HU 200,000 / 444,000). "
        "CRI_MEDICAL_HU merged into CRI_COST. MIN_EXPENSE_MONTHLY USD 100 floor on spend. Stress events: sizes in USD, "
        "personal risks by age (R_DEA 60, R_CRI 55, R_TPD 50, R_PAC 45, R_HOS 50, R_LTC LTC start age → life expectancy), "
        "R_WED / R_BAB years 5 / 3; SV tab applies them when switched on.",
        "Assumptions; People Like You; HappiU; Scenario Visualizer; Dictionary; Discrepancies 8.",
        "Not in code.",
    ),
    (
        "V0-20", "2026-09-26", "Parameter review",
        "New Parameter review tab: every fixed amount, age and timing with current value, currency, status and a proposal "
        "(stress events to USD and linked to need parameters; personal-risk timing by age; life-expectancy ages harmonised). "
        "Review only: no formula changed.",
        "Parameter review tab.",
        "—",
    ),
    (
        "V0-19", "2026-09-26", "N_LTC",
        "New protection calculator N_LTC long-term care: annuity-due (realReturn) of LTC_COST USD 129,000 a year over care "
        "years = lifeExpectancy − LTC start age (default 80, front-end input on the Need Calculator). Plan sizes it like other "
        "protection; Budget and SV include its premium. Not picked by the profiler (no label). R_LON block shows N_LTC at 99. "
        "R_LTC linked to N_LTC in the Dictionary.",
        "Assumptions LTC_COST / LTC_START_AGE; Need Calculator; Plan; Budget; Scenario Visualizer; Dictionary.",
        "Not in code; HappiU has no LTC.",
    ),
    (
        "V0-18", "2026-09-26", "TPD / N_PAC / R_LON",
        "TPD is the one name for total & permanent disability (profiler label, weight matrix, HappiU tab; JSON key still "
        "'disability', HU engine still PTD — Discrepancies 13). N_PAC agreed (1 year of income + USD 59,200). New stress "
        "event R_LON longevity: LON_AGE 99 on Assumptions; Need Calculator shows N_RET need and gap at 99; Scenario "
        "Visualizer toggle moves the chart horizon to 99 and reports wealth and spendable wealth there.",
        "Assumptions LON_AGE, stress table; Need Calculator R_LON block; Scenario Visualizer SV_lonV / SV_end; HappiU labels; Dictionary.",
        "Not in code.",
    ),
    (
        "V0-17", "2026-09-26", "Dictionary",
        "Accidental death N_ADB (risk R_ADB) added as a protection candidate: HappiU already supports it, no GP calculator "
        "or profiler label yet. N_PAC noted as supported by the HappiU engine (GP does not send it yet). New Need-dictionary.md "
        "(one section per need), generated with Dictionary.md.",
        "Dictionary tab; Need-dictionary.md; Dictionary.md.",
        "Not in code.",
    ),
    (
        "V0-16", "2026-09-26", "Dictionary",
        "New Dictionary tab and Dictionary.md: one code per need (N_), risk (R_) and parameter prefix. "
        "Parameters renamed (CI_COST → CRI_COST, HOSP_MONTHS → HOS_MONTHS, EDU_TOTAL_COST → EDU_COST, "
        "lifeSupport* → INC_SUPPORT_*, lifestyle* → RET_LIFESTYLE_*, sav/prpIncomeMultiple → SAV/PRP_INCOME_MULT). "
        "Stress events carry R_ codes (R_DEA, R_CRI, R_TPD, R_HOS, R_PAC, R_LTC, R_MKT, R_CCY, R_INF, R_ICT, R_EXP, R_WED, R_BAB).",
        "Dictionary; Assumptions named cells and stress-event table; Scenario Visualizer event labels.",
        "Not in code.",
    ),
    (
        "V0-16", "2026-09-26", "Need Profiler",
        "Farewell dropped (not scored; min–max scaling now over 11 labels). Home / Car / Travel Protection parked as "
        "coverage needs N_HOM / N_CAR / N_TRV (scored and prioritised, no calculator). Personal Accident (N_PAC) joins "
        "the protection pick. Growth pick is N_EDU vs N_SAV; the home-ownership SAV ↔ PRP swap is removed; N_PRP "
        "(home purchase) is never auto-picked.",
        "Need Profiler; Assumptions weight matrix (column Farewell removed).",
        "Not in code: need_profiler.py still scores Farewell and maps Home Protection to N_PRP.",
    ),
    (
        "V0-16", "2026-09-26", "Need Calculator / Plan / Budget",
        "New calculator N_PAC: annuity-due of income for PAC_YEARS + PAC_COST (proposal: 1 year, USD 59,200). "
        "Plan sizes it like other protection; Budget and SV include its premium. HappiU does not receive it. "
        "Farewell funeral lump removed from Assumptions.",
        "Need Calculator row N_PAC; Plan Calculator; Budget Calculator; Scenario Visualizer SV_protPrem.",
        "Not in code.",
    ),
    (
        "V0-15", "2026-09-25", "All components",
        "USD is the system currency (option A: market rate). Every fixed money amount on the Assumptions tab is USD "
        "(= the V0-14 SGD value × 0.74, so Singapore results are unchanged): CI / TPD / EDU costs, home-seed values and "
        "income bands, life-cover, lump, monthly, premium and HappiU benefit rounding, premium floor, HappiU envelope, funeral lump.",
        "Assumptions rows 21–24 (systemCurrency, fxMode, priceLevelOn) and the USD rows.",
        "Not in code: goal_math.py, predict.py, planProducts.ts, hu_payload.py still SGD.",
    ),
    (
        "V0-15", "2026-09-25", "FX",
        "Unknown currency → #N/A (no SGD fallback). Price-level column for option B (default 1, switch off). "
        "Rounding steps derived in user currency: USD step ÷ rate, then the nearest 1 / 2 / 5 × 10^k.",
        "FX tab: rate, price level, FX_lumpStep, FX_monthlyStep, FX_coverPremStep, FX_lifeRound, FX_benefitRound.",
        "Not in code: src/fx.py falls back to SGD; no session lock.",
    ),
    (
        "V0-15", "2026-09-25", "Need Calculator",
        "Runs in USD: an S-block converts every money input (session and sliders) to USD; amount / have / gap are "
        "calculated in USD (columns H–J), then converted back and rounded to whole units in user currency (B–D).",
        "Need Calculator S-block and results H–J; names NC_amountUSD_*, NC_gapUSD_*.",
        "Not in code: evaluate_session computes in session currency with SGD lumps.",
    ),
    (
        "V0-15", "2026-09-25", "People Like You",
        "Home seed in USD: income converted to USD, compared with USD bands, USD home value converted back. "
        "Life cover rounds to the life-cover step in user currency.",
        "People Like You: income USD, property USD, property, life sum assured.",
        "Not in code: seed_property_value and _assumed_life_policy use SGD.",
    ),
    (
        "V0-15", "2026-09-25", "Plan / HappiU",
        "Plan contributions and premiums round to steps in user currency (SGD: 50 and 10). HappiU benefit rounding "
        "in user currency (SGD: 50,000). Budget Calculator is ratios only; unchanged.",
        "Plan Calculator D-block; HappiU HU_benefitRound.",
        "Not in code: planProducts.ts and hu_payload.py use SGD steps.",
    ),
    (
        "V0-15", "2026-09-25", "CPF",
        "CPF tab framed as a social-security plug-in: SG-CPF module or the default module (no contribution). Runs in user currency.",
        "CPF tab: module per country, module used.",
        "Code has only src/cpf.py; HappiU and SV run their own CPF.",
    ),
    (
        "V0-14", "2026-09-25", "Scenario Visualizer",
        "Mortgage instalment is a level 20-year annuity at loanRate "
        "(mortgage × r / (1 − (1 + r)^−20); rate 0 → mortgage / 20), replacing round(mortgage / 20). "
        "The balance now runs smoothly to 0 in year 20 (no step at the end of the term).",
        "SV tab: SV_inst, mortgage balance column. deterministic_engines.twin_sv / sv_loans.",
        "In code (goal_math.annual_loan_payment, sv_payload.py). Workbook catches up.",
    ),
    (
        "V0-14", "2026-09-25", "Scenario Visualizer",
        "New SPENDABLE pre / post columns for the expense-funding panel: cash + investments + savings "
        "(+ plan pots on post) − max(0, remaining mortgage − (home + CPF)). Not floored at 0. "
        "New results: first age spendable wealth < 0 (pre / post).",
        "SV tab: spPre, spPost, SV_spOutPre, SV_spOutPost. twin_sv spendable. excel_check SV_COLS.",
        "SV engine (CashFlowGeneratorV2 spendableWealth). Earmarked goal pots funded from assets = 0 in "
        "the workbook: open question.",
    ),
    (
        "V0-14", "2026-09-25", "Folder",
        "New tree docs/calculations_clone (first named calculations-V0-14) cloned from docs/calculations (V0-13). Older trees stay as snapshots.",
        "Whole folder.",
        "—",
    ),
]


def build_changelog(wb: Workbook) -> None:
    ws = wb.create_sheet("Change log")
    ws.sheet_properties.tabColor = "404040"
    ws.freeze_panes = "A3"
    _fill(ws, "A1", "Change log — model changes by version (newest first)", title_font, paper_fill, border=False)
    ws.merge_cells("A1:F1")
    _fill(
        ws,
        "A2",
        "Workflow: change the Excel first, then the docs, then the code. The Status column says whether the "
        "code already follows. Same rows as CHANGELOG.md in this folder.",
        note_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A2:F2")
    _headers(ws, 3, ["Version", "Date", "Component", "Change", "Where in the workbook", "Code status"])
    for i, row in enumerate(CHANGELOG):
        rr = 4 + i
        for j, v in enumerate(row):
            cell = ws.cell(rr, j + 1, v)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    _widths(ws, {"A": 9, "B": 12, "C": 20, "D": 70, "E": 45, "F": 45})


def main() -> None:
    errors = verify_twins()
    if errors:
        print("Twin verification failed:")
        for e in errors[:20]:
            print(" ", e)
        raise SystemExit(1)
    print(f"Twin verification passed for {N} personas plus the Need-calculator sample.")

    wb = Workbook()
    build_assumptions(wb)
    build_overview(wb)
    build_personas_sheet(wb)
    build_selected(wb)
    build_cpf(wb)
    build_plu(wb)
    build_profiler(wb)
    build_need_calc(wb)
    build_plan(wb)
    build_budget(wb)
    build_sv(wb)
    build_hu(wb)
    build_fx(wb)
    build_validation(wb)
    build_discrepancies(wb)
    build_dictionary(wb)
    build_changelog(wb)
    build_code_check(wb)

    # Overview first
    wb.move_sheet("Overview", offset=-len(wb.sheetnames) + 1)
    order = [
        "Overview",
        "Dictionary",
        "Selected persona",
        "Personas",
        "CPF",
        "People Like You",
        "Need Profiler",
        "Need Calculator",
        "Plan Calculator",
        "Budget Calculator",
        "Scenario Visualizer",
        "HappiU",
        "FX",
        "Validation",
        "Assumptions",
        "Discrepancies",
        "Change log",
        "Code check",
    ]
    for i, name in enumerate(order):
        wb.move_sheet(name, offset=i - wb.sheetnames.index(name))

    wb.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
