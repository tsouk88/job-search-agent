---
type: Source Map
title: Source Map
description: Map of all entry points, supporting files, and the voice agent subsystem in the repository, with responsibilities and suggested edit order.
tags: [source-map, architecture, entry-points]
---

# Source map

## Entry points

- `main.py` — FastAPI server, endpoints, streaming, PDF upload, rate limiting, persistence setup
- `agent.py` — LangGraph workflow, source fetchers, deduplication, two-pass ranking, thread memory filter
- `frontend/app/page.tsx` — client UI for search, feedback, CV upload, streamed rendering
- `eval_runner.py` — LangSmith evaluation harness

## Voice agent subsystem

- `voice_agent.py` — `VoiceSession` wrapper around the root `agent.py` graph with in-memory `MemorySaver`, result caching, and local keyword filtering
- `voice/server/bot.py` — Pipecat pipeline: Daily transport, Deepgram STT, ElevenLabs TTS, `LangGraphProcessor`
- `voice/server/langgraph_processor.py` — bridges Pipecat frames to `VoiceSession.run()` / `resume()`
- `voice/server/pyproject.toml` — voice subsystem dependencies managed with `uv`
- `voice/README.md` — setup instructions and known limitations

## Supporting files

- `README.md` — product-facing overview, architecture sketch, setup notes, and workflow examples
- `.env.example` — required environment variable names and sample values
- `requirements.txt` — Python dependency surface
- `n8n_workflow.json` — optional automation workflow definition
- `assets/n8n_workflow.png` and `assets/email_digest.png` — documentation images for automation
- `.github/workflows/openwiki-update.yml` — documentation refresh automation

## What each source area is responsible for

### `agent.py`

Holds the real search graph and most business logic:

- source fan-out
- API calls to remote job feeds
- truncation for trace-size control
- deduplication
- two-pass ranking (titles, then descriptions)
- thread memory applied as a post-graph filter in `main.py`

### `main.py`

Owns the API surface and runtime composition:

- app startup / lifespan
- checkpoint wiring
- prompt formatting for streamed results
- `/ask`, `/upload`, `/feedback`, `/reset`, `/evaluate`
- rate limiting and CORS

### `frontend/app/page.tsx`

Implements the user interaction model:

- one conversation thread per browser session
- direct calls to backend endpoints
- markdown rendering of streamed job output
- special handling for exclusion feedback

### `eval_runner.py`

Captures the contract the repo cares about:

- query → search response
- reference output comparison
- judge-based scoring

## Suggested edit order

When changing behavior, update in this order:

1. `agent.py` if the search graph or job-source behavior changes
2. `main.py` if the API contract or formatting changes
3. `frontend/app/page.tsx` if user interaction changes
4. `eval_runner.py` if expected quality behavior changes
5. `README.md` if user-facing docs need to stay aligned

## Source-history note

The commit trail shows the project moving from a small multi-source job fetcher toward a more production-like system with:

- parallel source fan-out
- persistent thread memory
- streaming UX
- job-source pruning for quality
- eval-driven regression control
