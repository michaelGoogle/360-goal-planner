# Implementation plan — code follows model V0-24

*Written 2026-09-27 from the calculation model `Calculations V0-24.xlsx` and the docs in
`docs/calculations/`. The implementation runs in Cursor, one work package at a time.
The model stays the source of truth: if a rule has to change, change the Excel and docs
first, then the code.*

---

## 0. How to use this plan

1. Open the workspace at `D:\SiriHeritage` (GP, FM, HU, SV and `shared/portfolio_management` side by side).
2. Read in this order: this file → `CHANGELOG.md` (V0-15 … V0-25) → `Dictionary.md` /
   `Need-dictionary.md` → `Currency.md` → the **Discrepancies** tab of the workbook (empty
   as of V0-25) → the component docs (`Need-calculator.md`, `Plan-calculator.md`, …).
3. Do the work packages (WP) in the order of §4. One branch and one PR per WP.
4. A WP is done when its unit tests pass **and** the parity tests for its component match
   the workbook fixtures (§6).
5. Anything the plan does not answer: stop and ask; do not invent a rule.

### Sources of truth

| Question | Where |
|----------|-------|
| What a formula is | Workbook tab of that component (`Calculations V0-24.xlsx`), then the component doc |
| What a parameter is called, its value, unit, currency | Workbook **Assumptions** tab (one list, V0-21) and `Dictionary.md` |
| What a need is and how it is named in every component | `Need-dictionary.md` |
| How currency, FX and PPP work | `Currency.md`, `fx_ppp/SOURCES.md`, FX tab |
| What changed and why | `CHANGELOG.md` and the workbook **Change log** tab |
| What the code still has to do | Workbook **Discrepancies** tab (empty as of V0-25). Parked ideas in `Calculations.md` |
| Parked ideas (not to implement) | `Calculations.md` → Open issues (PLU-01, FB-40, FB-49, FB-54, PREM-01, PROF-01, CPF-01) |

---

## 1. Decisions that shape the code

| # | Decision | Source |
|---|----------|--------|
| D1 | Each calculator is a **service inside GP** with its own package, HTTP route and client interface. Callers use the client, so a service can later move to its own deployable (like HU and SV) without changing callers. | This plan |
| D2 | **Plan and Budget move to the backend.** The frontend calls `/v1/plan` and `/v1/budget` and only renders. `planProducts.ts` loses its maths. | This plan |
| D3 | **Two levels of assumptions.** Customer level per session (assumption box and goal cards). Admin level for every other parameter (config API + admin screen, versioned, workbook values as defaults). | This plan |
| D4 | **HU, SV and FM repos are in scope**: HU and SV accept the values GP sends and use GP's codes; FM hosts the FX service. | This plan |
| D5 | **USD is the system currency.** Money comes in in the user currency, is converted to USD, every calculator and validation runs in USD, results go back to the user currency and are rounded there. | V0-15, `Currency.md` |
| D6 | **FX is a service in the Fund Management (FM) docker, with FM's database**, cloned from InsApi (`D:\AIBackend\360-AI-Prototype\InsApi`, `currency_service.py`, `currency_router.py`, `utils/currency_converter.py`): daily Open Exchange Rates fetch (USD base), history with `isLatest`, cache, conversion helpers. Added: PPP price level, unknown currency is an error (no fallback). **GP only calls it** (HTTP client, like HU and SV) and locks the rate on its session. | V0-15, V0-22, §2.4 |
| D7 | **PPP**: relative price level per *country* (base `PPP_BASE_COUNTRY` = Singapore) multiplies every USD fixed amount and turns Need Profiler money into PPP-USD. Country without usable PPP → factor 1. | V0-22 |
| D8 | **Social security is a plug-in service** (SG-CPF module; default module = no contribution, take-home = gross). It runs in the user currency. | V0-15 |
| D9 | **Premium comes from an external API**; for now a mock that returns the placeholder rate. | Discrepancies 13 |
| D10 | Names follow `Dictionary.md` (N_ needs, R_ risks, `PREFIX_WHAT` parameters). | V0-16 |

---

## 2. Target architecture

### 2.1 Services

All GP services live in `GP/src/services/<name>/` with the same layout. **Exception: FX runs in the
Fund Management (FM) docker with FM's database** (§2.4); GP has only its client package.

```
src/services/<name>/
  models.py      # pydantic request / response (the API contract)
  service.py     # pure logic, no I/O, no FastAPI; takes parameters explicitly
  client.py      # <Name>Client Protocol + InProcess<Name>Client + Http<Name>Client (+ Mock where noted)
  router.py      # FastAPI APIRouter: POST /v1/<route>
  __init__.py
```

A registry (`src/services/registry.py`) builds one client per service. Per service an env
variable picks the mode: `GP_SVC_<NAME>=inproc|http|mock` and `GP_SVC_<NAME>_URL` for http.
Default is `inproc` (mock for premium and live FX feed).

| Service | Route | Mode today | Owns | Replaces |
|---------|-------|------------|------|----------|
| **config** | `GET/PUT /v1/config/parameters`, `GET /v1/config/parameters/{version}`, `GET/PUT /v1/config/session-assumptions/schema` | inproc | Admin parameters (versioned), customer-level assumption schema and defaults | `session_rates.py`, constants in `goal_math.py`, `predict.py`, `planProducts.ts`, `hu_payload.py`, `assumptions.ts` |
| **fx** (external, **in FM**) | FM routes: `POST /v1/fx/currencyref`, `GET /v1/fx/currencyrates`, `GET /v1/fx/currencyupdate` (InsApi-compatible), `GET /v1/fx/rate/{ccy}`, `GET /v1/fx/price-level/{country}`, `GET /v1/fx/countries`. GP: `FxClient.lock()` | **http** to FM (`GP_FM_URL`, the existing FM upstream); `snapshot` / `mock` client in GP for parity and unit tests | FM: daily rates with history in FM's DB, PPP table, relative price level. GP: session FX lock, `money.py` / `nice_step` | `src/fx.py` |
| **social-security** | `POST /v1/social-security/contribution` | inproc | Module per country: SG-CPF, default | `src/cpf.py` |
| **people-like-you** | `POST /v1/people-like-you` | inproc (LLM inside) | Income (LLM + clamp), spend, liquid assets, split, home seed, life cover | `people_like_you.py`, `predict._apply_plu` |
| **need-profiler** | `POST /v1/need-profiler` | inproc | Scores, picks, priority, parked coverage needs | `need_profiler.py` |
| **need-calculator** | `POST /v1/need-calculator` | inproc | amount / have / gap per need, R_LON stressed values | `need_calculator.py`, `goal_math.py` |
| **premium** | `POST /v1/premium/quote` | **mock** | Annual premium per protection need | `coverPremiumFor` in `planProducts.ts` |
| **plan** | `POST /v1/plan` | inproc | Suggested plans, sums, premiums (via premium client), contributions, totals | `planProducts.ts`, `local.ts seedProducts` |
| **budget** | `POST /v1/budget` | inproc | Free budget vs plan (monthly and lump) | `planAfford` in `planProducts.ts` |
| **hu** (external) | `POST /v1/score` → HU | http | Payload mapping only | `hu_payload.py` |
| **sv** (external) | `POST /v1/project` → SV | http | Payload mapping only | `sv_payload.py` |

### 2.2 Orchestration (what the frontend calls)

The existing endpoints stay so the frontend keeps working; they become thin orchestrators.

```
POST /v1/predict   = fx.lock → social-security → people-like-you → need-profiler → need-calculator
POST /v1/needs     = need-calculator (session already has fx lock)
POST /v1/plan      = plan (→ premium)                              NEW for the frontend
POST /v1/budget    = budget                                        NEW for the frontend
POST /v1/score     = hu payload → HU
POST /v1/project   = sv payload → SV
```

Orchestrators live in `src/orchestration/` (one function per endpoint) and only call clients.

### 2.3 Currency pipeline (D5–D7)

One helper module `src/money.py`, used by the orchestrators, never by the calculators:

```python
to_usd(amount_local, fx)            = amount_local × fx.usdPerLocal
to_user(amount_usd, fx)             = amount_usd ÷ fx.usdPerLocal
round_user(x)                       = round to whole units (half to even, as today)
nice_step(step_usd, fx)             = step_usd ÷ usdPerLocal → nearest 1 / 2 / 5 × 10^k
ppp_usd(amount_local, fx)           = amount_local × usdPerLocal ÷ fx.priceLevel
fixed(amount_usd_param, fx)         = amount_usd_param × fx.priceLevel      (option B on)
```

- `fx` is the **FxLock** stored on the session: `{currency, country, usdPerLocal, priceLevel,
  priceLevelCountry, priceLevelBase, asOf, source}`. Created by `fx.lock` at the start of
  predict; reused by every later call; refreshed only on explicit request.
- Calculators (need-profiler, need-calculator, plan, budget) receive **USD** money and the
  `priceLevel`, and return USD. The orchestrator converts results back with `to_user` and
  rounds in the user currency. Rounding steps come from `nice_step`.
- People Like You and social security run in the **user currency** (country plug-ins); the
  orchestrator converts their outputs to USD before the calculators.
- Parity rule: for a Singapore persona, results must equal the workbook in SGD (the USD fixed
  amounts are calibrated at the snapshot SGD rate, V0-24).

### 2.4 FX service — in the Fund Management (FM) docker, cloned from InsApi

The FX service runs in **FM** (`D:\SiriHeritage\FM`, FastAPI, docker) and stores its data in
**FM's database** (SQLAlchemy models in `shared/portfolio_management`, `FM_DATABASE_URL`:
Postgres in docker, SQLite locally, schema created by `portfolio_management.session.init_db`).
GP does not store rates; it calls FM like it calls HU and SV and keeps the locked rate on the
session. InsApi (`D:\AIBackend\360-AI-Prototype\InsApi`) already runs a working FX service;
FM clones it, so all products use the same source, conventions and refresh cycle.

**What InsApi has (clone into FM as is)**

| Piece | InsApi file | Behaviour |
|-------|-------------|-----------|
| Fetch | `app/services/currency_service.py` `fetch_currency_data` | Open Exchange Rates `latest.json`, base USD |
| Store with history | `store_currency_data`, models `Currency` (`currencyIso`, `refRate`, `createdAt`, `isLatest`) and `CurrencyRef` (`currencyIso`, `currencySymbol`, `currencyName`, `currencyRanking`, `currencyRegion`) | Old rows flagged `isLatest = False`, new rows inserted; USD always 1.0 |
| Change report | `compare_with_previous`, `sendEmail` | Logs moves > 2 %; e-mail optional (`SEND_CURRENCY_EMAIL`) |
| Clean-up | `cleanup_old_data(days=30)` | Deletes non-latest rows older than 30 days |
| Cache | `populate_currency_cache` | `currency_rates = {"FX_USD<ISO>": refRate}` (units of ISO per 1 USD) |
| Conversion | `app/utils/currency_converter.py` `get_conversionRate`, `convert_currency` | Cross rates through USD |
| Routes | `app/routes/currency_router.py` | `POST /currencyref`, `GET /currencyrates`, `GET /currencyupdate` |
| Schedule | `app/services/scheduler_service.py` | Daily at `CURRENCY_SCHEDULE_TIME` (07:00 UTC), `ENABLE_CURRENCY_SCHEDULER` |

**What changes when cloning into FM**

| # | Change | Why |
|---|--------|-----|
| F1 | **API key out of the code.** InsApi has the Open Exchange Rates `app_id` hard-coded in `fetch_currency_data`; FM reads `FM_OXR_APP_ID` from its `.env` / docker secrets. Rotate the key in InsApi as well. | Security |
| F2 | **Unknown currency → error.** InsApi's `get_conversionRate` returns 1.0 when a rate is missing; FM returns HTTP 404 `unknown_currency`, and GP's client raises `UnknownCurrency`. | D6, V0-15 |
| F3 | **Storage in FM's database.** Add `Currency`, `CurrencyRef` (same columns as InsApi) and `CountryPpp` (country, ISO2, ISO3, currency, PPP year, PPP, 2024 average rate, price level, flag) to the `shared/portfolio_management` models; created by `init_db` (and a migration if FM uses one). Seed `CurrencyRef` from InsApi's table and `CountryPpp` from `fx_ppp/countries_ppp.csv`. | One database, FM owns reference data |
| F4 | **Convention.** Keep InsApi's stored `refRate` = units per 1 USD. FM also returns `usdPerLocal = 1 / refRate`. | One stored convention for all products |
| F5 | **Session lock in GP.** GP calls `GET /v1/fx/rate/{ccy}` and `GET /v1/fx/price-level/{country}` once at the start of predict and stores the FxLock (§2.3) on the session with `asOf` (`createdAt`); it keeps it until an explicit refresh. | D6 |
| F6 | **PPP in FM.** Not in InsApi. `CountryPpp` table, relative price level vs a base country (GP sends `PPP_BASE_COUNTRY` from its admin parameters, default Singapore). Yearly refresh by re-seeding the table. | D7, V0-22 |
| F7 | **Offline and tests.** FM seeds `Currency` from `currencies_fx.csv` when the table is empty and the fetch fails. GP has `SnapshotFxClient` (reads the same CSVs, for parity tests) and `MockFxClient` (unit tests). | Robust start, deterministic tests |
| F8 | **No Flask.** InsApi's routes use `get_flask_app()` / `request_db_session()`; FM uses its FastAPI app and SQLAlchemy session from `portfolio_management`. New files: `FM/src/routers/fx.py`, `FM/src/services/fx_service.py`, `FM/src/services/fx_convert.py`. | FM is FastAPI |
| F9 | **Scheduler in FM.** Daily job at `CURRENCY_SCHEDULE_TIME` (APScheduler in the FM process, same env names as InsApi) or the docker host's cron calling `GET /v1/fx/currencyupdate`. | Daily refresh |
| F10 | **Docker.** Add the env variables (`FM_OXR_APP_ID`, `ENABLE_CURRENCY_SCHEDULER`, `CURRENCY_SCHEDULE_TIME`, `SEND_CURRENCY_EMAIL`) to FM's docker configuration; GP's docker gets `GP_FM_URL` (already used for People Like You). | Deployment |

Parity note: the workbook uses the snapshot rate of 2026-09-25 (SGD 0.78162734). Parity tests
in GP run with `GP_SVC_FX=snapshot`; production calls FM with live rates.

### 2.5 Assumptions, two levels (D3)

| Level | What | Stored | Edited by |
|-------|------|--------|-----------|
| **Admin parameters** | Every Assumptions row that is not customer level: costs (`CRI_COST`, `TPD_COST`, `PAC_COST`, `LTC_COST`, `EDU_COST`, stress sizes `R_xxx_SIZE`), years (`CRI_YEARS`, …), shares, bands, steps, HappiU envelope, `LON_AGE`, `PPP_BASE_COUNTRY`, `priceLevelOn`, target ages defaults, risk bands, profiler weights | `config/parameters/v<N>.json`, versioned; one active version; audit log (who, when, diff) | Admin screen (new) via `PUT /v1/config/parameters` |
| **Customer assumptions** | Assumption box: `inflationRate`, `interestRate`, `loanRate`, `incomeGrowthRate`, `investmentReturn`, `assetReturn`, `ageOfRetirement`, `lifeExpectancy`, `riskTolerance`. Goal cards: lifestyle, retAge, `targetYear` per goal (N_EDU, N_SAV, N_PRP), bequest, dependYears, incomeReplace, stored amounts, tags, LTC start age. Stress chips on / off. | On the session (`session.assumptions`, `needs[].inputs`, `stress[]`) | Customer in the app |

- Resolution order: session value → admin parameter (active version) → built-in default.
- Every session stores `parametersVersion` (the admin version used). Recalculating an old
  session uses its version unless the adviser chooses "update to current".
- The first admin version (`v24.json`) is **exported from the workbook** Assumptions tab (see
  WP0), so code and model start identical.
- Customer-level defaults (e.g. `targetYear` N_EDU = year the customer turns
  `EDU_TARGET_AGE`) are computed by the config service (`GET /v1/config/session-defaults`
  with age), so the frontend never re-implements them.

---

## 3. API contracts (first version)

Money fields carry the currency explicitly. All services validate with pydantic and return
`422` with a field list on bad input. Errors from dependencies return `424` with the
dependency name.

### 3.1 fx

```jsonc
// POST /v1/fx/lock
{ "currency": "VND", "country": "Vietnam" }
// 200
{ "currency": "VND", "country": "Vietnam", "usdPerLocal": 0.0000384904, "priceLevel": 0.4602,
  "priceLevelCountry": 0.2769, "priceLevelBase": 0.6017, "baseCountry": "Singapore",
  "pppAvailable": true, "asOf": "2026-09-25", "source": "snapshot:currency-api+worldbank-ppp" }
// 404 { "error": "unknown_currency", "currency": "XYZ" }   — never falls back to SGD
```

The lock above is what **GP's `FxClient.lock()`** returns; it is assembled from two FM calls:

```jsonc
// FM  GET /v1/fx/rate/VND
{ "currencyIso": "VND", "refRate": 25980.50, "usdPerLocal": 0.0000384904, "asOf": "2026-09-25T07:00:00Z" }
// FM  GET /v1/fx/price-level/Vietnam?base=Singapore
{ "country": "Vietnam", "currency": "VND", "priceLevel": 0.2769, "basePriceLevel": 0.6017,
  "relative": 0.4602, "pppYear": 2024, "available": true }
```

GP clients: `HttpFxClient` (FM, production), `SnapshotFxClient` (reads
`fx_ppp/*.csv`; parity tests), `MockFxClient` (unit tests). FM's InsApi-compatible routes
(`/v1/fx/currencyref`, `/v1/fx/currencyrates`, `/v1/fx/currencyupdate`) keep InsApi's
request and response shapes.

### 3.2 social-security

```jsonc
// POST /v1/social-security/contribution
{ "country": "Singapore", "residency": "Citizen", "age": 34, "grossMonthly": 7140, "currency": "SGD" }
// 200
{ "module": "SG-CPF", "employeeContribution": 1428, "takeHome": 5712, "rate": 0.20, "currency": "SGD" }
// other countries: { "module": "default", "employeeContribution": 0, "takeHome": <gross> }
```

### 3.3 people-like-you

Request: about-you fields + `fx` lock + parameters version. Response in **user currency**:
`incomeMonthly`, `expenseMonthly` (floored at `MIN_EXPENSE_MONTHLY` USD 100 converted),
`cash`, `investments`, `property`, `mortgage`, `liabilities`, `policies[]`,
`lifeExpectancy` (capped at `LON_AGE`), `isSmoker`, LLM flags (risk ability, lifestyle, ward,
sports, …). Home seed on USD bands (`propertyIncomeLow/High`, `propertyLow/Mid/High`,
× priceLevel). Life cover rounds to `nice_step(lifeRoundUnit)`.

### 3.4 need-profiler

Request: person + money in **USD** + `priceLevel` + LLM flags. Response:

```jsonc
{ "scores": { "Life Protection": 6.1, "Critical Illness": 7.4, "TPD": 5.0, ... },   // 11 labels, Farewell gone
  "picks": { "prot1": "N_INC", "prot2": "N_CRI", "grow2": "N_SAV" },
  "needs": [ { "type": "N_INC", "enabled": true, "priority": 3 }, ...                // 11 calculator needs
             { "type": "N_HOM", "parked": true, "priority": 5, "score": 7.6 }, ... ] } // N_HOM, N_CAR, N_TRV
```

### 3.5 need-calculator

Request: session money in **USD**, goal inputs (user currency converted by the orchestrator),
parameters, `priceLevel`, enabled flags. Response per need in USD:
`needAmount`, `have`, `gap`, plus `stress.R_LON` block (`N_RET` and `N_LTC` at `LON_AGE`),
horizons (`yearsToRet`, `yearsInRet`, `eduYears`, `savYears`, `prpYears`, `careYears`).
The orchestrator converts and rounds to user currency.

### 3.6 premium (mock)

```jsonc
// POST /v1/premium/quote
{ "needType": "N_CRI", "sumAssured": 681033, "currency": "SGD", "age": 46, "gender": "Male",
  "smoker": false, "country": "Singapore", "termYears": null }
// 200 (mock)
{ "annualPremium": 530, "currency": "SGD", "source": "mock:placeholder-rate",
  "rate": 0.00078, "indicative": true }
```

The mock reproduces the workbook exactly: `round(sum × protectionPremiumRate / step) × step`
with `step = nice_step(coverPremRoundStep)`. It reads an optional per-need rate table from
admin parameters (all rows = 0.078% today) so a better placeholder can be set without code.
The real API adapter implements the same interface.

### 3.7 plan

Request: needs (amount / have / gap, enabled), horizons, take-home, expense, `plansOff`,
customer edits (`planSum`, `planMth`, `planLump` touched flags), parameters. Response per need:
`suggested`, `included`, `planSum`, `planPrem` (from premium client), `planMth`, `planLump`,
`capMth`, `fv`, `remain`; totals `investMth`, `investLump`, `protPremYear`.
Rules: workbook **Plan Calculator** tab and `Plan-calculator.md` — suggested = enabled AND
gap > 0; protection sum = gap; wealth horizon per goal; cap = PMT to hit gap, rounded **up**;
default share = (free budget − protection premiums ÷ 12) ÷ n wealth, rounded **down**;
lump 0.

### 3.8 budget

Request: take-home, expense, investments, included premiums, `investMth`, `investLump`.
Response: `available`, `free`, `monthly`, `monthlyOver`, `lumps`, `lumpOver`.

---

## 4. Work packages

Order and dependencies:

```
WP0 ─► WP1 ─► WP2 ─► WP3 ─► WP4 ─► WP5 ─┐
                             └► WP6 ──────┼─► WP7 ─► WP8 ─► WP9 ─► WP10 ─► WP11 ─► WP12 ─► WP13 ─► WP14 ─► WP15
```

### WP0 — Baseline and parity fixtures

**Status: fixtures done 2026-09-27.** `GP/tests/fixtures/model_v0_24/` holds `parameters.json`
(81 Assumptions cells), 50 persona files and 3 scenario files, all without formula errors;
see its `README.md`. `tests/parity/test_fixtures_load.py` passes (55 tests). Still to do in
Cursor: commit the baseline and create the branch.

- Commit the current state on `main`; branch `feat/model-v0-24`.
- Export from the V0-24 workbook (LibreOffice recalculation, script in
  `docs/calculations/export_fixtures.py`):
  - `tests/fixtures/model_v0_24/parameters.json` — every Assumptions named cell (becomes
    admin `v24.json` in WP2).
  - `tests/fixtures/model_v0_24/personas/P01.json … P50.json` — inputs and expected outputs
    per persona: People Like You effective session, social security, FX lock, profiler scores
    and picks, need amount / have / gap for 10 needs, R_LON block, plan per need and totals,
    budget, HappiU payload fields GP sends, SV payload fields GP sends.
  - Scenario fixtures: P03 as VND / Vietnam (PPP), P03 with N_PAC and N_LTC switched on,
    P03 with all personal stress events on (SV payload only), P06 plan / budget.
- **Done:** fixtures committed; `pytest tests/parity -k fixtures_load` passes.

### WP1 — Service skeleton, registry, error model

- Create `src/services/` layout (§2.1) with empty services, clients (inproc / http / mock),
  routers mounted under `/v1/…`, `registry.py`, env switches, common error model (`422`,
  `424`, `404 unknown_currency`).
- Create `src/orchestration/` and move the bodies of `predict`, `needs`, `score`, `project`
  from `app.py` into orchestrators that still call today's functions (no behaviour change).
- **Done:** all existing tests green; every new route answers `501 not_implemented`;
  `GP_SVC_*` switches covered by a test.

### WP2 — Config service and assumption levels

- `config/parameters/v24.json` from the WP0 export; schema in `src/services/config/models.py`
  with name, value, unit, currency, level (`admin` / `customer`), min / max.
- Endpoints: read active, read version, write new version (validation, audit), session
  defaults (`/v1/config/session-defaults?age=&country=`).
- Replace constants: `session_rates.py` DEFAULTS, `goal_math.py` constants, `predict.py`
  seeds, `hu_payload.py` envelope, `assumptions.ts` defaults → all read from config.
- Session gets `parametersVersion`.
- Frontend: assumption box reads the customer-level schema; new admin screen (list,
  edit, save as new version; admin-only route).
- **Done:** parity test "parameters equal workbook" passes; changing a rate in the
  assumption box changes `/v1/needs` output; admin edit creates `v25` without touching `v24`.

### WP3 — FX service in FM (clone from InsApi), PPP, GP client and money helpers

**WP3a — FM repo (and `shared/portfolio_management`)**

- Clone InsApi's FX pieces (§2.4 table) into FM: `src/services/fx_service.py`
  (`fetch_currency_data`, `store_currency_data`, `compare_with_previous`, `cleanup_old_data`,
  `populate_currency_cache`, optional `sendEmail`), `src/services/fx_convert.py`
  (`get_conversionRate`, `convert_currency`), `src/routers/fx.py` (InsApi routes under
  `/v1/fx/` plus `rate/{ccy}`, `price-level/{country}`, `countries`). Apply F1–F10.
- Models `Currency`, `CurrencyRef`, `CountryPpp` in `shared/portfolio_management`; seed
  scripts `FM/scripts/seed_currency_ref.py` (from InsApi export) and
  `FM/scripts/seed_country_ppp.py` (from `fx_ppp/countries_ppp.csv`).
- Scheduler and docker env (F9, F10).
- Tests in FM: InsApi's currency tests ported (if present in `InsApi/tests`); unknown
  currency → 404; `usdPerLocal = 1 / refRate`; empty table + failed fetch → snapshot seed;
  price level and relative price level equal the FX tab.

**WP3b — GP repo**

- `src/services/fx/` becomes a client package only: `FxClient` Protocol, `HttpFxClient`
  (FM), `SnapshotFxClient`, `MockFxClient`, `lock()` building the FxLock (§2.3).
- `src/money.py` (§2.3) including `nice_step`.
- Remove `src/fx.py` (hard-coded 9 rates and the SGD fallback) once callers use the client.
- Tests: `nice_step` gives SGD 1,000 / 50 / 10 / 100,000 / 50,000 and VND 20,000,000 /
  1,000,000 / 200,000 / 2,000,000,000 / 1,000,000,000; unknown currency from FM surfaces as
  `424 fx_unknown_currency`.
- **Done:** FM serves rates and price levels; GP's lock for every persona (snapshot mode)
  equals the fixture FX block; a GP session against a running FM docker locks live rates.

### WP4 — Social-security service

- Interface `SocialSecurityModule.contribution(req) -> resp`; modules `SgCpfModule`
  (logic from `src/cpf.py`, ceiling and age bands from admin parameters) and
  `DefaultModule`. Module chosen by country (table in admin parameters).
- **Done:** parity with the CPF tab for all 50 personas; a non-Singapore country returns the
  default module.

### WP5 — People Like You in the new pipeline

- Service wraps the LLM call and `_apply_plu`, now with: `MIN_EXPENSE_MONTHLY` floor
  (USD 100 in user currency), home seed on USD bands × priceLevel converted back, life-cover
  rounding with `nice_step(lifeRoundUnit)`, `lifeExpectancy` capped at `LON_AGE` (99),
  default `lifeExpectancyDefault` (85).
- Money-page edits (`moneyTouched`) still win over seeds.
- Not in scope: PLU-01 emergency fund (parked).
- **Done:** effective session equals the People Like You tab for all 50 personas (LLM income
  taken from the fixture, not re-generated).

### WP6 — Names and need set

- Rename parameters to the Dictionary names everywhere (Python, TS, JSON): `CI_COST` →
  `CRI_COST`, `HOSP_MONTHS` → `HOS_MONTHS`, `EDU_TOTAL_COST` → `EDU_COST`,
  `LIFE_SUPPORT_*` → `INC_SUPPORT_*`, lifestyle rates → `RET_LIFESTYLE_*`,
  `sav/prpIncomeMultiple` → `SAV/PRP_INCOME_MULT`, `criMedicalPlaceholder` merged into
  `CRI_COST`, `funeralLump` removed.
- Need types: calculator needs `N_INC N_CRI N_TPD N_HOS N_PAC N_LTC N_RET N_EDU N_SAV N_PRP`;
  parked coverage `N_HOM N_CAR N_TRV` (no calculator); `N_ADB` listed as candidate only (not
  implemented). Update `types.ts NeedType`, `NEED_TYPES`, labels from `Need-dictionary.md`
  (TPD everywhere; "Home purchase" for N_PRP).
- Stress-event ids → R_ codes (`R_DEA`, `R_CRI`, `R_TPD`, `R_PAC`, `R_HOS`, `R_LTC`,
  `R_WED`, `R_BAB`, `R_LON`, `R_MKT`, `R_CCY`, `R_INF`, `R_ICT`, `R_EXP`); accept old ids on
  input for one release.
- **Done:** no old name left (`rg` check in CI); existing sessions with old ids load.

### WP7 — Need Profiler service

- Farewell removed from scoring (11 labels; min–max scaling over 11).
- Money factors in **PPP-USD** (`ppp_usd`); USD bands unchanged.
- Vocabulary map (V0-24): Basic / Comfortable / Luxurious → frugal / stress-free / only the
  best; Single → A, Double / Ward → B; adventurous or high-risk sports → 4, none → 0, other
  sports → 1.
- Picks: protection from N_INC, N_CRI, N_TPD, N_HOS, N_PAC (tie-break order in that
  sequence); N_RET always; growth N_EDU vs N_SAV (EDU first on a tie); **no** SAV ↔ PRP swap;
  N_PRP and N_LTC never auto-picked; parked N_HOM / N_CAR / N_TRV returned with score and
  priority only.
- Priority 5 if scaled score > 7, else 3.
- Fallback when the profiler fails stays as today (documented in `Need-profiler.md`).
- **Done:** scores, picks and priorities equal the Need Profiler tab for all 50 personas
  (e.g. P12 picks N_CRI, not N_INC).

### WP8 — Need Calculator service

- Pure USD calculator; formulas from the Need Calculator tab and `Need-calculator.md`:
  N_INC, N_CRI, N_TPD, N_HOS, **N_PAC** (annuity-due of income for `PAC_YEARS` +
  `PAC_COST`), **N_LTC** (annuity-due of `LTC_COST` over `lifeExpectancy − ltcStartAge`,
  start age default `LTC_START_AGE` 80, customer input), N_RET, N_EDU, N_SAV, N_PRP.
- Fixed amounts × `priceLevel`.
- Target years per goal: defaults from the customer's age (`EDU_TARGET_AGE` 50,
  `SAV_TARGET_AGE` 40, `PRP_TARGET_AGE` 33); savings never shorter than 5 years,
  property never shorter than 3; education next year if already older. Each goal its own
  horizon for amount and have.
- Investment pot walk RET → EDU → SAV → PRP unchanged.
- R_LON block: N_RET and N_LTC at `LON_AGE` (display only).
- **Done:** amount / have / gap for all 10 needs equal the Need Calculator tab for all 50
  personas; VND scenario equals its fixture (PPP).

### WP9 — Premium service (mock)

- Interface + `MockPremiumClient` (§3.6) + `HttpPremiumClient` skeleton for the future API.
- Per-need rate table in admin parameters (`PREMIUM_RATE_<TYPE>`, all 0.078% today).
- **Done:** mock premiums equal the Plan Calculator tab; switching `GP_SVC_PREMIUM=http`
  with a stub server works in a test.

### WP10 — Plan service (moved from the frontend)

- Port `planProducts.ts` / `seedProducts` to `src/services/plan/service.py` with the V0-24
  rules (§3.7): per-goal horizons (`NC_eduYears`, `NC_savYears`, `NC_prpYears`), share
  rounded **down**, premiums from the premium client, N_PAC and N_LTC as protection.
- Keep customer edits: touched `planSum` / `planMth` / `planLump` are not re-seeded;
  `plansOff` respected.
- **Done:** plan per need and totals equal the Plan Calculator tab for all 50 personas;
  P06 default plan 1,620 / month within a free budget of 1,693.

### WP11 — Budget service

- Port `planAfford` (§3.8); free = 50% of monthly surplus; premiums of included protection
  only.
- **Done:** equals the Budget Calculator tab for all 50 personas; default plan never shows
  `monthlyOver > 0`.

### WP12 — HappiU payload and HU repo

- GP `hu_payload.py`: send `CRI_COST` and `TPD_COST` (USD × priceLevel → user currency) as
  critical-illness and TPD medical cost; send `lifeExpectancyDefault` and cap `LON_AGE`;
  send N_PAC; per-goal withdrawal years (EDU, SAV, PRP); drop funeral lump; `annualBudget`,
  `placeholderNeedBudget`, `benefitRound` from admin parameters in user currency.
- HU repo: accept `N_HOS` (keep `N_HSP` as alias for one release), rename PTD → TPD in
  product, rate file and code (keep old file name as alias), use the sent costs and life
  expectancy instead of internal defaults (200,000 / 444,000 / 83).
- **Done:** payload for all 50 personas equals the fixture; HU contract test with the new
  fields; HappiU scores within ±1 of the HappiU tab (deterministic twin).

### WP13 — Scenario Visualizer payload, stress events and SV repo

- GP `sv_payload.py`: path end `LON_AGE` (99); chart horizon = session life expectancy (99
  under R_LON); per-goal withdrawals and goal pots with their own pay years; personal stress
  events from admin parameters (`R_xxx_SIZE` USD × priceLevel → user currency,
  `R_xxx_WHEN` as age, wedding / newborn as years from today; older than the age → next
  year); death stops salary and CPF wage; LTC every year from start age to the year before
  life expectancy; R_LON horizon toggle.
- Frontend `stressEvents.ts`: R_ codes, sizes and timing from `/v1/config/parameters`
  (no hard-coded S$).
- SV repo: accept `numYears` / life expectancy from GP instead of `conf.ini` 100; accept
  age-based events if SV needs them as years (GP converts; document which).
- **Done:** SV payload for all 50 personas and the all-events scenario equals the fixtures;
  Scenario Visualizer tab paths within tolerance (deterministic twin).

### WP14 — Frontend

- `api.ts`: new calls `/v1/plan`, `/v1/budget`, `/v1/config/*`, `/v1/fx/*`.
- `planProducts.ts`: remove maths; keep formatting only. `local.ts seedProducts` calls the
  plan service.
- Goal cards: target year per goal (N_EDU, N_SAV, N_PRP) with age-based defaults from the
  config service; LTC start age; new cards N_PAC and N_LTC; labels from the Dictionary
  (TPD, Home purchase).
- Parked coverage needs (N_HOM, N_CAR, N_TRV): show as "coverage to consider" with priority,
  no calculator.
- Amounts shown in the user currency with the locked rate; show `asOf` of the rate.
- Admin screen (WP2) and assumption box driven by the config schema.
- Stress chips: R_ codes, ages, USD sizes shown in user currency.
- **Done:** frontend tests green; a Singapore and a Vietnamese session run end to end.

### WP15 — Docs, twins and clean-up

- Update `GP/docs/Architecture.md`, `API.md`, `HU-and-SV-payloads.md` for the services and
  endpoints; the clone is now `docs/calculations/` (V0-13 archived).
- `deterministic_engines.py` twins and `excel_check.py`: now compare the workbook with the
  **code** (they should agree again, including owners after the N_PRP change).
- Workbook **Discrepancies** tab: each backlog row closed with the PR link, in a new model
  version (V0-25) whose change log records "code follows V0-24".
- **Done:** Discrepancies tab empty; leftover pipeline no longer swaps N_SAV for N_PRP;
  twins call the live Need Profiler and Plan Calculator; frontend spend floor is USD 100
  via FxLock; `Calculations V0-25.xlsx` rebuilt. HappiU and SV wealth/spendable agree with
  the twins; `savPost` can still differ as a savings-vs-plan-pot split. Parked (Open issues):
  real premium API, existing-cover wiring, HU/SV CPF engines.

---

## 5. Customer-level vs admin parameters (initial split)

| Customer level (session) | Admin level (config) |
|--------------------------|----------------------|
| `inflationRate`, `interestRate`, `loanRate`, `incomeGrowthRate`, `investmentReturn`, `assetReturn` | `CRI_COST`, `CRI_YEARS`, `TPD_COST`, `TPD_YEARS`, `HOS_MONTHS`, `PAC_COST`, `PAC_YEARS`, `LTC_COST`, `EDU_COST`, `SAV_INCOME_MULT`, `PRP_INCOME_MULT` |
| `ageOfRetirement`, `lifeExpectancy`, `riskTolerance` | `lifeExpectancyDefault`, `LON_AGE`, `LTC_START_AGE`, `EDU_TARGET_AGE`, `SAV_TARGET_AGE`, `PRP_TARGET_AGE` (defaults) |
| Goal cards: lifestyle, retAge, targetYear per goal, bequest, dependYears, incomeReplace, stored amounts, tags, LTC start age | `INC_SUPPORT_*`, `RET_LIFESTYLE_*`, household seeding shares, property bands and values, `PROPERTY_LTV`, `lifePremiumRate`, `lifeRoundUnit` |
| Stress chips on / off (and size / timing edits if the UI allows) | Stress sizes and timings `R_xxx_SIZE`, `R_xxx_WHEN` |
| Money page edits | Plan / budget: premium rates, `FREE_BUDGET_SHARE`, steps, `coverSliderPremFloor`; HappiU envelope; `MIN_EXPENSE_MONTHLY` |
| | System: `systemCurrency`, `fxMode`, `priceLevelOn`, `PPP_BASE_COUNTRY`; risk bands; profiler weights and vocabulary map; social-security module per country |

---

## 6. Testing

| Layer | What | Where |
|-------|------|-------|
| Unit | Each `service.py` function, pure inputs → outputs | `tests/services/<name>/` |
| Parity | Each service against the V0-24 fixtures for 50 personas + scenarios | `tests/parity/` |
| Contract | Router request / response shapes; HU and SV payload shapes | `tests/contract/` |
| Orchestration | `/v1/predict`, `/v1/needs`, `/v1/plan`, `/v1/budget` with mocked LLM, inproc services | `tests/test_orchestration.py` |
| Frontend | Vitest for API wiring and formatting; no maths | `frontend/src/**/*.test.ts` |
| End to end | One Singapore and one Vietnamese session (mock LLM, mock premium, HU / SV stubs) | `tests/e2e/` |

Tolerances: user-currency amounts exact after rounding (±1 unit allowed where Python and
Excel round halves differently); rates and price levels 1e-9; HappiU score ±1; SV path
±0.05% (deterministic twin).

---

## 7. Mocks

| Dependency | Mock | Switch |
|------------|------|--------|
| Premium API | `MockPremiumClient` (placeholder rate per need) | `GP_SVC_PREMIUM=mock` (default) |
| FX service in FM | GP: `SnapshotFxClient` (CSV) and `MockFxClient` (tests). FM: snapshot seed when the fetch fails | `GP_SVC_FX=http|snapshot|mock` (`http` = FM in production, `snapshot` for parity) |
| LLM (People Like You) | Fixture income and flags | existing test hooks |
| HU, SV | Stub HTTP servers returning recorded responses | `GP_SVC_HU=mock`, `GP_SVC_SV=mock` in tests |

---

## 8. Open points (decide before or during the WP named)

| # | Open point | Needed by | Proposal |
|---|-----------|-----------|----------|
| O1 | FX: where it runs and stores data | WP3 | Decided: clone the InsApi service into the FM docker, data in FM's database; GP calls it over HTTP. Rotate the Open Exchange Rates key that is hard-coded in InsApi. Open: does InsApi later switch to FM's FX service too? |
| O2 | Who is admin; authentication for the admin screen | WP2 | Reuse the existing auth; role `admin` |
| O3 | Old sessions: recalculate with their `parametersVersion` or migrate | WP2 | Keep their version; "update to current" button |
| O4 | Premium API contract (fields, per-product, term) | WP9 | Mock follows §3.6; adapt when the API spec exists |
| O5 | SV: does it take ages or years for events | WP13 | GP converts ages to engine years (as in the workbook) |
| O6 | N_PRP for customers older than 33 is due next year | WP8 | As modelled; consider a minimum horizon (e.g. 3 years) in the Excel first |
| O7 | Parked ideas: PLU-01 emergency fund, critical-illness income base / treatment overlap, N_ADB, off-needs display | — | Not in this plan; model first |

---

## 9. Definition of done (whole plan)

- All WPs merged; parity tests green for 50 personas and all scenarios.
- No hard-coded money constant left in GP, HU or SV (all from admin parameters or the FX
  service); no SGD fallback; no plan maths in the frontend.
- Workbook model V0-25: Discrepancies tab empty, change log "code follows V0-24".
