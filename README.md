# Job Search AI Agent

An AI-powered remote job search assistant. Type in your desired job keywords and the agent searches, evaluates, and presents the best matches for you.

⚡ ~15s response time | 💰 ~$0.01 per request

If you find this useful, give it a ⭐️ — it helps others discover the project!

---

## What it does

The agent connects to 5 job APIs simultaneously:

- [RemoteOK API](https://remoteok.com/api)
- [Himalayas API](https://himalayas.app/jobs/api)
- [Remotive API](https://remotive.com/api/remote-jobs)
- [Arbeitnow.com](https://www.arbeitnow.com/api/job-board-api)
- [Jobicy.com](https://jobicy.com/api/v2/remote-jobs)

It filters and evaluates results in a single LLM call — returning only the jobs that are a real match for your query.

---

## How it works

Built with **LangGraph** at its core. The graph uses a **fan-out architecture** — the agent spawns parallel fetch nodes using LangGraph's `Send` API. Results are collected, then a **Human-in-the-Loop (HITL)** interrupt pauses the graph and waits for your feedback.

You can tell the agent what to filter out (e.g. "no MERN", "no senior roles") and it stores your preferences in **PostgreSQL via LangGraphs's PostgresSaver**. Next time you search, it remembers — no need to repeat yourself.

The loop continues until you type `done`.


```mermaid
flowchart TD
    START([START]) --> fan_out{fan_out}
    
    fan_out -->|Send API| fetch_jobs[fetch_jobs]
    fan_out -->|Send API| fetch_sjobs[fetch_sjobs]
    fan_out -->|Send API| fetch_tjobs[fetch_tjobs]
    
    fetch_jobs --> collect_results[collect_results]
    fetch_sjobs --> collect_results
    fetch_tjobs --> collect_results
    
    collect_results --> human_review[human_review\nHITL interrupt]
    
    human_review -->|done| END([END])
    human_review -->|search again| search[search]
    
    search --> fan_out

    classDef startEnd fill:#a78bfa,stroke:#7c3aed,stroke-width:2px,color:#000;
    classDef nodeStyle fill:#f3e8ff,stroke:#9333ea,stroke-width:1px,color:#000;
    classDef condStyle fill:#faf5ff,stroke:#c084fc,stroke-width:2px,color:#000;
    classDef hitl fill:#fde68a,stroke:#f59e0b,stroke-width:2px,color:#000;
    
    class START,END startEnd;
    class fetch_jobs,fetch_sjobs,fetch_tjobs,collect_results,search nodeStyle;
    class fan_out condStyle;
    class human_review hitl;
```

By default, the agent fetches 10 jobs from each API to control costs. Remove `[:10]` in `agent.py` to search all results.

> **LangSmith tracing is enabled** — every run is fully observable. Monitor each node execution, token usage, latency, and cost in real time via LangSmith.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent | LangGraph (fan-out with `Send` API + HITL) |
| Memory | PostgreSQL via `PostgresSaver` |
| LLM | Google Gemini 2.5 Flash |
| LLM Integration | LangChain `init_chat_model` |
| Backend | FastAPI + robust text streaming |
| Frontend | Next.js 15 + ReactMarkdown + remark-gfm |
| Job APIs | RemoteOK, Himalayas, Remotive, Jobicy, Arbeitnow |
| Observability | LangSmith (EU endpoint supported) |

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

---

## CV Upload (New!)

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
| `/upload` | POST | Upload PDF resume — agent extracts skills and finds matching jobs |
| `/feedback` | POST | Send feedback to agent ("no MERN", "no senior") — stored in memory |
| `/evaluate` | POST | n8n integration — AI scoring of job listings |

---

## Project Structure

```
job-search-agent/
├── agent.py           # LangGraph agent — fan-out, HITL, memory
├── main.py            # FastAPI backend + all endpoints
├── requirements.txt
├── .env.example
├── n8n_workflow.json  # n8n automation workflow
└── frontend/          # Next.js 15 frontend
```