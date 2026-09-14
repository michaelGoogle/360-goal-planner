# Prototype InsApi (contacts + financial plans)

GP upserts a **Contact** and **Financial Plan** on the 360 Prototype when the
customer has given **both email and mobile**. Plans are owned by sales user
`mira.whatsapp`. Demo host: [https://demo-360-ai-prototype.360f.com](https://demo-360-ai-prototype.360f.com).

## When it runs

| Trigger | Behaviour |
|---------|-----------|
| Adviser FAB | `POST /v1/crm-sync` (blocking). UI requires email and mobile. |
| Share report | `POST /v1/crm-sync` then HeyGen `POST /v1/video-notify`. CRM failure does not block the video. |
| Estimate / Score / Plan | Background refresh if `reportEmail` + `reportMobile` are already on the session. |

Failures are best-effort on engine routes (log + continue). `/v1/crm-sync` returns the InsApi status (400/503) so the FAB can toast.

The browser keeps `insapiContactId` / `insapiPlanId` on the session. No GP CRM database.

## Env

| Var | Default | Purpose |
|-----|---------|---------|
| `INSAPI_UPSTREAM` | `https://demo-360-ai-prototype.360f.com` | Empty disables the client |
| `INSAPI_USER_NAME` | `mira.whatsapp` | Advisor lookup |
| `INSAPI_USER_ID` | `07e06e98-da76-496c-9ccc-9502ca535b03` | Skip search if set |
| `INSAPI_TIMEOUT_S` | `15` | Per-call timeout |

Code: [`src/insapi_client.py`](../src/insapi_client.py), [`src/insapi_sync.py`](../src/insapi_sync.py).

## InsApi calls (all POST JSON, no auth header)

1. `POST /users/searchUser` — resolve `mira.whatsapp` (cached).
2. `POST /contact/getContact` — find by email, then mobile.
3. `POST /contact/createContact` or `/contact/updateContact`.
4. `POST /api/2025-11-25/financialPlan/createFinancialPlan` or `updateFinancialPlan`.

Duplicate email returns `existingContactId` (HTTP 400); GP then updates.

## Mapping

Contact: name split, DOB, gender, E.164 → `+countryCode` / national number, occupation as `jobTitle`, dependents.

Plan: SGD totals (`SALARY`, `MISCELLANEOUS_EXPENSES`, `CASH` / `MUTUAL_FUNDS` / `REAL_ESTATE`, `HOME_LOAN`). Needs `N_INC→lifeProtection`, `N_CRI→criticalIllness`, `N_TPD→disability`, `N_HOS→hospitalization`, `N_RET→retirement`, `N_EDU→education`, `N_SAV→generalSavings`, `N_PRP→home`. HappiU scores and suggested premiums go in `notes`. InsApi rejects liabilities above assets and income below ~USD 1,000/month — those groups are omitted, and a notes-only plan is retried on 400.

Product recommendations are not sent (catalog `productId`s are unknown).
