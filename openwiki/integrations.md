# Integrations

## Job APIs

The backend graph integrates with four public job sources:

- RemoteOK: `https://remoteok.com/api?tags=...`
- Himalayas: `https://himalayas.app/jobs/api/search?q=...&worldwide=true&sort=recent`
- Remotive: `https://remotive.com/api/remote-jobs?search=...`
- Jobicy: `https://jobicy.com/api/v2/remote-jobs?tag=...`

The graph encodes user text before sending it to the APIs and truncates descriptions to reduce payload size.

## LLM / orchestration stack

- Gemini 2.5 Flash is the main chat model.
- LangGraph orchestrates fetch, collect, review, and resume steps.
- LangChain’s `init_chat_model` and `StrOutputParser` are used in the backend and eval runner.

## Persistence

- PostgreSQL via `langgraph.checkpoint.postgres.PostgresSaver` stores per-thread memory/state.
- The checkpointer is created in the FastAPI lifespan hook, so startup depends on the database.

## Observability and evals

- LangSmith tracing is enabled in the example environment.
- `eval_runner.py` creates a LangSmith evaluation run against `/ask`.
- The repo history suggests eval quality became a major concern after source filtering and source removal changes.

## UI contract

The frontend is intentionally thin and depends on these backend behaviors:

- `/ask` streams text that Markdown can render progressively
- `/upload` also streams text
- `/feedback` accepts JSON and returns a small confirmation object
- thread state is keyed by a browser-generated UUID stored in localStorage

## Optional automation

`n8n_workflow.json` integrates with:

- the backend `/evaluate` endpoint
- Gmail for email delivery
- scheduled execution in n8n

The included README screenshots in `assets/` document that automation path.

## Source references

- `main.py`
- `agent.py`
- `frontend/app/page.tsx`
- `eval_runner.py`
- `n8n_workflow.json`
- `assets/n8n_workflow.png`
- `assets/email_digest.png`
