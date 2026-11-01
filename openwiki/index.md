---
okf_version: "0.2"
---

# Files

- [Domain Concepts](domains.md) - Core domain concepts — five-source job aggregation, normalization and mojibake repair, alias-based query canonicalization, title-weighted scoring with frequency-based description contribution and generic-word tie-breaking, signal tokens, thread memory and the seniority/full-text filter split, country/location matching, age filtering, resume-derived search intent, and evaluation semantics.
- [Integrations](integrations.md) - External service integrations — five job APIs with their query patterns and quirks, the LLM and LangGraph stack, Redis (cache, rate-limit storage, Gemini budget), Celery over Redis, OpenRouter and laya serve judges, PostgreSQL persistence, LangSmith observability, the frontend HTTP contract, n8n automation, the MCP client contract, and the voice agent service stack.
- [MCP Server](mcp-server.md) - The Model Context Protocol stdio server in mcp_server.py — one read-only tool (search_remote_jobs), in-process 4h cache, no database, no LLM, no env vars. Designed for intent-based exclusion via explicit args. Backs five job sources through one LangGraph graph.
- [Operations / Runbook](operations.md) - Operational runbook — local startup (Redis + Celery), all environment variables, runtime dependencies, LangSmith observability config, Render/Vercel deployment, endpoint behavior, CORS gotchas, cold-start handling, and troubleshooting.
- [Job Search AI Agent Quickstart](quickstart.md) - Primary entry point for the repository; a LangGraph job search agent with REST, MCP, and voice interfaces, deterministic scoring, PostgreSQL memory, and evaluation systems.
- [Source Map](source-map.md) - File-level map of all entry points, supporting files, voice and evals subsystems, deployment files, and authoring-convention skills — with responsibilities and suggested edit order.
- [Testing and Evals](testing.md) - Two eval systems — the deterministic Harbor eval (frozen fixtures for five sources, CI, exact-set assertions) and the LangSmith eval (live job boards, LLM judge, ~0.90 baseline over 24 cases). No classic unit test suite.
- [Voice Agent](voice-agent.md) - Voice interface using Pipecat with Deepgram STT, ElevenLabs TTS, and Daily WebRTC transport. Shares the same agent.py graph as REST but uses in-memory MemorySaver, caches last_jobs for local re-filtering, and routes commands by first word.
- [Workflows](workflows.md) - User-visible and maintenance workflows — keyword search, feedback loop, CV upload, n8n digest, Harbor eval, and LangSmith eval — with change guidance for each.

# Directories

- [architecture](architecture/)
- [evals](evals/)
- [frontend](frontend/)
- [integrations](integrations/)
- [operations](operations/)
- [testing](testing/)
- [workflows](workflows/)
