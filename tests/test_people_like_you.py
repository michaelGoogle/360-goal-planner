from src.cpf import employee_cpf_monthly, employee_cpf_rate, take_home_income
from src.pipeline import people_like_you as plu


class _Messages:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if "temperature" in kwargs:
            raise TypeError("Messages.create() got an unexpected keyword argument 'temperature'")
        return "ok"


class _Client:
    def __init__(self) -> None:
        self.messages = _Messages()


def test_anthropic_messages_create_retries_without_temperature():
    client = _Client()
    got = plu._anthropic_messages_create(
        client,
        model="claude-sonnet-4-5",
        max_tokens=400,
        temperature=0.1,
        messages=[{"role": "user", "content": "hi"}],
    )
    assert got == "ok"
    assert len(client.messages.calls) == 2
    assert "temperature" not in client.messages.calls[-1]


def test_llm_settings_prefers_anthropic(monkeypatch):
    monkeypatch.setattr(plu, "_ensure_env", lambda: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test")
    monkeypatch.setenv("AN_MODEL", "claude-sonnet-4-5")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-test")
    provider, key, model = plu._llm_settings()
    assert provider == "anthropic"
    assert key == "ant-test"
    assert model == "claude-sonnet-4-5"


def test_predict_people_like_you_uses_llm_json(monkeypatch):
    monkeypatch.setattr(plu, "_ensure_env", lambda: None)
    raw = (
        '{"income":25000,"currency":"SGD","risk_ability":"aggressive",'
        '"price_sensitivity":"low","property":true,"car":true,'
        '"ward_type":"Single","hospitalization_type":"Private",'
        '"travelling":true,"sports":"Golf","retirement_lifestyle":"Luxurious",'
        '"is_smoker":false,"life_expectancy":82}'
    )
    captured: list[str] = []

    def _fake(prompt: str) -> str:
        captured.append(prompt)
        return raw

    monkeypatch.setattr(plu, "_complete_llm", _fake)
    got = plu.predict_people_like_you(
        dob="1984-09-05",
        occupation="CEO",
        country="Singapore",
        city="Singapore",
        dependents=2,
        gender="Male",
    )
    assert got["income"] == 25000
    assert got["currency"] == "SGD"
    assert got["property"] is True
    assert got["expenses"] > 0
    assert got["assets"] > 0
    assert got["liabilities"] == got["assets"] * 0.7
    assert captured
    assert "baker" in captured[0].lower()
    assert "Glassdoor" in captured[0]
    assert "Teacher / educator" in captured[0]


def test_income_anchors_place_unmatched_jobs():
    block = plu.format_income_anchor_block()
    assert "baker" in block.lower()
    assert "5,600" in block
    assert "Nurse" in block
    assert "Glassdoor" in block


def test_singapore_ceo_income_is_clamped(monkeypatch):
    monkeypatch.setattr(plu, "_ensure_env", lambda: None)
    raw = (
        '{"income":85000,"currency":"SGD","risk_ability":"aggressive",'
        '"price_sensitivity":"low","property":true,"car":true,'
        '"ward_type":"Single","hospitalization_type":"Private",'
        '"travelling":true,"sports":"Golf","retirement_lifestyle":"Luxurious",'
        '"is_smoker":false,"life_expectancy":82}'
    )
    monkeypatch.setattr(plu, "_complete_llm", lambda prompt: raw)
    got = plu.predict_people_like_you(
        dob="1984-09-05",
        occupation="CEO",
        country="Singapore",
        city="Singapore",
        dependents=2,
        gender="Male",
    )
    assert got["income"] == 42000


def test_baker_has_no_hard_clamp():
    assert plu.get_income_bounds("baker", "Singapore", "Singapore") is None
    assert plu.get_income_bounds("teacher", "Singapore", "Singapore") == {"min": 5600, "max": 9800}


def test_income_anchors_cover_every_country():
    plu.load_income_anchors.cache_clear()
    data = plu.load_income_anchors()
    country_ids = {row["id"] for row in data["countries"]}
    assert country_ids == {
        "australia",
        "germany",
        "hong kong",
        "malaysia",
        "philippines",
        "singapore",
        "thailand",
        "usa",
        "vietnam",
    }
    for occ in data["occupations"]:
        missing = country_ids - set(occ["bounds"])
        assert not missing, f"{occ['id']} missing {sorted(missing)}"


def test_income_anchors_include_local_country_bands():
    block = plu.format_income_anchor_block("Philippines")
    assert "PHP" in block
    assert "20,000" in block
    assert plu.get_income_bounds("nurse", "Germany", None) == {"min": 3200, "max": 4600}
    assert plu.get_income_bounds("software engineer", "USA", "San Francisco") == {
        "min": 10000,
        "max": 18000,
    }
    assert plu.get_income_bounds("CEO", "Vietnam", "Ho Chi Minh City") == {
        "min": 40000000,
        "max": 120000000,
    }


def test_take_home_nets_capped_employee_cpf():
    assert employee_cpf_monthly(6000, 42, "Singapore Citizen") == 1200
    assert employee_cpf_monthly(35000, 42, "Singapore Citizen") == 1600
    assert take_home_income(9500, 42, "Singapore Citizen") == 7900
    assert take_home_income(9500, 42, "Foreigner") == 9500
    assert employee_cpf_rate(58, "Permanent Resident") == 0.15


def test_expenses_are_share_of_take_home_by_dependents():
    kwargs = {"income": 9500, "age": 42, "marital_status": "married", "residency": "Singapore Citizen"}
    take_home = 7900
    assert plu.calculate_expenses_deterministically(**kwargs, dependents=0) == round(take_home * 0.675, 2)
    assert plu.calculate_expenses_deterministically(**kwargs, dependents=1) == round(take_home * 0.725, 2)
    assert plu.calculate_expenses_deterministically(**kwargs, dependents=2) == round(take_home * 0.775, 2)
    assert plu.calculate_expenses_deterministically(**kwargs, dependents=5) == round(take_home * 0.90, 2)


def test_foreigner_expenses_use_full_gross_as_take_home():
    got = plu.calculate_expenses_deterministically(
        9500, 42, "married", dependents=0, residency="Foreigner"
    )
    assert got == round(9500 * 0.675, 2)
