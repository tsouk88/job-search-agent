# Files

- [Agent Graph](agent-graph.md) - The LangGraph state machine in agent.py — fan-out to four job API fetchers via the Send API, collect_results with URL deduplication and title-weighted scoring, and the deterministic filter_jobs and normalize_jobs functions.
- [Backend API](backend-api.md) - The FastAPI backend in main.py — lifespan with PostgresSaver checkpointer, five endpoints (/ask, /feedback, /reset, /upload, /evaluate), the three-condition /ask cache, Gemini LLM chain, rate limiting, CORS, and markdown formatting.
- [Architecture Overview](overview.md) - Three interfaces (REST, MCP, Voice) over one deterministic LangGraph agent graph. The search path is LLM-free. The LLM boundary covers feedback extraction, CV parsing, and the auth-gated evaluator. Three persistence models — Postgres, in-process dict, and in-memory.
