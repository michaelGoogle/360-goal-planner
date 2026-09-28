"""Need Profiler: weighted scores, scaled 0-10, then two protection and one growth need.

No LLM. Fifteen factors, each worth an option weight, multiplied by a per-need weight
from ``src/pipeline/prompts/Need_profiler.json`` and summed. The factor order and the
weight matrix are the Need Profiler tab of the workbook; the option weights are the
JSON's, so a weight change is a data change.

What V0-24 settled, against the code before it:

- Farewell is not scored, so the min-max scaling runs over eleven labels, not twelve.
- Income, expense, assets and liabilities are compared in **PPP-USD**: market USD
  divided by the country's relative price level. Market FX alone would put a Vietnamese
  salary in the lowest band on every factor.
- The vocabulary the People Like You prompt returns is mapped onto the profiler's own:
  Basic / Comfortable / Luxurious to frugal / stress-free / only the best, Single to
  ward A and Double or Ward to B, and any sport that is not adventurous to "life style".
  Those three factors scored nothing before, because the strings never matched.
- Personal accident joins the protection pick; the tie-break order is the label order.
- Home purchase is no longer the home owner's savings need. N_PRP and N_LTC have no
  profiler label, so the customer switches them on.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.money import round_half_up
from src.needs import (
    CALCULATOR_NEEDS,
    CUSTOMER_ONLY_NEEDS,
    NEED_OF_PROFILER_LABEL,
    NEED_PROFILER_LABEL,
    PARKED_NEEDS,
    PROFILER_LABELS,
    PROTECTION_PICK_ORDER,
)
from src.services.need_profiler.models import (
    NeedProfilerRequest,
    NeedProfilerResponse,
    ProfiledNeed,
)

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "pipeline" / "prompts" / "Need_profiler.json"

#: The fifteen factors, in the order of the Assumptions weight matrix (B90:L104).
FACTORS: tuple[str, ...] = (
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
)

MONEY_FACTORS: tuple[str, ...] = ("Income", "Expense", "Assets", "Liabilities")

#: What the Need Profiler tab calls each factor's option-weight row.
DIAGNOSTIC_NAME: dict[str, str] = {
    "Date of Birth": "Age",
    "Dependants": "Deps",
    "Occupation": "Occ",
    "Smoking": "Smoke",
    "Liabilities": "Liab",
    "Hospitalization": "HospExist",
    "Disability": "DisExist",
    "Hospital Type": "HospType",
    "Ward Type": "Ward",
}

#: Where a factor's options live when the JSON spells its name differently.
OPTIONS_NAMED: dict[str, str] = {
    "Date of Birth": "Age",
    "Hospitalization": "Existing Hospitalization Insurance",
    "Disability": "Existing Disability Insurance",
}

#: A score above this is urgent. The app shows 5 and 3, not the 0-10 score.
PRIORITY_CUTOFF = 7.0
PRIORITY_HIGH = 5
PRIORITY_NORMAL = 3

#: Occupation counts as self-employed if any of these appears in the title.
SELF_EMPLOYED_TOKENS = ("self", "entrepreneur", "own business", "freelance")

#: Sports the insurer loads for. "Adventurous" in the customer's own words counts too.
ADVENTUROUS_TOKENS = (
    "adventur", "diving", "climb", "ski", "surf", "martial", "rugby",
    "motor", "extreme", "parachut", "boxing",
)

#: Ways of saying "no sport". Anything else is an ordinary one.
NO_SPORT_TOKENS = ("dont", "don't", "no sport", "none", "nil")

#: People Like You's words for a retirement lifestyle, and the profiler's.
LIFESTYLE_WORDS: dict[str, str] = {
    "frugal": "frugal",
    "basic": "frugal",
    "stress-free": "stress-free",
    "stress free": "stress-free",
    "comfortable": "stress-free",
    "only the best": "only the best",
    "luxurious": "only the best",
}

#: Ward names. A is a single room, B is shared, and the prompt's words map onto those.
WARD_WORDS: dict[str, str] = {
    "a": "A",
    "single": "A",
    "b": "B",
    "double": "B",
    "ward": "B",
}

#: Smoking has factor weights but no options in the JSON, so the weights live here.
SMOKER_WEIGHT = 3.0
NON_SMOKER_WEIGHT = 1.0

#: Existing cover is not wired into the profiler yet; the workbook records the same 0,
#: whose option weight is the "False" one. See Need-profiler.md, known limitations.
EXISTING_COVER = False


@lru_cache(maxsize=1)
def config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - a missing file scores everything 0
        logger.warning("Could not load %s: %s", CONFIG_PATH.name, exc)
        return {"weight_options": {}, "needs_factor_weights": {}}


def factor_weight(factor: str, label: str) -> float:
    """Per-need weight of a factor. A blank cell in the matrix is a zero."""
    matrix = config().get("needs_factor_weights") or {}
    return float((matrix.get(factor) or {}).get(label) or 0)


def _options(factor: str) -> list[dict[str, Any]]:
    name = OPTIONS_NAMED.get(factor, factor)
    return (config().get("weight_options") or {}).get(name) or []


def _named_weight(factor: str, option: str | None) -> float:
    if option is None:
        return 0.0
    for candidate in _options(factor):
        if str(candidate.get("option", "")).strip().lower() == option.strip().lower():
            return float(candidate.get("weight") or 0)
    return 0.0


def _band_weight(factor: str, amount: float) -> float:
    """Read the ``lt`` cut-overs. The last option has none and catches the rest."""
    for option in _options(factor):
        cut = option.get("lt")
        if cut is None or amount < float(cut):
            return float(option.get("weight") or 0)
    return 0.0


# --- the option a customer falls into, per factor -----------------------------


def age_option(age: int) -> str:
    if age < 21:
        return "Below 21"
    if age <= 30:
        return "21 to 30 years"
    if age <= 40:
        return "31 to 40 years"
    return "above 40 years"


def dependants_option(dependents: int) -> str:
    if dependents <= 0:
        return "No Dependant"
    if dependents == 1:
        return "1 Dependant"
    return "2 or More Dependants"


def occupation_option(occupation: str | None) -> str:
    lower = (occupation or "").lower()
    if any(token in lower for token in SELF_EMPLOYED_TOKENS):
        return "Self-employed & Entrepreneur"
    return "Salaried"


def sports_option(sports: str | None) -> str:
    lower = (sports or "").strip().lower()
    if any(token in lower for token in ADVENTUROUS_TOKENS):
        return "Adventurous Sports"
    if not lower or any(token in lower for token in NO_SPORT_TOKENS):
        return "I dont do sports"
    return "Life style activities"


def lifestyle_option(lifestyle: str | None) -> str | None:
    return LIFESTYLE_WORDS.get((lifestyle or "").strip().lower())


def ward_option(ward: str | None) -> str | None:
    return WARD_WORDS.get((ward or "").strip().lower())


def hospital_option(hospital: str | None) -> str | None:
    lower = (hospital or "").strip().lower()
    return {"private": "Private", "public": "Public"}.get(lower)


def gender_option(gender: str | None) -> str | None:
    lower = (gender or "").strip().lower()
    return {"male": "Male", "female": "Female"}.get(lower)


def ppp_usd(amount_usd: float, price_level: float) -> float:
    """What the amount buys in the base country. A missing price level is a 1."""
    level = float(price_level or 0) or 1.0
    return float(amount_usd or 0) / level


def option_weights(req: NeedProfilerRequest) -> dict[str, float]:
    """One weight per factor, in the order the weight matrix expects."""
    flags = req.flags or {}
    money = {
        "Income": ppp_usd(req.incomeMonthlyUsd, req.priceLevel),
        "Expense": ppp_usd(req.expenseMonthlyUsd, req.priceLevel),
        "Assets": ppp_usd(req.liquidAssetsUsd, req.priceLevel),
        "Liabilities": ppp_usd(req.liabilitiesUsd, req.priceLevel),
    }
    smoker = bool(flags.get("isSmoker"))
    existing = "True" if EXISTING_COVER else "False"
    return {
        "Date of Birth": _named_weight("Date of Birth", age_option(int(req.age or 0))),
        "Gender": _named_weight("Gender", gender_option(req.gender)),
        "Dependants": _named_weight("Dependants", dependants_option(int(req.dependents or 0))),
        "Occupation": _named_weight("Occupation", occupation_option(flags.get("occupation"))),
        "Smoking": SMOKER_WEIGHT if smoker else NON_SMOKER_WEIGHT,
        "Income": _band_weight("Income", money["Income"]),
        "Expense": _band_weight("Expense", money["Expense"]),
        "Assets": _band_weight("Assets", money["Assets"]),
        "Liabilities": _band_weight("Liabilities", money["Liabilities"]),
        "Hospitalization": _named_weight("Hospitalization", existing),
        "Disability": _named_weight("Disability", existing),
        "Hospital Type": _named_weight("Hospital Type", hospital_option(flags.get("hospitalType"))),
        "Ward Type": _named_weight("Ward Type", ward_option(flags.get("wardType"))),
        "Lifestyle": _named_weight("Lifestyle", lifestyle_option(flags.get("retirementLifestyle"))),
        "Sports": _named_weight("Sports", sports_option(flags.get("sports"))),
    }


# --- scoring ------------------------------------------------------------------


def raw_scores(weights: dict[str, float]) -> dict[str, float]:
    return {
        label: round_half_up(sum(weights.get(f, 0.0) * factor_weight(f, label) for f in FACTORS), 2)
        for label in PROFILER_LABELS
    }


def scale(raw: dict[str, float]) -> dict[str, float]:
    """Min-max over the eleven labels. When every score is equal they are all 0.

    Rounded half-up because the workbook's cell is ROUND: a score landing exactly on
    x.x5 decides whether a need is urgent (above 7) or ordinary.
    """
    if not raw:
        return {}
    low, high = min(raw.values()), max(raw.values())
    span = high - low if high > low else 1.0
    return {label: round_half_up(((value - low) / span) * 10, 1) for label, value in raw.items()}


def pick_protection(scaled: dict[str, float]) -> tuple[str, str]:
    """The two highest-scoring protection needs, the label order breaking a tie."""
    ranked = sorted(
        PROTECTION_PICK_ORDER,
        key=lambda need: (-scaled.get(NEED_PROFILER_LABEL[need], 0.0),
                          PROTECTION_PICK_ORDER.index(need)),
    )
    return ranked[0], ranked[1]


def pick_growth(scaled: dict[str, float]) -> str:
    """Education or savings beside the forced retirement need. Education wins a tie."""
    education = scaled.get(NEED_PROFILER_LABEL["N_EDU"], 0.0)
    savings = scaled.get(NEED_PROFILER_LABEL["N_SAV"], 0.0)
    return "N_EDU" if education >= savings else "N_SAV"


def priority(score: float | None) -> int:
    if score is None:
        return PRIORITY_NORMAL
    return PRIORITY_HIGH if score > PRIORITY_CUTOFF else PRIORITY_NORMAL


def score_of(need: str, scaled: dict[str, float]) -> float | None:
    label = NEED_PROFILER_LABEL.get(need)
    return scaled.get(label) if label else None


def profile(req: NeedProfilerRequest) -> NeedProfilerResponse:
    weights = option_weights(req)
    raw = raw_scores(weights)
    scaled = scale(raw)
    prot1, prot2 = pick_protection(scaled)
    grow2 = pick_growth(scaled)

    enabled = {prot1, prot2, grow2, "N_RET"}
    needs = [
        ProfiledNeed(
            type=need,
            enabled=need in enabled and need not in CUSTOMER_ONLY_NEEDS,
            priority=priority(score_of(need, scaled)),
            score=score_of(need, scaled),
        )
        for need in CALCULATOR_NEEDS
    ]
    needs += [
        ProfiledNeed(
            type=need,
            enabled=False,
            priority=priority(score_of(need, scaled)),
            score=score_of(need, scaled),
            parked=True,
        )
        for need in PARKED_NEEDS
    ]

    diagnostics = {
        f"ow {DIAGNOSTIC_NAME.get(factor, factor)}": weight for factor, weight in weights.items()
    }
    diagnostics.update(
        {
            "usd Income": ppp_usd(req.incomeMonthlyUsd, req.priceLevel),
            "usd Expense": ppp_usd(req.expenseMonthlyUsd, req.priceLevel),
            "usd Assets": ppp_usd(req.liquidAssetsUsd, req.priceLevel),
            "usd Liab": ppp_usd(req.liabilitiesUsd, req.priceLevel),
        }
    )
    return NeedProfilerResponse(
        scores={
            need: scaled[label]
            for label, need in NEED_OF_PROFILER_LABEL.items()
            if label in scaled
        },
        picks={"prot1": prot1, "prot2": prot2, "grow2": grow2},
        needs=needs,
        raw=raw,
        scaled=scaled,
        optionWeights=diagnostics,
    )


def fallback(age: int, dependents: int, owns_property: bool) -> NeedProfilerResponse:
    """What GP enables when scoring fails, per Need-profiler.md.

    Income, critical illness and retirement, plus education if anyone depends on the
    customer and a savings goal if not. Amounts stay at zero, and the customer can
    switch any need on. ``age`` and ``owns_property`` are not read: a home owner's
    savings need is no longer swapped for a home purchase.
    """
    _ = (age, owns_property)
    enabled = {"N_INC", "N_CRI", "N_RET", "N_EDU" if dependents else "N_SAV"}
    return NeedProfilerResponse(
        picks={"prot1": "N_INC", "prot2": "N_CRI", "grow2": "N_EDU" if dependents else "N_SAV"},
        needs=[
            ProfiledNeed(type=need, enabled=need in enabled, priority=PRIORITY_NORMAL)
            for need in CALCULATOR_NEEDS
        ]
        + [ProfiledNeed(type=need, enabled=False, parked=True) for need in PARKED_NEEDS],
        fallback=True,
    )
