---
type: Subsystem
title: Voice Agent
description: Voice interface for the job search agent using Pipecat, Deepgram STT, ElevenLabs TTS, and Daily WebRTC transport. Shares the same LangGraph brain as the REST API but uses in-memory state and local result caching for faster feedback loops.
tags: [voice, pipecat, deepgram, elevenlabs, daily, webrtc, langgraph]
---

# Voice Agent

A voice interface layer that lets users talk to the same LangGraph job search agent powering the REST API. Built with [Pipecat](https://pipecat.ai) and runs as a local single-user demo server.

## Architecture

```
User voice → Deepgram (STT) → LangGraph agent → ElevenLabs (TTS) → spoken response
```

Transport is Daily (WebRTC) for real-time audio. The pipeline is defined in `voice/server/bot.py`:

```
transport.input() → STT → user_aggregator → LangGraphProcessor → TTS → transport.output() → assistant_aggregator
```

Key design decision: voice sessions are **stateless and short-lived**, using an in-memory `MemorySaver` checkpointer instead of the PostgreSQL `PostgresSaver` the text agent uses. Each call gets a fresh `VoiceSession` with its own `thread_id`.

## How feedback differs from the text agent

The text agent's `/feedback` → `/ask` flow re-runs a fresh search each time because conversations persist across days and queries may change. In a voice call the query almost never changes mid-conversation, so the voice agent:

1. **Caches the last search results** in `VoiceSession.last_jobs`
2. Extracts avoidance keywords from user feedback via a small Gemini call
3. **Filters the cached results locally** — no repeated API calls, no re-running the search

This is faster and cheaper for the voice use case.

## Key files

- `voice_agent.py` — `VoiceSession` class wrapping the root `agent.py` graph with in-memory state, result caching, and local keyword filtering
- `voice/server/bot.py` — Pipecat pipeline wiring: transport, STT, TTS, and the `LangGraphProcessor`
- `voice/server/langgraph_processor.py` — `LangGraphProcessor` bridges Pipecat frames to `VoiceSession`, routing messages to `run()` or `resume()` based on conversation state
- `voice/server/pyproject.toml` — dependencies managed with `uv`
- `voice/README.md` — setup instructions and known limitations

## Running

```bash
cd voice/server
uv sync
cp .env.example .env   # add API keys
uv run bot.py
```

Starts a local server at `http://localhost:7860` with the Pipecat Playground UI.

### Required environment variables

- `DEEPGRAM_API_KEY` — speech-to-text
- `ELEVENLABS_API_KEY` — text-to-speech
- `ELEVENLABS_VOICE_ID` — must be a Premade voice (Library/Community voices require a paid plan)
- `GOOGLE_API_KEY` — same Gemini key used by the main agent
- `DAILY_API_KEY` — WebRTC transport

> **Windows note:** `daily-python` has no native Windows build. Run the voice server from WSL2 (Ubuntu), not native Windows.

## Known limitations

- Local, single-user demo — not deployed
- No conversation memory across calls (by design)
- Filtering is keyword-based, not semantic — "no backend roles" won't catch a listing titled "Server Engineer" unless word overlap exists
