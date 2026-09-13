"""Normalize customer mobile numbers for report video jobs."""

from __future__ import annotations

import re

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")

# Longest-prefix match on E.164 calling codes → country name for the spokesperson.
_CALLING_COUNTRY: dict[str, str] = {
    "1242": "the Bahamas",
    "1246": "Barbados",
    "1264": "Anguilla",
    "1268": "Antigua and Barbuda",
    "1284": "the British Virgin Islands",
    "1340": "the U.S. Virgin Islands",
    "1345": "the Cayman Islands",
    "1441": "Bermuda",
    "1473": "Grenada",
    "1649": "the Turks and Caicos Islands",
    "1664": "Montserrat",
    "1670": "the Northern Mariana Islands",
    "1671": "Guam",
    "1684": "American Samoa",
    "1721": "Sint Maarten",
    "1758": "Saint Lucia",
    "1767": "Dominica",
    "1784": "Saint Vincent and the Grenadines",
    "1787": "Puerto Rico",
    "1809": "the Dominican Republic",
    "1829": "the Dominican Republic",
    "1849": "the Dominican Republic",
    "1868": "Trinidad and Tobago",
    "1869": "Saint Kitts and Nevis",
    "1876": "Jamaica",
    "1939": "Puerto Rico",
    "1681": "Wallis and Futuna",
    "855": "Cambodia",
    "856": "Laos",
    "852": "Hong Kong",
    "853": "Macau",
    "886": "Taiwan",
    "880": "Bangladesh",
    "673": "Brunei",
    "960": "the Maldives",
    "961": "Lebanon",
    "962": "Jordan",
    "963": "Syria",
    "964": "Iraq",
    "965": "Kuwait",
    "966": "Saudi Arabia",
    "967": "Yemen",
    "968": "Oman",
    "971": "the United Arab Emirates",
    "972": "Israel",
    "973": "Bahrain",
    "974": "Qatar",
    "975": "Bhutan",
    "976": "Mongolia",
    "977": "Nepal",
    "992": "Tajikistan",
    "993": "Turkmenistan",
    "994": "Azerbaijan",
    "995": "Georgia",
    "996": "Kyrgyzstan",
    "998": "Uzbekistan",
    "420": "the Czech Republic",
    "421": "Slovakia",
    "351": "Portugal",
    "352": "Luxembourg",
    "353": "Ireland",
    "354": "Iceland",
    "355": "Albania",
    "356": "Malta",
    "357": "Cyprus",
    "358": "Finland",
    "359": "Bulgaria",
    "370": "Lithuania",
    "371": "Latvia",
    "372": "Estonia",
    "373": "Moldova",
    "374": "Armenia",
    "375": "Belarus",
    "376": "Andorra",
    "377": "Monaco",
    "378": "San Marino",
    "380": "Ukraine",
    "381": "Serbia",
    "382": "Montenegro",
    "383": "Kosovo",
    "385": "Croatia",
    "386": "Slovenia",
    "387": "Bosnia and Herzegovina",
    "389": "North Macedonia",
    "212": "Morocco",
    "213": "Algeria",
    "216": "Tunisia",
    "218": "Libya",
    "220": "the Gambia",
    "221": "Senegal",
    "233": "Ghana",
    "234": "Nigeria",
    "254": "Kenya",
    "255": "Tanzania",
    "256": "Uganda",
    "27": "South Africa",
    "20": "Egypt",
    "30": "Greece",
    "31": "the Netherlands",
    "32": "Belgium",
    "33": "France",
    "34": "Spain",
    "36": "Hungary",
    "39": "Italy",
    "40": "Romania",
    "41": "Switzerland",
    "43": "Austria",
    "44": "the United Kingdom",
    "45": "Denmark",
    "46": "Sweden",
    "47": "Norway",
    "48": "Poland",
    "49": "Germany",
    "51": "Peru",
    "52": "Mexico",
    "53": "Cuba",
    "54": "Argentina",
    "55": "Brazil",
    "56": "Chile",
    "57": "Colombia",
    "58": "Venezuela",
    "60": "Malaysia",
    "61": "Australia",
    "62": "Indonesia",
    "63": "the Philippines",
    "64": "New Zealand",
    "65": "Singapore",
    "66": "Thailand",
    "81": "Japan",
    "82": "South Korea",
    "84": "Vietnam",
    "86": "China",
    "90": "Turkey",
    "91": "India",
    "92": "Pakistan",
    "93": "Afghanistan",
    "94": "Sri Lanka",
    "95": "Myanmar",
    "98": "Iran",
    "7": "Russia or Kazakhstan",
    "1": "the United States",
}

_CALLING_PREFIXES = tuple(sorted(_CALLING_COUNTRY, key=len, reverse=True))


def country_from_mobile(e164: str | None) -> str:
    """Country name from an E.164 number. Unknown codes fall back to Singapore."""
    digits = "".join(c for c in str(e164 or "") if c.isdigit())
    for prefix in _CALLING_PREFIXES:
        if digits.startswith(prefix):
            return _CALLING_COUNTRY[prefix]
    return "Singapore"


def split_e164(e164: str | None) -> tuple[str, str]:
    """Split an E.164 number into (`+countryCode`, national number)."""
    digits = "".join(c for c in str(e164 or "") if c.isdigit())
    if not digits:
        return "+65", ""
    for prefix in _CALLING_PREFIXES:
        if digits.startswith(prefix) and len(digits) > len(prefix):
            return f"+{prefix}", digits[len(prefix) :]
    if len(digits) == 8:
        return "+65", digits
    return f"+{digits[:2]}", digits[2:]


def normalize_mobile(raw: str | None) -> str:
    """Singapore 8-digit locals become +65; otherwise E.164."""
    s = str(raw or "").strip().replace(" ", "").replace("-", "")
    if not s:
        raise ValueError("Enter a mobile number")
    digits = "".join(c for c in s if c.isdigit())
    if len(digits) < 8:
        raise ValueError("Enter a mobile number")
    if s.startswith("+"):
        candidate = s
    elif len(digits) == 8:
        candidate = f"+65{digits}"
    elif digits.startswith("65") and len(digits) >= 10:
        candidate = f"+{digits}"
    else:
        candidate = f"+{digits}"
    if not _E164_RE.match(candidate):
        raise ValueError("Enter a valid mobile number")
    return candidate


def email_optional_ok(email: str) -> bool:
    em = (email or "").strip()
    if not em:
        return True
    return "@" in em and "." in em.split("@")[-1]
