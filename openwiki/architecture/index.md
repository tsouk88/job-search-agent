# Files

- [Agent Graph Architecture](agent-graph.md) - Deterministic LangGraph state machine in agent.py executing a 6-source parallel fan-out, Getro VC portfolio thread pool search, deduplication, seniority/location filtering, and title-weighted scoring.
- [Backend API & Request Lifecycle](backend-api.md) - The FastAPI backend in main.py — lifespan compiling two graphs (PostgresSaver agent + InMemorySaver eval_agent), endpoint routing, Redis-backed rate limiting, Gemini budget, job cache with RedisError tolerance, async CV parsing worker, and response formatting.
- [System Architecture Overview](overview.md) - High-level system architecture connecting three user entrypoints (REST API, MCP server, Voice agent) to a deterministic LangGraph core, multi-tier persistence boundaries, and external services.
