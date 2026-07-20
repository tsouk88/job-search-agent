# Voice AI — Talk to the Job Search Agent

A voice interface for the [Job Search Agent](../README.md) — same LangGraph brain, spoken instead of typed. Built with [Pipecat](https://pipecat.ai).

## How it works

The core agent (`agent.py`, at the repo root) doesn't change — this is a thin voice layer on top of it.

```
Your voice → Deepgram (STT) → LangGraph agent → ElevenLabs (TTS) → spoken response
```

- **Transport:** Daily (WebRTC) — real-time audio in/out
- **STT:** Deepgram
- **TTS:** ElevenLabs
- **Brain:** the exact same `agent.py` graph used by the REST API — fan-out job search across 4 APIs, HITL feedback loop

### Session design

Voice sessions are stateless and short-lived, so they don't use the PostgreSQL checkpointer the text agent uses. Instead:

- Each call gets a fresh `VoiceSession` with an in-memory `MemorySaver` checkpointer and its own `thread_id`
- When the agent asks for feedback ("no MERN, no senior roles"), the session **caches the last search results** and filters them locally against the given keywords — no repeated API calls, no re-running the search on every round of feedback

This is a deliberate difference from the text agent's `/feedback` → `/ask` flow, which re-runs a fresh search each time (appropriate there, since the text agent persists across days and the next query may be completely different). In a single voice call, the query almost never changes mid-conversation — so caching + local filtering is faster and cheaper.

## Setup

> **Windows users:** Pipecat's Daily transport depends on `daily-python`, which has no native Windows build. Run this from **WSL2** (Ubuntu), not native Windows. Everything else in this repo runs fine on Windows — this constraint is specific to the voice layer.

```bash
cd voice/server
uv sync
cp .env.example .env   # add your API keys (see below)
uv run bot.py
```

This starts a local server at `http://localhost:7860` with the Pipecat Playground — open it in a browser, click Connect, and talk.

### Environment variables

```env
DEEPGRAM_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=      # must be a Premade voice — Library/Community voices require a paid ElevenLabs plan
GOOGLE_API_KEY=           # same Gemini key used by the main agent
DAILY_API_KEY=
```

Get a Deepgram key at [deepgram.com](https://deepgram.com) (free tier available), an ElevenLabs key at [elevenlabs.io](https://elevenlabs.io) (free tier, **pick a Premade voice**, not a Library one), and a Daily key at [dashboard.daily.co](https://dashboard.daily.co) (free tier, no card required for basic use).

## Known limitations

- Local, single-user demo — not deployed. Runs via Pipecat's built-in dev server + Playground UI.
- No conversation memory across calls (by design — each call is a fresh session).
- Filtering is keyword-based (extracted from your feedback via a small LLM call), not semantic — "no backend roles" won't catch a listing titled "Server Engineer" unless the word overlap is there.

## Project structure

```
voice/
└── server/
    ├── bot.py                   # Pipecat pipeline: transport, STT, TTS, wiring
    ├── voice_agent.py           # VoiceSession — stateless wrapper around agent.py's graph
    ├── langgraph_processor.py   # Bridges Pipecat frames <-> VoiceSession
    ├── pyproject.toml
    └── uv.lock
```

`voice_agent.py` imports `graph` directly from the root `agent.py` — no duplication, same agent, two interfaces.