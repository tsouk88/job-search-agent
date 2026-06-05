# Job Search AI Agent

An AI-powered remote job search assistant. Type in your desired job keywords and the agent searches, evaluates, and presents the best matches for you.

## What it does

The agent connects to the [RemoteOK API](https://remoteok.com/api), filters jobs based on your keywords, and uses Google Gemini to evaluate each one — returning only the jobs that are a real match.

## How it works

Built with **LangGraph** at its core. The graph uses a **fan-out architecture** — once jobs are fetched, the agent spawns parallel evaluation nodes (one per job) using LangGraph's `Send` API. Results are collected and presented via a clean chat interface.

```
START → fetch_jobs → fan_out → [evaluate_job × N] → END
```

> **LangSmith tracing is enabled** — every run is fully observable. You can monitor each node execution, token usage, latency, and cost in real time via LangSmith.

## Tech Stack

- **LangGraph** — agent graph, fan-out with `Send`, state management
- **LangChain** — LLM integration via `init_chat_model`
- **Google Gemini** — job evaluation and result presentation
- **FastAPI** — backend API
- **Next.js 15** — chat frontend
- **RemoteOK API** — live remote job data
- **LangSmith** — tracing and monitoring

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
```

## Environment Variables

See `.env.example` for required variables:
- `GEMINI_API_KEY`
- `LANGSMITH_API_KEY`
- `LANGSMITH_TRACING`
- `LANGSMITH_PROJECT`
