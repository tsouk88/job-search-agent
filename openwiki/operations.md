---
type: Runbook
title: Operations / Runbook
description: Operational runbook — local startup (Redis + Celery), all environment variables, runtime dependencies, LangSmith observability config, Render/Vercel deployment, endpoint behavior, CORS gotchas, cold-start handling, and troubleshooting.
tags: [operations, runbook, deployment, troubleshooting, config, render, vercel, redis, celery]
sources:
  - id: openwiki-source-833e692518af9eeaf8564cc6
    resource: repo://main.py
  - id: openwiki-source-51016da779816d3057e112d7
    resource: repo://n8n_workflow.json
  - id: openwiki-source-f70156010a8eb5325870bfc6
    resource: repo://render.yaml
generated: { by: "openwiki/0.9.0", at: "2026-11-05T09:45:53.453Z" }
verified:
  - by: openwiki/0.9.0
    at: 2026-11-05T09:45:53.453Z
---

# Operations / runbook

## Local startup

The backend now depends on a running Redis instance (used as the rate-limit
storage backend, the job-result cache, and the Celery broker/backend) and a
Celery worker for the async `/upload` CV pipeline. Start Redis, then run the
worker and the API in two terminals — this mirrors the production
`startCommand` in `render.yaml`:

Backend (worker terminal):

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY, DATABASE_URL, REDIS_URL, etc.
celery -A tasks worker --pool=solo -l info
```

Backend (API terminal):

```bash
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Voice (optional, WSL2 on Windows):

```bash
cd voice/server
uv sync
cp .env.example .env   # add voice-specific keys
uv run bot.py
```

The frontend talks to `NEXT_PUBLIC_API_BASE` (defaults to `http://localhost:8000`). The LangSmith eval runner posts to `http://localhost:8002/askeval`.

## Environment variables

From `.env.example`:

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | Gemini 2.5 Flash for feedback extraction, CV parsing, `/evaluate`, eval grading |
| `DATABASE_URL` | yes | PostgreSQL for `PostgresSaver` checkpointer; also backs the `n8njobs` dedup table |
| `REDIS_URL` | yes | Redis URL for slowapi rate-limit storage, the `/ask` job-result cache, and the Celery broker/backend |
| `EVALUATE_TOKEN` | for `/evaluate` | Auth token checked by `x-api-key` on `/evaluate` |
| `N8N_DEDUPE` | for `/digest`, `/digest/sent` | Auth token checked by `x-api-key` on the n8n digest endpoints |
| `EVALS` | for `/askeval` | Auth token checked by `x-api-key` on `/askeval` (the eval entry point) |
| `OPENROUTER_API_KEY` | for evals | OpenRouter key for the `jev` judge (`jev-1.13`) in `eval_runner.py` |
| `ALLOWED_ORIGINS` | yes | Comma-separated CORS origins (no trailing slash) |
| `LANGSMITH_TRACING` | optional | Set to `true` to enable tracing |
| `LANGSMITH_API_KEY` | for evals | LangSmith API key |
| `LANGSMITH_PROJECT` | for evals | LangSmith project name |
| `LANGSMITH_ENDPOINT` | optional | EU endpoint: `https://eu.api.smith.langchain.com` |

### LangSmith observability

`render.yaml` hardcodes two LangSmith values:
- `LANGSMITH_TRACING=true` — tracing is always on in production
- `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` — EU region endpoint

`LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` are synced secrets (set in the Render dashboard). `eval_runner.py`'s `Client()` consumes the same project configuration — the deployment env and the eval harness share the same LangSmith project.

### Which secrets are *not* in render.yaml

`render.yaml` only declares `GEMINI_API_KEY`, `DATABASE_URL`, `REDIS_URL`,
`ALLOWED_ORIGINS`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, plus the two
hardcoded `LANGSMITH_TRACING`/`LANGSMITH_ENDPOINT` values. It does **not**
declare `EVALUATE_TOKEN`, `EVALS`, `N8N_DEDUPE`, or `OPENROUTER_API_KEY`. If
any of those endpoints are used, the corresponding token must be added
manually as a Render dashboard environment variable. Without it the endpoint
returns 401 because `os.getenv(...)` is empty.

## N8N Integration

The project integrates with [n8n](https://n8n.io/) via `n8n_workflow.json`, which defines an automated job search pipeline.

### Workflow Components

The workflow automates the following cycle:
1. **Trigger**: A `Schedule Trigger` runs the workflow every 12 hours.
2. **Configuration**: `Search Settings` node defines the query (e.g., "python AI backend engineer remote") and `thread_id`.
3. **Execution**: An `HTTP Request` node (named "Wake node") calls the local API (often targeting a tunnel like `http://localhost:8002` in development or the deployed production URL) to trigger processing.
4. **Digest**: The system uses specialized endpoints (`/digest`, `/digest/sent`) protected by an `N8N_DEDUPE` API key to manage job alerts and prevent duplicate notifications.
5. **Notification**: A `Gmail` node sends the compiled results to the user.

### Operational Notes
- **API Key Security**: The API key used for the `/digest` endpoints (`N8N_DEDUPE`) must be manually configured in the environment where the workflow runs (e.g., the Render dashboard or local `.env`).
- **Development**: When testing n8n workflows locally, use a service like [ngrok](https://ngrok.com/) to expose the backend port so the n8n HTTP Request node can reach it.


PostgreSQL is required for persistent memory via `PostgresSaver`.

**Supabase (recommended):** Use the **session pooler** (port 5432), not the transaction pooler (port 6543). `PostgresSaver` relies on prepared statements, which the transaction pooler does not keep across queries — the failures are intermittent.

**Local:** `CREATE DATABASE jobsearch_memory;` and set `DATABASE_URL`. The `n8njobs` table used by `/digest` dedup must also exist.

### Redis

`REDIS_URL` points at a Redis instance (local default
`redis://localhost:6379/0`). The same connection is used for three things at
once: the `slowapi` limiter storage backend (with in-memory fallback on
connection error), the `jobs:{query}:{country}` job-result cache with a
14400s (4h) TTL, and the Celery broker/result backend configured in
`tasks.py`.

## Deployment

### Backend — Render

`render.yaml` declares a single web service `jobsearch-api`:
- Runtime: Python, free plan, Frankfurt region
- Build: `pip install -r requirements.txt`
- Start: `celery -A tasks worker --pool=solo -l info & uvicorn main:app --host 0.0.0.0 --port $PORT` — the Celery worker and uvicorn run in one process group
- Health check: `/health` (Redis ping + Celery ping)
- Synced secrets (`sync: false`): `GEMINI_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_ORIGINS`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`
- Hardcoded values: `LANGSMITH_TRACING=true`, `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com`

Deploy via Render → New → Blueprint.

### Frontend — Vercel

- Root Directory: `frontend`
- `NEXT_PUBLIC_API_BASE` → Render URL (no trailing slash)

### Two details that cost real time

- `NEXT_PUBLIC_API_BASE` takes **no trailing slash** — the client appends `/ask`
- `ALLOWED_ORIGINS` takes **no trailing slash** — the browser's `Origin` header is scheme, host, port only. A stray `/` makes every request fail CORS with no visible symptom except a browser console error

### Cold-start behavior

The free Render instance sleeps after 15 minutes of inactivity. The first
search takes about a minute (~50s to wake, then 15s to query four job APIs).
Every search after that is instant. The [n8n workflow](operations/n8n-automation.md)
handles this with a wake node (`GET /docs`, On Error: Continue) and a
**120-second** wait before calling `POST /digest`.

## Endpoint behavior

| Endpoint | LLM | Rate limit | Notes |
|---|---|---|---|
| `/ask` | no | 10/min | Four-condition cache (no fetch, query changed, country changed, >4h); on a miss it checks the Redis job cache before running the agent |
| `/reset` | no | 10/min | Clears memory, returns cached unfiltered jobs |
| `/feedback` | yes (Gemini) | 10/min | Extracts avoid-keywords, 100-char input cap |
| `/upload` | yes (Gemini, via Celery) | 10/min | PDF only, 5MB cap, first 5 pages; enqueues `filework.delay(...)` and returns `job_id` |
| `/jobs/{job_id}` | no | 60/min | Polls the Celery `AsyncResult`; returns `pending`/`done`/`failed` |
| `/evaluate` | yes (Gemini) | 10/min | `x-api-key` auth via `EVALUATE_TOKEN`; 429 after 5 `eval` Gemini calls/day |
| `/digest` | no | 10/min | `x-api-key` auth via `N8N_DEDUPE`; dedups against the `n8njobs` table |
| `/digest/sent` | no | 10/min | `x-api-key` auth via `N8N_DEDUPE`; inserts sent links into `n8njobs` |
| `/askeval` | no | 10/min | `x-api-key` auth via `EVALS`; runs the eval-agent (in-memory saver) with `run_type: eval` metadata |
| `/health` | no | — | `r.ping()` + `celery_app.control.ping(...)`; returns 503 if no Celery response within the ping window |

All rate-limited endpoints use `slowapi` keyed on `CF-Connecting-IP` (falling
back to `get_remote_address`) with `REDIS_URL` as the storage backend and an
in-memory fallback if Redis is unreachable. `/health` access-log lines are
filtered out of the uvicorn access log.

## Runtime dependencies

- **PostgreSQL** — required for REST backend startup (`PostgresSaver.setup()`) and the `n8njobs` dedup table
- **Redis** — required for rate-limit storage, the `/ask` job cache, and the Celery broker/backend
- **Celery worker** — required for `/upload`; the worker runs `filework`, which parses the CV, compiles the graph against `PostgresSaver`, and returns formatted jobs
- **Gemini API** — required for `/feedback`, `/upload`, `/evaluate`, and eval grading
- **`pdfplumber`** — PDF text extraction for `/upload`
- **`slowapi`** — rate limiting (Redis-backed, in-memory fallback)
- **`requests`** — job API fetchers
- **LangGraph + LangChain** — orchestration and model init
- **OpenRouter** — the `jev` judge in `eval_runner.py` (model `typesafe/jev-1.13`)

## Practical troubleshooting

| Symptom | Check |
|---|---|
| App fails to start | `DATABASE_URL` reachable? `PostgresSaver.setup()` runs at startup |
| Rate limiter silently in-memory | `REDIS_URL` reachable? `slowapi` falls back silently if Redis is down |
| `/upload` jobs never finish | Celery worker running? `celery -A tasks worker --pool=solo -l info` must be up; `/jobs/{job_id}` stays `pending` without it |
| `/jobs/{job_id}` stuck pending | Celery worker alive? `redis` broker reachable at `REDIS_URL`? |
| `/evaluate` returns 401 | `EVALUATE_TOKEN` set in env? `x-api-key` header sent? (not in `render.yaml`) |
| `/askeval` returns 401 | `EVALS` set in env? `x-api-key` header sent? (not in `render.yaml`) |
| `/digest` or `/digest/sent` returns 401 | `N8N_DEDUPE` set in env? n8n `httpHeaderAuth` credential sends `x-api-key`? (not in `render.yaml`) |
| `check_gemini_budget` 429 | Daily per-name Gemini call limit hit (`eval`: 5, `site`: 100); resets daily via Redis TTL |
| CORS failures (no visible symptom) | `ALLOWED_ORIGINS` has no trailing slash? |
| Frontend can't reach backend | `NEXT_PUBLIC_API_BASE` has no trailing slash? |
| Search results stale or narrow | Source APIs reachable? Graph still fans out to all 4 nodes? |
| Memory not retained | `thread_id` flowing correctly from frontend localStorage? |
| `/health` reports 503 | Redis reachable and Celery worker pinged back within the ping window? |
| First search is slow | Render instance sleeping (~50s cold start); n8n waits 120s before `/digest` |
| Harbor eval fails | Check `evals/jobs/<run-id>/result.json` and trial stdout |

## CI workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/eval.yml` | Push/PR to `agent.py`, `mcp_server.py`, `evals/**` | Runs Harbor eval (`filter-exclusion-senior`, no network in the container), checks the reward, uploads artifacts |
| `.github/workflows/openwiki-update.yml` | Monthly cron (`0 6 1 * *`) + manual dispatch | Runs OpenWiki (`openwiki code --update`), creates a docs update PR |

## Git-history failure modes

Recent commits show the most common operational issues were:
- Streaming buffering (commit `4524397`)
- Remote API rate limits (429s handled in all fetchers)
- Oversized prompts to tracing systems (description truncation)
- Data quality from unreliable sources (Arbeitnow removed)
- Event loop blocking (fixed with `asyncio.to_thread`, commit `cd1f884`)

## Source references

- `main.py`, `render.yaml`, `.env.example`, `requirements.txt`, `tasks.py`
- `.github/workflows/eval.yml`, `.github/workflows/openwiki-update.yml`
- `n8n_workflow.json`, `eval_runner.py`
