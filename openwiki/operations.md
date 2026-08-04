---
type: Runbook
title: Operations / Runbook
description: Operational runbook — local startup, all environment variables, runtime dependencies, LangSmith observability config, Render/Vercel deployment, endpoint behavior, CORS gotchas, cold-start handling, and troubleshooting.
tags: [operations, runbook, deployment, troubleshooting, config, render, vercel]
---

# Operations / runbook

## Local startup

Backend:

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY, DATABASE_URL, etc.
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

The frontend talks to `NEXT_PUBLIC_API_BASE` (defaults to `http://localhost:8000`). The LangSmith eval runner posts to `http://localhost:8002/ask`.

## Environment variables

From `.env.example`:

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | Gemini 2.5 Flash for feedback extraction, CV parsing, /evaluate |
| `DATABASE_URL` | yes | PostgreSQL for PostgresSaver checkpointer (REST only) |
| `EVALUATE_TOKEN` | for /evaluate | Auth token for the /evaluate endpoint |
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

### Database setup

PostgreSQL is required for persistent memory via `PostgresSaver`.

**Supabase (recommended):** Use the **session pooler** (port 5432), not the transaction pooler (port 6543). `PostgresSaver` relies on prepared statements, which the transaction pooler does not keep across queries — the failures are intermittent.

**Local:** `CREATE DATABASE jobsearch_memory;` and set `DATABASE_URL`.

## Deployment

### Backend — Render

`render.yaml` declares a single web service `jobsearch-api`:
- Runtime: Python, free plan, Frankfurt region
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check: `/docs`
- Secrets: `GEMINI_API_KEY`, `DATABASE_URL`, `ALLOWED_ORIGINS`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` (sync: false)

Deploy via Render → New → Blueprint.

### Frontend — Vercel

- Root Directory: `frontend`
- `NEXT_PUBLIC_API_BASE` → Render URL (no trailing slash)

### Two details that cost real time

- `NEXT_PUBLIC_API_BASE` takes **no trailing slash** — the client appends `/ask`
- `ALLOWED_ORIGINS` takes **no trailing slash** — the browser's `Origin` header is scheme, host, port only. A stray `/` makes every request fail CORS with no visible symptom except a browser console error

### Cold-start behavior

<!-- openwiki: broken internal link [n8n-automation.md] file "n8n-automation.md" does not exist. Fix the href or restore the target, then delete this comment. -->
The free Render instance sleeps after 15 minutes of inactivity. The first search takes about a minute (~50s to wake, then 15s to query four job APIs). Every search after that is instant. The [n8n workflow](n8n-automation.md) handles this with a wake node and 60s wait.

## Endpoint behavior

| Endpoint | LLM | Notes |
|---|---|---|
| `/ask` | no | Three-condition cache (no fetch, query changed, >4h) |
| `/reset` | no | Clears memory, returns cached unfiltered jobs |
| `/feedback` | yes | Gemini extracts keywords, 100-char input cap |
| `/upload` | yes | Gemini CV parsing, 5MB cap, first 5 pages, PDF only |
| `/evaluate` | yes | `x-api-key` auth via `EVALUATE_TOKEN` |

All endpoints: 10 requests/minute per IP via `slowapi`.

## Runtime dependencies

- PostgreSQL — required for REST backend startup (PostgresSaver)
- Gemini API — required for /feedback, /upload, /evaluate
- `pdfplumber` — PDF text extraction for /upload
- `slowapi` — rate limiting
- `requests` — job API fetchers
- LangGraph + LangChain — orchestration and model init

## Practical troubleshooting

| Symptom | Check |
|---|---|
| App fails to start | `DATABASE_URL` reachable? `PostgresSaver.setup()` runs at startup |
| CORS failures (no visible symptom) | `ALLOWED_ORIGINS` has no trailing slash? |
| Frontend can't reach backend | `NEXT_PUBLIC_API_BASE` has no trailing slash? |
| Search results stale or narrow | Source APIs reachable? Graph still fans out to all 4 nodes? |
| Memory not retained | `thread_id` flowing correctly from frontend localStorage? |
| /evaluate returns 401 | `EVALUATE_TOKEN` set in env? `x-api-key` header sent? |
| First search is slow | Render instance sleeping (~50s cold start) |
| Harbor eval fails | Check `evals/jobs/<run-id>/result.json` and trial stdout |

## CI workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/eval.yml` | Push/PR to `agent.py`, `mcp_server.py`, `evals/**` | Runs Harbor eval, checks reward, uploads artifacts |
| `.github/workflows/openwiki-update.yml` | Monthly cron + manual | Runs OpenWiki, creates a docs update PR |

## Git-history failure modes

Recent commits show the most common operational issues were:
- Streaming buffering (commit `4524397`)
- Remote API rate limits (429s handled in all fetchers)
- Oversized prompts to tracing systems (description truncation)
- Data quality from unreliable sources (Arbeitnow removed)
- Event loop blocking (fixed with `asyncio.to_thread`, commit `cd1f884`)

## Source references

- `main.py`, `render.yaml`, `.env.example`, `requirements.txt`
- `.github/workflows/eval.yml`, `.github/workflows/openwiki-update.yml`
- Commits `c995ad7` (Render deploy), `6ef4e7c` (port fix), `cd1f884` (async), `fee390c` (demo deployment)
