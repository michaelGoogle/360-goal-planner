"""Standalone HTML snapshot of the plan report for the media host.

Clones the in-app report (`frontend/src/pages/plan/PlanReport.tsx`): same
sections, copy, HappiU gauge, pies, tables, and embedded walkthrough video.
"""

from __future__ import annotations

import html
import math
from datetime import date
from typing import Any

from src.cpf import session_employee_cpf, session_take_home
from src.hu_payload import need_existing
from src.session_rates import DEFAULTS as ASSUME_DEFAULTS
from src.session_rates import session_rate

NEED_TYPES = ["N_INC", "N_CRI", "N_TPD", "N_HOS", "N_RET", "N_EDU", "N_SAV", "N_PRP"]
PROTECTION = {"N_INC", "N_CRI", "N_TPD", "N_HOS"}
WEALTH = {"N_RET", "N_EDU", "N_SAV", "N_PRP"}
NEED_LABEL = {
    "N_INC": "Income & family protection",
    "N_CRI": "Critical illness",
    "N_TPD": "Total & permanent disability",
    "N_HOS": "Hospitalisation",
    "N_RET": "Retirement",
    "N_SAV": "Savings goal",
    "N_EDU": "Child’s university education",
    "N_PRP": "Property purchase",
}
PLAN_TITLE = {
    "N_INC": "Life cover",
    "N_CRI": "Critical illness cover",
    "N_TPD": "Disability cover",
    "N_HOS": "Hospitalisation cover",
    "N_RET": "Retirement plan",
    "N_SAV": "Saving plan",
    "N_EDU": "Education plan",
    "N_PRP": "Property plan",
}
EXTRA_NEEDS = (("pa", "Personal accident"),)
ASSUME_LABEL = {
    "inflationRate": "Inflation",
    "interestRate": "Cash / savings interest",
    "incomeGrowthRate": "Income growth",
    "investmentReturn": "Net expected returns",
    "assetReturn": "Asset return",
}
POLICY_COL = {
    "Life Protection": "#7086FD",
    "Critical Illness": "#E8636C",
    "Permanent Disability": "#F5934A",
    "Hospitalisation": "#4BB6C4",
    "Personal Accident": "#F0952E",
    "Education": "#7B4BC4",
}
HAPPI_COL = {"POOR": "#E5484D", "FAIR": "#E8912B", "GOOD": "#12A150"}
PIE_FILL = {"pos": "#2563EB", "pos2": "#6E93F2", "neg": "#E5484D", "tot": "#12A150"}
FREE_BUDGET_SHARE = 0.5
MONEY_KEYS = ("income", "expense", "cash", "investments", "property", "loans", "cover")


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def _num(n: Any) -> float:
    try:
        return float(n or 0)
    except (TypeError, ValueError):
        return 0.0


def money(n: Any) -> str:
    try:
        v = int(round(float(n or 0)))
    except (TypeError, ValueError):
        return "—"
    sign = "−S$" if v < 0 else "S$"
    return sign + f"{abs(v):,}"


def rnum(v: float) -> str:
    return f"{float(v or 0):.2f}"


def _first_name(session: dict[str, Any]) -> str:
    raw = str(session.get("name") or "").strip().split()
    return raw[0] if raw else "you"


def _session_age(session: dict[str, Any]) -> int | None:
    try:
        age = int(session.get("age") or 0)
    except (TypeError, ValueError):
        return None
    return age if 18 <= age <= 70 else None


def happi_band(v: float) -> str:
    if v >= 85:
        return "GOOD"
    if v >= 50:
        return "FAIR"
    return "POOR"


def happi_caption(v: float) -> str:
    band = happi_band(v)
    if band == "GOOD":
        return "Good: You are well covered. Protect what you already have."
    if band == "FAIR":
        return "Fair: A solid start. Close the largest gaps to lift this."
    return "Poor: Start with the biggest shortfall, not everything at once."


def lift_copy(score: float, lift: int | None) -> str:
    if lift is None or lift <= 0:
        return happi_caption(score)
    band = happi_band(score)
    if band == "GOOD":
        return "Through a smart selection of these plans you are much better off and in good shape."
    if band == "FAIR":
        return (
            "Through a smart selection of these plans you are better off — a solid start. "
            "Close the largest gaps to lift this further."
        )
    return "These plans lift your HappiU. Start with the biggest shortfall to get on firmer ground."


def _map(val: Any) -> dict[str, float]:
    if not isinstance(val, dict):
        return {}
    return {str(k): _num(v) for k, v in val.items()}


def _liquid(session: dict[str, Any]) -> float:
    return _num(session.get("cash")) + _num(session.get("investments"))


def _assets(session: dict[str, Any]) -> float:
    return _liquid(session) + _num(session.get("property"))


def _net(session: dict[str, Any]) -> float:
    return _assets(session) - _num(session.get("mortgage"))


def _budget(session: dict[str, Any]) -> float:
    return session_take_home(session) - _num(session.get("expenseMonthly"))


def _money_out(session: dict[str, Any]) -> float:
    return _num(session.get("expenseMonthly")) + session_employee_cpf(session)


def _fv(pv: float, rate: float, periods: float) -> float:
    if periods <= 0:
        return max(0.0, pv)
    return pv * ((1 + rate) ** periods)


def _fv_annuity(pmt: float, rate: float, periods: float) -> float:
    if periods <= 0 or pmt <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return pmt * periods
    return (pmt * (((1 + rate) ** periods) - 1)) / rate


def _real_return(session: dict[str, Any]) -> float:
    nom = session_rate(session, "investmentReturn")
    inf = session_rate(session, "inflationRate")
    return max(0.0, (1 + nom) / (1 + inf) - 1)


def _now_year() -> int:
    return date.today().year


def _need_have(session: dict[str, Any], need: dict[str, Any]) -> float:
    t = str(need.get("type") or "")
    existing = need_existing(need, session)
    if t not in WEALTH:
        return existing
    r = _real_return(session)
    age = _session_age(session) or 40
    ret_age = int(need.get("retAge") or session.get("ageOfRetirement") or 65)
    y = _now_year()
    target = int(need.get("targetYear") or need.get("fundsNeededYear") or y + 10)
    contrib = _num(need.get("monthlyContribution"))
    contrib_yrs = _num(need.get("contributeYears") or max(1, target - y))
    if t == "N_RET":
        return round(_fv(existing, r, max(0, ret_age - age)))
    grown = _fv(existing, r, max(0, target - y))
    if t == "N_EDU":
        return round(grown)
    return round(grown + _fv_annuity(contrib * 12, r, contrib_yrs))


def _need_gap(session: dict[str, Any], need: dict[str, Any]) -> float:
    return max(0.0, _num(need.get("needAmount")) - _need_have(session, need))


def _plan_included(session: dict[str, Any], t: str) -> bool:
    off = {str(x) for x in (session.get("plansOff") or [])}
    return t not in off


def _horizon_years(session: dict[str, Any], need: dict[str, Any]) -> int:
    t = str(need.get("type") or "")
    age = _session_age(session) or 40
    if t == "N_RET":
        ret_age = int(need.get("retAge") or session.get("ageOfRetirement") or 65)
        return max(0, ret_age - age)
    y = _now_year()
    target = int(need.get("targetYear") or need.get("fundsNeededYear") or y + 10)
    return max(0, target - y)


def _plan_mth(session: dict[str, Any], t: str) -> float:
    return _map(session.get("planMth")).get(t, 0.0)


def _plan_lump(session: dict[str, Any], t: str) -> float:
    return _map(session.get("planLump")).get(t, 0.0)


def _cover_prem_for(sum_assured: float) -> float:
    return max(0.0, round((sum_assured * 0.00078) / 10) * 10)


def _plan_cover_sum(session: dict[str, Any], need: dict[str, Any]) -> float:
    t = str(need.get("type") or "")
    stored = _map(session.get("planSum"))
    if t in stored:
        return stored[t]
    return max(0.0, round(_need_gap(session, need)))


def _plan_cover_prem(session: dict[str, Any], need: dict[str, Any]) -> float:
    t = str(need.get("type") or "")
    stored = _map(session.get("planPrem"))
    if t in stored:
        return stored[t]
    indic = _cover_prem_for(_plan_cover_sum(session, need))
    return round((max(indic * 2, 200) / 2) / 10) * 10


def _plan_growth_fv(session: dict[str, Any], need: dict[str, Any]) -> float:
    t = str(need.get("type") or "")
    yrs = _horizon_years(session, need)
    r = _real_return(session)
    lump = _plan_lump(session, t)
    mth = _plan_mth(session, t)
    return round(_fv(lump, r, yrs) + _fv_annuity(mth * 12, r, yrs))


def _plan_remain(session: dict[str, Any], need: dict[str, Any]) -> float:
    t = str(need.get("type") or "")
    if t in WEALTH:
        have = _need_have(session, need)
        extra = _plan_growth_fv(session, need) if _plan_included(session, t) else 0.0
        return _num(need.get("needAmount")) - have - extra
    gap = _need_gap(session, need)
    if not _plan_included(session, t):
        return gap
    return gap - _plan_cover_sum(session, need)


def _suggested(session: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for n in session.get("needs") or []:
        if not isinstance(n, dict) or not n.get("enabled"):
            continue
        if _need_gap(session, n) <= 0:
            continue
        rows.append(n)
    order = {t: i for i, t in enumerate(NEED_TYPES)}
    rows.sort(key=lambda n: order.get(str(n.get("type") or ""), 99))
    return rows


def _goal_rows(session: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [n for n in (session.get("needs") or []) if isinstance(n, dict)]
    rows.sort(
        key=lambda n: (
            0 if n.get("enabled") else 1,
            -_need_gap(session, n),
        )
    )
    return rows


def _ratios(session: dict[str, Any]) -> list[dict[str, Any]]:
    income = _num(session.get("incomeMonthly"))
    expense = _num(session.get("expenseMonthly"))
    cash = _num(session.get("cash"))
    investments = _num(session.get("investments"))
    property_v = _num(session.get("property"))
    mortgage = _num(session.get("mortgage"))
    assets = cash + investments + property_v
    nw = assets - mortgage
    sav = income - expense
    loan_pay = mortgage / 240 if mortgage > 0 else 0.0

    def d(a: float, b: float) -> float:
        return a / b if b else 0.0

    return [
        {
            "k": "liq",
            "n": "Basic Liquidity Ratio",
            "v": d(cash, expense),
            "unit": "months",
            "rec": "3 to 6 months",
            "ok": d(cash, expense) >= 3,
        },
        {
            "k": "lnw",
            "n": "Liquid assets to net worth ratio",
            "v": d(cash, nw) * 100,
            "unit": "%",
            "rec": "at least 15%",
            "ok": d(cash, nw) * 100 >= 15,
        },
        {
            "k": "dsr",
            "n": "Debt service ratio",
            "v": d(loan_pay, income) * 100,
            "unit": "%",
            "rec": "35% or less",
            "ok": d(loan_pay, income) * 100 <= 35,
        },
        {
            "k": "dar",
            "n": "Debt asset ratio",
            "v": d(mortgage, assets) * 100,
            "unit": "%",
            "rec": "50% or less",
            "ok": d(mortgage, assets) * 100 <= 50,
        },
        {
            "k": "sav",
            "n": "Savings ratio",
            "v": d(sav, income) * 100,
            "unit": "%",
            "rec": "10% - 20%",
            "ok": d(sav, income) * 100 >= 10,
        },
        {
            "k": "inw",
            "n": "Total investment assets to net worth ratio",
            "v": d(investments, nw) * 100,
            "unit": "%",
            "rec": "at least 50%",
            "ok": d(investments, nw) * 100 >= 50,
        },
    ]


def _pct_an(v: float) -> str:
    s = f"{v * 100:.2f}".rstrip("0").rstrip(".")
    return f"{s}% p.a."


def _changed_assumptions(session: dict[str, Any]) -> list[tuple[str, str, str]]:
    out = []
    for key, base in ASSUME_DEFAULTS.items():
        val = session_rate(session, key)
        if round(val * 1000) != round(base * 1000):
            out.append((ASSUME_LABEL[key], _pct_an(val), _pct_an(base)))
    return out


def _plan_afford(session: dict[str, Any]) -> dict[str, Any]:
    available = max(0.0, _budget(session))
    free = round(available * FREE_BUDGET_SHARE)
    suggested = _suggested(session)
    prem_yr = 0.0
    contrib_mth = 0.0
    for n in suggested:
        t = str(n.get("type") or "")
        if not _plan_included(session, t):
            continue
        if t in PROTECTION:
            prem_yr += _plan_cover_prem(session, n)
        else:
            contrib_mth += _plan_mth(session, t)
    monthly = round(contrib_mth + prem_yr / 12)
    return {
        "available": available,
        "free": free,
        "freePct": round(FREE_BUDGET_SHARE * 100),
        "monthly": monthly,
        "monthlyOver": monthly - free,
    }


def _group_tag(session: dict[str, Any], who: str) -> str:
    prov = session.get("provenance") if isinstance(session.get("provenance"), dict) else {}
    vals = [prov.get(k) for k in MONEY_KEYS]
    if "doc" in vals:
        return '<em class="x-gtag doc">Read from your documents</em>'
    if "you" in vals:
        return '<em class="x-gtag you">Your own figures</em>'
    nm = "you" if who == "you" else who
    return f'<em class="x-gtag">People like {_esc(nm)} usually look like this</em>'


def _dl(rows: list[tuple[str, str, str]]) -> str:
    bits = []
    for k, v, cls in rows:
        extra = f' class="{cls}"' if cls else ""
        bits.append(f"<div><dt>{_esc(k)}</dt><dd{extra}>{v}</dd></div>")
    return f'<dl class="x-rpt-dl">{"".join(bits)}</dl>'


def _table(head: list[str], body: str, caption: str = "") -> str:
    caps = f"<caption>{_esc(caption)}</caption>" if caption else ""
    th = "".join(f"<th>{_esc(h)}</th>" for h in head)
    return f'<table class="x-rpt-table">{caps}<thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def _pie_point(cx: float, cy: float, r: float, angle: float) -> tuple[float, float]:
    rad = (angle - 90) * math.pi / 180
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _donut_slice(cx: float, cy: float, r_out: float, r_in: float, a0: float, a1: float) -> str:
    span = a1 - a0
    if span >= 359.99:
        o0, o1 = _pie_point(cx, cy, r_out, 0), _pie_point(cx, cy, r_out, 180)
        i0, i1 = _pie_point(cx, cy, r_in, 180), _pie_point(cx, cy, r_in, 0)
        return (
            f"M {o0[0]} {o0[1]} A {r_out} {r_out} 0 1 1 {o1[0]} {o1[1]} "
            f"A {r_out} {r_out} 0 1 1 {o0[0]} {o0[1]} L {i1[0]} {i1[1]} "
            f"A {r_in} {r_in} 0 1 0 {i0[0]} {i0[1]} A {r_in} {r_in} 0 1 0 {i1[0]} {i1[1]} Z"
        )
    large = 1 if span > 180 else 0
    x0, y0 = _pie_point(cx, cy, r_out, a0)
    x1, y1 = _pie_point(cx, cy, r_out, a1)
    xi1, yi1 = _pie_point(cx, cy, r_in, a1)
    xi0, yi0 = _pie_point(cx, cy, r_in, a0)
    return (
        f"M {x0} {y0} A {r_out} {r_out} 0 {large} 1 {x1} {y1} "
        f"L {xi1} {yi1} A {r_in} {r_in} 0 {large} 0 {xi0} {yi0} Z"
    )


def _eq_pie(rows: list[dict[str, Any]]) -> str:
    parts = [r for r in rows if abs(_num(r.get("v"))) > 0]
    total = sum(abs(_num(r.get("v"))) for r in parts)
    gap = 3.2 if len(parts) > 1 else 0.0
    angle = 0.0
    paths = []
    if total > 0:
        for r in parts:
            span = (abs(_num(r.get("v"))) / total) * 360
            a0 = angle + gap / 2
            a1 = angle + span - gap / 2
            angle += span
            if a1 <= a0:
                continue
            fill = r.get("fill") or PIE_FILL.get(str(r.get("c") or "pos"), PIE_FILL["pos"])
            d = _donut_slice(50, 50, 42, 26, a0, a1)
            paths.append(f'<path d="{_esc(d)}" fill="{_esc(fill)}"/>')
    else:
        paths.append('<circle cx="50" cy="50" r="42" fill="none" stroke="#EEF1F5" stroke-width="16"/>')
    keys = []
    for r in rows:
        fill = r.get("fill") or ""
        cls = _esc(str(r.get("c") or ""))
        style = f' style="background:{_esc(fill)}"' if fill else ""
        keys.append(
            f'<span class="x-gi"><span class="x-gk {cls}"><i{style}></i>'
            f'<span class="l">{_esc(r.get("l"))} <b>({_esc(money(abs(_num(r.get("v")))))})</b></span>'
            f"</span></span>"
        )
    return (
        '<div class="chart"><div class="x-pie"><div class="x-pied">'
        f'<svg viewBox="0 0 100 100" aria-hidden="true">{"".join(paths)}</svg>'
        f'</div><div class="x-gkey">{"".join(keys)}</div></div></div>'
    )


def _gauge_svg(value: float) -> str:
    v = max(0, min(100, int(round(value))))
    band = happi_band(v)
    w = 240
    sw = 18
    label_pad = 18
    r = w / 2 - label_pad - sw / 2
    cx = w / 2
    cy = label_pad + sw / 2 + r
    hub_r = r * 0.46
    h = math.ceil(cy + hub_r + 12)
    gid = f"xg{v}"

    def pt(val: float, rad: float) -> tuple[float, float]:
        a = ((180 - val * 1.8) * math.pi) / 180
        return cx + rad * math.cos(a), cy - rad * math.sin(a)

    def arc(a1: float, a2: float, rad: float) -> str:
        x1, y1 = pt(a1, rad)
        x2, y2 = pt(a2, rad)
        return f"M{x1} {y1} A{rad} {rad} 0 0 1 {x2} {y2}"

    ticks = []
    for t in range(2, 100, 2):
        x1, y1 = pt(t, r - sw / 2 + 2)
        x2, y2 = pt(t, r + sw / 2 - 2)
        ticks.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#fff" stroke-width="1" opacity=".55"/>'
        )
    labs = []
    for t in (0, 25, 50, 75, 100):
        x, y = pt(t, r + sw / 2 + 11)
        labs.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="11" font-weight="700" fill="#AEB6C0">{t}</text>'
        )
    px, py = pt(v, r - sw / 2 - 2)
    l1x, l1y = pt(v - 6, hub_r * 0.55)
    l2x, l2y = pt(v + 6, hub_r * 0.55)
    return f"""<div class="x-gauge" style="max-width:200px">
<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="HappiU Score {v} of 100, {band.lower()}">
<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="0">
<stop offset="0%" stop-color="#F0876B"/><stop offset="28%" stop-color="#F3B24A"/>
<stop offset="58%" stop-color="#EFDD73"/><stop offset="100%" stop-color="#7FD69B"/>
</linearGradient></defs>
<path d="{arc(0, 100, r)}" fill="none" stroke="url(#{gid})" stroke-width="{sw}" stroke-linecap="round"/>
{"".join(ticks)}
<path d="{arc(0, 100, r)}" fill="none" stroke="#fff" stroke-width="3" opacity=".5"/>
<polygon points="{px},{py} {l1x},{l1y} {l2x},{l2y}" fill="#1B2A4A"/>
<circle cx="{cx}" cy="{cy}" r="{hub_r}" fill="#fff"/>
<text x="{cx}" y="{cy}" text-anchor="middle">
<tspan x="{cx}" dy="-0.2em" font-size="42" font-weight="800" fill="#111A2B">{v}</tspan>
<tspan x="{cx}" dy="1.35em" font-size="11" fill="#8B95A2">of 100</tspan>
</text>
{"".join(labs)}
</svg></div>"""


REPORT_CSS = """
:root{--acc:#2554D6;--acc2:#4B7BFF;--ink0:#0C1424;--ink1:#4C5766;--ink2:#7B8694;
 --card:#fff;--page:#F5F7FA;--ln:#E7EBF1;--ok:#12A150;--no:#E5484D;--r2:20px;
 --sh:0 1px 2px rgba(12,20,36,.04),0 10px 26px -14px rgba(12,20,36,.16)}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink0);
 font:16px/1.5 "Segoe UI",system-ui,sans-serif}
.x-report{max-width:760px;margin:0 auto;padding:28px 20px 72px}
.x-eyebrow{font-size:13.2px;font-weight:750;letter-spacing:1.5px;text-transform:uppercase;
 color:var(--acc);margin-bottom:12px}
.x-rpt-hero h1{font-size:32px;letter-spacing:-.8px;font-weight:760;line-height:1.15;margin:0 0 10px}
.x-lead{font-size:18.4px;line-height:1.6;color:var(--ink1);max-width:62ch;margin:0}
.x-sm{font-size:15px;color:var(--ink2);line-height:1.55}
.x-rpt-scores{display:grid;grid-template-columns:minmax(0,220px) minmax(0,1fr);align-items:center;
 gap:8px 28px;margin:18px 0 8px;padding:16px 22px 18px;background:#fff;border:1px solid var(--ln);
 border-radius:var(--r2)}
.x-rpt-gauge{display:flex;flex-direction:column;align-items:center;gap:2px}
.x-rpt-gauge span,.x-rpt-score-side span{display:block;font-size:13px;color:var(--ink2);font-weight:650}
.x-rpt-score-side{display:flex;flex-direction:column;gap:10px;min-width:0}
.x-rpt-score-side b{display:block;font-size:28px;letter-spacing:-.6px}
.x-rpt-lift{font-size:52px;letter-spacing:-1.4px;font-weight:800;line-height:1}
.x-scorecap{margin:0;font-size:14.5px;font-weight:650;line-height:1.45;text-align:left}
.x-rpt-jump{display:flex;flex-wrap:wrap;gap:8px 14px;margin:4px 0 18px;padding:10px 0 12px;
 border-bottom:1px solid var(--ln)}
.x-rpt-jump a{font-size:13px;font-weight:700;color:var(--acc);text-decoration:none}
.x-gauge{width:100%;max-width:100%;margin:0 auto;line-height:0}
.x-gauge svg{display:block;width:100%;height:auto;overflow:visible}
.x-rpt-stage{margin:22px 0 8px}
.x-rpt-frame{padding:8px;background:#fff;border:1px solid var(--ln);border-radius:var(--r2);box-shadow:var(--sh)}
.x-rpt-frame-in{overflow:hidden;border-radius:14px;background:#0c1424;line-height:0}
.x-rpt-video{display:block;width:100%;aspect-ratio:16/9;height:auto;object-fit:cover;background:#0c1424}
.x-rpt-wait{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
 width:100%;aspect-ratio:16/9;padding:28px 32px;text-align:center;color:#fff;box-sizing:border-box;
 background:radial-gradient(120% 80% at 10% 0%,#4b7bff 0%,#16307f 42%,#0c1424 100%)}
.x-rpt-wait b{font-size:22px;letter-spacing:-.4px;font-weight:750}
.x-rpt-wait span{max-width:36em;font-size:14.5px;line-height:1.45;opacity:.88}
.x-rpt-cap{margin:10px 0 0;font-size:13.5px;color:var(--ink2);line-height:1.5}
.x-rpt-still{display:none;padding:16px 18px;border:1px dashed var(--ln);border-radius:14px;
 background:#fff;margin:18px 0}
.x-rpt-still b{display:block;font-size:15px;margin-bottom:4px}
.x-rpt-still span{font-size:14px;color:var(--ink1);line-height:1.5}
.x-rpt-sec{margin-top:28px;padding-top:8px}
.x-rpt-sec>summary{font-size:20px;font-weight:750;letter-spacing:-.3px;margin:0 0 12px;cursor:pointer;list-style:none}
.x-rpt-sec>summary::-webkit-details-marker{display:none}
.x-rpt-sec h2{font-size:20px;font-weight:750;letter-spacing:-.3px;margin:0 0 12px}
.x-rpt-sec h3{font-size:15px;font-weight:700;letter-spacing:-.2px;margin:16px 0 8px}
.x-rpt-chart{background:#fff;border:1px solid var(--ln);border-radius:14px;padding:12px 16px 10px;margin:0 0 12px}
.x-rpt-chart .chart{display:block}
.x-rpt-note{margin:0 0 12px}
.x-rpt-dl{display:grid;grid-template-columns:1fr 1fr;gap:10px 20px;margin:0}
.x-rpt-dl div{background:#fff;border:1px solid var(--ln);border-radius:12px;padding:10px 12px}
.x-rpt-dl dt{font-size:12.5px;color:var(--ink2);font-weight:650}
.x-rpt-dl dd{margin:4px 0 0;font-size:16px;font-weight:700;letter-spacing:-.2px}
.x-rpt-dl dd.ok{color:var(--ok)}
.x-rpt-dl dd.no{color:var(--no)}
.x-rpt-table{width:100%;border-collapse:collapse;font-size:13.5px;background:#fff;margin-top:12px}
.x-rpt-table caption{text-align:left;font-weight:700;font-size:14px;padding:0 0 8px}
.x-rpt-table th,.x-rpt-table td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--ln);vertical-align:top}
.x-rpt-table th{color:var(--ink2);font-weight:650;font-size:12px}
.x-rpt-table tr.off td{color:var(--ink2)}
.x-rpt-table td.ok{color:var(--ok);font-weight:700}
.x-rpt-table td.no{color:var(--no);font-weight:700}
.x-rpt-foot{margin-top:32px;padding-top:16px;border-top:1px solid var(--ln);font-size:13px;
 color:var(--ink2);line-height:1.55}
.x-gtag{display:inline-flex;align-items:center;gap:6px;font-style:normal;font-size:12px;
 font-weight:650;color:var(--acc);background:#EDF2FF;border-radius:99px;padding:4px 10px}
.x-gtag.doc{background:#EDF2FF;color:var(--acc)}
.x-gtag.you{background:#EEF1F5;color:var(--ink1)}
.x-pie{display:flex;align-items:center;gap:18px 24px;flex-wrap:wrap}
.x-pied{position:relative;width:148px;height:148px;flex:0 0 auto}
.x-pied svg{width:100%;height:100%}
.x-gkey{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin:0;flex:1;min-width:160px;
 flex-direction:column;align-items:flex-start;gap:8px}
.x-gi{display:inline-flex;align-items:center;gap:9px}
.x-gk{display:inline-flex;align-items:center;gap:6px;font-size:14.5px;color:var(--ink0)}
.x-gk>i{width:10px;height:10px;border-radius:3px;flex:0 0 auto}
.x-gk.pos>i{background:#2563EB}
.x-gk.pos2>i{background:#6E93F2}
.x-gk.neg>i{background:#E5484D}
.x-gk.tot>i{background:#12A150}
.x-gk .l{font-weight:650}
.x-gk b{font-weight:650;color:var(--ink1);letter-spacing:0;margin-left:0}
@media(max-width:640px){
 .x-rpt-dl{grid-template-columns:1fr}
 .x-rpt-scores{grid-template-columns:minmax(0,1fr);justify-items:center;text-align:center}
 .x-rpt-score-side{align-items:center}
}
@media print{
 .x-rpt-stage{display:none!important}
 .x-rpt-still{display:block!important}
}
"""


def render_report_html(
    session: dict[str, Any],
    pre: float | None,
    post: float | None,
    *,
    video_url: str = "",
) -> str:
    who = _first_name(session)
    title = "Your plan report" if who == "you" else f"{who}’s plan report"
    today = date.today()
    printed = f"{today.day} {today.strftime('%b')} {today.year}"
    age = _session_age(session)
    score = post if post is not None else (pre if pre is not None else 0)
    band = happi_band(score)
    lift = None
    if pre is not None and post is not None:
        lift = int(round(post)) - int(round(pre))
    lift_html = ""
    if lift is not None and lift != 0:
        col = HAPPI_COL["GOOD"] if lift > 0 else HAPPI_COL["POOR"]
        shown = f"+{lift}" if lift > 0 else str(lift)
        lift_html = (
            f'<b class="x-rpt-lift" style="color:{col}">{shown}</b>'
        )
    caption = lift_copy(score, lift)
    if lift is not None and lift != 0:
        caption = f"uplift. {caption}"
    cap_col = HAPPI_COL[band]
    whose = "your" if who == "you" else f"{who}’s"
    age_bit = f" · age {age}" if age is not None else ""

    if video_url:
        video_block = (
            f'<video class="x-rpt-video" controls playsinline preload="metadata" src="{_esc(video_url)}">'
            f"<track kind=\"captions\"></video>"
        )
        video_cap = f"A walkthrough of {whose} plan. This clip is not in the PDF."
    else:
        video_block = (
            '<div class="x-rpt-wait" role="status"><b>Plan report video</b>'
            "<span>A walkthrough of this report will play here.</span></div>"
        )
        video_cap = "A walkthrough of this report. It is not in the printed PDF."
    still_who = "" if who == "you" else f" for {who}"

    m_inc = _num(session.get("incomeMonthly"))
    surplus = _budget(session)
    net = _net(session)
    cashflow_label = "Short each month" if surplus < 0 else "Available budget"
    cashflow_c = "neg" if surplus < 0 else "tot"
    net_label = "Negative net wealth" if net < 0 else "Net wealth"
    net_c = "neg" if net < 0 else "tot"

    policies = [p for p in (session.get("policies") or []) if isinstance(p, dict)]
    if policies:
        pie_rows = [
            {
                "l": p.get("type") or "Cover",
                "v": _num(p.get("sum")),
                "fill": POLICY_COL.get(str(p.get("type") or ""), "#7086FD"),
            }
            for p in policies
        ]
        pol_body = "".join(
            "<tr>"
            f"<td>{_esc(p.get('type') or '—')}</td>"
            f"<td>{_esc(p.get('insurer') or '—')}</td>"
            f"<td>{_esc(money(p.get('sum')))}</td>"
            f"<td>{_esc(money(p.get('premium')))}</td></tr>"
            for p in policies
        )
        cover_html = (
            f'<div class="x-rpt-chart">{_eq_pie(pie_rows)}</div>'
            + _table(["Type", "Insurer", "Sum", "Premium / yr"], pol_body, "Existing cover")
        )
    else:
        cover_html = '<p class="x-sm">No existing policies on this session.</p>'

    goals = _goal_rows(session)
    goal_body = "".join(
        f'<tr class="{"off" if not n.get("enabled") else ""}">'
        f'<td>{_esc(NEED_LABEL.get(str(n.get("type") or ""), n.get("type") or "Goal"))}</td>'
        f'<td>{"Yes" if n.get("enabled") else "Off"}</td>'
        f'<td>{_esc(money(n.get("needAmount")))}</td>'
        f'<td>{_esc(money(_need_have(session, n)))}</td>'
        f'<td>{_esc(money(_need_gap(session, n))) if n.get("enabled") else "—"}</td></tr>'
        for n in goals
    ) or '<tr><td colspan="5">No goals on this session.</td></tr>'
    extras = [lab for k, lab in EXTRA_NEEDS if k in (session.get("extraNeeds") or [])]
    extras_html = f'<p class="x-sm">Also on: {_esc(", ".join(extras))}.</p>' if extras else ""

    ratios = _ratios(session)
    ok_n = sum(1 for r in ratios if r["ok"])
    ratio_body = "".join(
        "<tr>"
        f'<td>{_esc(r["n"])}</td>'
        f'<td>{_esc(rnum(r["v"]))}{"%" if r["unit"] == "%" else " " + r["unit"]}</td>'
        f'<td>{_esc(r["rec"])}</td>'
        f'<td class="{"ok" if r["ok"] else "no"}">{"In range" if r["ok"] else "Outside"}</td></tr>'
        for r in ratios
    )

    afford = _plan_afford(session)
    over = afford["monthlyOver"] > 0
    suggested = _suggested(session)
    if suggested:
        plan_body = "".join(
            "<tr>"
            f'<td>{_esc(PLAN_TITLE.get(str(n.get("type") or ""), n.get("type")))}</td>'
            f'<td>{"Yes" if _plan_included(session, str(n.get("type") or "")) else "Off"}</td>'
            f'<td>{_esc(
                f"{money(_plan_cover_sum(session, n))} cover · {money(_plan_cover_prem(session, n))} / yr"
                if str(n.get("type") or "") in PROTECTION
                else f"{money(_plan_lump(session, str(n.get("type") or "")))} lump · {money(_plan_mth(session, str(n.get("type") or "")))} / mo"
            )}</td>'
            f'<td>{_esc(money(_plan_remain(session, n)) if _plan_remain(session, n) > 0 else "Closed")}</td></tr>'
            for n in suggested
        )
        plan_table = _table(["Suggested product", "In plan", "Sizing", "Remaining gap"], plan_body)
    else:
        plan_table = '<p class="x-sm">Every activated goal is already funded.</p>'

    events_on = [e for e in (session.get("events") or []) if isinstance(e, dict) and e.get("on")]
    if events_on:
        event_line = "Stress tests on: " + ", ".join(
            str(e.get("label") or e.get("id") or "") for e in events_on
        ) + "."
    else:
        event_line = "No stress tests are on."
    assume = _changed_assumptions(session)
    if assume:
        assume_line = "Assumptions changed from default: " + "; ".join(
            f"{k} {v} (was {b})" for k, v, b in assume
        ) + "."
    else:
        assume_line = "Projection uses the default Singapore assumption set."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)} · FinPlan360</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<article class="x-report">
  <header class="x-rpt-hero">
    <p class="x-eyebrow">FinPlan360 · Powered by 360F</p>
    <h1>{_esc(title)}</h1>
    <p class="x-lead">Snapshot of this session on {_esc(printed)}{_esc(age_bit)}. Figures match Your plan. Not a quote, and not advice to buy.</p>
    <div class="x-rpt-scores">
      <div class="x-rpt-gauge">
        <span>Your new HappiU Score</span>
        {_gauge_svg(score)}
      </div>
      <div class="x-rpt-score-side">
        {lift_html}
        <p class="x-scorecap" style="color:{cap_col};text-align:left">{_esc(caption)}</p>
      </div>
    </div>
  </header>

  <nav class="x-rpt-jump" aria-label="Jump to report section">
    <a href="#rpt-video">Video</a>
    <a href="#rpt-about">About you</a>
    <a href="#rpt-money">Your money</a>
    <a href="#rpt-goals">Your goals</a>
    <a href="#rpt-score">Your score</a>
    <a href="#rpt-plan">Your plan</a>
  </nav>

  <div class="x-rpt-stage" id="rpt-video">
    <div class="x-rpt-frame"><div class="x-rpt-frame-in">{video_block}</div></div>
    <p class="x-rpt-cap">{_esc(video_cap)}</p>
  </div>
  <div class="x-rpt-still">
    <b>Plan video</b>
    <span>Watch the plan video in the online report{ _esc(still_who) }. It does not play in this PDF.</span>
  </div>

  <details class="x-rpt-sec" id="rpt-about" open>
    <summary>About you</summary>
    {_dl([
      ("Name", _esc(str(session.get("name") or "").strip() or "—"), ""),
      ("Age", _esc(age if age is not None else "—"), ""),
      ("Occupation", _esc(session.get("occupation") or "—"), ""),
      ("Residency", _esc(session.get("residency") or "—"), ""),
      ("Dependants", _esc(session.get("dependents") if session.get("dependents") is not None else 0), ""),
      ("Retire at", _esc(session.get("ageOfRetirement") or 65), ""),
    ])}
  </details>

  <details class="x-rpt-sec" id="rpt-money" open>
    <summary>Your money</summary>
    <p class="x-rpt-note">{_group_tag(session, who)}</p>
    <h3>What comes in and goes out</h3>
    <div class="x-rpt-chart">{_eq_pie([
      {"l": "Money coming in", "v": m_inc, "c": "pos"},
      {"l": "Money going out", "v": _money_out(session), "c": "neg"},
      {"l": cashflow_label, "v": surplus, "c": cashflow_c},
    ])}</div>
    <h3>What you own and owe</h3>
    <div class="x-rpt-chart">{_eq_pie([
      {"l": "Assets", "v": _assets(session), "c": "pos"},
      {"l": "Loans outstanding", "v": _num(session.get("mortgage")), "c": "neg"},
      {"l": net_label, "v": net, "c": net_c},
    ])}</div>
    {_dl([
      ("Cash & Savings", _esc(money(session.get("cash"))), ""),
      ("Investments", _esc(money(session.get("investments"))), ""),
      ("Property", _esc(money(session.get("property"))), ""),
    ])}
    <h3>What cover you have</h3>
    {cover_html}
  </details>

  <details class="x-rpt-sec" id="rpt-goals" open>
    <summary>Your goals</summary>
    {_table(["Goal", "On", "Need", "Have", "Gap"], goal_body)}
    {extras_html}
  </details>

  <details class="x-rpt-sec" id="rpt-score" open>
    <summary>Your score</summary>
    <p class="x-sm">{ok_n} of {len(ratios)} money-health ratios are in good shape.</p>
    {_table(["Ratio", "You", "Recommended", ""], ratio_body)}
  </details>

  <details class="x-rpt-sec" id="rpt-plan" open>
    <summary>Your plan</summary>
    {_dl([
      ("Monthly surplus", _esc(money(afford["available"])), ""),
      (f'Recommended free budget ({afford["freePct"]}%)', _esc(money(afford["free"])), ""),
      ("Premiums & contributions", _esc(f'{money(afford["monthly"])} / mo'), ""),
      (
        "Budget fit",
        _esc(f'{money(afford["monthlyOver"])} over') if over else "Fits",
        "no" if over else "ok",
      ),
    ])}
    {plan_table}
    <p class="x-sm">{_esc(event_line)}</p>
    <p class="x-sm">{_esc(assume_line)}</p>
  </details>

  <footer class="x-rpt-foot">
    People Like You figures are estimates until you edit them or add a statement. This report is not a product
    quote, application, or purchase, and it is not advice to buy, switch, or cancel cover.
  </footer>
</article>
</body>
</html>
"""
