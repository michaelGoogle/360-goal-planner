"""Deterministic twins of the Scenario Visualizer and HappiU engines.

Used by build_calculations_workbook.py to verify the SV and HappiU tabs.
Scenario Visualizer: GP sends noDeathFlag, so SV grows every asset by 1 + mu
and the tab is a one-path copy. HappiU: HU draws mortality / morbidity and
lognormal returns; the twin replaces them with survival-weighted expected
values on HU's cashflow rules.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

UNIFIED = ("N_INC", "N_CRI", "N_TPD", "N_HOS", "N_RET", "N_EDU", "N_SAV", "N_PRP")
PROT = ("N_INC", "N_CRI", "N_TPD", "N_HOS")
WEALTH = ("N_RET", "N_EDU", "N_SAV", "N_PRP")
CURRENT_YEAR = 2026


def session_for(p: dict, plu: dict, prof: dict, needs: dict, plan: dict, rates: dict) -> dict[str, Any]:
    """GP session as the Plan screen holds it after the default plan seed."""
    need_rows = []
    for t in UNIFIED:
        row = needs[t]
        need = {
            "type": t,
            "enabled": bool(row["enabled"]),
            "needAmount": row["needAmount"],
            "priority": prof["priority"][t],
        }
        if t in WEALTH and t != "N_RET":
            need["fundsNeededYear"] = CURRENT_YEAR + 10
        need_rows.append(need)
    policies = (
        [{"type": "Life Protection", "sum": plu["life_sum"], "premium": plu["life_prem"]}]
        if plu["life_sum"]
        else []
    )
    return {
        "age": int(p["age"]),
        "gender": p["gender"],
        "residency": "Foreigner" if p["residency"] == "Foreigner" else p["residency"],
        "isSmoker": bool(p["llm_smoker"]),
        "incomeMonthly": plu["income"],
        "expenseMonthly": plu["expense"],
        "cash": plu["cash"],
        "investments": plu["investments"],
        "property": plu["property"],
        "mortgage": plu["mortgage"],
        "dependents": int(p["dependents"]),
        "lifeExpectancy": plu["life_expectancy"],
        "ageOfRetirement": 65,
        "policies": policies,
        "needs": need_rows,
        "planSum": dict(plan["plan_sum"]),
        "planPrem": dict(plan["plan_prem"]),
        "planMth": dict(plan["plan_mth"]),
        "planLump": dict(plan["plan_lump"]),
        "plansOff": [],
        "events": [],
        **rates,
    }


# --------------------------------------------------------------------------- SV

SV_SAVINGS_RATE = 0.01  # helium conf.ini savingsRate
SV_LE = 100  # helium conf.ini lifeExpectancy
CPF_OW_CAP_YR = 96_000
CPF_MA_CAP = 63_000
CPF_TOTAL = ((55, 0.37), (60, 0.325), (65, 0.235), (70, 0.165), (999, 0.125))
CPF_EMP = ((55, 0.20), (60, 0.17), (65, 0.115), (70, 0.075), (999, 0.05))
CPF_BANDS = (35, 45, 50, 55, 60, 65, 70)
CPF_OA = (0.6217, 0.5677, 0.5136, 0.4055, 0.4069, 0.1709, 0.0646, 0.08)
CPF_SA = (0.1621, 0.1891, 0.2162, 0.3108, 0.2372, 0.3170, 0.2580, 0.08)
CPF_MA = (0.2162, 0.2432, 0.2702, 0.2837, 0.3559, 0.5121, 0.6774, 0.84)
BRS = (99_400, 102_900, 106_500, 110_200, 114_100)
CPF_LIFE_PAY = ((870, 1620, 2370), (900, 1640, 2350), (930, 1730, 2530), (950, 1780, 2610), (980, 1840, 2690))
FX_SHARE = 2.0 / 3.0


def _band(age: float, table) -> float:
    for top, rate in table:
        if age <= top:
            return rate
    return table[-1][1]


def _prop(age: float, props) -> float:
    for top, rate in zip(CPF_BANDS, props):
        if age <= top:
            return rate
    return props[-1]


def _zero_from(arr: list, k: int) -> None:
    """numpy ``arr[k:] = 0`` (negative k counts from the end)."""
    for i in range(*slice(k, None).indices(len(arr))):
        arr[i] = 0.0


def _brs_idx(age: int, year: int) -> int:
    return max(55 - age, 0) + year - 2023


def _brs(idx: int) -> float:
    return BRS[idx] if idx < len(BRS) else 114_100 * 1.03 ** (idx - 4)


def _cpf_life_pay(idx: int, mult: int) -> float:
    if idx < len(CPF_LIFE_PAY):
        return CPF_LIFE_PAY[idx][mult - 1]
    return CPF_LIFE_PAY[-1][mult - 1] * 1.03 ** (idx - 4)


def employee_cpf_monthly(gross: float, age: int, residency: str) -> float:
    if residency == "Foreigner" or gross <= 0:
        return 0.0
    rate = 0.20 if age <= 55 else 0.18 if age <= 60 else 0.125 if age <= 65 else 0.075 if age <= 70 else 0.05
    return float(int(min(gross, 8000.0) * rate))


def sv_events(s: dict) -> dict:
    """GP stress rows as the SV tab reads them (first version: crash, ccy, infl, inc, exp)."""
    out: dict[str, Any] = {}
    infl = s["inflationRate"]
    for ev in s.get("events") or []:
        if not ev.get("on"):
            continue
        k = ev["id"]
        y = int(ev.get("year", ev.get("from", 0)) or 0)
        start = max(1, int(ev.get("from", y) or 0) + 1)
        end = max(start, int(ev.get("to", y) or 0) + 1)
        v = float(ev["v"])
        if k == "crash":
            out["crash"] = (max(1, y + 1), 1 - abs(v))
        elif k == "ccy":
            out["ccy"] = (max(1, y + 1), 1 - abs(v) * FX_SHARE)
        elif k == "infl":
            out["infl"] = (start, infl + abs(v), max(1, end - start + 1))
        elif k == "inc":
            out["inc"] = (start, end, v if v <= 0 else -abs(v))
        elif k == "exp":
            out["exp"] = (start, end, abs(v))
    return out


def sv_plan_pots(s: dict, n_years: int) -> list[dict]:
    """GP plan_benefit_visualizer: premiums-to-date and account / benefit columns."""
    age, ret = s["age"], s["ageOfRetirement"]
    inv = s["investmentReturn"]
    out = []
    for need in s["needs"]:
        t = need["type"]
        if not need["enabled"] or t in s.get("plansOff", []):
            continue
        if t in WEALTH:
            mth = float(s["planMth"].get(t, 0) or 0)
            lump = float(s["planLump"].get(t, 0) or 0)
            if mth <= 0 and lump <= 0:
                continue
            pay = max(1, ret - age) if t == "N_RET" else max(1, int(need.get("fundsNeededYear") or CURRENT_YEAR + 10) - CURRENT_YEAR)
            paid = acc = 0.0
            prem, value = [], []
            for i in range(n_years):
                if i < pay:
                    c = mth * 12 + (lump if i == 0 else 0.0)
                    paid += c
                    acc = (acc + c) * (1 + inv)
                else:
                    acc *= 1 + inv
                prem.append(round(paid, 2))
                value.append(round(max(0.0, acc), 2))
            out.append({"type": t, "prem": prem, "value": value})
        elif t in PROT:
            sa = float(s["planSum"].get(t, 0) or 0)
            pp = s["planPrem"].get(t)
            pp = float(pp) if pp is not None else (max(0.0, round(sa * 0.00078 / 10) * 10) if sa else 0.0)
            if sa <= 0 and pp <= 0:
                continue
            pay = max(1, ret - age)
            paid = 0.0
            prem = []
            for i in range(n_years):
                if i < pay:
                    paid += pp
                prem.append(round(paid, 2))
            out.append({"type": t, "prem": prem, "value": None})
    return out


def twin_sv(s: dict) -> dict[str, Any]:
    """One deterministic SV path (pre and post) on GP's payload rules."""
    age, ret = int(s["age"]), int(s["ageOfRetirement"])
    T = max(SV_LE - age, 0)
    dtr = max(ret - age, 0)
    ev = sv_events(s)
    g, pi = s["incomeGrowthRate"], s["inflationRate"]
    sal0 = int(round(s["incomeMonthly"] * 12))
    exp0 = int(round(s["expenseMonthly"] * 12))
    mort = float(s["mortgage"] or 0)
    inst = int(round(annual_loan_payment(mort, s["loanRate"]))) if mort else 0
    take_home = round(max(0.0, s["incomeMonthly"] - employee_cpf_monthly(s["incomeMonthly"], age, s["residency"])), 2)
    contrib = int(round(max(0.0, take_home - s["expenseMonthly"])))
    life_prem = sum(float(p["premium"] or 0) for p in s["policies"] if "Life" in p["type"]) * (1 + SV_SAVINGS_RATE)

    # Human capital (length T, index i = year i + 1)
    sal = [sal0 * (1 + g) ** i for i in range(T)]
    if "inc" in ev:
        a, b, imp = ev["inc"]
        for i in range(a - 1, min(b, T)):
            sal[i] *= 1 + imp
    _zero_from(sal, dtr - 1)
    f = [1 + pi] * T
    if "infl" in ev:
        a, rate, n = ev["infl"]
        for i in range(a - 1, min(a + n - 1, T)):
            f[i] = 1 + rate
    cum, c = [], 1.0
    for x in f:
        c *= x
        cum.append(c)
    exp = [-exp0 * cum[i] / cum[0] for i in range(T)] if T else []
    for i in range(min(20 if mort else 0, T)):
        exp[i] -= inst
    withdrawals = sv_withdrawals(s, T)
    for yrs, amt in withdrawals:
        exp[yrs - 1] -= amt
    if "exp" in ev:
        a, b, imp = ev["exp"]
        for i in range(a - 1, min(b, T)):
            exp[i] *= 1 + imp
    prem = [-life_prem if i < 20 else 0.0 for i in range(T)]

    # Assets (length T + 1)
    crash = ev.get("crash")
    ccy = ev.get("ccy")

    def grow(v0: float, rate: float, add: float, liquid: bool) -> list[float]:
        v = [float(v0)]
        for yr in range(1, T + 1):
            x = (v[-1] + (add if yr <= 100 else 0.0)) * (1 + rate)
            if crash and yr == crash[0]:
                x *= crash[1]
            if liquid and ccy and yr == ccy[0]:
                x *= ccy[1]
            v.append(x)
        return v

    cash = grow(int(round(s["cash"])), s["interestRate"], 0.0, True)
    inv = grow(int(round(s["investments"])), s["investmentReturn"], contrib, True)
    prop = grow(int(round(s["property"])), max(0.0, s["assetReturn"] + 0.004), 0.0, False)
    inv_neg = [0.0] + [-contrib if yr <= 100 else 0.0 for yr in range(1, T + 1)]

    cpf = sv_cpf(s, T, sal0, ev)

    def run(pots: list[dict]) -> dict[str, list[float]]:
        ins_val = [0.0] * (T + 1)
        ins_cf = [0.0] * (T + 1)
        for pot in pots:
            vals = pot["prem"][:T] if len(pot["prem"]) > T + 1 else pot["prem"]
            prem_arr = [0.0] + list(vals) + [0.0] * max(0, T - len(vals))
            term = T if len(pot["prem"]) > T + 1 else len(pot["prem"])
            yoy = [prem_arr[0]] + [max(prem_arr[i + 1] - prem_arr[i], 0) for i in range(len(prem_arr) - 1)]
            for j in range(min(len(yoy), T + 1)):
                ins_cf[j] -= yoy[j]
            if pot["value"] is not None:
                v = pot["value"][:T] if len(pot["value"]) > T + 1 else pot["value"]
                val = [0.0] + list(v) + [0.0] * max(0, T - len(v))
                if term <= T:
                    ins_cf[term] += val[term]
                    val[term] = 0.0
                for j in range(T + 1):
                    ins_val[j] += val[j]
        sav = [0.0] * (T + 1)
        for j in range(1, T + 1):
            budget = sal[j - 1] + exp[j - 1] + prem[j - 1] + inv_neg[j] + cpf["cf"][j] + ins_cf[j]
            sav[j] = sav[j - 1] * (1 + SV_SAVINGS_RATE) + budget
        loans = sv_loans(mort, s["loanRate"], inst, T)
        wealth = [max(0.0, cash[j] + inv[j] + prop[j] + cpf["value"][j] + sav[j] + ins_val[j] - loans[j]) for j in range(T + 1)]
        return {"savings": sav, "ins": ins_val, "insCf": ins_cf, "loans": loans, "wealth": wealth}

    pre = run([])
    post = run(sv_plan_pots(s, max(20, 100 - age)))
    return {
        "T": T, "sal": sal, "exp": exp, "prem": prem, "cash": cash, "inv": inv, "prop": prop,
        "invNeg": inv_neg, "cpf": cpf, "pre": pre, "post": post, "contrib": contrib, "withdrawals": withdrawals,
        "sal0": sal0, "exp0": exp0, "inst": inst, "lifePrem": life_prem,
    }


def sv_withdrawals(s: dict, T: int) -> list[tuple[int, float]]:
    """SV _setWithdrawalDict: goal amount (capitalSumRequired, not inflated) leaves savings in year target - now."""
    out = []
    for need in s["needs"]:
        if need["enabled"] and need["type"] in ("N_EDU", "N_SAV", "N_PRP"):
            yrs = int(need.get("fundsNeededYear") or CURRENT_YEAR + 10) - CURRENT_YEAR
            if yrs <= T:
                out.append((yrs, float(need["needAmount"] or 0)))
    return out


def annual_loan_payment(principal: float, annual_rate: float, years: int = 20) -> float:
    """goal_math.annual_loan_payment: level annual payment that clears the loan in `years`."""
    p = float(principal or 0)
    if p <= 0:
        return 0.0
    n = max(1, int(years or 20))
    r = float(annual_rate or 0)
    if abs(r) < 1e-12:
        return p / n
    return p * r / (1.0 - (1.0 + r) ** (-n))


def sv_loans(principal: float, rate: float, pmt: float, T: int) -> list[float]:
    out = [0.0] * (T + 1)
    if principal <= 0:
        return out
    rem = float(int(principal))
    for t in range(min(20, T + 1)):
        if rem <= 0:
            break
        out[t] = rem
        rem = max(0.0, rem * (1 + rate) - pmt)
    return out


def sv_cpf(s: dict, T: int, sal0: int, ev: dict) -> dict[str, Any]:
    """SV SocialSecurityR_SGP on zero opening balances. Foreigners: all zero."""
    zero = {"value": [0.0] * (T + 1), "cf": [0.0] * (T + 1), "oa": [0.0] * (T + 1), "sa": [0.0] * (T + 1),
            "ma": [0.0] * (T + 1), "ra": [0.0] * (T + 1), "life": [0.0] * (T + 1), "payout": 0.0, "withdrawal": 0.0}
    if s["residency"] == "Foreigner":
        return zero
    age, ret = int(s["age"]), int(s["ageOfRetirement"])
    g = s["incomeGrowthRate"]
    asp = max(65, ret)
    stop = min(70, ret) - age + 1
    sp = asp - age + 1
    ow = [sal0 * (1 + g) ** i for i in range(T)]
    if "inc" in ev:
        a, b, imp = ev["inc"]
        for i in range(a - 1, min(b, T)):
            ow[i] *= 1 + imp
    ow = [min(x, CPF_OW_CAP_YR) for x in ow]
    ages = [age + i for i in range(T)]
    tot = [_band(x, CPF_TOTAL) for x in ages]
    emp = [_band(x, CPF_EMP) for x in ages]

    def account(props, rate: float, zero_at_payout: bool):
        pr = [_prop(x, props) for x in ages]
        contrib = [0.0] + [pr[i] * tot[i] * ow[i] for i in range(T)]
        _zero_from(contrib, stop)
        neg = [0.0] + [-pr[i] * emp[i] * ow[i] for i in range(T)]
        _zero_from(neg, stop - 1)
        val, acc = [], 0.0
        for c in contrib:
            acc = acc * (1 + rate) + c
            val.append(acc)
        if zero_at_payout:
            _zero_from(val, sp)
        return val, neg

    oa, oa_n = account(CPF_OA, 0.025, True)
    sa, sa_n = account(CPF_SA, 0.04, True)
    ma, ma_n = account(CPF_MA, 0.04, False)
    ra = [0.0] * (T + 1)
    ra[sp] += oa[sp - 1] + sa[sp - 1] + max(ma[sp - 1] - CPF_MA_CAP, 0)
    oa[sp] = 0.0
    sa[sp] = 0.0
    for j in range(*slice(sp, None).indices(T + 1)):
        ma[j] = min(ma[j], CPF_MA_CAP)
    idx = _brs_idx(age, CURRENT_YEAR)
    brs = _brs(idx) * 1.03 ** (asp - 55)
    mult = min(3, int(ra[sp] // brs)) if brs else 0
    wd, pay = (0.0, 0.0) if mult <= 0 else (brs * mult, _cpf_life_pay(idx, mult) * (1 + 0.07 * (asp - 65)))
    pos = [pay * 12] * (T + 1)
    for j in range(*slice(None, sp - 1).indices(T + 1)):
        pos[j] = 0.0
    life = [0.0] * (T + 1)
    life[sp] = 1.04 * (wd - pay * 12)
    ra[sp] = 1.04 * (ra[sp] - wd)
    for y in range(sp + 1, T + 1):
        life[y] = 1.04 * (life[y - 1] - pos[y])
        ra[y] = 1.04 * ra[y - 1]
    life = [0.0 if ra[j] < 0 else life[j] for j in range(T + 1)]
    value = [oa[j] + sa[j] + ra[j] + ma[j] + life[j] for j in range(T + 1)]
    cf = [pos[j] + oa_n[j] + sa_n[j] + ma_n[j] for j in range(T + 1)]
    return {"value": value, "cf": cf, "oa": oa, "sa": sa, "ma": ma, "ra": ra, "life": life,
            "payout": pay, "withdrawal": wd, "sp": sp, "stop": stop}


# --------------------------------------------------------------------------- HappiU

HU_TABLES = Path(__file__).resolve().parents[3] / "HU" / "src" / "CashflowHandler" / "Tables"
HU_RATES = ("mort", "adb", "morb", "ptd", "dis", "hosp")
HU_DEFAULT_LE = 83  # HU input_mapping default when durationOfRetirement is 0
HU_CI_DEFAULT_YEARS = 5
HU_MED_DEFAULT = 200_000  # HU ciAssumptions medicalCost
HU_PTD_COST = 444_000
HU_PTD_CUT = 0.5
HU_DIS_CUT = 1.0
HU_CI_MAX_AGE = 75
HU_DEP_YEARS = 10
HU_TERM = 10  # GP segregatedBudget policyTerm
HU_WHL = 0.25
HU_MIN_MU = 0.01
PROTECTION_HU = ("N_INC", "N_CRI", "N_ADB", "N_HSP", "N_TPD", "N_PAC")
HU_CODE = {"N_HOS": "N_HSP"}


def load_hu_tables(folder: Path = HU_TABLES) -> dict[str, dict]:
    """HU rate CSVs: {name: {column: {age: q}}}, plus ss tables {age: (contribution, cap)} / {age: growth}."""
    out: dict[str, dict] = {}
    for name in HU_RATES:
        rows = list(csv.DictReader(open(folder / f"{name}_rate.csv", encoding="utf-8-sig")))
        out[name] = {col: {int(float(r["Age"])): float(r[col]) for r in rows}
                     for col in ("Male", "MaleSmoker", "Female", "FemaleSmoker")}
    rows = list(csv.DictReader(open(folder / "ss_contribution_cap.csv", encoding="utf-8-sig")))
    out["ss_cap"] = {int(float(r["Age"])): (float(r["Contribution"]), float(r["Cap"])) for r in rows}
    rows = list(csv.DictReader(open(folder / "ss_growth_rate.csv", encoding="utf-8-sig")))
    out["ss_growth"] = {int(float(r["Age"])): float(r["GrowthRate"]) for r in rows}
    return out


def hu_value(w: float, need: float, whl: float, w0: float, alpha: float, beta: float = 1.0) -> float:
    """HU GoalSecurityValue (piecewise)."""
    sat = w0 / alpha + need
    if w > sat:
        return 0.5 * w0 / alpha
    if w >= need:
        x = w - need
        return x - 0.5 * alpha / w0 * x * x
    if w >= whl:
        return beta * (w - need)
    return beta * (whl - need)


def hu_goals(s: dict) -> list[dict]:
    """GP build_happiu_payload need list (enabled + synthetic N_RET) with HU inputs per goal."""
    age, ret = int(s["age"]), int(s["ageOfRetirement"])
    le = min(int(s["lifeExpectancy"] or 85), 99)
    off = set(s.get("plansOff") or [])
    needs = [dict(n) for n in s["needs"] if n["enabled"]]
    if not any(n["type"] == "N_RET" for n in needs):
        needs.append({"type": "N_RET", "enabled": True, "priority": 5,
                      "needAmount": s["expenseMonthly"] * 12 * max(0, le - ret)})
    life_sum = sum(float(p["sum"] or 0) for p in s["policies"] if p["type"] == "Life Protection")
    out = []
    for n in needs:
        t = n["type"]
        need = float(n["needAmount"] or 0)
        in_plan = t not in off
        if t in PROT:
            existing = life_sum if t == "N_INC" else 0.0
            if in_plan:
                term = min(HU_TERM, HU_DEP_YEARS) if t == "N_INC" else HU_TERM
            else:
                term = HU_DEP_YEARS if t == "N_INC" else HU_CI_MAX_AGE - age
            dur = term + 1
        else:
            existing = 0.0
            if t == "N_RET":
                dur = max(0, ret - age)
            else:
                dur = max(0, int(n.get("fundsNeededYear") or CURRENT_YEAR + 10) - CURRENT_YEAR)
        if not in_plan:
            ben = 0.0
        elif t in PROT and s["planSum"].get(t) is not None:
            ben = max(0.0, float(s["planSum"][t] or 0))
        else:
            ben = max(0.0, round(need / 50000) * 50000)
        out.append({"type": t, "code": HU_CODE.get(t, t), "need": need, "existing": existing, "benefit": ben,
                    "priority": int(n.get("priority") or 3), "duration": dur,
                    "fundsYear": int(n.get("fundsNeededYear") or CURRENT_YEAR + 10)})
    return out


def twin_hu(s: dict, tables: dict | None = None, risk_profile: int = 4) -> dict[str, Any]:
    """Expected-value HappiU on HU rules, alive-conditional path weighted by survival."""
    tables = tables or load_hu_tables()
    age, ret = int(s["age"]), int(s["ageOfRetirement"])
    le_s = min(int(s["lifeExpectancy"] or 85), 99)
    le = max(0, le_s - ret) + ret if le_s - ret > 0 else HU_DEFAULT_LE
    T = max(le - age, 0)
    dtr = max(ret - age, 0)
    col = ("Male" if s["gender"] == "Male" else "Female") + ("Smoker" if s["isSmoker"] else "")
    q = {n: [tables[n][col][age + 1 + k] for k in range(T)] for n in HU_RATES}
    pi, g, sr = s["inflationRate"], s["incomeGrowthRate"], s["interestRate"]
    inc0 = 1 + s["incomeMonthly"] * 12
    exp0 = s["expenseMonthly"] * 12
    ret_exp = exp0 * 0.75  # lifestyle 2 -> rate 1.0, x 0.75 expectedLivingExpenseInTheCountry
    goals = hu_goals(s)
    types = {gl["type"] for gl in goals}
    ci_years = 3 if "N_CRI" in types else HU_CI_DEFAULT_YEARS
    ci_prop = max(0.0, min(1.0, exp0 / inc0))
    ci_cost = HU_MED_DEFAULT
    wd = [(gl["type"], gl["fundsYear"] - CURRENT_YEAR, gl["need"] - gl["existing"])
          for gl in goals if gl["type"] in ("N_EDU", "N_SAV", "N_PRP")]
    wd = [(t, y, a) for t, y, a in wd if y <= T]

    surv, pptd, pptd_first, pdis, pci_win = [], [], [], [], []
    alive = no_ptd = no_dis = 1.0
    for k in range(T):
        alive *= (1 - q["mort"][k]) * (1 - q["adb"][k])
        surv.append(alive)
        pptd_first.append(no_ptd * q["ptd"][k])
        no_ptd *= 1 - q["ptd"][k]
        pptd.append(1 - no_ptd)
        pdis.append(1 - no_dis)
        no_dis *= 1 - q["dis"][k]
        win = 1.0
        for j in range(max(0, k - ci_years), k):
            win *= 1 - q["morb"][j]
        pci_win.append(1 - win)

    inc, ss, base, pos, cons, neg, med = [], [], [], [], [], [], []
    growth = 1.0
    for k in range(T):
        a = age + 1 + k
        growth *= 1 + tables["ss_growth"][a]
        infl = (1 + pi) ** (k + 1)
        x = inc0 * (1 + g) ** (k + 1) if k < dtr else 0.0
        c, cap = tables["ss_cap"][a]
        lump = min(x * c / (1 - c), cap) * growth if (dtr >= 1 and k == dtr - 1) else 0.0
        extra = sum(amt for t, y, amt in wd if t != "N_EDU" and (y - 1) % T == k) if T else 0.0
        b = x + lump + extra
        cut = ci_prop * pci_win[k] + HU_PTD_CUT * pptd[k] + HU_DIS_CUT * pdis[k]
        spend = (ret_exp if (ret_exp and k >= dtr) else exp0) * infl
        wd_out = sum(amt for t, y, amt in wd if (y - 1) % T == k) if T else 0.0
        m = -ci_cost * infl * q["morb"][k] - HU_PTD_COST * infl * pptd_first[k]
        inc.append(x)
        ss.append(lump)
        base.append(b)
        pos.append(b * (1 - cut))
        cons.append(-spend)
        neg.append(-spend - wd_out)
        med.append(m)

    cash0 = float(s["cash"] or 0) or 1.0
    v0 = float(s["investments"] or 0)
    mu = max(HU_MIN_MU, s["investmentReturn"]) if v0 > 0 else 0.0
    nan_equity = v0 > 0 and dtr == 0
    sav = [cash0]
    for k in range(T):
        sav.append(sav[-1] * (1 + sr) + pos[k] + neg[k] + med[k])
    eq = [v0 * math.exp(mu * t) for t in range(T + 1)]
    wealth = [max(0.0, eq[t] + sav[t]) for t in range(T + 1)]
    cwealth = [0.0] + [max(0.0, pos[k] + cons[k]) for k in range(T)]

    alpha = 1 + (risk_profile - 1) * 0.5
    n_cons = sum(1 for gl in goals if gl["code"] not in ("N_INC", "N_ADB", "N_RET"))
    rows = []
    for gl in goals:
        code, need = gl["code"], gl["need"]
        dur = min(gl["duration"], T)
        path = wealth if code in ("N_INC", "N_ADB", "N_RET") else cwealth
        if code in PROTECTION_HU:
            cols = [(t, surv[t]) for t in range(1, dur)]
        else:
            cols = [(dur, surv[dur] if dur < T else 0.0)]
        w0 = (wealth[1] if T >= 1 else wealth[0]) + need if code in ("N_INC", "N_ADB", "N_RET") else need
        whl = HU_WHL * need
        flag = ""
        if w0 == 0:
            rows.append({**gl, "pre": 1.0, "post": 1.0, "flag": "w0 = 0 (HU raises an error)", "cols": cols,
                         "w0": w0, "whl": whl})
            continue

        def u(add: float) -> float:
            return sum(wt * hu_value(path[t] + add, need, whl, w0, alpha) for t, wt in cols)

        ub = sum(wt * hu_value(0.0, need, whl, w0, alpha) for _, wt in cols)
        upre, urec, ufull = u(gl["existing"]), u(gl["existing"] + gl["benefit"]), u(need)
        dn = ufull - ub
        if dn == 0:
            pre = post = 1.0
            flag = "denominator 0"
        else:
            pre = 1.0 if (dn == upre - ub and upre > 0) else max(0.0, min(1.0, (upre - ub) / dn))
            post = 1.0 if (dn == urec - ub and urec > 0) else max(0.0, min(1.0, (urec - ub) / dn))
        rows.append({**gl, "pre": pre, "post": post, "flag": flag, "cols": cols, "w0": w0, "whl": whl,
                     "ub": ub, "upre": upre, "urec": urec, "ufull": ufull})
    for r in rows:
        calib = 1.0 if r["code"] in ("N_INC", "N_ADB") else 2.0 if r["code"] == "N_RET" else 1.0 / n_cons
        floor = 1 if r["code"] in ("N_INC", "N_RET", "N_CRI") else 0
        r["logPriority"] = max(math.log(r["priority"] + 1), math.log(floor + 1))
        r["calib"] = calib
    denom = sum(r["logPriority"] * r["calib"] for r in rows)
    sig = 1 + math.exp(-len(rows))
    for r in rows:
        r["weight"] = r["logPriority"] * r["calib"] / denom
    pre = sum(r["pre"] * r["weight"] for r in rows) / sig
    post = sum(r["post"] * r["weight"] for r in rows) / sig
    return {
        "T": T, "dtr": dtr, "le": le, "col": col, "q": q, "surv": surv, "pptd": pptd, "pdis": pdis,
        "pciWin": pci_win, "inc": inc, "ss": ss, "pos": pos, "neg": neg, "cons": cons, "med": med,
        "sav": sav, "eq": eq, "wealth": wealth, "cwealth": cwealth, "mu": mu, "alpha": alpha,
        "goals": rows, "sigmoid": sig, "preRaw": pre, "postRaw": post,
        "preHappiU": round(pre * 100), "postHappiU": round(post * 100), "nanEquity": nan_equity,
        "ciYears": ci_years, "ciProp": ci_prop, "withdrawals": wd,
    }
