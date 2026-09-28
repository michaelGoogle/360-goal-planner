"""Build Calculations.xlsx from the live GP formulas (not the docs).

Run from anywhere:
    python GP/docs/calculations/build_calculations_workbook.py

The workbook formulas are a transcription of:
    src/cpf.py
    src/predict.py (_apply_plu, seed_property_value, _assumed_life_policy)
    src/pipeline/need_profiler.py (score + scale + select_unified_top)
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
    sv_plan_pots,
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
from src.hu_payload import PARTNER_ID, build_happiu_payload  # noqa: E402
from src.pipeline.goal_math import (  # noqa: E402
    CI_COST,
    CI_YEARS,
    EDU_TOTAL_COST,
    HOSP_MONTHS,
    LIFE_EXPECTANCY,
    LIFE_EXPECTANCY_MAX,
    LIFE_SUPPORT_MAX_YEARS,
    LIFE_SUPPORT_MIN_YEARS,
    LIFE_SUPPORT_PIVOT_AGE,
    LIFESTYLE_RATES,
    RETIREMENT_AGE,
    TPD_COST,
    TPD_YEARS,
    fv,
    fv_annuity,
    life_support_years,
    lifestyle_rate,
    pv_annuity,
    pv_annuity_due,
    real_return,
    remaining_gap,
    round_money,
    years_in_retirement,
    years_to_retirement,
)
from src.pipeline.need_calculator import evaluate_session  # noqa: E402
from src.pipeline.need_profiler import (  # noqa: E402
    AI_NEED_LABELS,
    GROWTH_UNIFIED,
    PROTECTION_UNIFIED,
    identify_needs,
    scale_scores,
    score_all_needs,
    select_unified_top,
)
from src.predict import (  # noqa: E402
    CASH_SAVINGS_SHARE,
    INVESTMENTS_SHARE,
    PROPERTY_LTV,
    _assumed_life_policy,
    seed_property_value,
)
from src.session_rates import DEFAULTS  # noqa: E402
from src.sv_payload import build_sv_payload  # noqa: E402

# Bump the version in this filename for every workbook change. Do not overwrite
# a version the user already has open (V0-01, V0-02, … stay as snapshots).
OUT = Path(__file__).resolve().parent / "Calculations V0-13.xlsx"
ANCHORS = json.loads(
    (GP_ROOT / "src" / "pipeline" / "prompts" / "income_anchors.json").read_text(encoding="utf-8")
)
PROFILER_CFG = json.loads(
    (GP_ROOT / "src" / "pipeline" / "prompts" / "Need_profiler.json").read_text(encoding="utf-8")
)

CURRENT_YEAR = 2026
UNIFIED = ("N_INC", "N_CRI", "N_TPD", "N_HOS", "N_RET", "N_EDU", "N_SAV", "N_PRP")
PROT = ("N_INC", "N_CRI", "N_TPD", "N_HOS")
WEALTH = ("N_RET", "N_EDU", "N_SAV", "N_PRP")
AI_LABELS = list(AI_NEED_LABELS.values())  # insertion order
AI_KEYS = list(AI_NEED_LABELS.keys())

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
    profile = {
        "Age": int(p["age"]),
        "Gender": p["gender"],
        "Dependents": int(p["dependents"]),
        "Occupation": p["occupation"],
        "Smoker": bool(p["llm_smoker"]),
        "MonthlyIncome": float(plu["income"]),
        "MonthlyExpense": float(plu["expense"]),
        "Currency": p.get("llm_currency") or "SGD",
        "TotalAssets": float(plu["cash"] + plu["investments"]),
        "TotalLiabilities": float(plu["liabilities"]),
        "ExistingLifeProtection": 0,
        "ExistingCriticalIllnessCoverage": 0,
        "ExistingDisabilityProtection": 0,
        "ExistingHospitalizationCoverage": 0,
        "CarOwnership": bool(p["llm_car"]),
        "HomeOwnership": bool(p["llm_property"]),
        "InternationalTraveling": bool(p["llm_travelling"]),
        "Sports": p["llm_sports"],
        "HospitalType": p["llm_hospital_type"],
        "WardType": p["llm_ward_type"],
        "Lifestyle": p["llm_retirement_lifestyle"],
    }
    result = identify_needs(profile, top_n=4)
    ranked = result["rankedNeeds"]
    enabled = set(select_unified_top(ranked, top_n=4, has_property=bool(p["llm_property"])))
    raw = {n["needLabel"]: next(
        x["weightage_score"] for x in scale_scores(score_all_needs(profile)) if False
    ) for n in []}  # placeholder to keep linters calm
    del raw
    # raw before scale
    raw_list = score_all_needs(profile)
    raw_map = {n["needLabel"]: n["weightage_score"] for n in raw_list}
    scaled_map = {n["needLabel"]: n["weightage_score"] for n in ranked}
    unified_score = {}
    for lab, ut in [
        ("Life Protection", "N_INC"),
        ("Critical Illness", "N_CRI"),
        ("Disability", "N_TPD"),
        ("Hospitalization", "N_HOS"),
        ("Retirement", "N_RET"),
        ("Education", "N_EDU"),
        ("General Savings", "N_SAV"),
        ("Home Protection", "N_PRP"),
    ]:
        unified_score[ut] = scaled_map.get(lab)
    priority = {ut: (5 if (unified_score.get(ut) or 0) > 7 else 3) for ut in UNIFIED}
    return {
        "raw": raw_map,
        "scaled": scaled_map,
        "enabled": enabled,
        "priority": priority,
        "ranked": ranked,
    }


def twin_needs(p: dict, plu: dict, enabled: set[str]) -> dict:
    session = {
        "age": int(p["age"]),
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
            for t in UNIFIED
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
    infl = DEFAULTS["inflationRate"]
    inv = DEFAULTS["investmentReturn"]
    r = real_return(inv, infl)
    age = int(p["age"])
    suggested = [t for t in UNIFIED if t in enabled and (needs[t]["gap"] or 0) > 0]
    sug_p = [t for t in suggested if t in PROT]
    sug_w = [t for t in suggested if t in WEALTH]
    plan_sum, plan_prem = {}, {}
    for t in sug_p:
        sm = max(0, _js_round(needs[t]["gap"]))
        plan_sum[t] = sm
        plan_prem[t] = _cover_premium(sm)
    take = plu["take_home"]
    available = take - plu["expense"]
    bud = max(0.0, available * 12)
    prem_yr = sum(plan_prem.values())
    left = max(0.0, bud - prem_yr)
    if sug_w:
        share = max(0, _js_round((left * 0.5) / 12 / len(sug_w) / 50) * 50)
    else:
        share = 0
    plan_mth, plan_lump = {}, {}
    for t in sug_w:
        if t == "N_RET":
            yrs = max(0, RETIREMENT_AGE - age)
        else:
            yrs = max(0, (CURRENT_YEAR + 10) - CURRENT_YEAR)
        gap = needs[t]["gap"]
        if gap <= 0:
            monthly_cap = 0
        elif yrs <= 0:
            monthly_cap = _round_up(gap / 12, 50) if False else _round_up(0, 50)
            # periods<=0 → annualPmtToHitFv returns 0
            monthly_cap = 0
        elif abs(r) < 1e-12:
            monthly_cap = _round_up((gap / yrs) / 12, 50)
        else:
            annual = (gap * r) / ((1 + r) ** yrs - 1)
            monthly_cap = _round_up(annual / 12, 50)
        plan_mth[t] = min(share, monthly_cap)
        plan_lump[t] = 0
    return {
        "suggested": suggested,
        "plan_sum": plan_sum,
        "plan_prem": plan_prem,
        "plan_mth": plan_mth,
        "plan_lump": plan_lump,
        "share": share,
        "invest_mth": sum(plan_mth.values()),
        "invest_lump": sum(plan_lump.values()),
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
        # identify_needs is the live function.
        needs = twin_needs(p, plu, prof["enabled"])
        for t in UNIFIED:
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
    sample = {
        "age": 42,
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
    expect_inc = round_money(0 + 200000 + pv_annuity(4000 * 12, r, life_support_years(42)))
    expect_cri = round_money(pv_annuity_due(6800 * 12, r, CI_YEARS) + CI_COST)
    expect_tpd = round_money(pv_annuity_due(6800 * 12, r, TPD_YEARS) + TPD_COST)
    expect_hos = round_money(6800 * HOSP_MONTHS)
    expect_edu = round_money(EDU_TOTAL_COST * ((1 + 0.023) ** 10))
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
    errors.extend(verify_engine_inputs())
    return errors


def persona_session(p: dict) -> dict:
    """GP session after onboarding and the default plan seed, as the SV / HappiU tabs read it."""
    plu = twin_plu(p)
    prof = twin_profiler(p, plu)
    needs = twin_needs(p, plu, prof["enabled"])
    plan = twin_plan(p, plu, needs, prof["enabled"])
    return session_for(p, plu, prof, needs, plan, dict(DEFAULTS))


def verify_engine_inputs() -> list[str]:
    """The SV / HappiU twins must read the same numbers GP's payload builders send."""
    errors: list[str] = []
    tables = load_hu_tables()
    for p in PERSONAS:
        s = persona_session(p)
        pid = p["id"]
        sv = twin_sv(s)
        pay = build_sv_payload(s)
        pd = pay["personalDetails"][0]
        assets = {a["type"]: a for a in pd["assets"]}
        loans = pd["liabilities"]["loans"]
        prem = sum(x["regularPremium"] for x in pd["existingInsurance"] if x["death"] > 0)
        checks = {
            "salary": (pd["cashFlows"]["income"][0]["absoluteValue"], sv["sal0"]),
            "spend": (pd["cashFlows"]["expenses"][0]["absoluteValue"], sv["exp0"]),
            "cash": (assets["A_SAV"]["currentValue"], sv["cash"][0]),
            "investments": (assets["INVESTMENT_PORTFOLIO"]["currentValue"], sv["inv"][0]),
            "property": (assets["RESIDENTIAL_PROPERTY"]["currentValue"], sv["prop"][0]),
            "contribution": (assets["INVESTMENT_PORTFOLIO"]["recurringContribution"]["value"], sv["contrib"]),
            "cpf region": (pd["socialSecurity"]["region"] == "R_SGP", s["residency"] != "Foreigner"),
            "payout age": (pd["socialSecurity"]["ageStartPayout"], max(65, s["ageOfRetirement"])),
            "mortgage": (loans[0]["currentValue"] if loans else 0, sv["pre"]["loans"][0]),
            "instalment": (loans[0]["installments"] if loans else 0, sv["inst"]),
            "life premium": (prem * 1.01, sv["lifePrem"]),
        }
        for name, (got, want) in checks.items():
            if got != want and not (isinstance(got, (int, float)) and abs(got - want) < 1e-6):
                errors.append(f"{pid} SV {name}: payload {got} twin {want}")
        bvo = pay.get("benefitVisualizerOutput") or []
        pots = sv_plan_pots(s, max(20, 100 - s["age"]))
        if len(bvo) != len(pots):
            errors.append(f"{pid} SV plan pots: payload {len(bvo)} twin {len(pots)}")
        for prod, pot in zip(bvo, pots):
            cols = {c["column"]: c["values"] for c in prod["productPlans"][0]["benefitProjection"]}
            if cols["totalPremiumPaidToDate"] != pot["prem"]:
                errors.append(f"{pid} SV pot {pot['type']} premiums differ")
            if pot["value"] is not None and cols.get("totalAccountValue") != pot["value"]:
                errors.append(f"{pid} SV pot {pot['type']} account differs")

        try:
            hu = twin_hu(s, tables)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{pid} HU twin raised {exc!r}")
            continue
        hp = build_happiu_payload(s)
        hd = hp["personalDetails"][0]
        codes = [n["type"] for n in hd["needs"]]
        if codes != [gl["code"] for gl in hu["goals"]]:
            errors.append(f"{pid} HU goals: payload {codes} twin {[gl['code'] for gl in hu['goals']]}")
            continue
        budget = {b["goalId"]: b["benefitAmount"] for b in hp["solutionOptimizerOutput"]["segregatedBudget"]}
        for n, gl in zip(hd["needs"], hu["goals"]):
            if n["priority"] != gl["priority"]:
                errors.append(f"{pid} HU {gl['code']} priority: payload {n['priority']} twin {gl['priority']}")
            if abs(budget.get(gl["code"], 0.0) - gl["benefit"]) > 1e-6:
                errors.append(f"{pid} HU {gl['code']} benefit: payload {budget.get(gl['code'])} twin {gl['benefit']}")
            if gl["type"] == "N_INC" and float(n["existingSumAssured"] or 0) != gl["existing"]:
                errors.append(f"{pid} HU N_INC existing: payload {n['existingSumAssured']} twin {gl['existing']}")
        dur = hp["needCalculatorOutput"]["N_RET"]["primaryOutput"][PARTNER_ID][0]["durationOfRetirement"]
        if (dur + 65 if dur > 0 else 83) != hu["le"]:
            errors.append(f"{pid} HU life expectancy: payload {dur} + 65 twin {hu['le']}")
        a = {x["type"]: x["currentValue"] for x in hd["assets"]}
        if a["A_SAV"] != float(s["cash"]) or a["A_INV"] != float(s["investments"]):
            errors.append(f"{pid} HU assets differ")
        if hd["riskProfile"] != 4 or hd["cashFlows"]["monthlyIncome"] != s["incomeMonthly"]:
            errors.append(f"{pid} HU riskProfile / income differ")
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


def build_assumptions(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "Assumptions"
    ws.sheet_properties.tabColor = TEAL
    ws.freeze_panes = "A3"
    _fill(ws, "A1", "Assumptions and shared data — values the live code actually reads", title_font, paper_fill, border=False)
    ws.merge_cells("A1:G1")
    ws.row_dimensions[1].height = 22
    _fill(
        ws,
        "A2",
        "Yellow cells are editable. Every other tab reads these named cells. "
        "The HappiU q(age) and social-security tables (copied from HU) sit below the factor weights.",
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
        (17, "endAge (chart horizon)", 85),
        (19, "CPF rates and formulas live on the CPF tab (country on / off)", None),
        (27, "Need parameters (src/pipeline/goal_math.py)", None),
        (28, "lifestyleFrugal", 0.75),
        (29, "lifestyleStressFree", 1.00),
        (30, "lifestyleOnlyTheBest", 1.25),
        (31, "lifeSupportMin", LIFE_SUPPORT_MIN_YEARS),
        (32, "lifeSupportMax", LIFE_SUPPORT_MAX_YEARS),
        (33, "lifeSupportPivotAge", LIFE_SUPPORT_PIVOT_AGE),
        (34, "CI_YEARS", CI_YEARS),
        (35, "CI_COST", CI_COST),
        (36, "TPD_YEARS", TPD_YEARS),
        (37, "TPD_COST", TPD_COST),
        (38, "HOSP_MONTHS", HOSP_MONTHS),
        (39, "EDU_TOTAL_COST", EDU_TOTAL_COST),
        (40, "eduYearsDefault", 10),
        (41, "savIncomeMultiple", 1),
        (42, "prpIncomeMultiple", 5),
        (44, "Household seeding (src/predict.py spend / assets; CPF is on the CPF tab)", None),
        (45, "spendShareBase", 0.675),
        (46, "spendSharePerDependant", 0.05),
        (47, "spendShareCap", 0.90),
        (48, "assetsSaveShare", 0.5),
        (49, "workStartAge", 21),
        (50, "liabilityRatio (PLU only; not the mortgage)", 0.7),
        (51, "CASH_SAVINGS_SHARE", CASH_SAVINGS_SHARE),
        (52, "INVESTMENTS_SHARE", INVESTMENTS_SHARE),
        (53, "propertyLow", 350_000),
        (54, "propertyMid", 650_000),
        (55, "propertyHigh", 850_000),
        (56, "propertyIncomeLow", 10_000),
        (57, "propertyIncomeHigh", 20_000),
        (58, "PROPERTY_LTV", PROPERTY_LTV),
        (59, "lifePremiumRate", 0.0031),
        (60, "lifeRoundUnit", 100_000),
        (62, "Plan and budget (frontend/src/lib/planProducts.ts)", None),
        (63, "protectionPremiumRate", 0.00078),
        (64, "FREE_BUDGET_SHARE", 0.5),
        (65, "lumpRoundStep", 1000),
        (66, "monthlyRoundStep", 50),
        (67, "coverPremRoundStep", 10),
        (68, "coverSliderPremFloor", 200),
        (70, "HappiU budget envelope (src/hu_payload.py) — not Budget Calculator", None),
        (71, "annualBudget", 1500),
        (72, "placeholderNeedBudget", 200),
        (73, "gfr", 0.05),
        (74, "benefitRound", 50_000),
        (75, "huNumSims", 200),
        (76, "funeralLump", 10_000),
        (77, "criMedicalPlaceholder", 200_000),
        (79, "Risk → investmentReturn seed (frontend/src/lib/riskCapacity.ts)", None),
        (80, "suggestBand1", 0.030),
        (81, "suggestBand2", 0.035),
        (82, "suggestBand3", 0.042),
        (83, "suggestBand4", 0.050),
        (84, "suggestBand5", 0.055),
        (85, "defaultRiskTolerance", 3),
    ]
    named = {
        "inflationRate": "B5",
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
        "lifestyleFrugal": "B28",
        "lifestyleStressFree": "B29",
        "lifestyleOnlyTheBest": "B30",
        "lifeSupportMin": "B31",
        "lifeSupportMax": "B32",
        "lifeSupportPivotAge": "B33",
        "CI_YEARS": "B34",
        "CI_COST": "B35",
        "TPD_YEARS": "B36",
        "TPD_COST": "B37",
        "HOSP_MONTHS": "B38",
        "EDU_TOTAL_COST": "B39",
        "eduYearsDefault": "B40",
        "savIncomeMultiple": "B41",
        "prpIncomeMultiple": "B42",
        "spendShareBase": "B45",
        "spendSharePerDependant": "B46",
        "spendShareCap": "B47",
        "assetsSaveShare": "B48",
        "workStartAge": "B49",
        "liabilityRatio": "B50",
        "CASH_SAVINGS_SHARE": "B51",
        "INVESTMENTS_SHARE": "B52",
        "propertyLow": "B53",
        "propertyMid": "B54",
        "propertyHigh": "B55",
        "propertyIncomeLow": "B56",
        "propertyIncomeHigh": "B57",
        "PROPERTY_LTV": "B58",
        "lifePremiumRate": "B59",
        "lifeRoundUnit": "B60",
        "protectionPremiumRate": "B63",
        "FREE_BUDGET_SHARE": "B64",
        "lumpRoundStep": "B65",
        "monthlyRoundStep": "B66",
        "coverPremRoundStep": "B67",
        "coverSliderPremFloor": "B68",
        "annualBudget": "B71",
        "placeholderNeedBudget": "B72",
        "gfr": "B73",
        "benefitRound": "B74",
        "huNumSims": "B75",
        "funeralLump": "B76",
        "criMedicalPlaceholder": "B77",
    }
    for row, label, value in rows:
        if value is None:
            _fill(ws, f"A{row}", label, sec_font, sec_fill, border=False)
            ws.merge_cells(f"A{row}:C{row}")
            continue
        _fill(ws, f"A{row}", label)
        editable = row not in (11,)
        pct_rows = {
            5, 6, 7, 8, 9, 10, 28, 29, 30,
            45, 46, 47, 48, 50, 51, 52, 58, 59, 63, 64, 73, 80, 81, 82, 83, 84,
        }
        if row in pct_rows:
            num = "0.00%" if row in (59, 63) else "0.0%"
        elif isinstance(value, float) and abs(value) < 10 and value != int(value):
            num = "0.000"
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
    ws["C11"] = "Need Calculator and Plan Calculator discount at this rate"
    ws["C11"].font = note_font

    for name, cell in named.items():
        col = "".join(c for c in cell if c.isalpha())
        row = "".join(c for c in cell if c.isdigit())
        # Both column and row must be absolute. `$B45` is row-relative, so
        # =spendShareCap on People Like You row 28 reads Assumptions!B74.
        _name(wb, name, f"Assumptions!${col}${row}")

    # Income bands
    _fill(ws, "E4", "Singapore occupation income bands (income_anchors.json)", sec_font, sec_fill, border=False)
    ws.merge_cells("E4:G4")
    _fill(ws, "E5", "occupation", h_font, header_fill, center)
    _fill(ws, "F5", "min", h_font, header_fill, center)
    _fill(ws, "G5", "max", h_font, header_fill, center)
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
        _fill(ws, f"E{r}", short_name.get(occ["id"], occ["label"]))
        _fill(ws, f"F{r}", float(b["min"]), num="#,##0", align=center)
        _fill(ws, f"G{r}", float(b["max"]), num="#,##0", align=center)
        _fill(ws, f"H{r}", occ["label"], font=note_font)
        r += 1
    _name(wb, "IncomeBands", f"Assumptions!$E$6:$G${r - 1}")

    # Stress events (shared catalog; SV only)
    _fill(ws, "E20", "Stress events (frontend/src/lib/stressEvents.ts) — Scenario Visualizer only", sec_font, sec_fill, border=False)
    ws.merge_cells("E20:I20")
    for i, h in enumerate(["id", "label", "default size", "default year", "what SV applies"], 5):
        _fill(ws, f"{get_column_letter(i)}21", h, h_font, header_fill, center)
    events = [
        ("crash", "Market crash", "35%", "year 8", "Haircut on invested assets"),
        ("ccy", "Currency shock", "14%", "year 6", "Haircut on liquid assets at 2/3 of slider"),
        ("infl", "Inflation shock", "+3 pp", "years 4–9", "Session inflationRate plus extra"),
        ("inc", "Impact on income", "−20%", "years 5–10", "Salary reduced for that span"),
        ("death", "Death", "S$20,000", "year 17", "One-time cost; salary → 0"),
        ("ci", "Critical illness", "S$150,000", "year 12", "One-time medical cost"),
        ("tpd", "Total & permanent disability", "S$200,000", "year 15", "One-time medical cost"),
        ("pa", "Personal accident", "S$80,000", "year 10", "One-time medical cost"),
        ("hosp", "Hospitalisation", "S$120,000", "year 9", "One-time hospital bill"),
        ("care", "Long-term care years", "S$90,000 / yr", "years 30–35", "Extra annual spend"),
        ("wed", "Wedding / marriage", "S$60,000", "year 5", "One-time cost"),
        ("baby", "Newborn", "S$35,000", "year 3", "One-time cost"),
        ("exp", "Impact on expenses", "+15%", "years 6–12", "Living spend raised"),
    ]
    for i, row in enumerate(events):
        for j, v in enumerate(row):
            _fill(ws, f"{get_column_letter(5 + j)}{22 + i}", v)

    # Profiler factor-weight matrix
    _fill(ws, "A88", "Need Profiler factor weights (Need_profiler.json needs_factor_weights)", sec_font, sec_fill, border=False)
    ws.merge_cells("A88:M88")
    _fill(ws, "A89", "factor \\ need", h_font, header_fill, center)
    for i, lab in enumerate(AI_LABELS, 2):
        _fill(ws, f"{get_column_letter(i)}89", lab, h_font, header_fill, center)
    for i, factor in enumerate(FACTOR_ROWS):
        rr = 90 + i
        _fill(ws, f"A{rr}", factor)
        for j, lab in enumerate(AI_LABELS, 2):
            _fill(ws, f"{get_column_letter(j)}{rr}", _factor_weight(factor, lab), num="0", align=center)
    _name(wb, "ProfilerWeights", f"Assumptions!$B$90:$M${90 + len(FACTOR_ROWS) - 1}")
    for i, factor in enumerate(FACTOR_ROWS):
        _name(wb, f"PW_{i + 1}", f"Assumptions!$B${90 + i}:$M${90 + i}")

    _hu_tables(wb, ws, 90 + len(FACTOR_ROWS) + 3)

    ws["I4"] = (
        "Open issues (multi-country / multi-currency) are listed on the Discrepancies tab. "
        "Cash/investments is 15%/85%. Need Profiler money is local × FX → USD."
    )
    ws["I4"].font = note_font
    ws["I4"].alignment = wrap
    ws.merge_cells("I4:L6")

    _widths(ws, {"A": 52, "B": 16, "C": 56, "D": 14, "E": 36, "F": 14, "G": 14, "H": 16, "I": 22, "J": 16, "K": 16})
    ws.row_dimensions[2].height = 32
    ws.auto_filter.ref = "A5:B10"


HU_RATE_LABELS = {
    "mort": "mortality",
    "adb": "accidental death",
    "morb": "critical illness (morbidity)",
    "ptd": "permanent total disability",
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
        "Scenario Visualizer equals SV's one path (GP sends noDeathFlag). HappiU is a deterministic version of HU's Monte Carlo.",
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
            "Twelve AI labels are scored as Σ (factor_weight × option_weight), rounded to 2 dp, then min–max scaled 0–10. "
            "Income / expense / assets / liabilities convert local × FX to USD, then retuned USD bands. "
            "Car ownership, home ownership, travel, and existing life / CI cover have factor weights but no matching weight_options, so they add 0. "
            "select_unified_top ignores top_n (app.py still passes 4). If has_property, N_PRP replaces N_SAV in the second growth slot. "
            "priority = 5 if scaled score > 7 else 3. Personal accident / motor / travel / farewell are scored and dropped. "
            "Orange Enable? columns let you force a need on or off.",
            "src/pipeline/need_profiler.py, src/pipeline/prompts/Need_profiler.json, src/app.py top_n=4",
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
            "USD = local × rate. Example: 5,000 SGD × 0.74 = 3,700 USD; 5,000 VND × 0.000038 = 0.19 USD. "
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
            "The HappiU tab scores it without Monte Carlo: mortality, CI, PTD and dismemberment become probabilities, "
            "the alive path is weighted by survival, each goal is scored with HU's value function, then weights and "
            "the sigmoid give pre / post. Expect a few points of difference from live HU.",
            "src/hu_payload.py → POST /v1/score → HU. Twin: docs/calculations/deterministic_engines.py twin_hu",
            "HappiU (+ Assumptions q(age) tables)",
            "POST /v1/score",
        ),
        (
            "Scenario Visualizer",
            "SV, via GP",
            "Session after Plan, all six rates, ageOfRetirement, endAge, stress chips. CPF inside SV.",
            "Year-by-year wealth path. GP does not run the year step.",
            "preWealth = session without the plan; postWealth = plus included planMth / planLump / planSum / planPrem. "
            "svNumSims defaults to 20. Investment contribution = max(0, take-home − expenseMonthly) once a year. "
            "GP sends noDeathFlag, so every simulation is the same path: the Scenario Visualizer tab rebuilds it year "
            "by year (salary, spend, mortgage, CPF, assets, savings, plan pots) and equals SV. "
            "Crash, currency, inflation, income and expense events are orange inputs; life events are not modelled yet.",
            "src/sv_payload.py → POST /v1/project → SV. Twin: docs/calculations/deterministic_engines.py twin_sv",
            "Scenario Visualizer",
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
            plu["expense"], plu["cash"], plu["investments"], plu["property"],
            plu["mortgage"], plu["liabilities"], plu["life_sum"],
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
            "This is the only picker. CPF, People Like You, Need Profiler, Need Calculator, Plan, Budget, "
            "Scenario Visualizer, HappiU, FX, and Validation follow this cell."
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
        title="CPF — selected persona. Singapore employee ordinary-wage CPF (src/cpf.py). Off for every other country.",
    )
    _legend(ws, "F", 2)

    # Country on/off table (right of the form)
    _fill(ws, "I4", "D · COUNTRY SWITCH  —  CPF on? (edit)", font=h_font, fill=assume_hdr, align=center)
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
    r = _kv(ws, r, "propertyLow", "=propertyLow", "D", "seed_property_value: income < 10,000 → S$350,000.", "#,##0")
    r = _kv(ws, r, "propertyMid", "=propertyMid", "D", "income 10,000–20,000 → S$650,000.", "#,##0")
    r = _kv(ws, r, "propertyHigh", "=propertyHigh", "D", "income > 20,000 → S$850,000.", "#,##0")
    r = _kv(ws, r, "propertyIncomeLow", "=propertyIncomeLow", "D", "10,000. Below this → propertyLow.", "#,##0")
    r = _kv(ws, r, "propertyIncomeHigh", "=propertyIncomeHigh", "D", "20,000. Above this → propertyHigh.", "#,##0")
    r = _kv(ws, r, "PROPERTY_LTV", "=PROPERTY_LTV", "D", "Mortgage = round(property × 55%).", "0.0%")
    r = _kv(ws, r, "lifePremiumRate", "=lifePremiumRate", "D", "0.31% of sum assured.", "0.00%")
    r = _kv(ws, r, "lifeRoundUnit", "=lifeRoundUnit", "D", "Mortgage cover rounded to nearest S$100,000.", "#,##0")
    r = _kv(ws, r, "lifeExpectancyDefault", "=lifeExpectancyDefault", "D", "Used when raw LE is missing or ≤ 0.", "0")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  _apply_plu. Take-home is read from the CPF tab.", calc_hdr)
    r = _kv(
        ws, r, "band min",
        f'=IFERROR(INDEX(Assumptions!$F$6:$F$13,MATCH(B{occ},Assumptions!$E$6:$E$13,0)),"")',
        "C", "income_anchors.json Singapore min for occupation.", "#,##0",
    )
    bmin = r - 1
    r = _kv(
        ws, r, "band max",
        f'=IFERROR(INDEX(Assumptions!$G$6:$G$13,MATCH(B{occ},Assumptions!$E$6:$E$13,0)),"")',
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
    r = _kv(
        ws, r, "property",
        f'=IF(B{owns}=FALSE,0,IF(B{inc}<propertyIncomeLow,propertyLow,IF(B{inc}<=propertyIncomeHigh,propertyMid,propertyHigh)))',
        "C", "seed_property_value.", "#,##0",
    )
    prop = r - 1
    r = _kv(ws, r, "mortgage", f"=IF(B{prop}=0,0,{_round_even(f'B{prop}*PROPERTY_LTV')})", "C", "round(property × 55%).", "#,##0")
    mort = r - 1
    r = _kv(
        ws, r, "life sum assured",
        f"=MAX(IF(B{prop}>0,INT((B{mort}+lifeRoundUnit/2)/lifeRoundUnit)*lifeRoundUnit,0),"
        f"IF(B{deps}>0,{_round_even(f'B{inc}*12*5')},0))",
        "C", "_assumed_life_policy: max(mortgage rounded to 100k, 5 × annual income if dependents).", "#,##0",
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
        f"=MIN(99,IF(B{le_raw}>0,B{le_raw},lifeExpectancyDefault))",
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
    r = _kv(ws, r, "override expenseMonthly", f"={_px('W')}", "O", "Money page spend. Frontend MIN_EXPENSE_MONTHLY = 100 SGD.", "#,##0.00")
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
    r = _kv(ws, r, "expenseMonthly", f'=IF({_px("W")}="",B{exp},{_px("W")})', "C", "", "#,##0.00")
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
        title="Need Profiler — selected persona. Weighted scores → two protection + two growth. Orange Enable? overrides.",
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
    r = _kv(ws, r, "property (owns home)", f"={_px('N')}", "B", "Personas N. Swaps N_SAV ↔ N_PRP in the second growth slot.")
    owns = r - 1

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA  —  used by this component", assume_hdr)
    r = _kv(ws, r, "Existing hospital cover", 0, "D", "build_profiler_profile hard-codes Existing*Coverage = False → option weight 1.")
    r = _kv(ws, r, "Existing disability cover", 0, "D", "Same. Stored as 0 here; option weight of False is 1.")
    r = _kv(ws, r, "USD per 1 local", "=FX_usdPerLocal", "D", "From the FX tab. Income / expense / assets / liabilities convert local × this rate.", "0.000000")
    r = _kv(ws, r, "Selection rule", "2 prot + N_RET + 1 growth", "D", "select_unified_top ignores top_n. If owns home, N_PRP replaces N_SAV.")
    r = _kv(ws, r, "Profiler weight matrix", "Assumptions!B90:M104", "D", "Need_profiler.json needs_factor_weights. SUMPRODUCT with option weights.")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  local × FX → USD, then 15 option weights", calc_hdr)
    r = _kv(ws, r, "usd Income", "=IF(FX_usdPerLocal=\"\",\"\",PLU_incomeMonthly*FX_usdPerLocal)", "C", "local income × FX. S$5,000 × 0.74 ≈ 3,700 USD → Income weight 2.", "0.00")
    usd_inc = r - 1
    r = _kv(ws, r, "usd Expense", "=IF(FX_usdPerLocal=\"\",\"\",PLU_expenseMonthly*FX_usdPerLocal)", "C", "local expense × FX.", "0.00")
    usd_exp = r - 1
    r = _kv(ws, r, "usd Assets", "=IF(FX_usdPerLocal=\"\",\"\",(PLU_cash+PLU_investments)*FX_usdPerLocal)", "C", "cash + investments × FX.", "0.00")
    usd_ast = r - 1
    r = _kv(ws, r, "usd Liab", "=IF(FX_usdPerLocal=\"\",\"\",PLU_liabilities*FX_usdPerLocal)", "C", "PLU liabilities × FX.", "0.00")
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
    r = _kv(ws, r, "ow Ward", f'=IF(UPPER(B{ward})="A",3,IF(UPPER(B{ward})="B",2,0))', "C", "Ward Type.", "0")
    r = _kv(
        ws, r, "ow Lifestyle",
        f'=IF(LOWER(B{life})="frugal",1,IF(OR(LOWER(B{life})="stress-free",LOWER(B{life})="stress free"),2,IF(LOWER(B{life})="only the best",4,0)))',
        "C", "Basic/Comfortable/Luxurious score 0.", "0",
    )
    r = _kv(
        ws, r, "ow Sports",
        f'=IF(ISNUMBER(SEARCH("adventurous",B{sports})),4,IF(ISNUMBER(SEARCH("dont do sports",B{sports})),0,IF(ISNUMBER(SEARCH("life style",B{sports})),1,0)))',
        "C", "Free-text sports.", "0",
    )
    ow1 = r - 1
    ow_span = f"$B${ow0}:$B${ow1}"

    r += 1
    raw_rows = {}
    sc_rows = {}
    r = _section(ws, r, "C · RESULTS  —  raw Σ (factor × option), then min–max scale 0–10", calc_hdr)
    for i, lab in enumerate(AI_LABELS):
        src_col = get_column_letter(2 + i)
        r = _kv(
            ws, r, f"raw {lab}",
            f"=ROUND(SUMPRODUCT({ow_span},Assumptions!{src_col}$90:{src_col}$104),2)",
            "C", f"Need_profiler.json column {lab}.", "0.00",
        )
        raw_rows[lab] = r - 1
    raw_first = raw_rows[AI_LABELS[0]]
    raw_last = raw_rows[AI_LABELS[-1]]
    r = _kv(ws, r, "min raw", f"=MIN(B{raw_first}:B{raw_last})", "C", "scale_scores min.", "0.00")
    mn = r - 1
    r = _kv(ws, r, "max raw", f"=MAX(B{raw_first}:B{raw_last})", "C", "If max=min, divisor is forced to 1 so every scaled value is 0.", "0.00")
    mx = r - 1
    for lab in AI_LABELS:
        r = _kv(
            ws, r, f"scaled {lab}",
            f"=ROUND(((B{raw_rows[lab]}-B{mn})/IF(B{mx}>B{mn},B{mx}-B{mn},1))*10,1)",
            "C", "0–10, 1 decimal.", "0.0",
        )
        sc_rows[lab] = r - 1

    r += 1
    s_inc, s_cri, s_tpd, s_hos = (
        sc_rows["Life Protection"], sc_rows["Critical Illness"],
        sc_rows["Disability"], sc_rows["Hospitalization"],
    )
    s_edu, s_sav, s_prp = sc_rows["Education"], sc_rows["General Savings"], sc_rows["Home Protection"]
    r = _kv(ws, r, "tb N_INC", f"=B{s_inc}+0.004", "C", "Tie-break: Life Protection first in AI label order.", "0.000")
    tb_inc = r - 1
    r = _kv(ws, r, "tb N_CRI", f"=B{s_cri}+0.003", "C", "Critical Illness second.", "0.000")
    tb_cri = r - 1
    r = _kv(ws, r, "tb N_TPD", f"=B{s_tpd}+0.002", "C", "Disability third.", "0.000")
    tb_tpd = r - 1
    r = _kv(ws, r, "tb N_HOS", f"=B{s_hos}+0.001", "C", "Hospitalization last.", "0.000")
    tb_hos = r - 1
    mxp = f"MAX(B{tb_inc},B{tb_cri},B{tb_tpd},B{tb_hos})"
    r = _kv(
        ws, r, "prot1",
        f'=IF(B{tb_inc}={mxp},"N_INC",IF(B{tb_cri}={mxp},"N_CRI",IF(B{tb_tpd}={mxp},"N_TPD","N_HOS")))',
        "C", "Highest protection score after the 0.00x order bonus.",
    )
    prot1 = r - 1
    r = _kv(ws, r, "tb2 N_INC", f'=IF(B{prot1}="N_INC",-1,B{s_inc}+0.004)', "C", "Winner of prot1 is excluded.", "0.000")
    tb2_inc = r - 1
    r = _kv(ws, r, "tb2 N_CRI", f'=IF(B{prot1}="N_CRI",-1,B{s_cri}+0.003)', "C", "", "0.000")
    tb2_cri = r - 1
    r = _kv(ws, r, "tb2 N_TPD", f'=IF(B{prot1}="N_TPD",-1,B{s_tpd}+0.002)', "C", "", "0.000")
    tb2_tpd = r - 1
    r = _kv(ws, r, "tb2 N_HOS", f'=IF(B{prot1}="N_HOS",-1,B{s_hos}+0.001)', "C", "", "0.000")
    tb2_hos = r - 1
    mxp2 = f"MAX(B{tb2_inc},B{tb2_cri},B{tb2_tpd},B{tb2_hos})"
    r = _kv(
        ws, r, "prot2",
        f'=IF(B{tb2_inc}={mxp2},"N_INC",IF(B{tb2_cri}={mxp2},"N_CRI",IF(B{tb2_tpd}={mxp2},"N_TPD","N_HOS")))',
        "C", "Second protection.",
    )
    prot2 = r - 1
    r = _kv(ws, r, "tb N_EDU", f"=B{s_edu}+0.003", "C", "Education first among remaining growth.", "0.000")
    tb_edu = r - 1
    r = _kv(ws, r, "tb N_SAV", f"=B{s_sav}+0.002", "C", "General Savings second.", "0.000")
    tb_sav = r - 1
    r = _kv(ws, r, "tb N_PRP", f"=B{s_prp}+0.001", "C", "Home Protection last.", "0.000")
    tb_prp = r - 1
    mxg = f"MAX(B{tb_edu},B{tb_sav},B{tb_prp})"
    r = _kv(
        ws, r, "grow2 raw",
        f'=IF(B{tb_edu}={mxg},"N_EDU",IF(B{tb_sav}={mxg},"N_SAV","N_PRP"))',
        "C", "Before the home-ownership swap.",
    )
    grow_raw = r - 1
    r = _kv(
        ws, r, "grow2",
        f'=IF(AND(B{owns}=TRUE,B{grow_raw}="N_SAV"),"N_PRP",IF(AND(B{owns}=FALSE,B{grow_raw}="N_PRP"),"N_SAV",B{grow_raw}))',
        "C", "Second growth after forced N_RET. Home ownership swaps SAV/PRP.",
    )
    grow2 = r - 1

    sc_for = {
        "N_INC": s_inc, "N_CRI": s_cri, "N_TPD": s_tpd, "N_HOS": s_hos,
        "N_RET": sc_rows["Retirement"], "N_EDU": s_edu, "N_SAV": s_sav, "N_PRP": s_prp,
    }
    r += 1
    r = _section(ws, r, "C · RESULTS  —  eight UNIFIED flags. Orange Enable? = TRUE / FALSE / blank", calc_hdr)
    _fill(ws, f"A{r}", "type", font=h_font, fill=header_fill, align=center)
    _fill(ws, f"B{r}", "calc on", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"C{r}", "Enable?", font=h_font, fill=override_hdr, align=center)
    _fill(ws, f"D{r}", "on (effective)", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"E{r}", "priority", font=h_font, fill=calc_hdr, align=center)
    r += 1
    dv = DataValidation(type="list", formula1='"TRUE,FALSE,"', allow_blank=True)
    ws.add_data_validation(dv)
    first_en = r
    on_rows = {}
    for t in UNIFIED:
        if t in PROT:
            formula = f'=OR($B${prot1}="{t}",$B${prot2}="{t}")'
        elif t == "N_RET":
            formula = "TRUE"
        else:
            formula = f'=$B${grow2}="{t}"'
        _fill(ws, f"A{r}", t, font=h_font, fill=calc_hdr, align=center)
        _fill(ws, f"B{r}", formula, fill=calc_fill, align=center)
        _fill(ws, f"C{r}", "", fill=override_fill, align=center)
        _fill(ws, f"D{r}", f'=IF(C{r}="",B{r},C{r})', fill=green_fill, align=center)
        _fill(ws, f"E{r}", f"=IF(B{sc_for[t]}>7,5,3)", fill=calc_fill, align=center)
        on_rows[t] = r
        r += 1
    dv.add(f"C{first_en}:C{r - 1}")

    _bind(wb, "Need Profiler", {"NP_prot1": prot1, "NP_prot2": prot2, "NP_grow2": grow2})
    for t, row in on_rows.items():
        _name(wb, f"NP_on_{t}", f"'Need Profiler'!$D${row}")
        _name(wb, f"NP_priority_{t}", f"'Need Profiler'!$E${row}")
    _dash_widths(ws)
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 42


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
        title="Need Calculator — selected persona. evaluate_session / goal_math.py. Orange cells are goal-card sliders.",
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
    r = _kv(ws, r, "targetYear", "=currentYear+eduYearsDefault", "O", "Education horizon year.", "0")
    tgt = r - 1
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

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA  —  rates and need parameters", assume_hdr)
    r = _kv(ws, r, "inflationRate", "=inflationRate", "D", "Grows EDU cost. N_RET grows at realReturn, not inflation.", "0.00%")
    r = _kv(ws, r, "investmentReturn", "=investmentReturn", "D", "Used to form realReturn.", "0.00%")
    r = _kv(ws, r, "realReturn", "=realReturn", "D", "max(0, (1+i)/(1+π) − 1). Discount rate.", "0.00%")
    r = _kv(ws, r, "lifestyleFrugal", "=lifestyleFrugal", "D", "N_RET spend multiple when lifestyle=1.", "0.0%")
    r = _kv(ws, r, "lifestyleStressFree", "=lifestyleStressFree", "D", "Default lifestyle=2.", "0.0%")
    r = _kv(ws, r, "lifestyleOnlyTheBest", "=lifestyleOnlyTheBest", "D", "lifestyle=3.", "0.0%")
    r = _kv(ws, r, "lifeSupportMin / Max / Pivot", "=lifeSupportMin", "D", "supportYears = min(max(10, 50 − age), 25).", "0")
    r = _kv(ws, r, "CI_YEARS / CI_COST", "=CI_YEARS", "D", "3 years annuity-due + S$200,000.", "0")
    r = _kv(ws, r, "TPD_YEARS / TPD_COST", "=TPD_YEARS", "D", "5 years annuity-due + S$200,000.", "0")
    r = _kv(ws, r, "HOSP_MONTHS", "=HOSP_MONTHS", "D", "N_HOS = income × 6.", "0")
    r = _kv(ws, r, "EDU_TOTAL_COST", "=EDU_TOTAL_COST", "D", "75,000 grown at inflation.", "#,##0")
    r = _kv(ws, r, "savIncomeMultiple", "=savIncomeMultiple", "D", "1 × annual income if stored is 0.", "0")
    r = _kv(ws, r, "prpIncomeMultiple", "=prpIncomeMultiple", "D", "5 × annual income if stored is 0.", "0")
    r = _kv(ws, r, "currentYear / ageOfRetirement", "=currentYear", "D", "2026 / 65 in this workbook.", "0")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  horizons", calc_hdr)
    r = _kv(
        ws, r, "supportYears",
        f"=MIN(MAX(lifeSupportMin,lifeSupportPivotAge-B{age}),lifeSupportMax)",
        "C", "life_support_years(age).", "0",
    )
    supp = r - 1
    r = _kv(ws, r, "yearsToRet", f"=MAX(0,B{ret}-B{age})", "C", "years_to_retirement.", "0")
    ytr = r - 1
    r = _kv(ws, r, "yearsInRet", f"=MAX(0,PLU_leUsed-B{ret})", "C", "years_in_retirement(retAge, session LE).", "0")
    yir = r - 1
    r = _kv(ws, r, "eduYears", f"=MAX(0,B{tgt}-currentYear)", "C", "max(0, targetYear − thisYear).", "0")
    edu_y = r - 1

    rate_l = f"IF(B{life}=1,lifestyleFrugal,IF(B{life}=3,lifestyleOnlyTheBest,lifestyleStressFree))"
    dep_y = f'IF(OR(B{dep_y_cell}="",B{dep_y_cell}<=0),B{supp},B{dep_y_cell})'
    inc_rep = f'IF(B{inc_rep_cell}="",PLU_incomeMonthly,B{inc_rep_cell})'
    annual_ret = f"PLU_expenseMonthly*12*({rate_l})"
    grown = _fv(annual_ret, "realReturn", f"B{ytr}")
    ret_amt = f"MAX(0,ROUND({_pv_annuity(grown, 'realReturn', f'B{yir}')},0))"
    pmt_spend = "PLU_expenseMonthly*12"
    inc_amt = f"MAX(0,ROUND(B{beq}+PLU_mortgage+{_pv_annuity(pmt_spend, 'realReturn', dep_y)},0))"
    pmt_rep = f"({inc_rep})*12"
    cri_amt = f"MAX(0,ROUND({_pv_due(pmt_rep, 'realReturn', 'CI_YEARS')}+CI_COST,0))"
    tpd_amt = f"MAX(0,ROUND({_pv_due(pmt_rep, 'realReturn', 'TPD_YEARS')}+TPD_COST,0))"
    hos_amt = "MAX(0,ROUND(PLU_incomeMonthly*HOSP_MONTHS,0))"
    edu_amt = f"MAX(0,ROUND(EDU_TOTAL_COST*(1+inflationRate)^B{edu_y},0))"
    sav_amt = f"IF(B{sav_st}>0,ROUND(B{sav_st},0),ROUND(PLU_incomeMonthly*12*savIncomeMultiple,0))"
    prp_amt = f"IF(B{prp_st}>0,ROUND(B{prp_st},0),ROUND(PLU_incomeMonthly*12*prpIncomeMultiple,0))"

    rem0 = "PLU_investments"
    take_ret = f"MIN(MAX(0,B{tag_ret}),MAX(0,{rem0}))"
    rem1 = f"MAX(0,{rem0}-{take_ret})"
    take_edu = f"MIN(MAX(0,B{tag_edu}),{rem1})"
    rem2 = f"MAX(0,{rem1}-{take_edu})"
    take_sav = f"MIN(MAX(0,B{tag_sav}),{rem2})"
    rem3 = f"MAX(0,{rem2}-{take_sav})"
    take_prp = f"MIN(MAX(0,B{tag_prp}),{rem3})"

    amounts = {
        "N_INC": inc_amt,
        "N_CRI": cri_amt,
        "N_TPD": tpd_amt,
        "N_HOS": hos_amt,
        "N_RET": ret_amt,
        "N_EDU": edu_amt,
        "N_SAV": sav_amt,
        "N_PRP": prp_amt,
    }
    haves = {
        "N_INC": "ROUND(PLU_lifeSum,0)",
        "N_CRI": "0",
        "N_TPD": "0",
        "N_HOS": "0",
        "N_RET": f"ROUND({_fv(take_ret, 'realReturn', f'B{ytr}')},0)",
        "N_EDU": f"ROUND({_fv(take_edu, 'realReturn', f'B{edu_y}')},0)",
        "N_SAV": f"ROUND({_fv(take_sav, 'realReturn', f'B{edu_y}')},0)",
        "N_PRP": f"ROUND({_fv(take_prp, 'realReturn', f'B{edu_y}')},0)",
    }

    r += 1
    r = _section(ws, r, "C · RESULTS  —  amount / have / gap for every UNIFIED type (even when off)", calc_hdr)
    _fill(ws, f"A{r}", "type", font=h_font, fill=header_fill, align=center)
    _fill(ws, f"B{r}", "needAmount", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"C{r}", "have", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"D{r}", "gap", font=h_font, fill=calc_hdr, align=center)
    _fill(ws, f"E{r}", "Enable?", font=h_font, fill=override_hdr, align=center)
    _fill(ws, f"F{r}", "on (effective)", font=h_font, fill=calc_hdr, align=center)
    r += 1
    dv = DataValidation(type="list", formula1='"TRUE,FALSE,"', allow_blank=True)
    ws.add_data_validation(dv)
    first = r
    amt_rows, have_rows, gap_rows, on_rows = {}, {}, {}, {}
    notes = {
        "N_INC": "bequest + mortgage + PV of annual spend over dependYears.",
        "N_CRI": "Annuity-due of replacement income for CI_YEARS + CI_COST.",
        "N_TPD": "Annuity-due of replacement income for TPD_YEARS + TPD_COST.",
        "N_HOS": "incomeMonthly × HOSP_MONTHS.",
        "N_RET": "annualSpend × (1+realReturn)^T × a(realReturn, yearsInRet).",
        "N_EDU": "75,000 × (1+inflation)^eduYears.",
        "N_SAV": "Stored or 1× annual income.",
        "N_PRP": "Stored or 5× annual income.",
    }
    for t in UNIFIED:
        _fill(ws, f"A{r}", t, font=h_font, fill=calc_hdr, align=center)
        _fill(ws, f"B{r}", f"={amounts[t]}", fill=calc_fill, num="#,##0", align=center)
        _fill(ws, f"C{r}", f"={haves[t]}", fill=calc_fill, num="#,##0", align=center)
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

    _bind(wb, "Need Calculator", {"NC_age": age, "NC_yearsToRet": ytr, "NC_eduYears": edu_y, "NC_yearsInRet": yir})
    for t in UNIFIED:
        _name(wb, f"NC_amount_{t}", f"'Need Calculator'!$B${amt_rows[t]}")
        _name(wb, f"NC_have_{t}", f"'Need Calculator'!$C${have_rows[t]}")
        _name(wb, f"NC_gap_{t}", f"'Need Calculator'!$D${gap_rows[t]}")
        _name(wb, f"NC_on_{t}", f"'Need Calculator'!$F${on_rows[t]}")
    _dash_widths(ws)
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 16
    ws.column_dimensions["G"].width = 56


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
    for t in UNIFIED:
        r = _kv(ws, r, f"{t} on (from Need Calculator)", f"=NC_on_{t}", "A", "Effective enable after Need Calculator override.")
        r = _kv(ws, r, f"{t} gap (from Need Calculator)", f"=NC_gap_{t}", "A", "remaining_gap.", "#,##0")
    r = _kv(ws, r, "yearsToRet (from Need Calculator)", "=NC_yearsToRet", "A", "Retirement contribution horizon.", "0")
    r = _kv(ws, r, "eduYears (from Need Calculator)", "=NC_eduYears", "A", "EDU / SAV / PRP contribution horizon.", "0")

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS / SHARED DATA", assume_hdr)
    r = _kv(ws, r, "protectionPremiumRate", "=protectionPremiumRate", "D", "Dummy 0.00078. Future: premium-quote calculator API.", "0.00%")
    r = _kv(ws, r, "FREE_BUDGET_SHARE", "=FREE_BUDGET_SHARE", "D", "Half of leftover surplus split across wealth needs.", "0.0%")
    r = _kv(ws, r, "monthlyRoundStep", "=monthlyRoundStep", "D", "Contributions rounded to S$50.", "#,##0")
    r = _kv(ws, r, "coverPremRoundStep", "=coverPremRoundStep", "D", "Premium rounded to nearest step.", "#,##0")
    r = _kv(ws, r, "realReturn", "=realReturn", "D", "annualPmtToHitFv for the wealth cap.", "0.00%")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  suggested flags and protection sizing", calc_hdr)
    sug_rows = {}
    for t in UNIFIED:
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
    for t in PROT:
        r = _kv(
            ws, r, f"planSum {t}",
            f"=IF(B{sug_rows[t]},MAX(0,ROUND(NC_gap_{t},0)),0)",
            "C", "Suggested protection sum = gap.", "#,##0",
        )
        sum_rows[t] = r - 1
        r = _kv(
            ws, r, f"planPrem {t}",
            f"=IF(B{sum_rows[t]}<=0,0,MAX(0,ROUND((B{sum_rows[t]}*protectionPremiumRate)/coverPremRoundStep,0)*coverPremRoundStep))",
            "C", "coverPremiumFor(sum). Indicative, not half of slider max.", "#,##0",
        )
        prem_rows[t] = r - 1
    r = _kv(
        ws, r, "prot prem / yr",
        f"=B{prem_rows['N_INC']}+B{prem_rows['N_CRI']}+B{prem_rows['N_TPD']}+B{prem_rows['N_HOS']}",
        "C", "Sum of suggested protection premiums (before Include?).", "#,##0",
    )
    prot_yr = r - 1
    r = _kv(
        ws, r, "default wealth mth share",
        f"=IF(B{n_w}=0,0,MAX(0,ROUND((MAX(0,(PLU_takeHome-PLU_expenseMonthly)*12-B{prot_yr})"
        f"*FREE_BUDGET_SHARE)/12/B{n_w}/monthlyRoundStep,0)*monthlyRoundStep))",
        "C", "Leftover surplus × 50% / 12 / n wealth, rounded to S$50.", "#,##0",
    )
    share = r - 1

    cap_rows, mth_rows, lump_rows = {}, {}, {}
    for t in WEALTH:
        n_yrs = "NC_yearsToRet" if t == "N_RET" else "NC_eduYears"
        gap = f"NC_gap_{t}"
        annual = (
            f"IF(OR(({gap})<=0,({n_yrs})<=0),0,"
            f"IF(ABS(realReturn)<1E-12,({gap})/({n_yrs}),({gap})*realReturn/((1+realReturn)^({n_yrs})-1)))"
        )
        r = _kv(
            ws, r, f"cap mth {t}",
            f"=IF(({annual})<=0,0,ROUNDUP(({annual})/12/monthlyRoundStep,0)*monthlyRoundStep)",
            "C", "annualPmtToHitFv / 12, rounded up to S$50.", "#,##0",
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
    for t in UNIFIED:
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
        "+IF(PLAN_included_N_TPD,PLAN_prem_N_TPD,0)+IF(PLAN_included_N_HOS,PLAN_prem_N_HOS,0)",
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

    _fill(ws, "I4", "D · RATE TABLE  —  USD per 1 local unit (edit)", font=h_font, fill=assume_hdr, align=center)
    ws.merge_cells("I4:K4")
    _fill(ws, "I5", "currency", font=h_font, fill=header_fill, align=center)
    _fill(ws, "J5", "USD per 1 unit", font=h_font, fill=header_fill, align=center)
    _fill(ws, "K5", "note", font=h_font, fill=header_fill, align=center)
    fx_rows = [
        ("USD", 1.0, "Identity. 5,000 USD = 5,000 USD."),
        ("SGD", 0.74, "5,000 SGD × 0.74 = 3,700 USD."),
        ("VND", 0.000038, "5,000 VND × 0.000038 = 0.19 USD."),
        ("MYR", 0.225, ""),
        ("THB", 0.029, ""),
        ("PHP", 0.0175, ""),
        ("AUD", 0.66, ""),
        ("EUR", 1.09, ""),
        ("HKD", 0.128, ""),
    ]
    for i, (ccy, rate, note) in enumerate(fx_rows):
        rr = 6 + i
        _fill(ws, f"I{rr}", ccy, fill=input_fill, align=center)
        _fill(ws, f"J{rr}", rate, fill=input_fill, align=center, num="0.000000")
        _fill(ws, f"K{rr}", note, font=note_font, fill=paper_fill)
    _name(wb, "FxTable", f"FX!$I$6:$J${5 + len(fx_rows)}")

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
        '=IFERROR(VLOOKUP(PLU_currency,FxTable,2,FALSE),"")',
        "D",
        "Blank if Personas currency is not a row in the rate table.",
        "0.000000",
    )
    rate = r - 1

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  local × USD per 1", calc_hdr)
    usd = f'=IF($B${rate}="","",B{{loc}}*$B${rate})'
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

    _bind(wb, "FX", {
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
    ws.column_dimensions["K"].width = 42


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
        FormulaRule(formula=[f"OR(${in_col}{first}=FALSE,${age_col}{first}>endAge)"], fill=grey_fill),
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
    kv("SV_mortgage", "mortgage", "=PLU_mortgage", "A", "Mortgage loan, 20 years.", "#,##0")
    kv("SV_lifeSum", "life sum assured", "=PLU_lifeSum", "A", "Existing life policy (only when > 0).", "#,##0")
    kv("SV_lifePrem", "life premium / yr", "=PLU_lifePrem", "A", "regularPremium of the existing policy.", "#,##0")

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS  —  SV helium tenant conf.ini and SocialSecurityR_SGP", assume_hdr)
    kv("SV_LE", "lifeExpectancy (SV tenant)", 100, "D", "helium conf.ini. The path runs to age 100, not the session LE.", "0")
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
    pmt = "IF(ABS(loanRate)<1E-12,SV_mortgage/SV_loanYears,SV_mortgage*loanRate/(1-(1+loanRate)^(-SV_loanYears)))"
    kv("SV_inst", "mortgage instalment / yr", "=IF(SV_mortgage>0," + _round_even(pmt) + ",0)",
       "C", "Level annual payment that clears the loan in 20 years (goal_math.annual_loan_payment). "
       f"Paid from spend. {even}", "#,##0")
    kv("SV_contrib", "investment contribution / yr", "=" + _round_even("MAX(0,SV_takeHome-SV_expense)"),
       "C", f"sv_payload.py sends the MONTHLY surplus; SV adds it once a year. {even}", "#,##0")
    kv("SV_lifePremYr", "existing life premium / yr", "=IF(SV_lifeSum>0,SV_lifePrem,0)*(1+SV_savRate)",
       "C", "InsuranceBaseClass premium × (1 + savingsRate), first 20 years.", "#,##0.00")
    kv("SV_propRate", "property growth", "=MAX(0,assetReturn+SV_propPremium)", "C", "", "0.00%")
    kv("SV_wdYear", "goal withdrawal year", "=IF(NC_eduYears>=1,NC_eduYears,SV_T)",
       "C", "EDU / SAV / PRP fundsNeededYear − now (default 10).", "0")
    kv("SV_wdAmt", "goal withdrawal amount",
       "=IF(NC_eduYears<=SV_T,NC_on_N_EDU*NC_amount_N_EDU+NC_on_N_SAV*NC_amount_N_SAV+NC_on_N_PRP*NC_amount_N_PRP,0)",
       "C", "capitalSumRequired of each enabled goal, not inflated. Leaves savings in that year.", "#,##0")
    kv("SV_retMth", "plan RET monthly", "=IF(PLAN_included_N_RET,PLAN_mth_N_RET,0)", "C", "plan_benefit_visualizer pot.", "#,##0")
    kv("SV_retLump", "plan RET lump", "=IF(PLAN_included_N_RET,PLAN_lump_N_RET,0)", "C", "", "#,##0")
    kv("SV_retPay", "plan RET pay years", "=MAX(1,SV_ret-SV_age)", "C", "", "0")
    kv("SV_goalMth", "plan EDU + SAV + PRP monthly",
       "=IF(PLAN_included_N_EDU,PLAN_mth_N_EDU,0)+IF(PLAN_included_N_SAV,PLAN_mth_N_SAV,0)+IF(PLAN_included_N_PRP,PLAN_mth_N_PRP,0)",
       "C", "Same pay years and rate, so one pot column.", "#,##0")
    kv("SV_goalLump", "plan EDU + SAV + PRP lump",
       "=IF(PLAN_included_N_EDU,PLAN_lump_N_EDU,0)+IF(PLAN_included_N_SAV,PLAN_lump_N_SAV,0)+IF(PLAN_included_N_PRP,PLAN_lump_N_PRP,0)",
       "C", "", "#,##0")
    kv("SV_goalPay", "plan goal pay years", "=MAX(1,NC_eduYears)", "C", "", "0")
    kv("SV_protPrem", "plan protection premium / yr",
       "=IF(PLAN_included_N_INC,PLAN_prem_N_INC,0)+IF(PLAN_included_N_CRI,PLAN_prem_N_CRI,0)"
       "+IF(PLAN_included_N_TPD,PLAN_prem_N_TPD,0)+IF(PLAN_included_N_HOS,PLAN_prem_N_HOS,0)",
       "C", "Premiums only: protection pots have no account value on SV's no-death path.", "#,##0")
    kv("SV_protPay", "plan protection pay years", "=MAX(1,SV_ret-SV_age)", "C", "", "0")

    r += 1
    r = _section(ws, r, "E · OVERRIDE  —  stress events (blank size = off). Slider years as on the SV screen", override_hdr)
    kv("SV_crashY", "market crash: year", "", "O", "Slider year; SV applies it at year + 1.", "0")
    kv("SV_crashV", "market crash: size", "", "O", "e.g. 0.35. Every asset × (1 − size).", "0%")
    kv("SV_ccyY", "currency shock: year", "", "O", "", "0")
    kv("SV_ccyV", "currency shock: size", "", "O", "Liquid assets × (1 − size × 2/3).", "0%")
    kv("SV_inflFrom", "inflation shock: from", "", "O", "", "0")
    kv("SV_inflTo", "inflation shock: to", "", "O", "", "0")
    kv("SV_inflV", "inflation shock: extra", "", "O", "Added to inflationRate for the window.", "0.0%")
    kv("SV_incFrom", "income impact: from", "", "O", "", "0")
    kv("SV_incTo", "income impact: to", "", "O", "", "0")
    kv("SV_incV", "income impact: size", "", "O", "−0.2 = salary × 0.8 (also the CPF wage).", "0%")
    kv("SV_expFrom", "expense impact: from", "", "O", "", "0")
    kv("SV_expTo", "expense impact: to", "", "O", "", "0")
    kv("SV_expV", "expense impact: size", "", "O", "Scales spend, instalment and goal withdrawals.", "0%")
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
        "F", "C", "incF", "sal", "spend", "prem", "invNeg",
        "crashF", "ccyF", "cash", "inv", "home",
        "band", "ow", "oaRaw", "saRaw", "maRaw", "emp", "oa", "sa", "ma", "pay", "ra", "life", "cpf", "cpfCf",
        "loan", "savPre", "wPre",
        "retC", "retAcc", "goalC", "goalAcc", "protP", "pot", "insCf", "savPost", "wPost",
    ]
    c = _Cols(keys)
    top = r + 33  # room for the two sections below
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
    kv("SV_wPreEnd", "pre wealth at endAge", f'=IF(endAge-SV_age<=SV_T,INDEX({rng("wPre")},MAX(0,endAge-SV_age)+1),"")', "C", "Assumptions endAge.", "#,##0")
    kv("SV_wPostEnd", "post wealth at endAge", f'=IF(endAge-SV_age<=SV_T,INDEX({rng("wPost")},MAX(0,endAge-SV_age)+1),"")', "C", "", "#,##0")
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
            f"=IF(OR({live(rr)},{m(rr)}-1>=SV_salCut),0,SV_sal0*(1+incomeGrowthRate)^({m(rr)}-1)*{c('incF', rr)})"), money),
        ("spend", "spend + instalment + goals", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,(-SV_exp0*{c('C', rr)}-IF({m(rr)}<=SV_loanYears,SV_inst,0)"
            f"-IF(AND(SV_wdAmt>0,{m(rr)}=SV_wdYear),SV_wdAmt,0))"
            f"*IF(AND(SV_expOn,{m(rr)}>=SV_expS,{m(rr)}<=SV_expE),1+SV_expImp,1))"), money),
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
            f"=IF(OR({live(rr)},NOT(SV_cpfOn)),0,MIN(SV_sal0*(1+incomeGrowthRate)^({m(rr)}-1)*{c('incF', rr)},SV_owCap))"), money),
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
        ("loan", "mortgage balance", calc_fill, "=IF(SV_mortP>0,SV_mortP,0)", lambda rr: (
            f"=IF(OR({m(rr)}>SV_T,{m(rr)}>=SV_loanYears),0,MAX(0,{prev('loan', rr)}*(1+loanRate)-SV_inst))"), money),
        ("savPre", "savings (pre)", calc_fill, 0, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,{prev('savPre', rr)}*(1+SV_savRate)+{c('sal', rr)}+{c('spend', rr)}+{c('prem', rr)}"
            f"+{c('invNeg', rr)}+{c('cpfCf', rr)})"), money),
        ("wPre", "WEALTH pre", green_fill, None, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,MAX(0,{c('cash', rr)}+{c('inv', rr)}+{c('home', rr)}+{c('cpf', rr)}"
            f"+{c('savPre', rr)}-{c('loan', rr)}))"), money),
        ("retC", "RET paid in", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{m(rr)}-1>=SV_retPay),0,SV_retMth*12+IF({m(rr)}=1,SV_retLump,0))"), money),
        ("retAcc", "RET pot", calc_fill, 0, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,({prev('retAcc', rr)}+{c('retC', rr)})*(1+investmentReturn))"), money),
        ("goalC", "goal pots paid in", calc_fill, 0, lambda rr: (
            f"=IF(OR({live(rr)},{m(rr)}-1>=SV_goalPay),0,SV_goalMth*12+IF({m(rr)}=1,SV_goalLump,0))"), money),
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
            f"=IF({m(rr)}>SV_T,0,{prev('savPost', rr)}*(1+SV_savRate)+{c('sal', rr)}+{c('spend', rr)}+{c('prem', rr)}"
            f"+{c('invNeg', rr)}+{c('cpfCf', rr)}+{c('insCf', rr)})"), money),
        ("wPost", "WEALTH post", green_fill, None, lambda rr: (
            f"=IF({m(rr)}>SV_T,0,MAX(0,{c('cash', rr)}+{c('inv', rr)}+{c('home', rr)}+{c('cpf', rr)}"
            f"+{c('savPost', rr)}+{c('pot', rr)}-{c('loan', rr)}))"), money),
    ]
    groups = [
        ("year", "m", "in", header_fill),
        ("C · HUMAN CAPITAL  —  salary, spend, premiums (flows land in the year shown)", "F", "invNeg", calc_hdr),
        ("C · ASSETS", "crashF", "home", calc_hdr),
        ("C · CPF  —  SocialSecurityR_SGP", "band", "cpfCf", calc_hdr),
        ("C · PRE (today)", "loan", "wPre", calc_hdr),
        ("C · POST (with the plan)  —  plan_benefit_visualizer pots", "retC", "wPost", calc_hdr),
    ]
    _write_year_table(ws, top, specs, c, groups)
    _grey_rows(ws, first, last, c.letter["wPost"], c.letter["in"], c.letter["age"])
    for k in ("wPre", "wPost", "cpf", "savPre", "savPost", "sal", "spend", "cash", "inv", "home", "loan", "pot", "insCf"):
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
    kv("HU_leS", "session life expectancy", "=MIN(PLU_leUsed,99)", "A", "durationOfRetirement = LE − retirement age.", "0")

    r += 1
    r = _section(ws, r, "D · ASSUMPTIONS  —  HU conf.json / config/default/conf.ini / hu_payload.py", assume_hdr)
    kv("HU_ret", "ageOfRetirement", "=ageOfRetirement", "D", "", "0")
    kv("HU_defaultLE", "default life expectancy", 83, "D", "HU uses 83 when durationOfRetirement is 0.", "0")
    kv("HU_ciYearsGP", "CI income years (N_CRI on)", "=CI_YEARS", "D", "numYearsIncomeNeeded from GP.", "0")
    kv("HU_ciDefaultYears", "CI income years (N_CRI off)", 5, "D", "HU ciAssumptions default.", "0")
    kv("HU_medCost", "CI medical cost", 200_000, "D", "HU ciAssumptions medicalCost, × inflation.", "#,##0")
    kv("HU_ptdCost", "PTD medical cost", 444_000, "D", "ProductPTD, × inflation, first PTD only.", "#,##0")
    kv("HU_ptdCut", "PTD income cut", 0.5, "D", "", "0%")
    kv("HU_disCut", "dismemberment income cut", 1.0, "D", "From the year after.", "0%")
    kv("HU_ciMaxAge", "cover age (off-plan CI / TPD / HSP)", 75, "D", "Off-plan protection runs to age 75.", "0")
    kv("HU_depYears", "dependent years (N_INC)", 10, "D", "numYearDependents default.", "0")
    kv("HU_term", "plan policy term", 10, "D", "segregatedBudget policyTerm in hu_payload.py.", "0")
    kv("HU_whl", "wealth high-loss factor", 0.25, "D", "conf.ini wealth_hight_loss_factor.", "0.00")
    kv("HU_beta", "beta", 1, "D", "conf.ini beta.", "0.00")
    kv("HU_minMu", "minimum equity drift", 0.01, "D", "ProductEquity mu floor.", "0.00%")
    kv("HU_riskProfile", "riskProfile", 4, "D", "hu_payload.py default.", "0")
    kv("HU_retLifestyle", "retirement lifestyle rate", "=lifestyleStressFree", "D", "N_RET lifestyle 2.", "0.00")
    kv("HU_retShare", "retirement spend share", 0.75, "D", "expectedLivingExpenseInTheCountry = living × 0.75.", "0.00")
    kv("HU_benefitRound", "benefit round", "=benefitRound", "D", "Wealth / unplanned benefit = round(need / 50,000) × 50,000.", "#,##0")
    kv("HU_calRet", "N_RET calibration", 2, "D", "N_INC 1, N_RET 2, consumption goals 1 / count.", "0")

    r += 1
    r = _section(ws, r, "C · DETERMINISTICALLY CALCULATED  —  HU input mapping", calc_hdr)
    kv("HU_le", "life expectancy (HU)", "=IF(HU_leS>HU_ret,HU_leS,HU_defaultLE)", "C", "durationOfRetirement + 65, or 83.", "0")
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
    kv("HU_wdOn", "goal withdrawals on the path", "=AND(HU_T>0,NC_eduYears<=HU_T)", "C", "")
    kv("HU_wdYear", "goal withdrawal year", "=IF(HU_T>0,MOD(NC_eduYears-1,HU_T)+1,0)", "C", "fundsNeededYear − now.", "0")
    kv("HU_wdIncome", "SAV + PRP booked as income",
       "=NC_on_N_SAV*NC_amount_N_SAV+NC_on_N_PRP*NC_amount_N_PRP", "C",
       "HU adds the SAV / PRP amount as income in the target year and spends it again (net 0).", "#,##0")
    kv("HU_wdOut", "EDU + SAV + PRP spent",
       "=NC_on_N_EDU*NC_amount_N_EDU+NC_on_N_SAV*NC_amount_N_SAV+NC_on_N_PRP*NC_amount_N_PRP", "C", "", "#,##0")

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
            }.get(t, f"=IF({plan_ok},HU_term,HU_ciMaxAge-HU_age)+1" if t in PROT else "=MAX(0,NC_eduYears)"),
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
        ("qp", "q PTD", calc_fill, None, q("ptd"), prob),
        ("qd", "q dismemberment", calc_fill, None, q("dis"), prob),
        ("S", "alive", calc_fill, 1, lambda rr: f"=IF({t_(rr)}>HU_T,0,{prev('S', rr)}*(1-{c('qm', rr)})*(1-{c('qa', rr)}))", prob),
        ("survW", "score weight", calc_fill, None, lambda rr: f"=IF({t_(rr)}>=HU_T,0,N({c('S', rr + 1)}))", prob),
        ("noPtd", "no PTD yet", calc_fill, 1, lambda rr: f"={prev('noPtd', rr)}*(1-{c('qp', rr)})", prob),
        ("pPtd", "P(PTD so far)", calc_fill, 0, lambda rr: f"=1-{c('noPtd', rr)}", prob),
        ("pPtdF", "P(first PTD)", calc_fill, 0, lambda rr: f"={prev('noPtd', rr)}*{c('qp', rr)}", prob),
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
            f"={c('x', rr)}+{c('ss', rr)}+IF(AND(HU_wdOn,{t_(rr)}=HU_wdYear),HU_wdIncome,0)"), money),
        ("cut", "expected income cut", calc_fill, 0, lambda rr: (
            f"=HU_ciProp*{c('pCi', rr)}+HU_ptdCut*{c('pPtd', rr)}+HU_disCut*{c('pDis', rr)}"), "0.0000"),
        ("pos", "income after cut", calc_fill, 0, lambda rr: f"=IF({live(rr)},0,{c('base', rr)}*(1-{c('cut', rr)}))", money),
        ("spend", "spend", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,IF(AND(HU_retExp>0,{t_(rr)}-1>=HU_dtr),HU_retExp,HU_exp0)*{c('infl', rr)})"), money),
        ("neg", "spend + goals", calc_fill, 0, lambda rr: (
            f"=-{c('spend', rr)}-IF(AND(HU_wdOn,{t_(rr)}=HU_wdYear),HU_wdOut,0)"), money),
        ("med", "expected medical", calc_fill, 0, lambda rr: (
            f"=IF({live(rr)},0,-HU_medCost*{c('infl', rr)}*{c('qc', rr)}-HU_ptdCost*{c('infl', rr)}*{c('pPtdF', rr)})"), money),
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


def build_discrepancies(wb: Workbook) -> None:
    ws = wb.create_sheet("Discrepancies")
    ws.sheet_properties.tabColor = "9B1D20"
    ws.freeze_panes = "A3"
    _fill(ws, "A1", "Open issues — multi-country / multi-currency, and the SV / HappiU engines", title_font, paper_fill, border=False)
    ws.merge_cells("A1:F1")
    _fill(
        ws,
        "A2",
        "Resolved formula/docs mismatches from V0-11 were closed. "
        "What remains is product work for more than one country or currency. "
        "People Like You stays local. Need Profiler ranks in USD after FX. Need Calculator stays in session currency.",
        note_font,
        paper_fill,
        border=False,
    )
    ws.merge_cells("A2:F2")
    _headers(ws, 3, ["#", "Component", "Open issue", "Today", "Needed for multi-country", "Where"])
    rows = [
        (
            "1",
            "Need Calculator SGD lumps",
            "CI/TPD add 200,000 and education starts at 75,000 as Singapore-dollar constants. Annuities follow the session currency. A VND income plus a 200,000 add-on mixes units.",
            "Session-local spend/income formulas + fixed SGD lumps. No FX on constants.",
            "FX-convert the SGD lumps into the session currency, or ship per-country cost tables. Do not compute needAmount in USD while income stays local.",
            "src/pipeline/goal_math.py CI_COST TPD_COST EDU_TOTAL_COST; Need-calculator.md",
        ),
        (
            "2",
            "Need Profiler FX is market FX, not PPP",
            "Income/expense/assets convert local × market USD-per-local, then USD bands. Cost of living is not adjusted.",
            "src/fx.py rates match the FX tab. Bands in Need_profiler.json (lt).",
            "Purchasing-power (PPP) rates if “middle class” should mean the same living standard across countries.",
            "src/fx.py; Need_profiler.json weight_options Income/Expense/Assets/Liabilities",
        ),
        (
            "3",
            "Need Profiler × People Like You enums",
            "PLU lifestyle/ward/sports strings do not match profiler options, so those flags score 0 in every country.",
            "PLU: Basic|Comfortable|Luxurious, Single|Double|Ward. Profiler: frugal|stress-free|only the best, A|B.",
            "One vocabulary in both prompts (or an explicit map). Same issue in every market.",
            "people_like_you_all_fields.json; Need_profiler.json Lifestyle / Ward / Sports",
        ),
        (
            "4",
            "Need Profiler existing cover / ownership",
            "Existing cover is hard-coded 0. Car/home/travel weights have no option labels. A scoring redesign may be required.",
            "build_profiler_profile Existing*Coverage = 0. Ownership stored, score unchanged.",
            "Wire policies into Existing*Coverage and add weight_options. Redesign if the factor model cannot take cover/ownership.",
            "src/pipeline/onboarding.py; need_profiler.py",
        ),
        (
            "5",
            "Plan dummy premium",
            "Protection premium is a 0.00078 placeholder, not a quoted tariff, and is not country-specific.",
            "coverPremiumFor(sum) dummy. Labelled in Plan-calculator.md, planProducts.ts, this workbook.",
            "Premium-quote calculator API per market / product.",
            "frontend/src/lib/planProducts.ts coverPremiumFor",
        ),
        (
            "6",
            "CPF / property seed",
            "Employee CPF is Singapore-only (country switch). Property seed bands 350k/650k/850k are SGD.",
            "CPF tab on for Singapore only. predict.py seed_property_value in SGD.",
            "Per-country social contribution and home-value tables (or FX the SGD seeds into local).",
            "src/cpf.py; src/predict.py seed_property_value; CPF tab",
        ),
    ]
    for i, row in enumerate(rows):
        rr = 4 + i
        for j, v in enumerate(row, 1):
            _fill(ws, f"{get_column_letter(j)}{rr}", v, align=wrap)
        ws.row_dimensions[rr].height = 68

    top = 4 + len(rows) + 2
    _fill(ws, f"A{top}", "Scenario Visualizer and HappiU — found while building their tabs (V0-13)", sec_font, sec_fill, border=False)
    ws.merge_cells(f"A{top}:F{top}")
    _headers(ws, top + 1, ["#", "Component", "Finding", "What the tab does", "Suggested fix", "Where"])
    engine_rows = [
        ("7", "SV life events",
         "Death, CI, TPD, accident, hospital, care, wedding and newborn events are not on the SV tab.",
         "Only crash, currency, inflation, income and expense events (orange cells).",
         "Second pass: add them as one-off costs / salary stops, same years as SV.",
         "Scenario Visualizer tab; SV ScenarioHandler"),
        ("8", "SV CPF past age 66",
         "When age > payout age + 1, the payout index is negative. numpy counts it from the end, so RA and "
         "CPF LIFE wrap into year 0 (P27 shows about S$693k of CPF in year 0) and contributions keep running.",
         "Copies SV exactly (wrap steps and seed rows), so the tab equals SV.",
         "Clamp the payout index at 0 in SocialSecurityR_SGP and stop contributions for retirees.",
         "SV SocialSecurityR_SGP; SV tab CPF section"),
        ("9", "SV salary for retirees",
         "Salary is cut with arr[dtr − 1:] = 0. When years to retirement is 0, only the last year is zeroed, "
         "so a retiree keeps drawing salary every year.",
         "Copies SV (salary-cut index = T − 1 when dtr = 0).",
         "Zero the whole salary array when dtr = 0.",
         "SV ProductHumanCapital"),
        ("10", "SV investment contribution",
         "sv_payload.py sends the monthly surplus; SV adds that figure once a year (no × 12).",
         "Copies SV: contribution = round(take-home − spend) a year.",
         "Send surplus × 12, or let SV apply the payload frequency.",
         "src/sv_payload.py; SV AssetBaseClass"),
        ("11", "SV goal withdrawals",
         "EDU / SAV / PRP take the full needAmount (not inflated) out of savings in the target year.",
         "Copies SV. The spend column carries the withdrawal.",
         "Decide whether the amount is today's money or target-year money, then inflate or not in one place.",
         "SV _setWithdrawalDict"),
        ("12", "HappiU deterministic vs live",
         "Live HU is Monte Carlo (lognormal returns, random death / illness). The tab uses expected values "
         "weighted by survival, so scores differ by a few points (P04: tab 87, live 82 on 10,000 draws).",
         "Deterministic twin on HU's cashflow rules; flags goals where HU would divide by 0.",
         "Accept as a reading aid, or seed HU with fixed draws for golden tests.",
         "HappiU tab; deterministic_engines.twin_hu"),
        ("13", "HappiU ignores noDeathFlag",
         "GP sends noDeathFlag: true, but HU still draws deaths and scores only alive paths.",
         "Weights each year by survival, as HU effectively does.",
         "Either honour the flag in HU or stop sending it.",
         "src/hu_payload.py; HU StochasticBaseClass"),
        ("14", "HappiU retirees with investments",
         "HU returns NaN (error) when investments > 0 and age ≥ retirement age (P12).",
         "Scores anyway and flags it (HU_nanEquity = TRUE).",
         "Guard ProductEquity for dtr = 0.",
         "HU ProductEquity"),
        ("15", "HappiU SAV / PRP booked as income",
         "HU adds the Savings / Property goal amount as income in the target year and spends it again, "
         "so those goals score close to 100% whatever the plan.",
         "Copies HU (base column adds the amount; spend removes it).",
         "Book the goal as a pure outflow, like education.",
         "HU cashflow_aggregation"),
        ("16", "SV hospital cost inflation",
         "SV multiplies the hospital bill by the plain inflation rate, not (1 + inflation)^years.",
         "Not on the tab (life events are deferred).",
         "Use the compounded inflation index.",
         "SV ScenarioHandler hospitalisation"),
    ]
    for i, row in enumerate(engine_rows):
        rr = top + 2 + i
        for j, v in enumerate(row, 1):
            _fill(ws, f"{get_column_letter(j)}{rr}", v, align=wrap)
        ws.row_dimensions[rr].height = 68
    _widths(ws, {"A": 4, "B": 22, "C": 42, "D": 52, "E": 36, "F": 48})
    ws.row_dimensions[2].height = 36


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
    ws.merge_cells("A1:X1")
    headers = [
        "id", "incomeMonthly", "expenseMonthly", "cash", "investments", "property", "mortgage",
        "life sum", "on N_INC", "on N_CRI", "on N_TPD", "on N_HOS", "on N_RET", "on N_EDU", "on N_SAV", "on N_PRP",
        "N_INC amount", "N_RET amount",
        "SV pre wealth 65", "SV post wealth 65", "SV pre wealth 85", "SV post wealth 85",
        "HappiU pre (det.)", "HappiU post (det.)",
    ]
    _headers(ws, 2, headers)
    tables = load_hu_tables()
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
        for t in UNIFIED:
            vals.append(t in prof["enabled"])
        vals.append(needs["N_INC"]["needAmount"])
        vals.append(needs["N_RET"]["needAmount"])
        s = persona_session(p)
        sv = twin_sv(s)
        for a in (65, 85):
            j = a - s["age"]
            for path in ("pre", "post"):
                vals.append(round(sv[path]["wealth"][j]) if 0 <= j <= sv["T"] else "")
        hu = twin_hu(s, tables)
        vals += [hu["preHappiU"], hu["postHappiU"]]
        for j, v in enumerate(vals, 1):
            num = "#,##0.00" if j in (2, 3) else ("#,##0" if j in (4, 5, 6, 7, 8, 17, 18, 19, 20, 21, 22) else None)
            _fill(ws, f"{get_column_letter(j)}{r}", v, num=num, align=center if j != 1 else left)
    _widths(ws, {get_column_letter(i): 14 for i in range(1, 25)})
    ws.column_dimensions["A"].width = 8
    ws.auto_filter.ref = f"A2:X{R1}"
    ws.row_dimensions[1].height = 36


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
    build_code_check(wb)

    # Overview first
    wb.move_sheet("Overview", offset=-len(wb.sheetnames) + 1)
    order = [
        "Overview",
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
        "Code check",
    ]
    for i, name in enumerate(order):
        wb.move_sheet(name, offset=i - wb.sheetnames.index(name))

    wb.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
