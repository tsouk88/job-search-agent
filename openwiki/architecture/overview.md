# Architecture overview

This application is a small full-stack system with three major layers:

1. A LangGraph agent that fetches and filters jobs.
2. A FastAPI backend that streams results and stores memory.
3. A Next.js frontend that provides the user experience.

## Execution model

The core graph is defined in `agent.py`.
It starts at `START`, fans out in parallel to source-specific fetch nodes, collects and deduplicates jobs, then pauses for human review before continuing or ending.

Key graph concepts:

- `fan_out` uses `Send` to run source fetches in parallel.
- `fetch_jobs`, `fetch_sjobs`, `fetch_tjobs`, and `fetch_fjobs` call RemoteOK, Himalayas, Remotive, and Jobicy.
- `collect_results` removes duplicate jobs by URL.
- `human_review` is an interrupt step that captures feedback like `no MERN`.
- `should_continue` ends the loop when feedback is `done`; otherwise it returns to `search`.

## Backend responsibilities

`main.py` owns the HTTP boundary and runtime setup:

- Loads environment variables with `dotenv`
- Creates the FastAPI app with a lifespan hook
- Initialises `PostgresSaver` from `DATABASE_URL`
- Compiles the graph with persisted checkpointing
- Adds permissive CORS
- Enables rate limiting via `slowapi`
- Defines the public endpoints:
  - `POST /ask`
  - `POST /upload`
  - `POST /feedback`
  - `POST /evaluate`

The backend also normalises job records before prompting Gemini:

- deduplicates by company + position hash
- truncates descriptions for smaller prompts and traces
- converts different API field names into a common output shape
- streams the final response with `StreamingResponse`

## Frontend responsibilities

`frontend/app/page.tsx` is a single-page client component.
It keeps a locally generated `thread_id`, sends user queries to `/ask`, sends filter feedback to `/feedback`, and uploads PDFs to `/upload`.
It renders streamed responses with `react-markdown` and `remark-gfm`.

## Why the architecture looks this way

Recent commits show a clear progression:

- streaming and buffering were hardened so the UI receives partial output reliably
- job source fan-out was improved to reduce latency and cost
- an unreliable source was removed from the graph because it hurt eval quality
- HITL and persistent memory were added so the agent can learn user-specific exclusions
- eval tooling was added once the codebase had enough behavior to measure

## Things to watch when editing

- The backend prompt text still encodes output formatting rules; changing source names or output format requires updating the prompt and the UI expectations together.
- The graph state contains memory and fetched jobs; preserve those keys if you refactor the graph.
- If you change streaming behavior, re-check the frontend’s incremental read loop.
- If you change persistence, ensure the lifespan hook still compiles the graph with a working checkpointer.

## Source references

- `agent.py`
- `main.py`
- `frontend/app/page.tsx`
- Recent history: commits `4524397`, `6e0cf7f`, `b3738bc`, `662d71d`
