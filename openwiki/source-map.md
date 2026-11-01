---
type: Source Map
title: Source Map
description: File-level map of all entry points, supporting files, voice and evals subsystems, deployment files, and authoring-convention skills — with responsibilities and suggested edit order.
tags: [source-map, architecture, entry-points, files]
sources:
  - id: openwiki-source-eca60e2ced68ba99bd0ac710
    resource: repo://agent.py
  - id: openwiki-source-f1644da1c1a64a6a6567706b
    resource: repo://eval_runner.py
  - id: openwiki-source-ab20f2fabcf9dffc06e9a9a7
    resource: repo://evals/filter-exclusion-senior/tests/expected.json
  - id: openwiki-source-6f3a365387ad1dfc55a94d24
    resource: repo://evals/filter-exclusion-senior/tests/test_outputs.py
  - id: openwiki-source-18837785d6eee548467c07ac
    resource: repo://evals/harbor_agents/pipeline_agent.py
  - id: openwiki-source-1691a76fbd7a6781b3420f6c
    resource: repo://evals/harbor_agents/run_pipeline.py
  - id: openwiki-source-46c84c82a35e96f529aef1f3
    resource: repo://evals/specs/filter-exclusion-senior/environment.md
  - id: openwiki-source-502b8ec3f7fed4ad66c8f8dd
    resource: repo://evals/specs/filter-exclusion-senior/harness.md
  - id: openwiki-source-e3ff670d1996f2afaaf51e04
    resource: repo://evals/specs/filter-exclusion-senior/task.md
  - id: openwiki-source-8c042cb3c17efe62134801ac
    resource: repo://frontend/app/page.tsx
  - id: openwiki-source-ab9b6a971a877d6f6da86dd0
    resource: repo://laya/Dockerfile
  - id: openwiki-source-833e692518af9eeaf8564cc6
    resource: repo://main.py
  - id: openwiki-source-7a041713b68b973227e27f3e
    resource: repo://mcp_server.py
  - id: openwiki-source-f70156010a8eb5325870bfc6
    resource: repo://render.yaml
  - id: openwiki-source-373640cd8a0886cee69db282
    resource: repo://requirements.txt
  - id: openwiki-source-3ea4f69fcc0222dbd310ddfc
    resource: repo://tasks.py
  - id: openwiki-source-3a30c14a947fb74b6b9d65b7
    resource: repo://voice_agent.py
generated: { by: "openwiki/0.6.1", at: "2026-11-01T14:50:14.085Z" }
verified:
  - by: openwiki/0.6.1
    at: 2026-11-01T15:48:11.877Z
---

# Source map

## Entry points

| File | Role | Lines |
|---|---|---|
| `main.py` | FastAPI server — 10 endpoints, `PostgresSaver` + `InMemorySaver` lifespan, Redis rate-limiter/job cache/Gemini budget, Celery enqueue, `keycheck` header auth, async PDF upload, `/digest` n8njobs dedup, `/health` | ~333 |
| `agent.py` | LangGraph graph — 5 fetchers, fan-out via `Send`, `collect_results`, scoring, normalization, filtering, location/age checks, Workable helpers, Remotive feed cache | ~597 |
| `mcp_server.py` | MCP stdio server — one read-only tool, in-process cache (4h TTL) | ~47 |
| `voice_agent.py` | `VoiceSession` — in-memory `MemorySaver`, `last_jobs` cache, local re-filtering | ~51 |
| `frontend/app/page.tsx` | Next.js chat UI — message routing, streaming reader, markdown rendering, country dropdown, theme toggle, async CV upload polling | ~423 |
| `eval_runner.py` | LangSmith eval harness — posts queries to `localhost:8002/askeval`, Gemini full/listing judges, Jev (OpenRouter), Laya judges | ~238 |

## Voice agent subsystem

| File | Responsibility |
|---|---|
| `voice_agent.py` | `VoiceSession` wrapping `agent.py` graph with `MemorySaver`, `last_jobs` cache, `run`/`reset`/`resume` |
| `voice/server/bot.py` | Pipecat pipeline: Daily transport, Deepgram STT, ElevenLabs TTS, `LangGraphProcessor` |
| `voice/server/langgraph_processor.py` | Bridges Pipecat frames to `VoiceSession`; routes by `FEEDBACK_WORDS`, `DETAIL_PREFIXES`, "reset", default search |
| `voice/server/pyproject.toml` | Voice subsystem deps managed with `uv` (Pipecat, LangChain, Gemini) |
| `voice/README.md` | Setup, architecture, known limitations |

## Async task subsystem

| File | Responsibility |
|---|---|
| `tasks.py` | Celery app (`celery_app`, broker+result backend = `REDIS_URL`) and the `filework` task — async CV parse, graph search, normalize/filter, markdown formatting |
| `Redis` | Broker and result backend for Celery; also the storage backing the slowapi rate limiter, the per-query job cache, and the Gemini daily-call budget (see `main.py`) |

The async path exists so the PDF upload does not block the event loop. `main.py` `/upload` reads the file, parses the PDF in a thread (`asyncio.to_thread`), checks the Gemini budget, then enqueues `filework.delay(...)` and immediately returns `{job_id}`. `tasks.py`'s `filework` reconstructs a `PostgresSaver`-compiled graph, extracts CV keywords via the structured-output chain, runs the search, and returns the formatted markdown. The frontend polls `GET /jobs/{job_id}` (backed by `AsyncResult` over the Redis result backend) until the task is `SUCCESS` or `FAILURE`.

## Evals subsystem

| File | Responsibility |
|---|---|
| `eval_runner.py` | LangSmith eval — posts each query to `localhost:8002/askeval` (auth `EVALS`), returns `{md, jobs}`; four evaluators (`gemini_full_correctness`, `gemini_listing_correctness`, `jev_correctness`, `laya_correctness`); `empty_ok` short-circuits an accepted-empty response to a score of 1.0 without invoking a judge |
| `evals/check_reward.py` | Harbor build verdict — reads `result.json`, exits 0/1/2 (0 pass, 1 eval failed, 2 infrastructure error) |
| `evals/harbor_agents/pipeline_agent.py` | Harbor adapter (`jobsearch-pipeline` v1.0.0) — uploads `agent.py` + `mcp_server.py` + `run_pipeline.py` unmodified, records stdout/stderr/return code; no model, no setup |
| `evals/harbor_agents/run_pipeline.py` | Harness — patches `requests.get` via `frozen_apis` before fetchers load, imports `mcp_server.search_remote_jobs`, parses the fenced JSON request from `instruction.md`, writes `prefilter.json` + `output.json` |
| `evals/filter-exclusion-senior/` | Harbor task — `task.toml`, `instruction.md`, `environment/`, `tests/` |
| `evals/filter-exclusion-senior/environment/frozen_apis.py` | Host router replacing `requests.get` with fixture reads, blocks all other methods |
| `evals/filter-exclusion-senior/environment/fixtures/` | Frozen JSON responses from 4 APIs + Workable HTML pages (search + per-listing) |
| `evals/filter-exclusion-senior/environment/Dockerfile` | Eval environment image — requests, langgraph, mcp, pytest, pytest-json-ctrf; copies `frozen_apis.py` + fixtures |
| `evals/filter-exclusion-senior/tests/test_outputs.py` | Deterministic verifier — 5 pytest assertions (environment guard, no seniority-in-title survivor, no free keyword survivor, nothing valid dropped, exact result set) |
| `evals/filter-exclusion-senior/tests/expected.json` | Hand-written expected keep/drop sets — 6 keep / 6 drop |
| `evals/filter-exclusion-senior/tests/test.sh` | Runs pytest under the container, writes `1`/`0` to `reward.txt` |
| `evals/specs/filter-exclusion-senior/` | Design notes for the eval: `task.md` (capability, request, pass condition, negative control), `harness.md` (what Harbor runs as the agent, adapter, fidelity limits), `environment.md` (frozen dependencies, network policy, validation gate), `harness-digest.txt` |
| `evals/configs/no-network.yaml` | Docker Compose overlay: `network_mode: none` |
| `laya/Dockerfile` | Local judge image — `laya[serve]==0.3.28` (`laya-serve`), the Laya multilingual model backing `laya_correctness` in `eval_runner.py` |

## Deployment and CI

| File | Responsibility |
|---|---|
| `render.yaml` | Render backend deployment (Python, free, Frankfurt); `startCommand` runs a Celery worker (`--pool=solo`) and `uvicorn main:app`; `healthCheckPath: /health`; managed env vars incl. `REDIS_URL` |
| `.github/workflows/eval.yml` | Harbor eval CI — runs on push/PR to `agent.py`/`mcp_server.py`/`evals`; `harbor run` + `check_reward.py` |
| `.github/workflows/openwiki-update.yml` | Monthly OpenWiki documentation refresh (`cron: 0 6 1 * *`) — installs `openwiki`, runs `openwiki code --update`, opens a PR |
| `.env.example` | Environment variable names and sample values — `GEMINI_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `EVALUATE_TOKEN`, `N8N_DEDUPE`, `EVALS`, `OPENROUTER_API_KEY`, `ALLOWED_ORIGINS`, LangSmith vars |
| `requirements.txt` | Python dependency surface — FastAPI, LangGraph, LangChain, `celery`, `redis`, `mcp`, `langchain-protocol`, pdfplumber, slowapi |
| `n8n_workflow.json` | Optional n8n scheduled digest workflow — `POST /digest` (returns `{md, links}` after dedup) → If links not empty → Gmail → `POST /digest/sent` |
| `assets/n8n_workflow.jpg`, `assets/email_digest.png` | Documentation images |

## Authoring conventions

| File | Purpose |
|---|---|
| `skills/mermaid-diagrams/SKILL.md` | Mermaid diagram authoring rules for wiki pages |
| `skills/write-connector.md`, `skills/write-connector/SKILL.md` | OpenWiki connector authoring guide |

Mermaid diagrams across this wiki follow `skills/mermaid-diagrams/SKILL.md`.

## What each source area is responsible for

### `agent.py`

Holds the search graph and the core business logic (~597 lines). It is the single source of truth for fetching, scoring, filtering, and normalizing listings; every interface (`main.py`, `mcp_server.py`, `voice_agent.py`, `tasks.py`) imports `graph`, `normalize_jobs`, and `filter_jobs` from here.

- `SENIORITY`, `GENERIC` word sets and `TITLE_WEIGHT`, `MAX_RESULTS`, `MAX_AGE_DAYS`, `TAG_LIMIT`, `ENOUGH` constants
- `signal_tokens` — strips generic words from queries (falls back to every word when the query is only generic ones)
- `canon` / `ALIASES` — spell synonyms one way ("machine learning" → "ml") so one token matches all forms; used by `distinctive_tokens`, `job_title`, `score_job`
- `distinctive_tokens` — the narrowing words, in order, deduplicated and capped at `TAG_LIMIT`
- `title_hit` — whole-word match with optional plural/`js`/version suffix (`react` hits `reactjs`, `python` hits `python3`)
- `score_job` — title-weighted scoring: `title_hits * TITLE_WEIGHT + min(desc_hits + gen_hits + frequency_bonus, 9)`
- `filter_jobs` — exclusion logic; seniority terms matched against title only (`title_only=SENIORITY`), every other keyword against title + description + location
- `normalize_jobs` — field unification, mojibake repair (`fix_mojibake`), HTML strip, hash dedup
- `job_location` / `job_company` / `job_title` — field accessors that read whichever spelling the source uses
- `location_ok` / `job_is_recent` — country and age gates applied in `collect_results` (not by the fetchers); `location_ok` passes worldwide/unset locations, `job_is_recent` keeps undated and unparseable listings
- `remotive_feed` — module-level cached Remotive feed (6h TTL) shared across calls; a failed refresh keeps the previous list
- Workable helpers — `workable_urls` (search-page ItemList links), `workable_title` (title from slug), `workable_key` (title+company dedup key), `workable_job` (JobPosting JSON-LD to dict)
- Five fetchers: `fetch_jobs` (RemoteOK, tag-iterated), `fetch_sjobs` (Himalayas, search API), `fetch_tjobs` (Remotive, cached feed), `fetch_fjobs` (Jobicy, tag+geo, falls back to unfiltered on 400), `fetch_wjobs` (Workable, two-round URLs→postings)
- `collect_results` — dedup by company+title, `location_ok` + `job_is_recent` gates, score, keep `>= TITLE_WEIGHT`, sort, cap at `MAX_RESULTS`, truncate descriptions to 2000 chars
- `fan_out` — `Send`-based parallel dispatch to all five fetchers
- `graph` — the `StateGraph` wiring: `fan_out` from `START`, each fetcher → `collect_results` → `END`

### `main.py`

Owns the API surface and runtime composition (~333 lines):

- `lifespan` — `PostgresSaver` setup for `agent` and `InMemorySaver` for `eval_agent`; both are compiled `graph` instances
- `run_agent` — graph invocation helper (in `helper.py`), passes `country` into state
- LLM chain — `init_chat_model` + `StrOutputParser` (in `helper.py`), `max_retries=2`
- `keycheck(envname)` — returns a FastAPI `Depends` that reads the `x-api-key` header and uses `secrets.compare_digest` against the named env var; gates `/evaluate` (`EVALUATE_TOKEN`), `/digest` + `/digest/sent` (`N8N_DEDUPE`), `/askeval` (`EVALS`)
- `check_gemini_budget` / `jobcache` — Redis-backed per-day Gemini-call budgets and per-query+country job cache (14400s TTL)
- `searchhelper` — four-condition cache (query, country, fetch time, 14400s TTL): hit Redis cache, else run the graph, else reuse the checkpointer state
- `/ask` — search, normalize, filter, format markdown
- `/evaluate` — `EVALUATE_TOKEN` auth, prompt-injection guard in the system prompt (job content treated as data, never commands)
- `/upload` — async PDF parsing (5MB, pdfplumber, first 5 pages), CV→keywords, enqueue Celery `filework`, returns `{job_id}`
- `/jobs/{job_id}` — poll Celery `AsyncResult` (60/min), returns `done`/`failed`/`pending`
- `/digest` — `N8N_DEDUPE` auth; dedups filtered jobs against the Postgres `n8njobs` table, returns `{md, links}`
- `/digest/sent` — `N8N_DEDUPE` auth; inserts sent links into `n8njobs` (`on conflict do nothing`)
- `/feedback` — Gemini keyword extraction, memory update, re-filter
- `/reset` — clear memory, return unfiltered cached jobs
- `/health` — Redis ping + Celery worker ping; 503 if the worker has been unreachable past `PING_TIME`
- `/askeval` — `EVALS` auth; runs `searchhelper` against `eval_agent` (the `InMemorySaver` graph), returns `{jobs, md}` for the eval runner
- `SearchInput` — carries `user_input`, `thread_id`, `country`
- `format_jobs_markdown` / `active_filters_line` / `site_of` — response formatting (in `helper.py`): per-board site names (`SITE_NAMES`), showing country + active filters footer, source attribution line

### `tasks.py`

The Celery worker (~36 lines) — the only thing that runs off the web event loop. `celery_app` uses `REDIS_URL` as both broker and result backend. The `filework` task is the body of async CV upload: it builds a `PostgresSaver`-compiled `graph`, calls the structured-output chain to extract up to ten CV keywords (most important first), runs the search, and returns `format_jobs_markdown`. The web server enqueues it from `/upload` and the frontend reads its result via `/jobs/{job_id}` against the Redis result backend.

### `frontend/app/page.tsx`

Next.js chat UI (~423 lines):

- `sendMessage` — routes by prefix (`reset` → `/reset`, `no `/`skip ` → `/feedback`, else `/ask`)
- `handleFileUpload` — `FormData` upload to `/upload`, carries `country`; then `waitForJob` polls `/jobs/{job_id}`
- `waitForJob` — polls `/jobs/{job_id}` every 2s up to 120s, returns `done` result or `failed` detail
- Streaming reader — reads `res.body` chunks, appends to message
- `getThreadId` — `localStorage` UUID
- Country dropdown — `COUNTRIES` list, selected value persisted in `localStorage` and read via `useSyncExternalStore` (server renders "All locations", browser picks up the saved choice after hydration)
- `ReactMarkdown` rendering with custom `ul`/`li`/`a`/`code`/`strong` components, `remarkGfm`

### `conversation_history/`

An empty placeholder directory — not a source. It is not imported by any entry point and contributes no behavior; the persisted thread/conversation state lives in the Postgres checkpointer (and the Redis cache), not here.

## Suggested edit order

When changing behavior, update in this order. A change to `agent.py` that touches the graph, scoring, filtering, or normalization propagates to **all four interfaces** (`main.py`, `mcp_server.py`, `voice_agent.py`, `tasks.py`) because they import `graph`, `normalize_jobs`, and `filter_jobs` directly — update the affected interface contracts in lockstep.

1. `agent.py` — if the search graph, scoring, filtering, normalization, or any fetcher changes. This affects all four interfaces.
2. `main.py` — if the API contract, caching, `format_jobs_markdown`/`active_filters_line`/`site_of` formatting, `keycheck` auth, `/digest` dedup, or `/evaluate` auth/guard changes.
3. `tasks.py` — if the async CV-upload task contract or its Celery wiring changes (also touches `REDIS_URL` and `helper.py`).
4. `mcp_server.py` — if the MCP tool surface changes (usually inherits from `agent.py` changes).
5. `voice_agent.py` + `voice/server/langgraph_processor.py` — if voice routing or memory changes.
6. `frontend/app/page.tsx` — if user interaction, country dropdown, upload polling, or routing changes.
7. `eval_runner.py` or `evals/` — if expected quality behavior changes; the Harbor `filter-exclusion-senior` task freezes `agent.py` + `mcp_server.py` by digest, so a change to either invalidates prior run evidence.
8. `n8n_workflow.json` — if the automation contract changes.
9. `README.md` — if user-facing docs need to stay aligned.

## Source-history note

The commit trail shows the project moving from a small multi-source job fetcher toward a production-like system with:
- Parallel source fan-out (`a246e56`)
- Persistent thread memory (`6e0cf7f`)
- Streaming UX (`a454953`)
- LLM removed from search path (`3fca572`, `dd282ff`)
- Deterministic filtering eval (`bc47271`, `df2b58a`)
- MCP server (`2511139`)
- Voice interface (`64f458d`)
