"""Need and risk codes, from ``docs/calculations/Need-dictionary.md``.

One place for what a need is called, so a rename is one edit rather than a search. The
codes are the model's: ``N_xxx`` for a need, ``R_xxx`` for the risk or event that
triggers it (N_CRI is triggered by R_CRI, N_INC by R_DEA).

Old ids are accepted on input for one release. A session saved before the rename still
loads, which matters because sessions live in the browser and in InsApi, not in a
database we could migrate.
"""

from __future__ import annotations

# Needs the calculator produces an amount for.
CALCULATOR_NEEDS: tuple[str, ...] = (
    "N_INC",
    "N_CRI",
    "N_TPD",
    "N_HOS",
    "N_PAC",
    "N_LTC",
    "N_RET",
    "N_EDU",
    "N_SAV",
    "N_PRP",
)

# Coverage the profiler scores and ranks but does not size. There is nothing to
# calculate: the answer is "you should have this", not "you need this much".
PARKED_NEEDS: tuple[str, ...] = ("N_HOM", "N_CAR", "N_TRV")

# Listed in the dictionary as a candidate. No calculator, not scored, not sent.
CANDIDATE_NEEDS: tuple[str, ...] = ("N_ADB",)

PROTECTION_NEEDS: frozenset[str] = frozenset(
    {"N_INC", "N_CRI", "N_TPD", "N_HOS", "N_PAC", "N_LTC"}
)
WEALTH_NEEDS: frozenset[str] = frozenset({"N_RET", "N_EDU", "N_SAV", "N_PRP"})

ALL_NEEDS: tuple[str, ...] = CALCULATOR_NEEDS + PARKED_NEEDS

# The profiler picks two protection needs. Its order is also the tie-break order.
PROTECTION_PICK_ORDER: tuple[str, ...] = ("N_INC", "N_CRI", "N_TPD", "N_HOS", "N_PAC")

# The profiler has no label for these, so it never switches them on. The customer does.
CUSTOMER_ONLY_NEEDS: tuple[str, ...] = ("N_PRP", "N_LTC")

# What Need_profiler.json calls each need. Farewell was dropped in V0-16 and has no
# code; N_PRP and N_LTC have no label, which is why the profiler cannot pick them.
NEED_PROFILER_LABEL: dict[str, str] = {
    "N_INC": "Life Protection",
    "N_CRI": "Critical Illness",
    "N_TPD": "Disability",
    "N_HOS": "Hospitalization",
    "N_PAC": "Personal Accident",
    "N_RET": "Retirement",
    "N_EDU": "Education",
    "N_SAV": "General Savings",
    "N_HOM": "Home Protection",
    "N_CAR": "Car Protection",
    "N_TRV": "Travel Protection",
}

#: The eleven scored labels, in the JSON's own order. Farewell is not among them.
PROFILER_LABELS: tuple[str, ...] = (
    "Life Protection",
    "Critical Illness",
    "Disability",
    "Retirement",
    "Education",
    "Hospitalization",
    "General Savings",
    "Personal Accident",
    "Car Protection",
    "Home Protection",
    "Travel Protection",
)

NEED_OF_PROFILER_LABEL: dict[str, str] = {v: k for k, v in NEED_PROFILER_LABEL.items()}

NEED_LABEL: dict[str, str] = {
    "N_INC": "Income & family protection",
    "N_CRI": "Critical illness",
    "N_TPD": "Total & permanent disability (TPD)",
    "N_HOS": "Hospitalisation",
    "N_PAC": "Personal accident",
    "N_LTC": "Long-term care",
    "N_RET": "Private retirement",
    "N_EDU": "Child's university education",
    "N_SAV": "Savings goal",
    "N_PRP": "Home purchase",
    "N_HOM": "Home protection",
    "N_CAR": "Car protection",
    "N_TRV": "Travel protection",
    "N_ADB": "Accidental death",
}

# The risk each need answers. A need with no trigger (a savings goal) has none.
NEED_RISK: dict[str, str] = {
    "N_INC": "R_DEA",
    "N_CRI": "R_CRI",
    "N_TPD": "R_TPD",
    "N_HOS": "R_HOS",
    "N_PAC": "R_PAC",
    "N_LTC": "R_LTC",
    "N_RET": "R_LON",
    "N_ADB": "R_ADB",
}

# Stress events, in the order the app shows them.
MARKET_RISKS: tuple[str, ...] = ("R_MKT", "R_CCY", "R_INF")
HOUSEHOLD_RISKS: tuple[str, ...] = ("R_ICT", "R_EXP")
NEED_RISKS: tuple[str, ...] = ("R_DEA", "R_CRI", "R_TPD", "R_PAC", "R_HOS", "R_LTC")
LIFE_RISKS: tuple[str, ...] = ("R_WED", "R_BAB")
# R_LON is a horizon toggle rather than a cost: it re-sizes N_RET and N_LTC to LON_AGE.
HORIZON_RISKS: tuple[str, ...] = ("R_LON",)

ALL_RISKS: tuple[str, ...] = (
    MARKET_RISKS + HOUSEHOLD_RISKS + NEED_RISKS + LIFE_RISKS + HORIZON_RISKS
)

RISK_LABEL: dict[str, str] = {
    "R_DEA": "Death",
    "R_CRI": "Critical illness",
    "R_TPD": "Total & permanent disability",
    "R_HOS": "Hospitalisation",
    "R_PAC": "Personal accident",
    "R_LTC": "Long-term care",
    "R_LON": "Longevity",
    "R_MKT": "Market crash",
    "R_CCY": "Currency shock",
    "R_INF": "Inflation shock",
    "R_ICT": "Income cut",
    "R_EXP": "Expense shock",
    "R_WED": "Wedding / marriage",
    "R_BAB": "Newborn",
    "R_ADB": "Accidental death",
}

# What a session saved before V0-24 called things.
NEED_ALIAS: dict[str, str] = {
    "N_HSP": "N_HOS",
    "N_PTD": "N_TPD",
}

RISK_ALIAS: dict[str, str] = {
    "crash": "R_MKT",
    "Crash": "R_MKT",
    "MarketCrash": "R_MKT",
    "ccy": "R_CCY",
    "CurrencyShock": "R_CCY",
    "infl": "R_INF",
    "Inflation": "R_INF",
    "inc": "R_ICT",
    "Unemployment": "R_ICT",
    "Income": "R_ICT",
    "exp": "R_EXP",
    "death": "R_DEA",
    "Death": "R_DEA",
    "ci": "R_CRI",
    "CI": "R_CRI",
    "tpd": "R_TPD",
    "ptd": "R_TPD",
    "PTD": "R_TPD",
    "Disability": "R_TPD",
    "pa": "R_PAC",
    "PersonalAccident": "R_PAC",
    "hosp": "R_HOS",
    "Hospitalization": "R_HOS",
    "care": "R_LTC",
    "wed": "R_WED",
    "Marriage": "R_WED",
    "baby": "R_BAB",
    "Newborn": "R_BAB",
    "lon": "R_LON",
}


def need_code(value: str | None) -> str:
    """A need code, translating an old one. Unknown values come back unchanged."""
    code = (value or "").strip()
    return NEED_ALIAS.get(code, code)


def risk_code(value: str | None) -> str:
    """A risk code, translating an old stress-event id."""
    code = (value or "").strip()
    return RISK_ALIAS.get(code, code)


def is_need(value: str | None) -> bool:
    return need_code(value) in ALL_NEEDS


def is_risk(value: str | None) -> bool:
    return risk_code(value) in ALL_RISKS
