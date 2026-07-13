# Operations / runbook

## Local startup

Backend:

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend talks directly to `http://localhost:8000`.

## Required configuration

From `.env.example`, the main runtime variables are:

- `GEMINI_API_KEY`
- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_ENDPOINT` for EU-region LangSmith
- `DATABASE_URL` for PostgreSQL checkpoint storage

Do not document or store real secret values in the wiki.

## Runtime dependencies

- PostgreSQL is required for persistent memory via `PostgresSaver`.
- LangSmith tracing is enabled by default in the example configuration.
- Gemini powers both search response generation and evaluation.
- `pdfplumber` is used for CV upload parsing.
- `slowapi` provides request rate limiting.

## Endpoint behavior to remember

- `/ask` and `/upload` are streamed plain-text responses.
- `/feedback` resumes the graph with extracted avoidance keywords.
- `/evaluate` is intended for the n8n automation path.
- Rate limiting is set to `10/minute` on the public endpoints.

## Practical troubleshooting

- If the app fails to start, verify `DATABASE_URL` is reachable before debugging LangGraph.
- If streaming appears buffered, check both the backend headers and the frontend reader loop.
- If search results look stale or narrow, confirm the source APIs are reachable and that the graph still fans out to all expected nodes.
- If memory is not retained between searches, inspect the `thread_id` flow from the frontend into the backend.

## Git-history cues

Recent commits indicate the most common operational failure modes were:

- streaming buffering
- remote API reliability / rate limits
- oversized prompts to tracing/eval systems
- data quality issues from one unreliable source

## Source references

- `main.py`
- `requirements.txt`
- `.env.example`
- `README.md`
- git commits `4524397`, `09fd3c7`, `49c746f`, `b3738bc`
