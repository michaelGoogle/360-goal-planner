"""Upsert a Prototype InsApi contact + financial plan from a GP session."""
from __future__ import annotations

import logging
import threading
from typing import Any

from src.heygen.mobile import normalize_mobile, split_e164
from src.hu_payload import dob_from_age
from src.insapi_client import (
    InsApiError,
    advisor_user_name,
    configured_user_id,
    create_contact,
    create_financial_plan,
    enabled,
    get_contact,
    search_user,
    update_contact,
    update_financial_plan,
)

logger = logging.getLogger(__name__)

_user_id_cache: str | None = None
_user_lock = threading.Lock()
_email_locks: dict[str, threading.Lock] = {}
_email_locks_guard = threading.Lock()

NEED_MAP = {
    "N_INC": ("lifeProtection", "Life Protection"),
    "N_CRI": ("criticalIllness", "Critical Illness"),
    "N_TPD": ("disability", "Disability"),
    "N_RET": ("retirement", "Retirement"),
    "N_EDU": ("education", "Education"),
    "N_SAV": ("generalSavings", "General Savings"),
    "N_PRP": ("home", "Home"),
}
EXTRA_NEED_MAP = {
    "hosp": ("hospitalization", "Hospitalization"),
}
CURRENCY = "SGD"


def _email_lock(email: str) -> threading.Lock:
    key = email.strip().lower()
    with _email_locks_guard:
        lock = _email_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _email_locks[key] = lock
        return lock


def resolve_advisor_user_id() -> str:
    global _user_id_cache
    configured = configured_user_id()
    if configured:
        return configured
    with _user_lock:
        if _user_id_cache:
            return _user_id_cache
        name = advisor_user_name()
        data = search_user(name)
        users = data.get("users") if isinstance(data, dict) else None
        match = None
        for row in users or []:
            if str(row.get("userName") or "").strip().lower() == name.lower():
                match = row
                break
        if not match and users:
            match = users[0]
        user_id = str((match or {}).get("userId") or "").strip()
        if not user_id:
            raise InsApiError(502, f"InsApi searchUser did not return {name}")
        _user_id_cache = user_id
        return user_id


def split_name(raw: str | None) -> tuple[str, str]:
    parts = str(raw or "").strip().split()
    if not parts:
        return "Customer", "-"
    if len(parts) == 1:
        return parts[0][:100], "-"
    return " ".join(parts[:-1])[:100], parts[-1][:100]


def _dob(session: dict[str, Any]) -> str:
    dob = str(session.get("dateOfBirth") or "").strip()
    if len(dob) >= 10 and dob[4] == "-":
        return dob[:10]
    try:
        age = int(session.get("age") or 40)
    except (TypeError, ValueError):
        age = 40
    return dob_from_age(age)


def _gender(session: dict[str, Any]) -> str:
    g = str(session.get("gender") or "Male").strip().title()
    return g if g in {"Male", "Female"} else "Male"


def _contact_values(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    values = data.get("values")
    return [v for v in values or [] if isinstance(v, dict)]


def _nested_first(row: dict[str, Any], key: str) -> dict[str, Any]:
    val = row.get(key)
    if isinstance(val, list) and val and isinstance(val[0], dict):
        return val[0]
    if isinstance(val, dict):
        return val
    return {}


def _find_contact(user_id: str, email: str, mobile_digits: str) -> str:
    email_l = email.strip().lower()
    data = get_contact(
        {
            "language": "en",
            "userId": user_id,
            "searchContactEmail": email,
            "page": 1,
            "perPage": 50,
            "showCategory": "Individual",
        }
    )
    for row in _contact_values(data):
        corr = _nested_first(row, "correspondenceDetails")
        got = str(corr.get("emailAddress") or "").strip().lower()
        if got == email_l:
            cid = str(row.get("contactId") or "").strip()
            if cid:
                return cid
    digits = "".join(c for c in mobile_digits if c.isdigit())
    if len(digits) < 8:
        return ""
    data = get_contact(
        {
            "language": "en",
            "userId": user_id,
            "searchContactPhone": digits,
            "page": 1,
            "perPage": 50,
            "showCategory": "Individual",
        }
    )
    for row in _contact_values(data):
        corr = _nested_first(row, "correspondenceDetails")
        got = "".join(c for c in str(corr.get("primaryMobileNumber") or "") if c.isdigit())
        if got.endswith(digits) or digits.endswith(got):
            cid = str(row.get("contactId") or "").strip()
            if cid:
                return cid
    return ""


def _duplicate_contact_id(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
    if not isinstance(detail, dict):
        return ""
    return str(detail.get("existingContactId") or "").strip()


def build_contact_body(user_id: str, email: str, e164: str, session: dict[str, Any]) -> dict[str, Any]:
    first, last = split_name(session.get("name"))
    cc, national = split_e164(e164)
    occupation = str(session.get("occupation") or "").strip()
    body: dict[str, Any] = {
        "userId": user_id,
        "category": "Individual",
        "status": "DRAFT",
        "personalDetails": {
            "firstName": first,
            "lastName": last,
            "dob": _dob(session),
            "gender": _gender(session),
        },
        "correspondenceDetails": {
            "primaryCountryCode": cc,
            "primaryMobileNumber": national,
            "emailAddress": email,
            "country": "Singapore",
            "timezone": "Asia/Singapore",
        },
        "marketingDetails": {
            "preferredLanguage": "en",
            "consent": True,
            "channel": "mobile",
        },
        "relationshipDetails": {
            "numberOfDependents": max(0, min(20, int(session.get("dependents") or 0))),
        },
    }
    if occupation:
        body["employmentDetails"] = {"jobTitle": occupation[:100]}
    return body


def _money(v: Any) -> float:
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        return 0.0
    return n if n > 0 else 0.0


def _record(account_type: str, category: str, amount: float, *, frequency: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "accountType": account_type,
        "accountCategory": category,
        "amount": round(amount, 2),
        "currency": CURRENCY,
    }
    if frequency:
        row["frequency"] = frequency
    return row


def _group(account_type: str, parts: list[tuple[str, float]], *, frequency: str | None = None) -> list[dict[str, Any]] | None:
    parts = [(cat, amt) for cat, amt in parts if amt > 0]
    if not parts:
        return None
    total = sum(amt for _, amt in parts)
    rows = [_record(account_type, "TOTAL", total, frequency=frequency)]
    rows.extend(_record(account_type, cat, amt, frequency=frequency) for cat, amt in parts)
    return rows


def _ranking(priority: Any) -> str:
    try:
        p = int(priority)
    except (TypeError, ValueError):
        return "medium"
    if p <= 2:
        return "high"
    if p >= 4:
        return "low"
    return "medium"


def _needs(session: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in session.get("needs") or []:
        if not isinstance(row, dict):
            continue
        mapped = NEED_MAP.get(str(row.get("type") or ""))
        if not mapped:
            continue
        key, label = mapped
        amount = _money(row.get("needAmount"))
        existing = _money(row.get("existing") or row.get("existingSumAssured") or row.get("existingInvestment"))
        gap = _money(row.get("gap"))
        if gap <= 0:
            gap = max(0.0, amount - existing)
        item: dict[str, Any] = {
            "needKey": key,
            "needLabel": label,
            "ranking": _ranking(row.get("priority")),
            "selected": bool(row.get("enabled")),
        }
        if amount > 0:
            item["needAmount"] = round(amount, 2)
        if gap > 0:
            item["gapAmount"] = round(gap, 2)
        out.append(item)
    extras = session.get("extraNeeds") or []
    if isinstance(extras, list):
        for extra in extras:
            mapped = EXTRA_NEED_MAP.get(str(extra))
            if not mapped:
                continue
            key, label = mapped
            if any(n.get("needKey") == key for n in out):
                continue
            out.append({"needKey": key, "needLabel": label, "ranking": "medium", "selected": True})
    return out


def _notes(session: dict[str, Any], pre: float | None, post: float | None) -> str:
    bits = ["Goal Planner D2C"]
    if pre is not None:
        bits.append(f"preHappiU={pre}")
    if post is not None:
        bits.append(f"postHappiU={post}")
    plan_sum = session.get("planSum") or {}
    plan_prem = session.get("planPrem") or {}
    if isinstance(plan_sum, dict) and plan_sum:
        bits.append("planSum=" + ",".join(f"{k}:{v}" for k, v in plan_sum.items() if v))
    if isinstance(plan_prem, dict) and plan_prem:
        bits.append("planPrem=" + ",".join(f"{k}:{v}" for k, v in plan_prem.items() if v))
    return " ".join(bits)[:1000]


def build_plan_body(
    user_id: str,
    contact_id: str,
    session: dict[str, Any],
    pre: float | None,
    post: float | None,
    *,
    plan_id: str = "",
    include_financial: bool = True,
) -> dict[str, Any]:
    first, last = split_name(session.get("name"))
    title = f"Financial plan for {first} {last}".replace(" -", "").strip()[:100]
    body: dict[str, Any] = {
        "language": "en",
        "userId": user_id,
        "contactId": contact_id,
        "title": title,
        "campaignName": "GP D2C",
        "leadSource": "Goal Planner",
        "notes": _notes(session, pre, post),
    }
    if plan_id:
        body["planId"] = plan_id
    needs = _needs(session)
    if needs:
        body["need"] = needs
    if not include_financial:
        return body

    income_m = _money(session.get("incomeMonthly"))
    expense_m = _money(session.get("expenseMonthly"))
    cash = _money(session.get("cash"))
    investments = _money(session.get("investments"))
    property_v = _money(session.get("property"))
    mortgage = _money(session.get("mortgage"))
    cpf = _money(session.get("cpfOa")) + _money(session.get("cpfSa")) + _money(session.get("cpfMa"))

    detail: dict[str, Any] = {}
    # InsApi converts to USD and rejects monthly income below ~USD 1000.
    if income_m >= 1500:
        grouped = _group("INCOME", [("SALARY", income_m)], frequency="M")
        if grouped:
            detail["income"] = grouped
        if 400 <= expense_m <= income_m * 0.95:
            exp = _group("EXPENSE", [("MISCELLANEOUS_EXPENSES", expense_m)], frequency="M")
            if exp:
                detail["expense"] = exp
    assets = _group(
        "ASSET",
        [("CASH", cash), ("MUTUAL_FUNDS", investments), ("REAL_ESTATE", property_v)],
    )
    asset_total = cash + investments + property_v
    if assets:
        detail["asset"] = assets
    if 0 < mortgage <= asset_total:
        liab = _group("LIABILITY", [("HOME_LOAN", mortgage)])
        if liab:
            detail["liability"] = liab
    if cpf > 0:
        gov = _group("ASSET", [("PENSION_FUND", cpf)])
        if gov:
            detail["retirementGovernmentSavings"] = gov
    if investments > 0:
        pers = _group("ASSET", [("MUTUAL_FUNDS", investments)])
        if pers:
            detail["retirementPersonalSavings"] = pers
    try:
        ret_age = int(session.get("ageOfRetirement") or 65)
    except (TypeError, ValueError):
        ret_age = 65
    if 55 <= ret_age <= 70:
        detail["retirementAge"] = ret_age
    detail["isSmoker"] = bool(session.get("isSmoker"))
    if property_v > 0:
        detail["propertyIsPropertyOwnership"] = True
        detail["homeIsHomeOwnership"] = True
    existing: dict[str, Any] = {}
    for row in session.get("needs") or []:
        if not isinstance(row, dict):
            continue
        mapped = NEED_MAP.get(str(row.get("type") or ""))
        if not mapped:
            continue
        amt = _money(row.get("existing") or row.get("existingSumAssured") or row.get("existingInvestment"))
        if amt > 0:
            existing[mapped[0]] = {"amount": round(amt, 2), "currency": CURRENCY}
    if existing:
        detail["existingResources"] = existing
    if detail:
        body["financialDetail"] = detail
    return body


def _plan_id_from(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    return str(data.get("planId") or "").strip()


def _save_plan(body: dict[str, Any], *, update: bool) -> tuple[int, Any]:
    if update and body.get("planId"):
        return update_financial_plan(body)
    create_body = {k: v for k, v in body.items() if k != "planId"}
    return create_financial_plan(create_body)


def _upsert_plan(user_id: str, contact_id: str, session: dict[str, Any], pre: float | None, post: float | None) -> str:
    plan_id = str(session.get("insapiPlanId") or "").strip()
    last_err: Any = "financial plan failed"
    for include_financial in (True, False):
        body = build_plan_body(
            user_id, contact_id, session, pre, post, plan_id=plan_id, include_financial=include_financial
        )
        status, data = _save_plan(body, update=bool(plan_id))
        if status < 400:
            return _plan_id_from(data) or plan_id
        last_err = data
    if plan_id:
        body = build_plan_body(user_id, contact_id, session, pre, post, include_financial=False)
        status, data = _save_plan(body, update=False)
        if status < 400:
            return _plan_id_from(data)
        last_err = data
    raise InsApiError(400, f"InsApi financial plan failed: {last_err}", last_err)


def sync_contact_and_plan(
    email: str,
    mobile: str,
    session: dict[str, Any],
    pre: float | None = None,
    post: float | None = None,
) -> dict[str, str]:
    """Create or update the Prototype contact and financial plan. Raises InsApiError."""
    if not enabled():
        raise InsApiError(503, "Prototype CRM is not configured (INSAPI_UPSTREAM)")
    email = (email or "").strip()
    if not email or "@" not in email:
        raise InsApiError(400, "Email is required")
    try:
        e164 = normalize_mobile(mobile)
    except ValueError as exc:
        raise InsApiError(400, str(exc)) from exc
    session = dict(session or {})
    with _email_lock(email):
        user_id = resolve_advisor_user_id()
        contact_id = str(session.get("insapiContactId") or "").strip() or _find_contact(
            user_id, email, e164
        )
        payload = build_contact_body(user_id, email, e164, session)
        if contact_id:
            update_contact({"contactId": contact_id, **{k: v for k, v in payload.items() if k != "userId"}})
        else:
            status, data = create_contact(payload)
            if status >= 400:
                contact_id = _duplicate_contact_id(data)
                if not contact_id:
                    raise InsApiError(status, f"InsApi createContact HTTP {status}: {data}", data)
                update_contact({"contactId": contact_id, **{k: v for k, v in payload.items() if k != "userId"}})
            else:
                contact_id = str((data or {}).get("contactId") or "").strip()
        if not contact_id:
            raise InsApiError(502, "InsApi did not return a contactId")
        plan_id = _upsert_plan(user_id, contact_id, session, pre, post)
        return {"contactId": contact_id, "planId": plan_id}


def sync_best_effort(
    email: str,
    mobile: str,
    session: dict[str, Any],
    pre: float | None = None,
    post: float | None = None,
) -> dict[str, str] | None:
    if not enabled():
        return None
    email = (email or session.get("reportEmail") or session.get("email") or "").strip()
    mobile = mobile or str(session.get("reportMobile") or session.get("mobile") or "")
    if not email or not mobile:
        return None
    try:
        return sync_contact_and_plan(email, mobile, session, pre, post)
    except Exception:
        logger.warning("Prototype InsApi sync failed", exc_info=True)
        return None


def schedule_insapi_sync(
    session: dict[str, Any],
    *,
    email: str = "",
    mobile: str = "",
    pre: float | None = None,
    post: float | None = None,
) -> None:
    if not enabled():
        return
    email = (email or session.get("reportEmail") or session.get("email") or "").strip()
    mobile = mobile or str(session.get("reportMobile") or session.get("mobile") or "")
    if not email or not mobile:
        return
    threading.Thread(
        target=sync_best_effort,
        args=(email, mobile, dict(session), pre, post),
        name="gp-insapi-sync",
        daemon=True,
    ).start()
