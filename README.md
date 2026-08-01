# Job Search AI Agent

An AI-powered remote job search assistant. Type in your desired job keywords and the agent searches, filters, and presents the best matches for you. Talk to it instead, if you'd rather — see [Voice AI](#️-voice-ai).

**[▶ Try it live](https://job-search-agent-blond.vercel.app)** — no signup, no API key.

⚡ Instant results | 💰 $0 per search — searching and filtering are fully deterministic | 📊 [0.812 relevance](#evals) across 22 eval cases

> The backend runs on a free Render instance that sleeps after 15 minutes of inactivity. If the demo has been idle, the first search takes about a minute — roughly 50s to wake the server, then 15s to query four job APIs. Every search after that is instant.

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

Filtering at the source instead fixed the bug, removed the cost, and made results reproducible. Quality is measured — see [Evals](#evals).

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

Four details that matter in practice:

Short query words have to match a whole word. Searching `ai` should not hit `p-ai-d media specialist`. Words of four characters or more still match inside a word, so `python` finds `python3`.

A listing needs a title hit to qualify at all. Mentioning your keywords somewhere in the body text is not enough. Description hits still count, but only to break ties between listings that already earned their place.

The agent returns what matched, up to a cap of 12, and it will happily return three listings or none. An earlier version guaranteed a minimum of eight; on narrow queries, seven of those eight turned out to be noise.

Generic words are dropped. `developer`, `engineer`, `remote`, `role` and the rest show up in half of all job titles, so they can't rank anything. If a query is nothing but generic words, they get used anyway rather than matching the entire board.

RemoteOK's tags are not trusted. The API is still queried by tag, but every listing that comes back is re-checked against its own title. Across 101 listings that's an average of 23.6 tags each, a nursing role tagged `python`, `sql`, `postgres` and `golang`, and three unrelated listings sharing an identical 36-tag list. The tags are SEO filler. The title isn't.

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
| Evals | LangSmith dataset + LLM-as-judge (Gemini 2.5 Flash) — 0.812 / 22 cases |

---

## Getting Started

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env  # add your API keys
uvicorn main:app --reload

# Frontend
cd frontend
npm install
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
3. Copy the connection string from Connect → **Session pooler, port 5432**
4. Add it to your `.env` as `DATABASE_URL`

Use the session pooler, not the transaction pooler on port 6543. `PostgresSaver`
relies on prepared statements, which the transaction pooler does not keep across
queries — the failures are intermittent rather than clean.

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
ALLOWED_ORIGINS=http://localhost:3000  # comma-separated list of browser origins allowed to call the API
```

For Voice AI environment variables, see [`voice/README.md`](./voice/README.md).

---

## Deployment

The backend deploys to Render from the checked-in `render.yaml` (New → Blueprint).
It declares the build and start commands, pins Python, and lists the secrets to
fill in from the dashboard. The frontend deploys to Vercel with **Root Directory
set to `frontend`** and `NEXT_PUBLIC_API_BASE` pointing at the Render URL.

Two details cost real time if you get them wrong:

- `NEXT_PUBLIC_API_BASE` takes **no trailing slash** — the client appends `/ask`.
- `ALLOWED_ORIGINS` takes **no trailing slash** either. The browser's `Origin`
  header is scheme, host and port only, and the match is exact. A stray `/` makes
  every request fail CORS while the page itself loads fine, so the only symptom
  is an error hidden in the browser console.

---

## CV Upload

Upload your PDF resume and the agent automatically extracts your skills and finds matching remote jobs — no keywords needed.

- `POST /upload` — accepts a PDF up to 5MB and returns matching job listings

Only the first five pages reach the model, and only to compress the CV into a
single line of keywords. That line becomes the search query; the listings that
come back are then filtered and formatted by the same deterministic code that
serves `/ask`.

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

> The workflow connects to `http://host.docker.internal:8002/evaluate` by default (Docker setup). Change to `http://localhost:8002/evaluate` if running n8n locally without Docker.

> `/evaluate` is the one endpoint that sends arbitrary text to Gemini, so it is not public. Set `EVALUATE_TOKEN` in your `.env` and put the same value in the workflow's `x-api-key` header, where the exported JSON carries a `YOUR_EVALUATE_TOKEN` placeholder. Without it the endpoint answers 401.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ask` | POST | Search jobs with keywords + applies memory filters |
| `/feedback` | POST | Send feedback to agent ("no MERN", "no senior") — stored in memory |
| `/reset` | POST | Clear all stored filters and return the unfiltered results |
| `/upload` | POST | Upload PDF resume — agent extracts skills and finds matching jobs |
| `/evaluate` | POST | n8n integration — AI scoring of job listings. Requires the `x-api-key` header |

---

## Evals

The agent scores **0.812 across 22 test cases**. Roughly four out of every five listings it returns are relevant to the query, and twelve of the cases score a clean 1.0.

The setup is a LangSmith dataset where each query carries a written description of what a good answer looks like, plus a Gemini 2.5 Flash judge that counts how many returned listings meet it. Score is relevant divided by returned, so padding a response with weak matches costs you.

The queries include narrow niches (`rust`, `blockchain solidity`), vague ones (`remote job`), one where the right answer is probably nothing at all (`COBOL mainframe developer`), and misspellings. Typos are not corrected on purpose. Search for `pyton developer` and you get nothing back; the reference answer says that is correct.

```bash
python eval_runner.py   # posts to localhost:8002/ask, change the port if your backend runs elsewhere
```

### How it got there

Most of the gain came from taking things out. Every step below was measured against the same 22 cases:

| Change | Score |
|---|---|
| Starting point | 0.558 |
| Stopped trusting RemoteOK's tags, matched on titles | 0.575 |
| Removed the guaranteed minimum of 8 results | 0.679 |
| Treated `developer` and `engineer` as meaningful words | 0.584, reverted |
| Fixed the reference answers for the typo queries | 0.751 |
| Fixed a missing comma in the generic-word list | 0.812 |

The big jump came from deleting a rule that guaranteed at least 8 results. On a query like `rust` the agent would find one genuine match and then pad the list with seven listings that happened to mention the word somewhere in their body text. Three good results beat twelve mediocre ones.

The missing comma is worth a mention because Python never complained about it. Two adjacent string literals in a set silently became one, which quietly dropped `engineer` and `remote` from the generic-word list. It only surfaced because a nonsense query started returning listings with "Remote" in the title.

### What the number doesn't cover

It measures the first response only. Users narrow results by talking to the agent ("no support roles", "no senior"), and none of the 22 cases exercise that path, so day-to-day use is better than 0.812 suggests.

It also moves. The agent queries live job boards, so two runs an hour apart see different listings and individual cases wobble by a lot. The aggregate is the signal, not any single row.

### Known limitation

One title match is enough to admit a listing. That is fine when the distinctive word in a query is unambiguous, and it falls apart when it isn't: `data` pulls in Data Analysts, `wordpress` pulls in WordPress Support Specialists.

The obvious fix, requiring two matching words, was tried and rejected because it threw away correct results like `Software Engineer (Go, Python, TS)`. Measurement showed why it could never have worked. Specific terms like `sql`, `aws` and `pytorch` appear in **0%** of returned job titles, because titles say "DevOps Engineer", not "DevOps Kubernetes AWS Engineer". There is only ever one word to match on.

### Next

Both problems above have the same root: the eval runs against live data, so a change can't be isolated from the market shifting underneath it. The plan is to rebuild the hard cases as Harbor tasks with LangChain's [eval-engineering skill](https://github.com/langchain-ai/langchain-skills), where the listings are fixed and verification is deterministic instead of judged. That is also where the conversational filtering path gets its first real test.

The old 0.90 baseline is gone. It was measured against LLM-based filtering on a different dataset and was never comparable to this one.

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
