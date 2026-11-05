---
okf_version: "0.2"
---

# Files

- [Domain Concepts & Scoring Models](domains.md) - Core domain entities, data schemas, multi-source job aggregation, deterministic scoring heuristics, location filtering, memory exclusion semantics, and correctness evaluation models.
- [External Integrations & Job Boards](integrations.md) - Integration protocols, rate limits, error handling, caching behaviors, and infrastructure contracts for six job sources, Google Gemini, Redis, PostgreSQL, and Celery.
- [Model Context Protocol (MCP) Server](mcp-server.md) - Model Context Protocol stdio server in mcp_server.py exposing the read-only search_remote_jobs tool with an in-process 4-hour cache and intent-based exclusions over the 6-source LangGraph agent.
- [Operations & Runbook](operations.md) - Deployment, configuration, background workers, storage operations, and operational runbook for running the system in production and locally.
- [Quickstart & Task Routing](quickstart.md) - Primary entry point, operational overview, task routing guide, and developer onboarding instructions for the job search assistant.
- [Repository Source Map](source-map.md) - Exhaustive file-by-file and module-by-module navigation index mapping repository paths to their architectural responsibilities across agent execution, backend API, Celery tasks, evals, and frontend.
- [Testing & Quality Assurance](testing.md) - Comprehensive testing and quality assurance guide covering deterministic Harbor evaluations, live LangSmith benchmarks, same-day control discipline, and manual verification.
- [Voice Agent Interface](voice-agent.md) - Real-time conversational voice assistant interface powered by Pipecat, Deepgram, ElevenLabs, Daily WebRTC, and in-memory LangGraph sessions.
- [Developer Workflows & Runbooks](workflows.md) - Step-by-step developer workflows for adding job sources, tuning ranking rules, running Harbor and LangSmith evaluations, and debugging runtime degradation.

# Directories

- [architecture](architecture/)
- [evals](evals/)
- [frontend](frontend/)
- [integrations](integrations/)
- [operations](operations/)
- [testing](testing/)
- [workflows](workflows/)
