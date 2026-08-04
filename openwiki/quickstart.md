---
type: Quickstart
title: Job Search AI Agent Quickstart
description: Entry point for the wiki — a LangGraph job search agent with three interfaces (REST, MCP, Voice), deterministic scoring, PostgreSQL memory, Next.js frontend, Harbor and LangSmith evals, and optional n8n automation.
tags: [quickstart, overview, navigation]
---

# Job Search AI Agent — Quickstart

A remote job search assistant that queries four job APIs in parallel, scores and filters results with deterministic Python (no LLM in the search path), and exposes three interfaces: a REST API, an MCP tool, and a voice agent. Results are reproducible and cost nothing to search.

## Wiki map

| Page | What it covers |
|---|---|
| [Architecture overview](architecture/overview.md) | Three interfaces over one graph, LLM boundary, three persistence models |
| [Agent graph](architecture/agent-graph.md) | The LangGraph state machine — fan-out, scoring, filtering, normalization |
| [Backend API](architecture/backend-api.md) | FastAPI endpoints, caching, LLM chain, rate limiting, CORS |
| [MCP server](mcp-server.md) | Stdio MCP tool with explicit exclusion args, in-process cache |
| [Voice agent](voice-agent.md) | Pipecat voice interface, command routing, in-memory sessions |
| [Frontend chat UI](frontend/chat-ui.md) | Next.js single-page app, message routing, streaming reader |
| [Harbor eval](evals/harbor-eval.md) | Deterministic CI eval with frozen fixtures |
| [LangSmith eval](evals/langsmith-eval.md) | LLM-judge quality measurement (0.812 baseline) |
| [Domain concepts](domains.md) | Scoring rules, filter semantics, normalization, evaluation semantics |
| [Workflows](workflows.md) | User-visible flows — search, feedback, upload, n8n digest, eval |
| [Operations](operations.md) | Runbook — startup, config, deployment, troubleshooting |
| [n8n automation](operations/n8n-automation.md) | Scheduled digest workflow |
| [Integrations](integrations.md) | External services and their contracts |
| [Testing and evals](testing.md) | How to run both eval systems and manual checks |
| [Source map](source-map.md) | File-level map with responsibilities and edit order |

## What this repo does

1. Searches four remote job APIs in parallel (RemoteOK, Himalayas, Remotive, Jobicy)
2. Scores results by title-weighted keyword matching (deterministic, no LLM)
3. Filters by accumulated user exclusions (seniority terms against title, others against full text)
4. Returns the top 12 matches as markdown (REST) or JSON (MCP)
5. Remembers exclusions per thread in PostgreSQL (REST), in-memory (voice), or via explicit args (MCP)

## Main runtime pieces

| File | Role |
|---|---|
| `agent.py` | LangGraph graph — fan-out, scoring, filtering, normalization |
| `main.py` | FastAPI backend — 5 endpoints, PostgresSaver, LLM chain, rate limiting |
| `mcp_server.py` | MCP stdio server — one read-only tool, in-process cache |
| `voice_agent.py` | VoiceSession wrapper — in-memory MemorySaver, result caching |
| `voice/server/bot.py` | Pipecat pipeline — Deepgram STT, ElevenLabs TTS, Daily transport |
| `voice/server/langgraph_processor.py` | Command routing for voice (feedback/search/reset/details) |
| `frontend/app/page.tsx` | Next.js chat UI — message routing, streaming, markdown rendering |
| `eval_runner.py` | LangSmith eval harness |
| `evals/` | Harbor deterministic eval — frozen fixtures, CI |
| `n8n_workflow.json` | Optional scheduled digest |

## Primary external services

- Gemini 2.5 Flash — feedback extraction, CV parsing, `/evaluate` scoring (not in search)
- LangGraph — orchestration and memory via `Send` API and checkpointers
- PostgreSQL via `PostgresSaver` — persistent thread memory (REST only)
- LangSmith — tracing and eval dataset
- RemoteOK, Himalayas, Remotive, Jobicy — job source data

## Quick start

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY, DATABASE_URL, etc.
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# MCP (optional, no env vars needed)
# Add to claude_desktop_config.json with absolute paths to .venv/bin/python and mcp_server.py

# Harbor eval (optional, needs Docker)
uv tool install harbor
harbor run -p evals -i "*filter-exclusion-senior*" \
  -a evals.harbor_agents.pipeline_agent:PipelineAgent \
  -e docker -o evals/jobs \
  --extra-docker-compose evals/configs/no-network.yaml -y
python evals/check_reward.py evals/jobs/ci-<run-id>

# LangSmith eval (optional, needs backend on port 8002)
python eval_runner.py
```

## Task routing table

| If you are changing... | Read first | Edit order | Validate with |
|---|---|---|---|
| Search/scoring logic | [Agent graph](architecture/agent-graph.md) | `agent.py` → [Backend API](architecture/backend-api.md) → [MCP server](mcp-server.md) | Harbor eval (CI runs automatically) |
| `filter_jobs` exclusion | [Agent graph](architecture/agent-graph.md) | `agent.py` → all interfaces | Harbor eval + LangSmith eval |
| API contract or formatting | [Backend API](architecture/backend-api.md) | `main.py` → `frontend/app/page.tsx` → `n8n_workflow.json` | Manual `/ask` + `/feedback` |
| Frontend behavior | [Frontend chat UI](frontend/chat-ui.md) | `frontend/app/page.tsx` | Manual browser test |
| Voice interface | [Voice agent](voice-agent.md) | `voice_agent.py` → `voice/server/langgraph_processor.py` | Manual voice call |
| MCP tool | [MCP server](mcp-server.md) | `mcp_server.py` → `agent.py` | Harbor eval + MCP client test |
| Eval coverage | [Testing](testing.md) | `evals/` or `eval_runner.py` | Run the eval |
| Deployment | [Operations](operations.md) | `render.yaml` → `.env` → Vercel settings | Render health check |
| n8n digest | [n8n automation](operations/n8n-automation.md) | `n8n_workflow.json` → Search Settings | Trigger manually |

## Backlog

No deferred items. All substantial components and workflows are documented.
