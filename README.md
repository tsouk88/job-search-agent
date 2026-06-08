# Job Search AI Agent

An AI-powered remote job search assistant. Type in your desired job keywords and the agent searches, evaluates, and presents the best matches for you.
⚡ ~10s response time | 💰 ~$0.007 per request

## What it does

The agent connects to :
[RemoteOK API](https://remoteok.com/api)
[HimalayasAPI]( https://himalayas.app/jobs/api)
[RemotiveAPI](https://remotive.com/api/remote-jobs) 
 
filters and presents results in a single LLM call — returning only the jobs that are a real match.

## How it works

Built with **LangGraph** at its core. The graph uses a **fan-out architecture** , the agent spawns parallel fetch nodes  using LangGraph's `Send` API. Results are collected then Gemini evaluates them and are presented in a nice bullet list.

```
START → fan_out → fetch_jobs  ↘
                → fetch_sjobs → END
                → fetch_tjobs ↗
```
By default, the agent fetch 10 jobs from each API to control API costs. Remove [:10] in agent.py to search all results.

> **LangSmith tracing is enabled** — every run is fully observable. You can monitor each node execution, token usage, latency, and cost in real time via LangSmith.

## Tech Stack

- **LangGraph** — agent graph, fan-out with `Send`, state management
- **LangChain** — LLM integration via `init_chat_model`
- **Google Gemini** — job evaluation and result presentation
- **FastAPI** — backend API
- **Next.js 15** — chat frontend
- **RemoteOK API** — live remote job data
- **Remotive API** — live remote job data
- **Himalayas API** — live remote job data
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
- `LANGSMITH_ENDPOINT` if you are outside US
