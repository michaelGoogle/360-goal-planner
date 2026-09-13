"""Build the Video Agent prompt (look + spoken script) from a GP report session."""

from __future__ import annotations

import math
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


def _round_sigfigs(n: float, sig: int = 3) -> float:
    """Round the magnitude to ``sig`` significant figures (3 digits)."""
    mag = abs(float(n))
    if mag == 0:
        return 0.0
    exp = math.floor(math.log10(mag))
    factor = 10 ** (sig - 1 - exp)
    return round(mag * factor) / factor


def _fmt_scaled(x: float) -> str:
    """Speak a million/billion scale with up to 2 decimal digits (e.g. 4.99)."""
    ax = abs(x)
    if abs(ax - round(ax)) < 1e-9:
        return str(int(round(ax)))
    if ax < 10:
        return f"{ax:.2f}"
    if ax < 100:
        return f"{ax:.1f}".rstrip("0").rstrip(".")
    return f"{ax:.0f}"


def _money_value(n: Any) -> float | None:
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _speak_money(n: Any) -> str:
    """Spoken amount, no currency. Big figures: 3 significant digits.

    4,993,922 → ``4.99 million``. 11,232 → ``11 thousand 200``.
    Under 1,000 stays exact. Never ``S$`` / ``SGD`` / ``Singapore dollars``.
    """
    v = _money_value(n)
    if v is None:
        return "0"
    sign = "minus " if v < 0 else ""
    rounded = _round_sigfigs(v, 3)
    if rounded >= 1_000_000_000:
        return f"{sign}{_fmt_scaled(rounded / 1_000_000_000)} billion"
    if rounded >= 1_000_000:
        return f"{sign}{_fmt_scaled(rounded / 1_000_000)} million"
    if rounded >= 1_000:
        thousands = int(rounded // 1000)
        rest = int(round(rounded % 1000))
        if rest == 0:
            return f"{sign}{thousands} thousand"
        return f"{sign}{thousands} thousand {rest}"
    return f"{sign}{int(round(rounded))}"


def _display_money(n: Any) -> str:
    """Digit overlay for the same rounded amount ``_speak_money`` uses.

    8,500 → ``8500``. 4,993,922 → ``4990000``. No thousand separators, no
    ``thousand`` / ``million`` words.
    """
    v = _money_value(n)
    if v is None:
        return "0"
    sign = "-" if v < 0 else ""
    rounded = _round_sigfigs(v, 3)
    if abs(rounded - round(rounded)) < 1e-9:
        return f"{sign}{int(round(abs(rounded)))}"
    text = f"{abs(rounded):.10f}".rstrip("0").rstrip(".")
    return f"{sign}{text}"


def _plan_money(session: dict[str, Any]) -> dict[str, float]:
    """Session amounts the spoken script may mention."""
    try:
        income = float(session.get("incomeMonthly") or 0)
        expense = float(session.get("expenseMonthly") or 0)
        avail = max(0.0, session_take_home(session) - expense)
    except (TypeError, ValueError):
        income = 0.0
        expense = 0.0
        avail = 0.0
    _, gap_amt = _biggest_gap(session)
    return {
        "income": income,
        "expense": expense,
        "avail": avail,
        "free": round(avail * 0.5) if avail > 0 else 0.0,
        "gap": gap_amt,
    }


def _overlay_pairs(session: dict[str, Any]) -> list[tuple[str, str]]:
    """Spoken → digit pairs for captions when they differ."""
    money = _plan_money(session)
    amounts = [money["income"], money["expense"]]
    if money["avail"] > 0:
        amounts.extend([money["avail"], money["free"]])
    if money["gap"] > 0:
        amounts.append(money["gap"])
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for n in amounts:
        spoken = _speak_money(n)
        display = _display_money(n)
        if spoken == display or spoken in seen:
            continue
        seen.add(spoken)
        pairs.append((spoken, display))
    return pairs


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


def _agent_prompt(
    look: str,
    script: str,
    *,
    duration: str,
    overlays: list[tuple[str, str]] | None = None,
) -> str:
    parts = [
        f"Create a landscape talking-head plan-report video, about {duration}. ",
        f"The spokesperson should be: {look}. ",
        "The spokesperson must speak in English. ",
        "Speak this script verbatim. Do not add numbers, products, premiums, "
        "or advice that is not in the script.",
    ]
    if overlays:
        lines = [
            "",
            "Captions, subtitles, and on-screen stat cards must show amounts as digits, "
            "not spoken words. Never overlay the words thousand, million, or billion. "
            "When the voice says a spoken amount below, display the matching digits exactly.",
            "",
            "CRITICAL ON-SCREEN TEXT (display literally):",
        ]
        lines.extend(f'- spoken "{spoken}" → show {display}' for spoken, display in overlays)
        parts.append("\n".join(lines))
    parts.append("\n\n" + script)
    return "".join(parts)


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


def build_dummy_video_prompt() -> str:
    """Video Agent prompt for the shared dummy walkthrough."""
    return _agent_prompt(
        spokesperson_look(DEFAULT_COUNTRY),
        build_dummy_spoken_script(),
        duration="30 to 45 seconds",
    )


def build_spoken_script(
    session: dict[str, Any],
    pre: float | None,
    post: float | None,
) -> str:
    """Words the spokesperson speaks. Only figures from the session."""
    name = _first_name(session)
    age = session.get("age") or ""
    occ = str(session.get("occupation") or "").strip() or "their occupation"
    deps = int(session.get("dependents") or 0)
    money = _plan_money(session)
    income = _speak_money(money["income"])
    expense = _speak_money(money["expense"])
    gap_type, gap_amt = _biggest_gap(session)
    gap_label = NEED_LABEL.get(gap_type, gap_type or "their largest goal")
    pre_s = "not yet scored" if pre is None else str(int(round(pre)))
    post_s = "not yet scored" if post is None else str(int(round(post)))
    you = "You are" if name else "They are"
    parts: list[str] = []
    if name:
        parts.append(f"Hello {name}. ")
    parts.append("All numbers presented are in Singapore dollars. ")
    parts.append("I am walking you through this FinPlan360 plan snapshot. ")
    parts.append(
        f"{you} {age} years old, work as {occ}, and have {deps} dependant"
        f"{'' if deps == 1 else 's'}. "
    )
    parts.append(f"Monthly income is {income} and monthly spend is {expense}. ")
    if money["avail"] > 0:
        parts.append(
            f"Monthly surplus is {_speak_money(money['avail'])}; the recommended free budget (50 percent) is {_speak_money(money['free'])}. "
        )
    parts.append(f"The HappiU score today is {pre_s}")
    if post is not None:
        parts.append(f", and with this suggested plan it is {post_s}")
    parts.append(". ")
    if gap_amt > 0:
        parts.append(f"The largest remaining gap is {gap_label} at {_speak_money(gap_amt)}. ")
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
    """Look note plus spoken script for HeyGen Video Agent."""
    look = spokesperson_look(country_from_mobile(mobile))
    script = build_spoken_script(session, pre, post)
    return _agent_prompt(
        look,
        script,
        duration="45 to 60 seconds",
        overlays=_overlay_pairs(session),
    )
