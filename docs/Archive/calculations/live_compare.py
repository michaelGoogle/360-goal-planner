"""Post GP payloads to running SV / HU services and compare with the deterministic twins.

Manual, not part of the GP tests. Start the services first (SV :8001, HU :8002), then:
    python GP/docs/calculations/live_compare.py            # all 50 personas
    python GP/docs/calculations/live_compare.py P01 P12    # a few
    python GP/docs/calculations/live_compare.py --sv http://127.0.0.1:8001 --hu http://127.0.0.1:8002

SV runs with noDeathFlag, so its wealth path should equal the Scenario Visualizer tab.
HU is Monte Carlo: expect a few points of difference from the HappiU tab.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import build_calculations_workbook as B  # noqa: E402
from deterministic_engines import load_hu_tables, twin_hu, twin_sv  # noqa: E402
from src.hu_payload import build_happiu_payload  # noqa: E402
from src.sv_payload import build_sv_payload  # noqa: E402


def _post(url: str, body: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _up(base: str) -> bool:
    try:
        urllib.request.urlopen(f"{base}/health", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--sv", default="http://127.0.0.1:8001")
    ap.add_argument("--hu", default="http://127.0.0.1:8002")
    args = ap.parse_args()
    sv_up, hu_up = _up(args.sv), _up(args.hu)
    print(f"SV {args.sv}: {'up' if sv_up else 'down'}   HU {args.hu}: {'up' if hu_up else 'down'}")
    if not (sv_up or hu_up):
        return 1
    tables = load_hu_tables()
    for p in B.PERSONAS:
        if args.ids and p["id"] not in args.ids:
            continue
        s = B.persona_session(p)
        line = [p["id"]]
        if sv_up:
            try:
                res = _post(f"{args.sv}/api/v2/scenario-visualizer", build_sv_payload(s))
                tw = twin_sv(s)
                for kind in ("pre", "post"):
                    live = [float(x) for x in res[f"{kind}Wealth"]]
                    want = tw[kind]["wealth"]
                    n = min(len(live), len(want))
                    diff = max((abs(live[j] - want[j]) for j in range(n)), default=0.0)
                    line.append(f"SV {kind} max|Δ| {diff:,.2f} over {n} yrs")
            except Exception as exc:  # noqa: BLE001
                line.append(f"SV error {exc!r}"[:120])
        if hu_up:
            try:
                res = _post(f"{args.hu}/v1/happi-u", build_happiu_payload(s))
                tw = twin_hu(s, tables)
                line.append(f"HU live {res.get('preHappiU')}/{res.get('postHappiU')} tab {tw['preHappiU']}/{tw['postHappiU']}")
            except Exception as exc:  # noqa: BLE001
                line.append(f"HU error {exc!r}"[:120])
        print("  ".join(line))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
