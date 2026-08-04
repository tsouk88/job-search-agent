---
type: Reference
title: Integrations
description: External service integrations — four job APIs with their query patterns, the LLM and LangGraph stack, PostgreSQL persistence, LangSmith observability, the frontend HTTP contract, n8n automation, the MCP client contract, and the voice agent service stack.
tags: [integrations, external-services, apis, job-boards, llm, persistence]
---

# Integrations

## Job APIs

Four public job sources, each with a different schema and query pattern:

| Source | URL pattern | Query encoding | Rate limiting |
|---|---|---|---|
| RemoteOK | `https://remoteok.com/api?tags={query}` | First keyword only, URL-encoded | Returns 429 on overuse |
| Himalayas | `https://himalayas.app/jobs/api/search?q={query}&worldwide=true&sort=recent` | Full query, URL-encoded | Returns 429 |
| Remotive | `https://remotive.com/api/remote-jobs?search={query}` | Full query, URL-encoded | Returns 429 |
| Jobicy | `https://jobicy.com/api/v2/remote-jobs?tag={query}` | Full query, URL-encoded | Returns 429 |

All fetchers: 30-second timeout, `User-Agent: Mozilla/5.0` (RemoteOK only), catch `RequestException` and return empty list on failure. RemoteOK listings are re-checked against their own title (tags are SEO filler). Each fetcher caps at 10 raw listings for cost control.

Arbeitnow was removed (commit `b3738bc`) — its remote flag was unreliable and it hurt eval quality.

## LLM and orchestration stack

- **Gemini 2.5 Flash** — the only LLM, initialized via `init_chat_model("google_genai:gemini-2.5-flash", temperature=0.1, max_retries=10)`. Used for:
  - `/feedback` — extracting avoidance keywords from user feedback
  - `/upload` — compressing a CV into a keyword summary
  - `/evaluate` — scoring job listings against a hardcoded profile
  - `voice_agent.py` — keyword extraction for voice feedback
  - `eval_runner.py` — LangSmith judge with structured output
- **LangGraph** — orchestrates the fan-out fetch and `collect_results` ranking via the `Send` API
- **LangChain** — `init_chat_model` and `StrOutputParser` chain (`chain = llm | parser`)

The search path itself is LLM-free. LLM calls are bounded: 100-char feedback, 5MB/5-page PDF, auth-gated `/evaluate`.

## Persistence

Three models depending on interface:

| Interface | Checkpointer | Scope |
|---|---|---|
| REST (`main.py`) | `PostgresSaver` | Per-thread, persists across days |
| MCP (`mcp_server.py`) | In-process `_cache` dict (4h TTL) | Per-query, per-process |
| Voice (`voice_agent.py`) | `MemorySaver` + `last_jobs` list | Per-call, in-memory only |

The REST checkpointer is created in the FastAPI `lifespan` hook, so startup depends on the database. `PostgresSaver.setup()` creates the checkpoint tables.

## Observability

- **LangSmith tracing** — enabled in production via `LANGSMITH_TRACING=true` in `render.yaml`. EU endpoint: `https://eu.api.smith.langchain.com`
- **LangSmith evals** — `eval_runner.py` uses `langsmith.Client()` against the `job-search-eval` dataset

Token usage appears only for feedback extraction, CV upload, and the n8n evaluator — the search path makes no LLM calls.

## Frontend HTTP contract

The frontend ([chat UI](frontend/chat-ui.md)) depends on:

| Endpoint | Method | Request body | Response |
|---|---|---|---|
| `/ask` | POST | `{user_input: str, thread_id: str}` | Plain text (markdown), streamed |
| `/feedback` | POST | `{feedback: str, thread_id: str}` | Plain text (markdown) |
| `/reset` | POST | `{user_input: str, thread_id: str}` | Plain text (markdown) |
| `/upload` | POST | `FormData(file, thread_id)` | Plain text (markdown), streamed |

Thread state is keyed by a browser-generated UUID stored in `localStorage`. The frontend routes by prefix: `reset` → `/reset`, `no `/`skip ` → `/feedback`, else → `/ask`.

## MCP client contract

The [MCP server](mcp-server.md) exposes one stdio tool:

```python
search_remote_jobs(query: str, exclude_keywords: list[str] = []) -> list[dict]
```

Returns a list of normalized job dicts (`position`, `company`, `location`, `salary`, `description`, `apply_url`). No thread state, no database, no LLM. The client's conversation is the memory.

## n8n automation

The [n8n workflow](operations/n8n-automation.md) integrates with:
- `POST /ask` — returns the formatted digest
- `POST /feedback` — sets persistent filters (optional, one-time)
- Gmail — email delivery
- Schedule trigger — every 12 hours

The workflow holds no filtering logic. It calls the backend and mails the result.

## Voice agent services

The [voice agent](voice-agent.md) uses a separate service stack:

| Service | Purpose |
|---|---|
| Daily (WebRTC) | Real-time audio transport |
| Deepgram | Speech-to-text |
| ElevenLabs | Text-to-speech (Premade voice required) |
| Gemini 2.5 Flash | Keyword extraction for voice feedback |

Environment variables (`voice/server/.env`): `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `GOOGLE_API_KEY`, `DAILY_API_KEY`.

`daily-python` has no native Windows build — run the voice server from WSL2.

## Source references

- `agent.py` — job API fetchers, scoring, filtering
- `main.py` — endpoint definitions, LLM chain, checkpointer
- `mcp_server.py` — MCP tool, cache
- `voice_agent.py`, `voice/server/bot.py` — voice pipeline
- `frontend/app/page.tsx` — HTTP client
- `n8n_workflow.json` — automation
- `render.yaml` — deployment config
