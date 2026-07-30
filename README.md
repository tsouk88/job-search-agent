# Job Search AI Agent

An AI-powered remote job search assistant. Type in your desired job keywords and the agent searches, filters, and presents the best matches for you. Talk to it instead, if you'd rather — see [Voice AI](#️-voice-ai).

⚡ Instant results | 💰 $0 per search — searching and filtering are fully deterministic

If you find this useful, give it a ⭐️ — it helps others discover the project!

---

## What it does

The agent connects to 4 job APIs simultaneously:

- [RemoteOK API](https://remoteok.com/api)
- [Himalayas API](https://himalayas.app/jobs/api)
- [Remotive API](https://remotive.com/api/remote-jobs)
- [Jobicy.com](https://jobicy.com/api/v2/remote-jobs)

Results are scored, ranked and filtered in plain Python — no model in the search path. An LLM is still used where judgement genuinely helps: turning your spoken feedback into filter keywords, reading your CV, and scoring listings for the n8n digest.

### Why no LLM in the search path

The agent originally passed every fetched listing through Gemini to decide relevance. That worked, but it hid a bug: irrelevant results (Marketing, Janitor) were never filtered out at fetch time — the model just declined to print them. The moment you asked for them a second way, they came back.

Filtering at the source instead fixed the bug, removed the cost, and made results reproducible. Same quality, measured on the same queries.

---

## How it works

Built with **LangGraph** at its core. The graph uses a **fan-out architecture** — the agent spawns parallel fetch nodes using LangGraph's `Send` API. Results are deduplicated, scored for relevance against your query, ranked, and stored.

```mermaid
flowchart TD
    START([START]) --> fan_out{fan_out}

    fan_out -->|Send API| fetch_jobs[fetch_jobs]
    fan_out -->|Send API| fetch_sjobs[fetch_sjobs]
    fan_out -->|Send API| fetch_tjobs[fetch_tjobs]
    fan_out -->|Send API| fetch_fjobs[fetch_fjobs]

    fetch_jobs --> collect_results[collect_results\ndedupe · score · rank]
    fetch_sjobs --> collect_results
    fetch_tjobs --> collect_results
    fetch_fjobs --> collect_results

    collect_results --> END([END])

    classDef startEnd fill:#a78bfa,stroke:#7c3aed,stroke-width:2px,color:#000;
    classDef nodeStyle fill:#f3e8ff,stroke:#9333ea,stroke-width:1px,color:#000;
    classDef condStyle fill:#faf5ff,stroke:#c084fc,stroke-width:2px,color:#000;

    class START,END startEnd;
    class fetch_jobs,fetch_sjobs,fetch_tjobs,fetch_fjobs,collect_results nodeStyle;
    class fan_out condStyle;
```

### Relevance scoring

A job scores on where your query words appear. A hit in the **title** outweighs any number of hits in the description, so `title_hits * 10 + description_hits` sorts real matches to the top.

Two details that matter in practice:

- **Short query words match whole words only.** Searching `ai` should not match `p-ai-d media specialist`. Words of 4+ characters still match as substrings, so `python` finds `python3`.
- **Two passes.** The strict pass looks at titles only. If that leaves too few results, it widens to descriptions. A query like `ai engineer` is satisfied by titles alone; `python backend developer` usually needs the wider pass, because those words live in the body text.

### Feedback and memory

Tell the agent what to filter out — "no MERN", "no senior roles", "no usa" — and it stores your preferences in **PostgreSQL via LangGraph's PostgresSaver**. Filters persist across searches and across days.

Seniority words (`senior`, `junior`, `lead`, `principal`, …) are matched against the **title only**. Every posting says "work with senior engineers" somewhere in its body; that shouldn't disqualify a mid-level role. Everything else — technologies, locations — is matched against title, description and location.

Active filters are shown at the bottom of every response. Say **"reset filters"** to clear them.

By default, the agent fetches 10 jobs from each API to control costs, and returns the top 12 after ranking. Both limits live at the top of `agent.py`.

> **LangSmith tracing is enabled.** Graph runs are fully observable — every node execution, its latency and its output. Note that the search path no longer makes LLM calls, so token usage now appears only for feedback extraction, CV upload and the n8n evaluator.

---

## 🎙️ Voice AI

Talk to the agent instead of typing. Same LangGraph brain (`agent.py`, unmodified) — a new interface built with [Pipecat](https://pipecat.ai): Deepgram (STT), ElevenLabs (TTS), Daily (real-time transport).

Feedback works over voice too — say "no senior roles" mid-conversation and the agent filters the results it already found, live, with no repeated API calls. Ask "tell me more about the first one" for details on a specific listing. Voice sessions are intentionally stateless (in-memory only, no Postgres) since a single call is short-lived, unlike the text agent's persistent memory across days.

See [`voice/README.md`](./voice/README.md) for architecture details and setup instructions.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent | LangGraph (fan-out with `Send` API) |
| Memory | PostgreSQL via `PostgresSaver` |
| Voice | Pipecat (Daily transport, Deepgram STT, ElevenLabs TTS) |
| LLM | Google Gemini 2.5 Flash — feedback extraction, CV parsing, n8n scoring |
| LLM Integration | LangChain `init_chat_model` |
| Backend | FastAPI |
| Frontend | Next.js 15 + ReactMarkdown + remark-gfm |
| Job APIs | RemoteOK, Himalayas, Remotive, Jobicy |
| Evals | LangSmith dataset + LLM-as-judge (Gemini 2.5 Flash) |

---

## Getting Started

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env  # add your API keys
uvicorn main:app --reload

# Frontend
cd frontend
npm install react-markdown remark-gfm
npm run dev

# Voice AI (optional, see voice/README.md for details)
cd voice/server
uv sync
uv run bot.py
```

---

## Database Setup

This project uses PostgreSQL for persistent memory via LangGraph's `PostgresSaver`.

**Option 1 — Supabase (recommended, free)**
1. Create a free account at [supabase.com](https://supabase.com)
2. Create a new project
3. Copy the connection string from Settings → Database
4. Add it to your `.env` as `DATABASE_URL`

**Option 2 — Local PostgreSQL**
1. Install PostgreSQL locally
2. Create a database: `CREATE DATABASE jobsearch_memory;`
3. Add connection string to `.env`

## Environment Variables

See `.env.example` for all required variables:

```env
GEMINI_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com  # if outside US
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/jobsearch_memory
```

For Voice AI environment variables, see [`voice/README.md`](./voice/README.md).

---

## CV Upload

Upload your PDF resume and the agent automatically extracts your skills and finds matching remote jobs — no keywords needed.

- `POST /upload` — accepts a PDF and returns AI-matched job listings

## n8n Automation (Optional)

The included `n8n_workflow.json` adds automated job alerts every 12 hours — no manual searches needed.

### What the workflow does
![n8n Workflow](assets/n8n_workflow.png)
```
Schedule (every 12h)
  → Fetch from RemoteOK + Remotive + Himalayas (parallel)
  → Filter by keywords
  → Merge results
  → POST to /evaluate (AI scoring)
  → Send digest email via Gmail
```
![Email Digest](assets/email_digest.png)

### Setup

1. Import `n8n_workflow.json` into your n8n instance
2. Configure your Gmail credentials in the Gmail node
3. Update the `positionKeywords` array in the Code nodes to match your job search criteria
4. Make sure your FastAPI backend is running and update the URL in the HTTP Request node if needed

> The workflow connects to `http://host.docker.internal:8000/evaluate` by default (Docker setup). Change to `http://localhost:8000/evaluate` if running n8n locally without Docker.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ask` | POST | Search jobs with keywords + applies memory filters |
| `/feedback` | POST | Send feedback to agent ("no MERN", "no senior") — stored in memory |
| `/reset` | POST | Clear all stored filters and return the unfiltered results |
| `/upload` | POST | Upload PDF resume — agent extracts skills and finds matching jobs |
| `/evaluate` | POST | n8n integration — AI scoring of job listings |

---

## Evals

The agent includes an evaluation pipeline built with LangSmith.

- Dataset of test cases covering different query types
- LLM-as-judge evaluator using Gemini 2.5 Flash
- Float scoring (0.0 / 0.5 / 1.0) for granular feedback

Run evaluations:
```bash
python eval_runner.py
```

Results are visible in your LangSmith dashboard under the configured project.

> **Being rebuilt.** The previous 0.90 baseline was measured against the old LLM-based filtering and no longer reflects how the agent works. New eval cases — empty results, ambiguous queries, typos — are being generated from fresh traces with the [LangSmith eval engineering skill](https://github.com/langchain-ai/langsmith-skills), landing shortly.
>
> `eval_runner.py` posts to `http://localhost:8000/ask`; change the port if you run the backend elsewhere.

## Project Structure

```
job-search-agent/
├── agent.py           # LangGraph agent — fan-out, scoring, filtering
├── voice_agent.py     # VoiceSession — stateless wrapper around the same graph
├── main.py            # FastAPI backend + all endpoints
├── eval_runner.py     # LangSmith evaluation pipeline
├── requirements.txt
├── .env.example
├── n8n_workflow.json  # n8n automation workflow
├── frontend/          # Next.js 15 frontend
└── voice/             # Voice AI interface (Pipecat) — see voice/README.md
    └── server/
        ├── bot.py
        └── langgraph_processor.py
```
