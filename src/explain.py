"""LLM audio explainers. Prompts live in src/prompts/*.md."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.openai_client import chat_complete, llm_configured

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

KINDS = ("mira", "intro", "money", "score", "needs", "chart", "prod")
ROUTES = ("d2cIntro", "d2cAbout", "d2cMoney", "d2cScore", "d2cPlan")

_MIRA_FILES = {
    "d2cIntro": "mira_intro.md",
    "d2cAbout": "mira_about.md",
    "d2cMoney": "mira_money.md",
    "d2cScore": "mira_score.md",
    "d2cPlan": "mira_plan.md",
}
_KIND_FILES = {
    "intro": "intro.md",
    "money": "money.md",
    "score": "score.md",
    "needs": "needs.md",
    "chart": "chart.md",
    "prod": "products.md",
}
_CONCAT = {
    "mira_money.md": "money.md",
    "mira_score.md": "score.md",
}

NEED_LABELS = {
    "N_INC": "income and family protection",
    "N_CRI": "critical illness",
    "N_TPD": "total and permanent disability",
    "N_RET": "retirement",
    "N_EDU": "child's university education",
    "N_SAV": "savings goal",
    "N_PRP": "property purchase",
}


def prompt_filename(kind: str, route: str | None) -> str:
    if kind == "mira":
        if route not in _MIRA_FILES:
            raise ValueError("Mira needs a known route")
        return _MIRA_FILES[route]
    if kind not in _KIND_FILES:
        raise ValueError(f"Unknown explainer '{kind}'")
    return _KIND_FILES[kind]


def load_prompt(kind: str, route: str | None) -> str:
    voice = (PROMPTS_DIR / "voice.md").read_text(encoding="utf-8").strip()
    name = prompt_filename(kind, route)
    task = (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()
    extra = _CONCAT.get(name)
    if extra:
        task = task + "\n\n" + (PROMPTS_DIR / extra).read_text(encoding="utf-8").strip()
    return voice + "\n\n" + task


def listed_prompt_files() -> list[str]:
    names = ["voice.md", *_MIRA_FILES.values(), *_KIND_FILES.values()]
    return sorted(set(names))


def _say_money(n: Any) -> str:
    try:
        v = abs(float(n or 0))
    except (TypeError, ValueError):
        return "zero dollars"
    if v >= 1_000_000:
        s = f"{v / 1_000_000:.2f}".rstrip("0").rstrip(".")
        return f"{s} million dollars"
    if v >= 10_000:
        return f"{round(v / 1000)} thousand dollars"
    return f"{int(round(v))} dollars"


def _first_name(ctx: dict[str, Any]) -> str:
    you = ctx.get("you") if isinstance(ctx.get("you"), dict) else {}
    name = str(you.get("firstName") or "").strip()
    return name if name and name.lower() != "you" else ""


def _gap_of(n: dict[str, Any]) -> float:
    try:
        return float(n.get("gap") or 0)
    except (TypeError, ValueError):
        return 0.0


def _need_spoken_label(n: dict[str, Any]) -> str:
    typed = NEED_LABELS.get(str(n.get("type") or ""))
    if typed:
        return typed
    raw = str(n.get("label") or "a goal").replace("&", "and")
    return raw.strip() or "a goal"


def _enabled_needs(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    rows = ctx.get("needs") if isinstance(ctx.get("needs"), list) else []
    out = []
    for n in rows:
        if not isinstance(n, dict) or not n.get("enabled"):
            continue
        out.append(n)
    out.sort(key=_gap_of, reverse=True)
    return out


def _enabled_gaps(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    return [n for n in _enabled_needs(ctx) if _gap_of(n) > 0]


def fallback_script(kind: str, route: str | None, context: dict[str, Any]) -> str:
    """Deterministic spoken text when OpenAI is off or fails."""
    you = context.get("you") if isinstance(context.get("you"), dict) else {}
    money = context.get("money") if isinstance(context.get("money"), dict) else {}
    score = context.get("score") if isinstance(context.get("score"), dict) else {}
    chart = context.get("chart") if isinstance(context.get("chart"), dict) else {}
    products = context.get("products") if isinstance(context.get("products"), dict) else {}
    name = _first_name(context)

    if kind == "mira" and route == "d2cIntro":
        return (
            "Hello, I am Mira. I will walk you through this if you would like me to. "
            "The whole plan takes about three minutes — that is the point. You tell us a little "
            "about yourself. We predict where you stand today from people like you — unless you "
            "type the figures or add a statement, in which case we use those instead. Then you see "
            "how far what you already have goes toward the goals that matter — income if you could "
            "not work, retirement, family — and a year-by-year picture you can test. There is no "
            "sign-up and we do not ask for an identity number. Press Start my plan when you are "
            "ready."
        )
    if kind == "intro":
        return (
            "FinPlan360 is a goal planner. The wow is that it takes about three minutes to see "
            "how ready you are for the life you want. You tell us a little about yourself. We "
            "predict where you stand today from people like you — income, spending, Cash & Savings, "
            "investments, cover. If you type your own figures or add a statement, we use those "
            "instead of the prediction. Then we size the goals that actually matter — income if "
            "you could not work, retirement, family — against what you already have. You leave "
            "with the gaps, and a year-by-year picture of your wealth you can test. There is no "
            "sign-up and we do not ask for an identity number. Press Start my plan when you are ready."
        )
    if kind == "mira" and route == "d2cAbout":
        missing = context.get("missing") if isinstance(context.get("missing"), list) else []
        labels = [str(m) for m in missing if m]
        tail = (
            f"Right now {', '.join(labels[:-1]) + ' and ' + labels[-1] if len(labels) > 1 else (labels[0] if labels else 'a few answers')} "
            f"still {'need' if len(labels) != 1 else 'needs'} an answer before we can continue."
            if labels
            else "Everything we need is answered — press Predict my finance when you are ready."
        )
        return (
            "This first screen is six answers about you. Nothing financial yet. "
            "The quickest way is to say it in one sentence — press Speak and describe yourself "
            "the way you would to a person. If you would rather type it into boxes, turn on "
            "Enter data classically. "
            + tail
        )
    if kind in ("money",) or (kind == "mira" and route == "d2cMoney"):
        inc = _say_money(money.get("incomeMonthly"))
        exp = _say_money(money.get("expenseMonthly"))
        bud = money.get("budgetMonthly")
        try:
            bud_n = float(bud or 0)
        except (TypeError, ValueError):
            bud_n = 0
        bud_t = (
            f"you short by {_say_money(abs(bud_n))} a month"
            if bud_n < 0
            else f"an available budget of {_say_money(bud_n)} a month"
        )
        lead = (
            f"This is where you stand today{f', {name}' if name else ''}."
            if kind == "mira"
            else "These are estimates, not your records."
        )
        return (
            f"{lead} Money coming in is {inc} a month — a typical figure from public sources "
            f"like Glassdoor, not your payslip. Money going out is {exp}. "
            f"That leaves {bud_t}. "
            f"Savings and investments, {_say_money(money.get('liquid'))}. "
            f"If any of these is wrong, tap the pencil beside it."
        )
    if kind in ("score",) or (kind == "mira" and route == "d2cScore"):
        pre = score.get("pre")
        band = str(score.get("band") or "").lower() or "being worked out"
        gaps = _enabled_gaps(context)
        short = f"{len(gaps)} needs are short" if gaps else "nothing on your list is short"
        top = gaps[0] if gaps else None
        top_l = ""
        if top:
            lab = str(top.get("label") or NEED_LABELS.get(str(top.get("type") or ""), "a goal"))
            top_l = f" The largest is {lab.lower()}."
        return (
            f"Your HappiU Score is {pre if pre is not None else 'being worked out'} out of 100, "
            f"which is {band}. {short}.{top_l} Start with the biggest shortfall rather than everything at once."
        )
    if kind == "needs":
        rows = _enabled_needs(context)
        who = name or "you"
        if not rows:
            return (
                f"These are the goals and needs people like {who} typically have. "
                "None are switched on yet. Add one from the list below."
            )
        short_bits: list[str] = []
        funded: list[str] = []
        for n in rows:
            lab = _need_spoken_label(n)
            gap = _gap_of(n)
            if gap > 0:
                short_bits.append(f"{lab} is short by {_say_money(gap)}")
            else:
                funded.append(lab)
        bits = [f"These are the goals and needs people like {who} typically have."]
        if short_bits:
            bits.append(". ".join(short_bits) + ".")
        if funded:
            if len(funded) == 1:
                bits.append(f"{funded[0]} is fully funded.")
            else:
                bits.append(", ".join(funded[:-1]) + f" and {funded[-1]} are fully funded.")
        elif not short_bits:
            bits.append("Every switched-on need is fully funded.")
        if short_bits:
            bits.append(f"The largest gap is {_need_spoken_label(rows[0])}.")
        bits.append(
            "Tap a line to revise a figure that does not fit. "
            "This screen identifies the goals, the needs, and the gaps."
        )
        return " ".join(bits)
    if kind == "chart":
        if not chart.get("ready"):
            return "The projection is still being drawn. Give it a moment, then ask me again."
        view = str(chart.get("view") or "wealth")
        start = chart.get("startAge") or you.get("age") or 40
        end = chart.get("endAge") or 85
        if view == "wealth" and chart.get("withPlanEnd") is not None:
            low = chart.get("lowest")
            extra = f" Its lowest point is {_say_money(low)}." if low is not None else ""
            plans_on = bool(chart.get("plansOn"))
            side = "with the plan applied" if plans_on else "without the recommended plan"
            end_wealth = chart.get("withPlanEnd") if plans_on else (chart.get("withoutEnd") or chart.get("withPlanEnd"))
            return (
                f"This chart is your money projected from age {start} to {end}. "
                f"You are looking at net wealth {side}. It reaches {_say_money(end_wealth)} "
                f"by age {end}.{extra} It is not a forecast. "
                f"It is arithmetic on the rates under Assumptions."
            )
        if view == "cash":
            side = (
                "with the plan applied — premiums out, payouts in"
                if chart.get("plansOn")
                else "without the recommended plan"
            )
            return (
                f"This chart is your money projected from age {start} to {end}. "
                f"You are looking at cashflow {side}. Money in is above the line, money out below it. "
                "It is not a forecast."
            )
        if view == "exp":
            side = (
                "with the plan applied"
                if chart.get("plansOn")
                else "without the recommended plan"
            )
            return (
                f"This chart is your money projected from age {start} to {end}. "
                f"You are looking at how expenses are funded {side}. "
                "It is not a forecast."
            )
        return (
            f"This chart is your money projected from age {start} to {end}. "
            "Switch a goal or a stress event and watch the line move."
        )
    if kind == "prod":
        life = (
            f"Life cover { _say_money(products.get('lifePrem')) } a year, "
            f"sum assured {_say_money(products.get('lifeSum'))}. "
            if products.get("lifeOn")
            else "Life cover is switched off. "
        )
        inv = (
            f"Investment plan {_say_money(products.get('investMth'))} a month. "
            if products.get("investOn")
            else "The investment plan is switched off. "
        )
        return (
            "Two kinds of product sit on this screen: cover that absorbs an event, "
            "and an investment plan that builds the balance. "
            + life
            + inv
            + "Switch either off and watch the chart. Nothing here is a recommendation to buy."
        )
    if kind == "mira":
        gaps = _enabled_gaps(context)
        end = (context.get("chart") or {}).get("endAge") if isinstance(context.get("chart"), dict) else 85
        n = len(gaps)
        gap_sum = sum(float(g.get("gap") or 0) for g in gaps)
        goals = (
            f"You have {n} goal{'s' if n != 1 else ''} in it, {_say_money(gap_sum)} short in total. "
            if n
            else "There are no goals in it yet. Add one from the panel. "
        )
        return (
            f"This last screen is your plan. The chart is your savings projected to age {end or 85}. "
            + goals
            + "Switch a goal or a product and watch the line move."
        )
    raise ValueError(f"Unknown explainer '{kind}'")


def _call_openai(system: str, user: str) -> str:
    return chat_complete(
        system=system,
        user=user,
        timeout=25.0,
        temperature=0.4,
        max_tokens=900,
    )


def generate_explanation(
    kind: str,
    route: str | None,
    context: dict[str, Any] | None,
) -> tuple[str, str]:
    if kind not in KINDS:
        raise ValueError(f"Unknown explainer '{kind}'")
    if kind == "mira" and route not in ROUTES:
        raise ValueError("Mira needs a known route")
    ctx = context if isinstance(context, dict) else {}
    fallback = fallback_script(kind, route, ctx)
    if not llm_configured():
        return fallback, "fallback"
    system = load_prompt(kind, route)
    user = "Context JSON:\n" + json.dumps(ctx, default=str)
    try:
        text = _call_openai(system, user)
    except Exception:
        return fallback, "fallback"
    text = " ".join(text.split())
    if len(text) < 40:
        return fallback, "fallback"
    return text, "llm"
