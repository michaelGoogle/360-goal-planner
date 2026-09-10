"""
People Like You — predict financial profile from demographics via Claude
(Anthropic), with OpenAI as fallback if no Anthropic key is set.

Ported from FM ``people_like_you_service.py`` (itself from InsApi) so GP
runs this in-process. Spend / CPF closed forms live in ``src.cpf``.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from src.cpf import expenses_from_gross, take_home_income

logger = logging.getLogger(__name__)

_RISK_TO_PROFILE = {
    "conservative": 2,
    "moderate": 3,
    "aggressive": 5,
}


def load_prompt_template() -> str:
    """Load the People Like You prompt template (unified JSON ``human`` lines)."""
    prompts_dir = Path(__file__).resolve().parent / "prompts"
    path = prompts_dir / "people_like_you_all_fields.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        human = data.get("human")
        if isinstance(human, list) and human:
            return "\n".join(str(line) for line in human)
        if isinstance(human, str) and human.strip():
            return human
        raise ValueError("No human prompt in people_like_you_all_fields.json")
    except Exception as e:
        logger.error("Failed to load prompt template: %s", e)
        raise


_INCOME_ANCHORS_PATH = Path(__file__).resolve().parent / "prompts" / "income_anchors.json"


@functools.lru_cache(maxsize=1)
def load_income_anchors() -> dict[str, Any]:
    """Load configurable occupation income bands from prompts/income_anchors.json."""
    return json.loads(_INCOME_ANCHORS_PATH.read_text(encoding="utf-8"))


def _canonical_country(country_text: str, aliases: dict[str, list[str]]) -> str:
    for canon, extras in aliases.items():
        if country_text == canon or country_text in extras:
            return canon
    return country_text


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _occupation_matches(occupation_text: str, match: dict[str, Any]) -> bool:
    clauses: list[bool] = []
    for pat in match.get("regex") or []:
        clauses.append(bool(re.search(pat, occupation_text)))
    for needle in match.get("any_substring") or []:
        clauses.append(needle in occupation_text)
    groups = match.get("all_groups")
    if groups:
        clauses.append(all(any(opt in occupation_text for opt in group) for group in groups))
    return any(clauses)


def _band(min_v: Any, max_v: Any) -> dict[str, float]:
    return {"min": float(min_v), "max": float(max_v)}


def get_income_bounds(
    occupation: str | None,
    country: str | None,
    city: str | None,
) -> dict[str, float] | None:
    """Return min/max monthly income bounds when defined in income_anchors.json."""
    occupation_text = _normalize_text(occupation)
    country_text = _normalize_text(country)
    city_text = _normalize_text(city)
    data = load_income_anchors()
    aliases = data.get("country_aliases") or {}
    country_key = _canonical_country(country_text, aliases)

    for occ in data.get("occupations") or []:
        if not _occupation_matches(occupation_text, occ.get("match") or {}):
            continue
        for ov in occ.get("city_overrides") or []:
            ov_country = _canonical_country(_normalize_text(ov.get("country")), aliases)
            needle = _normalize_text(ov.get("city_contains"))
            if ov_country == country_key and needle and needle in city_text:
                return _band(ov.get("min"), ov.get("max"))
        bounds = (occ.get("bounds") or {}).get(country_key)
        if bounds:
            return _band(bounds.get("min"), bounds.get("max"))
        return None
    return None


def _country_catalog(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in data.get("countries") or [] if row.get("id")}


def _format_money_band(bounds: dict[str, Any]) -> str:
    return f"{int(bounds['min']):,}–{int(bounds['max']):,}"


def format_income_anchor_block(country: str | None = None) -> str:
    """Singapore scale plus, when known, local-currency bands for the person's country."""
    data = load_income_anchors()
    by_id = {occ.get("id"): occ for occ in data.get("occupations") or []}
    prompt = data.get("prompt") or {}
    lines = [str(x) for x in (prompt.get("intro") or [])]
    if lines:
        lines.append("")
    order = data.get("prompt_order") or [
        occ.get("id") for occ in data.get("occupations") or [] if occ.get("include_in_prompt")
    ]
    for occ_id in order:
        occ = by_id.get(occ_id)
        if not occ or not occ.get("include_in_prompt"):
            continue
        sg = (occ.get("bounds") or {}).get("singapore")
        if not sg:
            continue
        lines.append(f"- {occ.get('label') or occ_id}: {_format_money_band(sg)}")
    unmatched = [str(x) for x in (prompt.get("unmatched") or [])]
    if unmatched:
        lines.append("")
        lines.extend(unmatched)

    catalog = _country_catalog(data)
    aliases = data.get("country_aliases") or {}
    country_key = _canonical_country(_normalize_text(country), aliases)
    local = catalog.get(country_key)
    if local and country_key != "singapore":
        currency = local.get("currency") or ""
        label = local.get("label") or country_key
        suffix = f" ({currency})" if currency else ""
        lines += [
            "",
            f"For this person in {label}, use these monthly GROSS bands{suffix} "
            "for a typical jobholder — not listed-company packages:",
            "",
        ]
        for occ_id in order:
            occ = by_id.get(occ_id)
            if not occ or not occ.get("include_in_prompt"):
                continue
            bounds = (occ.get("bounds") or {}).get(country_key)
            if not bounds:
                continue
            lines.append(f"- {occ.get('label') or occ_id}: {_format_money_band(bounds)}")
    return "\n".join(lines)


def calculate_age_from_dob(dob: str) -> int:
    """Calculate age from date of birth string (YYYY-MM-DD)."""
    try:
        birth_date = datetime.strptime(dob, "%Y-%m-%d").date()
        today = datetime.now().date()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
    except Exception as e:
        logger.warning("Failed to calculate age from DOB %s: %s", dob, e)
        return 30


def infer_marital_status(age: int, marital_status: str | None) -> str:
    if marital_status:
        return marital_status.lower()
    return "single" if age < 30 else "married"


def format_location(country: str | None, city: str | None) -> str:
    parts = []
    if city:
        parts.append(city)
    if country:
        parts.append(country)
    return ", ".join(parts) if parts else "Location not specified"


def calculate_expenses_deterministically(
    income: float,
    age: int,
    marital_status: str,
    dependents: int,
    residency: str | None = None,
) -> float:
    """Spend is a share of take-home. ``marital_status`` is unused."""
    del marital_status
    return expenses_from_gross(income, dependents, age, residency)


def risk_ability_to_profile(risk_ability: str | None) -> int:
    key = (risk_ability or "").strip().lower()
    return _RISK_TO_PROFILE.get(key, 3)


def _ensure_env() -> None:
    """Load GP + workspace .env (same files as the BFF)."""
    from src.env_bootstrap import load_env_files

    load_env_files()


def _llm_settings() -> tuple[str, str, str]:
    """Return (provider, api_key, model). Prefer Claude; fall back to OpenAI."""
    _ensure_env()
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if anthropic_key:
        model = (
            os.environ.get("AN_MODEL")
            or os.environ.get("STATEMENT_LLM_MODEL")
            or "claude-sonnet-4-5"
        ).strip()
        return "anthropic", anthropic_key, model
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if openai_key:
        model = (os.environ.get("OPENAI_API_MODEL") or "gpt-4o-mini").strip()
        return "openai", openai_key, model
    raise RuntimeError("ANTHROPIC_API_KEY is not configured (workspace .env)")


def _anthropic_messages_create(client: Any, **kwargs: Any) -> Any:
    """Call Claude. SDK 1.x dropped temperature/top_p/top_k from the signature."""
    try:
        return client.messages.create(**kwargs)
    except TypeError:
        for key in ("temperature", "top_p", "top_k"):
            kwargs.pop(key, None)
        return client.messages.create(**kwargs)


def _complete_llm(prompt: str) -> str:
    provider, api_key, model = _llm_settings()
    if provider == "anthropic":
        from anthropic import Anthropic

        logger.info("Calling Claude for People Like You (model=%s)...", model)
        client = Anthropic(api_key=api_key)
        response = _anthropic_messages_create(
            client,
            model=model,
            max_tokens=400,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()

    from openai import OpenAI

    logger.info("Calling OpenAI for People Like You (model=%s)...", model)
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=400,
    )
    return (response.choices[0].message.content or "").strip()


def _extract_json_object(response_text: str) -> str:
    json_str = response_text.strip()
    json_str = re.sub(r"^```json\s*", "", json_str, flags=re.MULTILINE)
    json_str = re.sub(r"^```\s*", "", json_str, flags=re.MULTILINE)
    json_str = re.sub(r"```\s*$", "", json_str, flags=re.MULTILINE)
    json_str = json_str.strip()
    first_brace = json_str.find("{")
    if first_brace >= 0:
        brace_count = 0
        last_brace = -1
        in_string = False
        escape_next = False
        for i in range(first_brace, len(json_str)):
            char = json_str[i]
            if escape_next:
                escape_next = False
                continue
            if char == "\\":
                escape_next = True
                continue
            if char == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        last_brace = i
                        break
        if last_brace > first_brace:
            json_str = json_str[first_brace : last_brace + 1]
    return json_str.strip()


def predict_people_like_you(
    dob: str,
    occupation: str,
    country: str | None = None,
    city: str | None = None,
    dependents: int = 0,
    marital_status: str | None = None,
    years_employed: int | None = None,
    gender: str | None = None,
    residency: str | None = None,
) -> dict[str, Any]:
    """Predict financial profile using Claude (or OpenAI fallback)."""
    logger.info(
        "Starting People Like You prediction for occupation=%s location=%s",
        occupation,
        country or city,
    )

    timing: dict[str, float] = {}
    overall_start = time.time()
    response_text = ""

    try:
        age = calculate_age_from_dob(dob)
        inferred_marital_status = infer_marital_status(age, marital_status)
        location_str = format_location(country, city)

        fields_to_predict = [
            "income",
            "currency",
            "risk_ability",
            "price_sensitivity",
            "property",
            "car",
            "ward_type",
            "hospitalization_type",
            "travelling",
            "sports",
            "retirement_lifestyle",
            "is_smoker",
            "life_expectancy",
        ]
        fields_list = "\n- ".join(fields_to_predict)

        years_info = (
            f", {years_employed} years of experience" if years_employed is not None else ""
        )
        gender_info = (
            f"Gender: {gender}"
            if gender
            else "Gender: Not specified (infer from context if needed)"
        )
        occupation_for_prompt = f"{occupation}{years_info}"

        prompt_start = time.time()
        prompt_template = load_prompt_template()
        prompt = prompt_template.format(
            dob=dob,
            occupation=occupation_for_prompt,
            location_str=location_str,
            dependents=dependents,
            marital_status=inferred_marital_status,
            fields_list=fields_list,
            years_info=years_info,
            gender_info=gender_info,
            income_anchors=format_income_anchor_block(country=country),
        )
        prompt += (
            "\n\nIMPORTANT: Respond with ONLY a JSON object starting with { and ending "
            "with }. No other text, no markdown, no explanations."
        )
        timing["prompt_preparation"] = time.time() - prompt_start

        llm_start = time.time()
        response_text = _complete_llm(prompt)
        timing["llm_inference"] = time.time() - llm_start

        json_parse_start = time.time()
        json_str = _extract_json_object(response_text)
        if not json_str or not json_str.startswith("{"):
            raise RuntimeError(
                "People Like You returned non-JSON response. Expected JSON object but got: "
                f"{response_text[:200]}..."
            )

        predictions = json.loads(json_str)
        timing["json_parsing"] = time.time() - json_parse_start

        calc_start = time.time()
        income = predictions.get("income", 0)
        try:
            income = float(income)
        except (TypeError, ValueError):
            logger.warning("Invalid income value from model: %s. Defaulting to 0.", income)
            income = 0.0

        predictions["income"] = income
        bounds = get_income_bounds(occupation=occupation, country=country, city=city)
        if bounds and income:
            min_income = bounds["min"]
            max_income = bounds["max"]
            if income < min_income or income > max_income:
                clamped = min(max(income, min_income), max_income)
                logger.warning(
                    "Clamping income from %s to %s for occupation=%s country=%s city=%s",
                    income,
                    clamped,
                    occupation,
                    country,
                    city,
                )
                income = clamped
                predictions["income"] = income

        expenses = calculate_expenses_deterministically(
            income=income,
            age=age,
            marital_status=inferred_marital_status,
            dependents=dependents,
            residency=residency,
        )
        predictions["expenses"] = expenses

        if income and expenses and age > 21:
            savings_per_month = take_home_income(income, age, residency) - expenses
            working_years = max(0, age - 21)
            assets = savings_per_month * 12 * 0.5 * working_years
            predictions["assets"] = max(0, assets)
        else:
            predictions["assets"] = 0

        assets = predictions.get("assets", 0)
        predictions["liabilities"] = assets * 0.7
        timing["asset_calculation"] = time.time() - calc_start
        timing["total"] = time.time() - overall_start
        predictions["_timing"] = timing
        return predictions

    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON response from People Like You: %s", e)
        logger.error("Response text: %s", response_text[:500])
        raise RuntimeError(f"Invalid JSON response from People Like You: {e}") from e
    except Exception as e:
        logger.error("Error in People Like You prediction: %s", e, exc_info=True)
        raise


def map_predictions_to_onboarding(
    predictions: dict[str, Any],
    *,
    demographics: dict[str, Any],
) -> dict[str, Any]:
    """Map raw PLU predictions into portal onboarding field patches."""
    risk = risk_ability_to_profile(predictions.get("risk_ability"))
    currency = (predictions.get("currency") or "USD")
    if isinstance(currency, str):
        currency = currency.upper()[:8]
    else:
        currency = "USD"

    policy_patch = {
        "dateOfBirth": demographics.get("dob") or demographics.get("dateOfBirth"),
        "gender": demographics.get("gender"),
        "occupation": demographics.get("occupation"),
        "country": demographics.get("country"),
        "city": demographics.get("city"),
        "dependents": demographics.get("dependents", 0),
        "maritalStatus": demographics.get("maritalStatus")
        or demographics.get("marital_status"),
        "yearsEmployed": demographics.get("yearsEmployed")
        if demographics.get("yearsEmployed") is not None
        else demographics.get("years_employed"),
        "isSmoker": bool(predictions.get("is_smoker", False)),
        "riskProfile": risk,
    }
    # Drop Nones so we don't wipe existing values unintentionally at merge time.
    policy_patch = {k: v for k, v in policy_patch.items() if v is not None}

    finance_patch = {
        "monthlyIncome": float(predictions.get("income") or 0),
        "monthlyExpense": float(predictions.get("expenses") or 0),
        "liquidAssetValue": float(predictions.get("assets") or 0),
    }

    result = {
        "income": predictions.get("income"),
        "expenses": predictions.get("expenses"),
        "assets": predictions.get("assets"),
        "liabilities": predictions.get("liabilities"),
        "currency": currency,
        "riskAbility": predictions.get("risk_ability"),
        "priceSensitivity": predictions.get("price_sensitivity"),
        "ownershipInformation": {
            "property": predictions.get("property", False),
            "car": predictions.get("car", False),
        },
        "clientPreferences": {
            "wardType": predictions.get("ward_type"),
            "hospitalType": predictions.get("hospitalization_type"),
            "travelling": predictions.get("travelling", False),
            "sports": predictions.get("sports"),
            "retirementLifestyle": predictions.get("retirement_lifestyle"),
            "isSmoker": predictions.get("is_smoker", False),
        },
        "lifeExpectancy": predictions.get("life_expectancy"),
    }

    return {
        "policyOwner": policy_patch,
        "finance": finance_patch,
        "home_currency": currency,
        "result": result,
        "timing": predictions.get("_timing") or {},
    }
