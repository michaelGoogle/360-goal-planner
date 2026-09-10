"""Build the Avatar III talking-head script from a GP report session."""

from __future__ import annotations

from typing import Any

from src.heygen.mobile import country_from_mobile
from src.cpf import session_take_home

DEFAULT_COUNTRY = "Singapore"


def spokesperson_look(country: str) -> str:
    where = (country or DEFAULT_COUNTRY).strip() or DEFAULT_COUNTRY
    return (
        f"A professional woman from {where} in her 30s, having red lipstick, "
        "wearing professional attire, standing in a modern office"
    )


NEED_LABEL = {
    "N_INC": "income and family protection",
    "N_CRI": "critical illness",
    "N_TPD": "disability",
    "N_RET": "retirement",
    "N_EDU": "education",
    "N_SAV": "savings",
    "N_PRP": "property",
}


def _money(n: Any) -> str:
    """Spoken amounts. 'Singapore dollars', not S$ (TTS says S-dollars) or SGD (spelled letter by letter)."""
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        return "0 Singapore dollars"
    sign = "minus " if v < 0 else ""
    return f"{sign}{abs(v):,} Singapore dollars"


def _first_name(session: dict[str, Any]) -> str:
    raw = str(session.get("name") or "").strip().split()
    return raw[0] if raw else ""


def _biggest_gap(session: dict[str, Any]) -> tuple[str, float]:
    best = ("", 0.0)
    for n in session.get("needs") or []:
        if not n.get("enabled"):
            continue
        need = float(n.get("needAmount") or 0)
        have = float(n.get("existing") or n.get("existingSumAssured") or n.get("existingInvestment") or 0)
        gap = max(0.0, need - have)
        if gap > best[1]:
            best = (str(n.get("type") or ""), gap)
    return best


def build_dummy_spoken_script() -> str:
    """Generic report walkthrough. Same for every customer. No figures, no persona."""
    return (
        "This is your plan report. It has two parts. "
        "First, what you have today: who you are, money coming in and going out, "
        "what you own and owe, and the cover you already hold. "
        "Then, what you get from the suggested plan: how it sizes protection and growth, "
        "and how that changes your financial picture next to going without it. "
        "These are estimates for this session, not a quote, and not advice to buy. "
        "Click Share report, leave your mobile number with us, and within a few minutes "
        "we will WhatsApp you a link to a customised video and this report."
    )


def build_spoken_script(
    session: dict[str, Any],
    pre: float | None,
    post: float | None,
) -> str:
    """Words the Avatar III talking-head speaks. Only figures from the session."""
    name = _first_name(session)
    age = session.get("age") or ""
    occ = str(session.get("occupation") or "").strip() or "their occupation"
    deps = int(session.get("dependents") or 0)
    income = _money(session.get("incomeMonthly"))
    expense = _money(session.get("expenseMonthly"))
    gap_type, gap_amt = _biggest_gap(session)
    gap_label = NEED_LABEL.get(gap_type, gap_type or "their largest goal")
    pre_s = "not yet scored" if pre is None else str(int(round(pre)))
    post_s = "not yet scored" if post is None else str(int(round(post)))
    you = "You are" if name else "They are"
    parts: list[str] = []
    if name:
        parts.append(f"Hello {name}. ")
    parts.append("I am walking you through this FinPlan360 plan snapshot. ")
    parts.append(
        f"{you} {age} years old, work as {occ}, and have {deps} dependant"
        f"{'' if deps == 1 else 's'}. "
    )
    parts.append(f"Monthly income is {income} and monthly spend is {expense}. ")
    try:
        avail = max(
            0.0,
            session_take_home(session) - float(session.get("expenseMonthly") or 0),
        )
    except (TypeError, ValueError):
        avail = 0.0
    if avail > 0:
        free = round(avail * 0.5)
        parts.append(
            f"Monthly surplus is {_money(avail)}; the recommended free budget (50 percent) is {_money(free)}. "
        )
    parts.append(f"The HappiU score today is {pre_s}")
    if post is not None:
        parts.append(f", and with this suggested plan it is {post_s}")
    parts.append(". ")
    if gap_amt > 0:
        parts.append(f"The largest remaining gap is {gap_label} at {_money(gap_amt)}. ")
    parts.append(
        "These are estimates and a sizing illustration, not a quote and not advice to buy, "
        "switch, or cancel cover. Please open the link and review the full report."
    )
    return "".join(parts)


def build_video_prompt(
    session: dict[str, Any],
    pre: float | None,
    post: float | None,
    mobile: str = "",
) -> str:
    """Look note plus spoken script. HeyGen receives only the spoken script."""
    look = spokesperson_look(country_from_mobile(mobile))
    script = build_spoken_script(session, pre, post)
    return (
        f"The spokesperson should be: {look}. "
        "The spokesperson must speak in English. "
        f"{script}"
    )
