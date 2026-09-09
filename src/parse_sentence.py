"""Extract About You fields from free-form text via Claude, with strict enums."""

from __future__ import annotations

import json
import re
from typing import Any

from src.env_bootstrap import load_env_files  # noqa: F401 — load .env before LLM settings
from src.openai_client import chat_complete

GENDERS = ("Male", "Female")
RESIDENCIES = ("Singapore Citizen", "Permanent Resident", "Foreigner")
DEPS = ("0", "1", "2", "3", "4+")

_RES_ALIASES = {
    "singapore citizen": "Singapore Citizen",
    "singaporean": "Singapore Citizen",
    "sg citizen": "Singapore Citizen",
    "citizen": "Singapore Citizen",
    "local": "Singapore Citizen",
    "singapore": "Singapore Citizen",
    "resident": "Singapore Citizen",
    "resident of singapore": "Singapore Citizen",
    "singapore resident": "Singapore Citizen",
    "permanent resident": "Permanent Resident",
    "pr": "Permanent Resident",
    "spr": "Permanent Resident",
    "foreigner": "Foreigner",
    "foreign": "Foreigner",
    "expat": "Foreigner",
    "expatriate": "Foreigner",
}

_OCC_ALIASES = {
    "ceo": "Chief Executive Officer",
    "chief executive": "Chief Executive Officer",
    "chief executive officer": "Chief Executive Officer",
    "see eo": "Chief Executive Officer",
    "c e o": "Chief Executive Officer",
    "cfo": "Chief Financial Officer",
    "chief financial officer": "Chief Financial Officer",
    "cto": "Chief Technology Officer",
    "chief technology officer": "Chief Technology Officer",
    "gp": "Doctor / General Practitioner",
    "general practitioner": "Doctor / General Practitioner",
    "home maker": "Homemaker",
    "homemaker": "Homemaker",
}

_OCC_REJECT = {
    "null",
    "none",
    "n/a",
    "kids",
    "kid",
    "wife",
    "husband",
    "0",
    "oh",
    "o",
    "zero",
    "yeah",
    "yes",
    "um",
    "uh",
    "mail",
    "kits",
    "worse",
    "maths",
    "solution",
    "actually",
}

_GENDER_ALIASES = {
    "male": "Male",
    "mail": "Male",
    "man": "Male",
    "female": "Female",
    "femail": "Female",
    "fe mail": "Female",
    "woman": "Female",
}

SYSTEM_PROMPT = """\
You extract structured profile fields from informal English about a person in Singapore.
The text is often a speech-to-text transcript: expect missing verbs, homophones, fillers,
and broken job titles. Reply with ONLY a JSON object. No markdown. Use this shape:
{"name": string|null, "age": number|null, "gender": "Male"|"Female"|null,
 "res": "Singapore Citizen"|"Permanent Resident"|"Foreigner"|null,
 "deps": "0"|"1"|"2"|"3"|"4+"|null, "occ": string|null}

Rules:
- Never invent a field that is not in the text. Use null when unsure.
- Fix speech errors and obvious typos:
  "I mail" / "I'm mail" / "I may" (when they mean sex) → gender Male
  "fe mail" / "femail" → Female
  "I actually Michael" / "is Michael" / "my name ic Michael" → name Michael
  "for two years old" → age 42; "year sold" → years old
  "city zen" → Singapore Citizen; "sing a pore" / "Singapore sitting" → they live in Singapore
  "pea are" / "pre" / "SPR" → Permanent Resident
  "kits" → kids; "for kids" → four kids; "no kits" → deps "0"
  "see eo" / "C E O" → Chief Executive Officer
  "worse" (job) → nurse; "account tent" → accountant; "home maker" → homemaker
  "working as 0" / "working as oh" → occ null, not a job
- age: whole years 18–70 only. Do not use a child's age or a unit/house number.
- res must use the key "res" (not "residency"). Values:
  Singapore Citizen — Singaporean, SG citizen, citizen of Singapore, local,
  resident of Singapore, Singapore resident, living in Singapore, live in Singapore,
  or "I'm a resident in/of Singapore". This is the default when they place themselves
  in Singapore and do not say PR, EP, work pass, visa, expat, or foreigner.
  Permanent Resident — PR, SPR, permanent resident, "pea are", "pre".
  Foreigner — EP, work pass, visa, expat, not a resident.
- deps: people who depend on the speaker's income. Count children. Do NOT count a spouse
  or partner unless they are described as not working (housewife, homemaker, stay-at-home).
  Example: "two kids and one wife" → deps "2".
- occ: the job title only. "I'm a CEO as occupation and I have two kids" → occ "Chief Executive Officer".
  Expand CEO/CFO/CTO. Never use family words (kids, wife, husband) as occupation.
  Never use fillers, digits, "0", "oh", "yeah", or "solution" as occupation — use null.
- name: a given name if they state one (including "I actually NAME" / "is NAME"), otherwise null.
  Do not infer gender from the name.
"""


def _call_openai(text: str) -> str:
    return chat_complete(
        system=SYSTEM_PROMPT,
        user=text,
        timeout=20.0,
        temperature=0,
        max_tokens=250,
        json_object=True,
    )


def _strip_fences(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _norm_res(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    t = raw.strip()
    if t in RESIDENCIES:
        return t
    return _RES_ALIASES.get(t.lower())


def _job_ok(job: str) -> bool:
    low = re.sub(r"\s+", " ", job).strip().lower()
    if not low or len(low) < 3 or low in _OCC_REJECT:
        return False
    if re.fullmatch(r"[\d.]+", low):
        return False
    if re.search(r"\b(yeah|um|uh)\b", low):
        return False
    if re.search(r"\b(kids?|kits|wife|husband|children|child|daughters?|sons?)\b", low):
        return False
    if re.search(r"city zen|singapore sitting|see eo|account tent|no kits|pea are", low):
        return False
    if low in {"pre", "pr"}:
        return False
    return True


def _title_job(raw: str) -> str:
    o = re.sub(r"\s+", " ", raw).strip(" .,;:!-")
    key = o.lower()
    if key in _OCC_ALIASES:
        return _OCC_ALIASES[key]
    return o[:1].upper() + o[1:] if o else o


def normalize_fields(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}

    name = data.get("name")
    if isinstance(name, str):
        n = name.strip()
        if n and n.lower() not in {"null", "none", "n/a"}:
            out["name"] = n[:1].upper() + n[1:]

    age = data.get("age")
    if age is not None and str(age).strip() != "":
        try:
            n = int(float(str(age).strip()))
        except (TypeError, ValueError):
            n = 0
        if 18 <= n <= 70:
            out["age"] = str(n)

    gender = data.get("gender")
    if isinstance(gender, str):
        g = _GENDER_ALIASES.get(gender.strip().lower())
        if g:
            out["gender"] = g
        elif gender in GENDERS:
            out["gender"] = gender

    res = _norm_res(data.get("res") or data.get("residency") or data.get("residencyStatus"))
    if res:
        out["res"] = res

    deps = data.get("deps")
    if deps is not None:
        d = str(deps).strip()
        if d in DEPS:
            out["deps"] = d

    occ = data.get("occ")
    if isinstance(occ, str):
        job = _title_job(occ)
        if _job_ok(job):
            out["occ"] = job

    return out


def extract_about_you(text: str) -> dict[str, str]:
    raw = _call_openai(text)
    parsed = json.loads(_strip_fences(raw))
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI returned a non-object")
    return normalize_fields(parsed)
