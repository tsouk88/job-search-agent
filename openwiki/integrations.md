---
type: Reference
title: Integrations
description: External service integrations for the job search agent — job APIs, LLM/orchestration stack, persistence, observability, UI contract, n8n automation, and the voice agent's separate service stack.
tags: [integrations, external-services, apis]
---

# Integrations

## Job APIs

The backend graph integrates with four public job sources:

- RemoteOK: `https://remoteok.com/api?tags=...`
- Himalayas: `https://himalayas.app/jobs/api/search?q=...&worldwide=true&sort=recent`
- Remotive: `https://remotive.com/api/remote-jobs?search=...`
- Jobicy: `https://jobicy.com/api/v2/remote-jobs?tag=...`

The graph encodes user text before sending it to the APIs and truncates descriptions to reduce payload size.

## LLM / orchestration stack

- Gemini 2.5 Flash is the main chat model, used for feedback extraction, CV upload, and the n8n evaluator (the search path itself is LLM-free).
- LangGraph orchestrates the fan-out fetch and `collect_results` ranking; the graph ends there, with no review or resume node.
- LangChain’s `init_chat_model` and `StrOutputParser` are used in the backend and eval runner.

## Persistence

- PostgreSQL via `langgraph.checkpoint.postgres.PostgresSaver` stores per-thread memory/state.
- The checkpointer is created in the FastAPI lifespan hook, so startup depends on the database.

## Observability and evals

- LangSmith tracing is enabled in the example environment.
- `eval_runner.py` creates a LangSmith evaluation run against `/ask`.
- The repo history suggests eval quality became a major concern after source filtering and source removal changes.

## UI contract

The frontend is intentionally thin and depends on these backend behaviors:

- `/ask` streams text that Markdown can render progressively
- `/upload` also streams text
- `/feedback` accepts JSON and returns a small confirmation object
- thread state is keyed by a browser-generated UUID stored in localStorage

## Optional automation

`n8n_workflow.json` integrates with:

- the backend `/evaluate` endpoint
- Gmail for email delivery
- scheduled execution in n8n

The included README screenshots in `assets/` document that automation path.

## Voice agent services

The [voice agent](voice-agent.md) uses a separate service stack from the text/REST backend:

- **Transport:** Daily (WebRTC) for real-time audio in/out
- **STT:** Deepgram for speech-to-text
- **TTS:** ElevenLabs for text-to-speech (requires a Premade voice ID)
- **LLM:** same Gemini model as the text agent via `voice_agent.py`
- **Checkpointer:** in-memory `MemorySaver` instead of PostgreSQL — sessions are stateless and short-lived

Environment variables for the voice layer (`voice/server/.env`): `DEEPGRAM_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `GOOGLE_API_KEY`, `DAILY_API_KEY`.

## Source references

- `main.py`
- `agent.py`
- `frontend/app/page.tsx`
- `eval_runner.py`
- `n8n_workflow.json`
- `assets/n8n_workflow.png`
- `assets/email_digest.png`
- `voice/server/bot.py`
- `voice_agent.py`
- `voice/README.md`
