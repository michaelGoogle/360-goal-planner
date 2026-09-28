"""Recalculate the workbook in Excel and compare the SV / HappiU tabs to the Python twins.

Windows + Excel only (pywin32). Manual, not part of the GP tests:
    python GP/docs/calculations/excel_check.py            # all 50 personas
    python GP/docs/calculations/excel_check.py P01 P42    # a few
    python GP/docs/calculations/excel_check.py --events   # SV stress events on (HappiU ignores them)
"""

from __future__ import annotations

import sys
from pathlib import Path

import win32com.client  # type: ignore[import-not-found]

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_calculations_workbook as B  # noqa: E402
from deterministic_engines import load_hu_tables, session_for, twin_hu, twin_sv  # noqa: E402
from src.session_rates import DEFAULTS  # noqa: E402

SV_COLS = {
    "wPre": lambda t: t["pre"]["wealth"],
    "wPost": lambda t: t["post"]["wealth"],
    "cpf": lambda t: t["cpf"]["value"],
    "savPre": lambda t: t["pre"]["savings"],
    "savPost": lambda t: t["post"]["savings"],
}
HU_COLS = {
    "W": lambda t: t["wealth"],
    "Cw": lambda t: t["cwealth"],
    "sav": lambda t: t["sav"],
}
HU_SCALARS = {"HU_preHappiU": "preHappiU", "HU_postHappiU": "postHappiU", "HU_preRaw": "preRaw", "HU_postRaw": "postRaw"}


def _col(xl_wb, name: str) -> list[float]:
    vals = xl_wb.Application.Range(name).Value
    return [float(v[0] or 0) for v in vals]


def _scalar(xl_wb, name: str) -> float:
    return float(xl_wb.Application.Range(name).Value or 0)


def _close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(b))


EVENTS = [
    {"id": "crash", "on": True, "year": 8, "v": 0.35},
    {"id": "ccy", "on": True, "year": 6, "v": 0.14},
    {"id": "infl", "on": True, "from": 4, "to": 9, "v": 0.03},
    {"id": "inc", "on": True, "from": 5, "to": 10, "v": -0.2},
    {"id": "exp", "on": True, "from": 6, "to": 12, "v": 0.15},
]
EVENT_CELLS = {
    "crash": ("SV_crashY", None, "SV_crashV"),
    "ccy": ("SV_ccyY", None, "SV_ccyV"),
    "infl": ("SV_inflFrom", "SV_inflTo", "SV_inflV"),
    "inc": ("SV_incFrom", "SV_incTo", "SV_incV"),
    "exp": ("SV_expFrom", "SV_expTo", "SV_expV"),
}


def _set_events(xl, events: list[dict]) -> None:
    for a, b, v in EVENT_CELLS.values():
        for name in (a, b, v):
            if name:
                xl.Range(name).Value = None
    for ev in events:
        a, b, v = EVENT_CELLS[ev["id"]]
        xl.Range(a).Value = ev.get("year", ev.get("from"))
        if b:
            xl.Range(b).Value = ev["to"]
        xl.Range(v).Value = ev["v"]


def main(ids: list[str]) -> int:
    with_events = "--events" in ids
    ids = [i for i in ids if i != "--events"]
    tables = load_hu_tables()
    xl = win32com.client.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(str(B.OUT), ReadOnly=True)
    sel = wb.Worksheets("Selected persona").Range("B2")
    if with_events:
        _set_events(xl, EVENTS)
    bad = 0
    try:
        for p in B.PERSONAS:
            if ids and p["id"] not in ids:
                continue
            plu = B.twin_plu(p)
            prof = B.twin_profiler(p, plu)
            needs = B.twin_needs(p, plu, prof["enabled"])
            plan = B.twin_plan(p, plu, needs, prof["enabled"])
            s = session_for(p, plu, prof, needs, plan, dict(DEFAULTS))
            if with_events:
                s["events"] = EVENTS
            sel.Value = p["id"]
            xl.CalculateFull()
            errs: list[str] = []
            sv = twin_sv(s)
            n = sv["T"] + 1
            for key, fn in SV_COLS.items():
                got = _col(wb, f"SV_Y_{key}")[:n]
                want = fn(sv)
                worst = max(range(n), key=lambda j: abs(got[j] - want[j]))
                if not _close(got[worst], want[worst], 1e-6) and abs(got[worst] - want[worst]) > 0.05:
                    errs.append(f"SV {key}[{worst}] excel {got[worst]:,.2f} twin {want[worst]:,.2f}")
            try:
                hu = twin_hu(s, tables)
            except Exception as exc:  # noqa: BLE001
                errs.append(f"HU twin error {exc}")
                hu = None
            if hu is not None and "HU_Y_W" in [nm.Name for nm in wb.Names]:
                n = hu["T"] + 1
                for key, fn in HU_COLS.items():
                    got = _col(wb, f"HU_Y_{key}")[:n]
                    want = fn(hu)
                    worst = max(range(n), key=lambda j: abs(got[j] - want[j]))
                    if not _close(got[worst], want[worst], 1e-6) and abs(got[worst] - want[worst]) > 0.05:
                        errs.append(f"HU {key}[{worst}] excel {got[worst]:,.2f} twin {want[worst]:,.2f}")
                for name, key in HU_SCALARS.items():
                    got, want = _scalar(wb, name), float(hu[key])
                    if not _close(got, want, 1e-6):
                        errs.append(f"HU {name} excel {got} twin {want}")
            status = "ok" if not errs else "FAIL"
            score = ""
            if hu is not None:
                score = (f"HappiU excel {_scalar(wb, 'HU_preHappiU'):.0f}/{_scalar(wb, 'HU_postHappiU'):.0f}"
                         f" twin {hu['preHappiU']}/{hu['postHappiU']}")
            print(p["id"], status, score, *errs[:6], sep="  ")
            bad += bool(errs)
    finally:
        wb.Close(SaveChanges=False)
        xl.Quit()
    print("all ok" if not bad else f"{bad} persona(s) differ")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
