---
type: Source Map
title: Source Map
description: File-level map of all entry points, supporting files, voice and evals subsystems, deployment files, and authoring-convention skills — with responsibilities and suggested edit order.
tags: [source-map, architecture, entry-points, files]
---

# Source map

## Entry points

| File | Role | Lines |
|---|---|---|
| `main.py` | FastAPI server, 5 endpoints, PostgresSaver lifespan, LLM chain, rate limiting, CORS, PDF upload | ~230 |
| `agent.py` | LangGraph graph — 4 fetchers, fan-out via Send, collect_results, scoring, normalization, filtering | ~280 |
| `mcp_server.py` | MCP stdio server — one read-only tool, in-process cache (4h TTL) | ~45 |
| `voice_agent.py` | VoiceSession — in-memory MemorySaver, result caching, local re-filtering | ~51 |
| `frontend/app/page.tsx` | Next.js chat UI — message routing, streaming reader, markdown rendering, theme toggle | ~343 |
| `eval_runner.py` | LangSmith eval harness — posts 22 queries to /ask, Gemini judge | ~71 |

## Voice agent subsystem

| File | Responsibility |
|---|---|
| `voice_agent.py` | `VoiceSession` wrapping `agent.py` graph with `MemorySaver`, `last_jobs` cache, `run`/`reset`/`resume` |
| `voice/server/bot.py` | Pipecat pipeline: Daily transport, Deepgram STT, ElevenLabs TTS, `LangGraphProcessor` |
| `voice/server/langgraph_processor.py` | Bridges Pipecat frames to `VoiceSession`; routes by `FEEDBACK_WORDS`, `DETAIL_PREFIXES`, "reset", default search |
| `voice/server/pyproject.toml` | Voice subsystem deps managed with `uv` (Pipecat, LangChain, Gemini) |
| `voice/README.md` | Setup, architecture, known limitations |

## Evals subsystem

| File | Responsibility |
|---|---|
| `eval_runner.py` | LangSmith eval — 22 queries, Gemini judge, `relevant/total` score |
| `evals/check_reward.py` | Harbor build verdict — reads `result.json`, exits 0/1/2 |
| `evals/harbor_agents/pipeline_agent.py` | Harbor adapter — uploads `agent.py` + `mcp_server.py`, runs `run_pipeline.py` |
| `evals/harbor_agents/run_pipeline.py` | Harness — patches `requests.get` with frozen APIs, calls `search_remote_jobs`, writes `prefilter.json` + `output.json` |
| `evals/filter-exclusion-senior/` | Harbor task — `task.toml`, `instruction.md`, `environment/`, `tests/` |
| `evals/filter-exclusion-senior/environment/frozen_apis.py` | Host router replacing `requests.get` with fixture reads, blocks all other methods |
| `evals/filter-exclusion-senior/environment/fixtures/` | Frozen JSON responses from 4 APIs (captured 04/08/2026) |
| `evals/filter-exclusion-senior/tests/test_outputs.py` | Deterministic verifier — 4 pytest assertions |
| `evals/filter-exclusion-senior/tests/expected.json` | Hand-written expected keep/drop sets |
| `evals/specs/filter-exclusion-senior/` | Design documents (task, harness, environment) |
| `evals/configs/no-network.yaml` | Docker Compose overlay: `network_mode: none` |

## Deployment and CI

| File | Responsibility |
|---|---|
| `render.yaml` | Render backend deployment (Python, free, Frankfurt, healthcheck /docs) |
| `.github/workflows/eval.yml` | Harbor eval CI — runs on push/PR to agent.py/mcp_server.py/evals |
| `.github/workflows/openwiki-update.yml` | Monthly OpenWiki documentation refresh |
| `.env.example` | Environment variable names and sample values |
| `requirements.txt` | Python dependency surface (FastAPI, LangGraph, LangChain, mcp, pdfplumber, slowapi) |
| `n8n_workflow.json` | Optional n8n scheduled digest workflow |
| `assets/n8n_workflow.png`, `assets/email_digest.png` | Documentation images |

## Authoring conventions

| File | Purpose |
|---|---|
| `skills/mermaid-diagrams/SKILL.md` | Mermaid diagram authoring rules for wiki pages |
| `skills/write-connector.md`, `skills/write-connector/SKILL.md` | OpenWiki connector authoring guide |

Mermaid diagrams across this wiki follow `skills/mermaid-diagrams/SKILL.md`.

## What each source area is responsible for

### `agent.py`

Holds the search graph and the core business logic:
- `SENIORITY`, `GENERIC` word sets and `TITLE_WEIGHT`, `MAX_RESULTS` constants
- `signal_tokens` — strips generic words from queries
- `score_job` — title-weighted scoring (`title_hits * 10 + desc_hits`)
- `filter_jobs` — exclusion logic with seniority/full-text branch split
- `normalize_jobs` — field unification, mojibake repair, hash dedup
- `fetch_jobs`/`fetch_sjobs`/`fetch_tjobs`/`fetch_fjobs` — 4 API fetchers
- `collect_results` — dedup by URL, score, keep title matches, sort, cap at 12
- `fan_out` — Send-based parallel dispatch
- `graph` — the StateGraph wiring

### `main.py`

Owns the API surface and runtime composition:
- `lifespan` — PostgresSaver setup and graph compilation
- `run_agent` — graph invocation helper
- LLM chain — `init_chat_model` + `StrOutputParser`
- `/ask` — three-condition cache, normalize, filter, format markdown
- `/evaluate` — auth-gated LLM evaluation
- `/upload` — async PDF parsing, CV→keywords, search
- `/feedback` — Gemini keyword extraction, memory update, re-filter
- `/reset` — clear memory, return unfiltered cached jobs
- `format_jobs_markdown`, `active_filters_line` — response formatting

### `frontend/app/page.tsx`

- `sendMessage` — routes by prefix (reset/feedback/search)
- `handleFileUpload` — FormData upload to `/upload`
- Streaming reader — reads `res.body` chunks, appends to message
- `getThreadId` — localStorage UUID
- ReactMarkdown rendering with custom components

## Suggested edit order

When changing behavior, update in this order:

1. `agent.py` — if the search graph, scoring, or filtering changes
2. `main.py` — if the API contract, caching, or formatting changes
3. `mcp_server.py` — if the MCP tool surface changes (usually inherits from agent changes)
4. `voice_agent.py` + `voice/server/langgraph_processor.py` — if voice routing or memory changes
5. `frontend/app/page.tsx` — if user interaction or routing changes
6. `eval_runner.py` or `evals/` — if expected quality behavior changes
7. `n8n_workflow.json` — if the automation contract changes
8. `README.md` — if user-facing docs need to stay aligned

## Source-history note

The commit trail shows the project moving from a small multi-source job fetcher toward a production-like system with:
- Parallel source fan-out (`a246e56`)
- Persistent thread memory (`6e0cf7f`)
- Streaming UX (`a454953`)
- LLM removed from search path (`3fca572`, `dd282ff`)
- Deterministic filtering eval (`bc47271`, `df2b58a`)
- MCP server (`2511139`)
- Voice interface (`64f458d`)
