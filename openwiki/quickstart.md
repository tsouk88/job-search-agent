---
type: Quickstart
title: Job Search AI Agent Quickstart
description: Entry point for understanding the remote job search assistant — a LangGraph agent with FastAPI backend, Next.js frontend, optional n8n automation, LangSmith evals, and a voice interface.
tags: [quickstart, overview, navigation]
---

# Job Search AI Agent — Quickstart

This repository is a remote job search assistant built around a LangGraph agent, a FastAPI backend, and a Next.js frontend. It searches multiple remote job APIs in parallel, filters results with Gemini, remembers user feedback in PostgreSQL, and exposes an optional eval/automation layer for LangSmith and n8n.

Start here, then follow the focused pages:

- [Architecture overview](architecture/overview.md)
- [Workflows](workflows.md)
- [Domain concepts](domains.md)
- [Operations / runbook](operations.md)
- [Integrations](integrations.md)
- [Testing and evals](testing.md)
- [Voice agent](voice-agent.md)
- [Source map](source-map.md)

## What this repo does

At a high level, the app lets a user:

1. Search for remote jobs by keyword.
2. Stream back a filtered shortlist of relevant matches.
3. Send feedback like `no MERN` or `no senior` to update future searches.
4. Upload a CV PDF to derive search keywords automatically.
5. Run scheduled evaluation/digest workflows through n8n.
6. Measure quality through LangSmith evals.

## Main runtime pieces

- `main.py` — FastAPI app, HTTP endpoints, request throttling, PDF upload parsing, and streaming response handling.
- `agent.py` — LangGraph state machine that fans out to multiple job APIs, deduplicates and ranks results, and ends; memory is applied as a post-graph filter in `main.py`.
- `frontend/app/page.tsx` — single-page chat-like UI that talks directly to the backend.
- `eval_runner.py` — LangSmith dataset/evaluator harness for regression checks.
- `n8n_workflow.json` — optional automation workflow for periodic digests.
- `voice_agent.py` / `voice/server/` — voice interface using Pipecat, Deepgram, and ElevenLabs; shares the same `agent.py` graph.

## Primary external services

- Gemini 2.5 Flash for generation and evaluation
- LangGraph for orchestration and memory
- PostgreSQL via `PostgresSaver` for persistence
- LangSmith for tracing and evals
- RemoteOK, Himalayas, Remotive, and Jobicy for job source data

## Repo layout worth knowing

- `frontend/` — Next.js UI
- `voice/server/` — Pipecat voice bot server (see [Voice agent](voice-agent.md))
- `assets/` — screenshots used in the README and workflow docs
- `.env.example` — required environment variables
- `README.md` — product-facing summary, setup notes, and screenshots

## When changing the code

- Backend logic lives in `main.py` and `agent.py`.
- UI behavior is mostly in `frontend/app/page.tsx`.
- If search quality changes, update eval assumptions in `eval_runner.py` and confirm the README/workflow docs still match reality.
- If job sources change, check both the graph and the prompt text because the backend still hard-codes source names in a few places.

## Notes on current behavior

- The backend streams plain text responses from `/ask` and `/upload`.
- Feedback is routed through `/feedback`, which appends avoid-keywords to thread memory and re-filters the cached jobs; the search graph is not re-run.
- Rate limiting is enabled on the main endpoints.
- CV upload expects a PDF and extracts text with `pdfplumber`.
- Arbeitnow was removed from the active graph because it was unreliable; older docs may still mention it.

## Backlog

- **Architecture overview page** — quickstart links to `architecture/overview.md` but no such page exists yet. Should cover the LangGraph state machine, data flow between agent/main/frontend, and the voice agent pipeline in a single diagram-oriented page. Deferred because the initial init run focused on text-based workflows.
