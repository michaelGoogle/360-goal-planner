# 360-Goal Planner — HTTP API

Base URL (local): `http://127.0.0.1:8009`  
Compose: `http://127.0.0.1:8069`  
OpenAPI: `GET /docs`, `GET /redoc`, `GET /openapi.json`

CORS: allow all origins. No login. `/v1/predict` runs People Like You in-process.

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness |
| `GET` | `/healthz` | Same as `/health` |
| `POST` | `/v1/parse-sentence` | Extract About You fields from free text |
| `POST` | `/v1/explain` | Spoken explainer script (LLM or fallback) |
| `POST` | `/v1/predict` | People Like You → Need Profiler → Need Calculator |
| `POST` | `/v1/needs` | Recompute needAmount, projected have, and gap |
| `POST` | `/v1/score` | HappiU `preHappiU` / `postHappiU` |
| `POST` | `/v1/project` | Scenario Visualizer wealth path |
| `POST` | `/v1/sv-payload` | SV body only (debug; no projection) |
| `POST` | `/v1/crm-sync` | Upsert contact + financial plan on Prototype InsApi |
| `GET` | `/v1/report-walkthrough` | Public URL of the shared dummy report video |
| `POST` | `/v1/video-notify` | Queue HeyGen plan video; WhatsApp (and optional email) when ready |
| `GET` | `/v1/video-notify/{jobId}` | Poll job status and public media URL |

When `frontend/dist` is present, `GET /` serves the React UI.

---

## `POST /v1/crm-sync`

Upsert a Prototype InsApi contact (owned by `mira.whatsapp`) and a Goal Planner
financial plan. **Email and mobile are required.** See
[Prototype-insapi.md](Prototype-insapi.md).

### Request

Same shape as video-notify: `{ email, mobile, pre, post, session }`.

**200** `{ success, contactId, planId }`. **400** if email/mobile invalid.
**503** if InsApi is unset or unreachable. Engine routes (`/v1/predict`,
`/v1/score`, `/v1/project`) and Share report also refresh this plan in the
background once contact is on the session; those paths do not fail the
customer journey if Prototype is down.

---

## `GET /health` / `GET /healthz`

**200**

```json
{ "status": "ok", "service": "gp" }
```

---

## `POST /v1/parse-sentence`

### Request

```json
{ "text": "I'm a 42 year old male CEO in Singapore with two kids" }
```

Text shorter than 4 characters → `{ "success": true, "source": "none", "fields": {} }`.

### Success **200**

| `source` | Meaning |
|----------|---------|
| `llm` | Claude extracted fields (`name`, `age`, `gender`, `res`, `deps`, `occ`) |
| `unavailable` | No `ANTHROPIC_API_KEY` (or OpenAI fallback key) — `{ "success": false, "fields": {} }` |
| `none` | Text too short |

**503** if the model call throws (`detail`: “Could not read that sentence”).

The UI falls back to a local regex parser when the BFF returns `unavailable`.

---

## `POST /v1/explain`

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | string | yes | `mira` \| `intro` \| `money` \| `score` \| `chart` \| `prod` |
| `route` | string | Mira only | `d2cIntro` \| `d2cAbout` \| `d2cMoney` \| `d2cScore` \| `d2cPlan` |
| `context` | object | no | Compact figures from the UI (see [Architecture.md](Architecture.md)) |

### Success **200**

```json
{
  "success": true,
  "kind": "money",
  "source": "llm",
  "text": "Money coming in is nine thousand dollars a month. …"
}
```

`source` is `fallback` when the key is missing or the model fails. Unknown
`kind` / Mira without a known `route` → **400**.

---

## `POST /v1/predict`

Body is a **GpSession** (all fields optional with defaults). Important fields:

| Field | Default | Notes |
|-------|---------|-------|
| `age` | 40 | Used to synthesize `dateOfBirth` if omitted |
| `occupation` | `""` | Passed to People Like You |
| `residency` | `Singapore Citizen` | CPF vs foreigner on HU/SV payloads |
| `gender` | `Male` | Passed to FM / HU |
| `dependents` | 0 | Need profiler + assumed life cover |
| `persist` | `false` | If true **and** Bearer token present, FM `/v1/me/onboarding/…` |
| Money / needs / policies | empty / 0 | Overwritten by FM unless the UI already edited them |

Header: `Authorization: Bearer <jwt>` optional.

### Success **200**

```json
{
  "success": true,
  "session": {
    "incomeMonthly": 9000,
    "expenseMonthly": 5500,
    "needs": [{ "type": "N_RET", "enabled": true, "needAmount": 1200000, "gap": 1200000 }],
    "source": "people-like-you",
    "policies": []
  },
  "notes": []
}
```

`source` is `people-like-you`. `notes` explains skipped Need Profiler / Need
Calculator steps. People Like You down or `success: false` returns **503**.

Assumed life cover (when FM returns a property owner or the session has
dependants): max of mortgage rounded to S$100,000 and 5× annual income.

---

## `POST /v1/needs`

Recompute `needAmount`, projected `have`, and `gap` for every UNIFIED need.
Same session body as predict. The UI calls this (debounced) whenever goal,
money, or assumption inputs that feed the calculator change. `/v1/predict`
uses the same engine (`evaluate_session`).

Formulas: [Calculations.md](Calculations.md) §4–5 and
[People-like-you-and-needs.md](People-like-you-and-needs.md) §5.

UNIFIED types: `N_INC`, `N_CRI`, `N_TPD`, `N_HOS`, `N_RET`, `N_EDU`, `N_SAV`,
`N_PRP`. Every non-retirement amount follows the TFM_2604 Needs Calculator
workbook with Singapore-only SGD constants. Per-row inputs the calculator
reads: `enabled`, `existing`, `retAge`, `lifestyle`, `incomeReplaceMonthly`,
`dependYears`, `liabilities`, `bequest`, `targetYear`, `monthlyContribution`,
`contributeYears`. `region`, `courseYears` and `childrenToFund` are **gone** —
education is one Singapore course total inflated to `targetYear`.

### Success **200**

```json
{
  "success": true,
  "session": {
    "ageOfRetirement": 65,
    "needs": [
      {
        "type": "N_RET",
        "enabled": true,
        "needAmount": 867000,
        "have": 211000,
        "existing": 154224,
        "gap": 656000,
        "retAge": 65,
        "lifestyle": 2,
        "monthlyContribution": 0
      }
    ]
  }
}
```

**503** if the calculator raises.

---

## `POST /v1/score`

Same session body as predict.

### Success **200**

```json
{
  "success": true,
  "preHappiU": 38,
  "postHappiU": 61,
  "result": { "preHappiU": 38, "postHappiU": 61 },
  "breakdown": null
}
```

Upstream mapping: [`src/hu_payload.py`](../src/hu_payload.py). Side-by-side with
SV: [HU-and-SV-payloads.md](HU-and-SV-payloads.md). Unreachable HU → **503**.
Other HU errors pass through the status and `detail`.

---

## `POST /v1/project`

Same session body.

### Success **200**

```json
{
  "success": true,
  "data": {
    "preWealth": [/* … */],
    "postWealth": [/* … */],
    "prePositiveCashFlow": [/* … */],
    "postPositiveCashFlow": [/* … */]
  },
  "raw": {}
}
```

`data` is the inner SV envelope the Plan chart plots. Mapping:
[`src/sv_payload.py`](../src/sv_payload.py). Side-by-side with HU:
[HU-and-SV-payloads.md](HU-and-SV-payloads.md). Query on SV: `tenant_id=helium`.
Unreachable SV → **503**.

---

## `POST /v1/sv-payload`

Same session body as project. Returns `{ success, payload }` — the SV JSON only,
no upstream call. Use this to inspect mapping without running Monte Carlo.

---

## `GET /v1/report-walkthrough`

**200** `{ success, dummyUrl }`. `dummyUrl` is
`{MEDIA_PUBLIC_BASE_URL}/gp/generic-walkthrough.mp4` — the same generic clip for
every customer. The report plays this until a customised job sets `mediaUrl`.

## `POST /v1/video-notify`

Queue a HeyGen Video Agent clip of the current plan report. **Mobile is
required** (customer key; Singapore 8-digit numbers are stored as `+65…`).
The Share report UI also requires email and calls `POST /v1/crm-sync` first.
The same mobile **overwrites** the previous job and
`media/gp/{jobId}.mp4` rather than creating a second version.

Returns **202** `{ success, jobId }` immediately; a background thread polls
HeyGen, writes `{jobId}.mp4` and a hosted HTML snapshot `{jobId}.html` on the
lx43 media volume, then sends **the same two text links** (never HeyGen CDN,
never attached files) over WhatsApp and SMTP when an address was given.

GP also best-effort POSTs the snapshot to FM `POST /v1/public/plan-report`
and schedules a Prototype InsApi refresh. FM or InsApi down does not block the
video.

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mobile` | string | **yes** | Customer key. Local 8-digit SG → `+65`. WhatsApp destination. |
| `email` | string | UI **yes** | Required in Share report / FAB for Prototype; optional on this route |
| `pre` | number \| null | no | HappiU today |
| `post` | number \| null | no | HappiU with this plan |
| `session` | object | yes | Full GP session (prompt + FM snapshot) |

Needs `HEYGEN_API_KEY`, `MEDIA_DIR`, and `MEDIA_PUBLIC_BASE_URL` (e.g.
`https://mgzh11.synology.me:8442/videos`). Public files:

- Customised video: `{MEDIA_PUBLIC_BASE_URL}/gp/{jobId}.mp4`
- Hosted HTML report: `{MEDIA_PUBLIC_BASE_URL}/gp/{jobId}.html`

**202** `{ success, jobId }`. **400** if mobile is missing/invalid. **503** if
HeyGen or the media volume is unset, or generate fails.

## `GET /v1/video-notify/{jobId}`

**200** `{ success, jobId, status, mediaUrl, error }`. **404** if unknown.
`status` is `pending` / `completed` / `failed`. The report page polls this
until `mediaUrl` is set.

---

## Errors

| Status | When |
|--------|------|
| **400** | Unknown explainer kind / Mira missing route; video-notify missing mobile; crm-sync missing email/mobile |
| **422** | Invalid JSON body (Pydantic) |
| **503** | Upstream unreachable, parse-sentence model failure, or video-notify without HeyGen / media volume |

FastAPI `detail` is a string or the upstream JSON. There is no Prometheus
`/metrics` on GP.
