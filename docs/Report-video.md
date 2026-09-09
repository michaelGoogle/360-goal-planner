# Plan report video (HeyGen notify)

On **Your plan**, **Share report** captures a **mobile number** (required) and
optional email, then queues a HeyGen spokesperson clip. The HTML report is
always available; the **video window is hidden until that mobile is provided**.
After share, the same window shows a preparing state, then the lx MP4.

HTTP contract: [API.md](API.md) (`POST` / `GET /v1/video-notify`). This page is
how the pipeline works and **where to change the spoken prompt**.

---

## Edit the prompt

The talking-head script is **Python**, not a Markdown file under `src/prompts/`.

| What to change | Where |
|----------------|--------|
| Spoken script, figures, close | [`src/heygen/prompt.py`](../src/heygen/prompt.py) → `build_spoken_script()` |
| Avatar look note | same file, `spokesperson_look()` — country from the **mobile** calling code (stored on the job; HeyGen uses a stock Avatar III look) |
| Need-type labels (“retirement”, …) | same file, `NEED_LABEL` |
| Which avatar / voice | `HEYGEN_AVATAR_ID` (default `Juan_standing_office_front`, June Office Front 2), optional `HEYGEN_VOICE_ID` |

`submit_notify()` in [`src/heygen/pipeline.py`](../src/heygen/pipeline.py) stores the look+script
string on the job and POSTs the spoken script to HeyGen `POST /v3/videos`
(`type: avatar`, `engine: avatar_iii`).

Trust rule (same as Mira): **only numbers already in the session** (and the
HappiU pre/post the UI sent). Do not invent premiums, quotes, or product names.
Keep the close: not a quote, not advice to buy.

Pytest: `tests/test_video_notify.py` → `test_prompt_uses_session_figures`. If you
change which figures are spoken, update that test.

---

## What the customer does

1. Plan footer or report bar → **Share report**.
2. Popup: **mobile required**, email optional. UI:
   [`frontend/src/pages/plan/ReportNotify.tsx`](../frontend/src/pages/plan/ReportNotify.tsx).
3. Toast: we will notify you when the video is ready. **View report** then shows
   the video window (preparing, then the clip). Without a mobile, the HTML
   report has no video window.
4. Later: WhatsApp and optional SMTP with a **text link** to the MP4 (not the
   file attached).

The customer is **the mobile number** (Singapore 8-digit locals stored as
`+65…`). The same mobile **overwrites** the previous video and FM row. A
different mobile is a different customer. Email is an extra attribute / channel.

---

## Pipeline

```text
Share report  POST /v1/video-notify   (mobile required)
     │
     ▼
GP BFF      202 { jobId }     (thread continues)
     │
     ├─ reuse job id + gp/{jobId}.mp4 when this mobile already exists
     ├─ FM POST /v1/public/plan-report  (best-effort: contact, session, HappiU, ids)
     ├─ HeyGen  POST /v3/videos  Avatar III talking-head { script, avatar_id }
     ├─ poll    GET  /v3/videos/{id}      every 15s, up to 40 min
     ├─ store   {MEDIA_DIR}/gp/{jobId}.mp4     (overwrite)
     ├─ FM POST again with heygen id + lx URL
     └─ notify  WhatsApp and optional SMTP
```

The report UI polls `GET /v1/video-notify/{jobId}` until `mediaUrl` is set.

Startup (`lifespan` in [`src/app.py`](../src/app.py)) resumes sqlite jobs that
are still `pending` and already have a HeyGen id.

| Module | Role |
|--------|------|
| [`src/heygen/prompt.py`](../src/heygen/prompt.py) | Build the prompt |
| [`src/heygen/agent.py`](../src/heygen/agent.py) | Generate + poll |
| [`src/heygen/jobs.py`](../src/heygen/jobs.py) | sqlite (`GP_VIDEO_JOBS` or `GP/data/video_jobs.sqlite`) |
| [`src/heygen/media_store.py`](../src/heygen/media_store.py) | Download MP4 onto the media volume |
| [`src/heygen/delivery.py`](../src/heygen/delivery.py) | Email + WhatsApp **text** |
| [`src/heygen/mobile.py`](../src/heygen/mobile.py) | Normalize SG / E.164 |
| [`src/heygen/public_id.py`](../src/heygen/public_id.py) | 12-hex job id (reused per mobile) |
| [`src/heygen/pipeline.py`](../src/heygen/pipeline.py) | Orchestrate thread + resume + FM persist |

Unset `HEYGEN_API_KEY` → **503** (no fake video). HeyGen generate failure → **503**.

---

## Where the file lives (lx43 media, not Azure)

Nginx `media` already serves a host directory read-only as `/videos/` on LAN
**8042** / WAN **8442**. GP mounts the **same directory read-write** and writes
`gp/{jobId}.mp4`. Re-share for the same mobile **replaces** that file.

Public URL (customers open this; it is not a GP redirect). The filename is a
**12-character hex id** from `new_job_id()` (or the previous id for that
mobile). The same id is in the email/WhatsApp body as `Video id:` so you can
find `media/gp/{jobId}.mp4` later.

`{MEDIA_PUBLIC_BASE_URL}/gp/{jobId}.mp4`

Examples:

- LAN: `http://192.168.1.43:8042/videos/gp/{jobId}.mp4`
- WAN: `https://mgzh11.synology.me:8442/videos/gp/{jobId}.mp4`

If `MEDIA_DIR` is unset (laptop without the volume), that job may fall back to
the HeyGen CDN URL (those expire). If `MEDIA_DIR` is set but the write fails,
the job is marked failed and nothing is sent.

---

## FM snapshot

`POST /v1/public/plan-report` (no JWT) upserts:

| Field | Meaning |
|-------|---------|
| `app_user` | Found/created by `mobile_e164`; optional email; placeholder `gp.{digits}@finplan360.invalid` if none |
| `gp_plan_report` | One row per mobile (overwrite): contact, full session JSON, HappiU pre/post, HeyGen id, lx `mediaUrl`, job id |

FM down is logged and ignored so the video can still run.

---

## Delivery

Need **mobile**; send WhatsApp to that number. Send email only when an address
was given.

- **Email:** workspace SMTP (`SMTP_HOST`, `SMTP_FROM`, …). If `SMTP_HOST` is
  unset, email is skipped (not treated as a hard fail).
- **WhatsApp:** Baileys gateway `POST {WHATSAPP_GATEWAY_URL}/send` with a text
  body that includes the public URL. Not Twilio. Not the MP4 as media (HeyGen
  URLs expire; large media also fails on some gateways).

If WhatsApp is down, email still goes when an address was given. If only mobile
was given and WhatsApp fails, that channel is marked failed on the job.

---

## Ops alerts

GP emails `HEYGEN_ALERT_EMAIL` (default `michael.gerber@vitalus.ch`) via the
same SMTP relay when:

- the HeyGen API **wallet is below $10** (checked on GP startup and each Share
  report; at most once per 12 hours while it stays low)
- a HeyGen **API call fails** (generate or poll; same failure is quiet for 30
  minutes). The mail includes HTTP status, endpoint, job id, and a truncated
  response body — not the API key.

Top up at https://app.heygen.com → Settings → API (pay-as-you-go wallet).

---

---

## Environment

Set on compose service `gp` (see workspace `.env.example`). Never put a real
HeyGen key in git.

| Variable | Meaning |
|----------|---------|
| `HEYGEN_API_KEY` | Required for notify |
| `HEYGEN_API_BASE_URL` | Default `https://api.heygen.com` |
| `HEYGEN_AVATAR_ID` | Avatar III look (default `Juan_standing_office_front`, June Office Front 2) |
| `HEYGEN_VOICE_ID` | Optional; omit to use the look’s default voice |
| `HEYGEN_ALERT_EMAIL` | Ops inbox when wallet &lt; $10 or HeyGen API fails (default `michael.gerber@vitalus.ch`) |
| `HEYGEN_ALERT_BALANCE_USD` | Wallet alert threshold (default `10`) |
| `MEDIA_DIR` | Container/host path to write (`/media` in compose) |
| `MEDIA_HOST_DIR` | Compose bind of the host media dir (same dir nginx serves) |
| `MEDIA_PUBLIC_BASE_URL` | Origin customers open, including `/videos`, no trailing slash |
| `GP_VIDEO_JOBS` | sqlite path (compose: `/app/data/video_jobs.sqlite`) |
| `WHATSAPP_GATEWAY_URL` | Baileys, default `http://127.0.0.1:8091` (compose: `http://wa:8091`) |
| `SMTP_*` | Same vars FM already uses |
| `FM_UPSTREAM` | For the plan-report snapshot |

---

## Tests

```powershell
cd GP
python -m pytest tests/test_video_notify.py -q

cd ..\FM
python -m pytest tests/test_gp_plan_report.py -q
```

Mocks HeyGen generate/poll, media download, and delivery. Writes a temp
`MEDIA_DIR`. Does not call the real HeyGen API.

---

## Out of scope

- Azure Blob / SAS
- Twilio
- Multiple stored versions per mobile (always overwrite)
