"""Pattern-recognition parse for About You sentences.

Mirrors GP/frontend/src/lib/parse.ts so pytest can check the same rules as the live chips.
Keep this file in lock-step with the TypeScript parser.
"""

from __future__ import annotations

import re

OCCUPATIONS = [
    "Accountant",
    "Actuary",
    "Architect",
    "Auditor",
    "Business Analyst",
    "Business Owner",
    "Chief Executive Officer",
    "Chief Financial Officer",
    "Chief Technology Officer",
    "Civil Engineer",
    "Consultant",
    "Data Scientist",
    "Dentist",
    "Doctor / General Practitioner",
    "Engineer",
    "Entrepreneur",
    "Financial Adviser",
    "Financial Analyst",
    "General Manager",
    "Homemaker",
    "Investment Banker",
    "Lawyer",
    "Lecturer",
    "Manager",
    "Medical Specialist",
    "Nurse",
    "Operations Manager",
    "Pharmacist",
    "Pilot",
    "Product Manager",
    "Project Manager",
    "Retired",
    "Risk Manager",
    "Sales Manager",
    "Software Developer",
    "Software Engineer",
    "Student",
    "Surgeon",
    "Teacher",
    "Web Developer",
]

NUMW = {
    "zero": 0,
    "no": 0,
    "none": 0,
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

NOTOCC = re.compile(
    r"^(married|single|unmarried|divorced|widowed|separated|male|female|man|woman|lady|guy|"
    r"citizen|singaporean|singapore citizen|sg citizen|local|permanent resident|pr|foreigner|"
    r"foreign|expat|expatriate|employment pass|work permit|s pass|kids?|children|child|"
    r"dependants?|no dependants|years? old|year old|none|no kids|nothing|myself|"
    r"oh|zero|mail|kits|worse|maths|solution|actually)$"
)

_CATALOG_JOBS = [
    "software engineer",
    "data scientist",
    "product manager",
    "business owner",
    "civil servant",
    "sales manager",
    "project manager",
    "operations manager",
    "financial adviser",
    "it consultant",
]

_SHORT_JOBS = [
    "engineer",
    "teacher",
    "nurse",
    "doctor",
    "lawyer",
    "accountant",
    "manager",
    "designer",
    "developer",
    "consultant",
    "analyst",
    "architect",
    "dentist",
    "pharmacist",
    "pilot",
    "chef",
    "driver",
    "banker",
    "entrepreneur",
    "freelancer",
    "student",
    "homemaker",
    "retired",
]


def _job_ok(o: str) -> bool:
    low = o.lower().strip()
    if len(low) < 3 or NOTOCC.match(low) or re.fullmatch(r"[\d.]+", low):
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


def _num(w: str) -> int | None:
    if w in NUMW:
        return NUMW[w]
    return int(w) if re.fullmatch(r"\d+", w) else None


def parse_sentence_regex(text: str) -> dict[str, str]:
    raw = str(text or "")
    s = " " + raw.lower().replace("\u2018", "'").replace("\u2019", "'")
    s = re.sub(r"\s+", " ", s) + " "
    out: dict[str, str] = {}

    m = re.search(r"\b(?:i'?m|i am|aged?|age of|age)\s*:?\s*(\d{2})\b", raw, re.I)
    if not m:
        m = re.search(r"\b(\d{2})\s*(?:-|\s)?\s*(?:years?[- ]old|yrs?[- ]old|y/?o)\b", raw, re.I)
    if not m:
        m = re.search(r"(?:^|[,;(\s])(\d{2})(?=[,;)\s]|$)", raw)
    if m and 18 <= int(m.group(1)) <= 70:
        out["age"] = str(int(m.group(1)))

    if re.search(r"\b(female|woman|lady|girl|mrs|ms|miss|mother|mum|mom)\b", s):
        out["gender"] = "Female"
    elif re.search(r"\b(male|man|guy|mr|father|dad)\b", s):
        out["gender"] = "Male"

    if re.search(r"\b(permanent resident|spr|sg pr|s'pore pr)\b", s) or re.search(r"\bpr\b", s):
        out["res"] = "Permanent Resident"
    elif re.search(
        r"\b(foreigner|foreign|expat|expatriate|employment pass|ep holder|s pass|"
        r"work permit|not a resident|on a visa)\b",
        s,
    ):
        out["res"] = "Foreigner"
    elif re.search(
        r"\b(singaporean|singapore citizen|sg citizen|citizen|local|"
        r"resident of singapore|singapore resident|living in singapore|"
        r"live in singapore|resident in singapore)\b",
        s,
    ):
        out["res"] = "Singapore Citizen"

    kids: int | None = None
    m = re.search(
        r"\b([a-z]+|\d+)\s+(?:young |small |little |grown )?(?:kids?|children|child|sons?|daughters?|boys?|girls?)\b",
        s,
    )
    if m and _num(m.group(1)) is not None:
        kids = _num(m.group(1))
    if kids is None and re.search(r"\b(no kids|no children|childless|without children)\b", s):
        kids = 0
    m = re.search(r"\b([a-z]+|\d+)\s+dependants?\b", s)
    if m and _num(m.group(1)) is not None:
        kids = _num(m.group(1))
    married = bool(re.search(r"\b(married|wife|husband|spouse|partner)\b", s))
    spouse_dep = married and bool(
        re.search(
            r"\b(housewife|homemaker|stay[- ]at[- ]home|not working|does not work|"
            r"doesn't work|unemployed|full[- ]time (?:mum|mom|dad))\b",
            s,
        )
    )
    if kids is not None or married:
        n = max(0, (kids or 0) + (1 if spouse_dep else 0))
        out["deps"] = "4+" if n >= 4 else str(n)
    elif re.search(r"\b(single|unmarried|nobody depends|no one depends|no dependants|on my own)\b", s):
        out["deps"] = "0"

    cands: list[str] = []
    for pat, prefix in (
        (r"\b(?:i work as|working as|employed as|i work in)\s+an?\s+([a-z][a-z \-/&']{2,44})", ""),
        (r"\b(?:self[- ]employed|freelance)\s+([a-z][a-z \-/&']{2,44})", "self-employed "),
        (r"\b(?:my job is|by profession|profession|occupation|job)\s*:?\s+([a-z][a-z \-/&']{2,44})", ""),
        (r"\b(?:i run|i own|i operate|running|i drive|i teach)\s+(?:an?\s+)?([a-z][a-z \-/&']{2,44})", ""),
        (
            r"\b(?:i am|i'm)\s+an?\s+(?:\d{1,2}[\s-]*(?:years?|yrs?)[\s-]*old\s+)?([a-z][a-z \-/&']{2,44})",
            "",
        ),
        (r",\s*([a-z][a-z \-/&']{2,44}?)\s*[.,!]?\s*$", ""),
    ):
        m2 = re.search(pat, s)
        if m2:
            cands.append(prefix + m2.group(1) if prefix else m2.group(1))

    for k in _CATALOG_JOBS:
        if k in s:
            cands.append(k)
    occ_hits = [o.lower() for o in OCCUPATIONS if len(o) > 4 and "/" not in o and o.lower() in s]
    occ_hits.sort(key=lambda o: (-s.rfind(o), -len(o)))
    cands.extend(occ_hits[:2])
    for k in _SHORT_JOBS:
        if " " + k in s:
            cands.append(k)

    def clean(c: str) -> str | None:
        o = str(c or "")
        o = re.sub(
            r"\s+(?:earning|earn|making|make|with|and|who|based|living|salary|income|"
            r"at|for|in|on|since|about)\b[\s\S]*$",
            "",
            o,
        )
        o = re.sub(r"^\s*(?:a|an|the|also|currently|now)\s+", "", o)
        o = re.sub(r"^\s*\d{1,2}[\s-]*(?:years?|yrs?)[\s-]*old\s+", "", o)
        o = re.sub(
            r"^(?:\s*(?:male|female|man|woman|married|single|young|singaporean|"
            r"singapore citizen|sg citizen|permanent resident|pr|foreigner|expat|"
            r"local|citizen)\b[, ]*)+",
            "",
            o,
        )
        o = re.sub(r"[.,;!]+$", "", o)
        o = re.sub(r"\s+(?:of|at|in|for|with|and|to|by|from|the|a|an)$", "", o)
        o = re.sub(r"\s+", " ", o).strip()
        if len(o) < 3 or NOTOCC.match(o) or not _job_ok(o):
            return None
        o = re.sub(r"\b[a-z]", lambda mm: mm.group(0).upper(), o)

        def acronym(w: str) -> str:
            needle = w.upper()
            if re.search(rf"(^|[^A-Za-z]){re.escape(needle)}([^A-Za-z]|$)", raw):
                return needle
            return w

        return re.sub(r"\b[A-Za-z]{2,4}\b", lambda mm: acronym(mm.group(0)), o)

    for cand in cands:
        c = clean(cand)
        if c:
            out["occ"] = c
            break

    m = re.search(
        r"\b(?:my name is|i am called|call me|this is|name's)\s+([A-Za-z][a-zA-Z'-]{1,20})",
        raw,
        re.I,
    )
    if m:
        n = m.group(1)
        out["name"] = n[0].upper() + n[1:]

    return out
