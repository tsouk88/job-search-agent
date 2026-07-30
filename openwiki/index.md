---
okf_version: "0.1"
---

# Files

- [Domain Concepts](domains.md) - Core domain concepts for the job search agent — job source aggregation, deduplication, two-pass ranking, thread memory (avoid-keywords), query interpretation, resume-derived search, and evaluation semantics.
- [Integrations](integrations.md) - External service integrations for the job search agent — job APIs, LLM/orchestration stack, persistence, observability, UI contract, n8n automation, and the voice agent's separate service stack.
- [Operations / Runbook](operations.md) - Operational runbook for the job search agent — local startup, required configuration, runtime dependencies, endpoint behavior, troubleshooting, and git-history failure modes.
- [Job Search AI Agent Quickstart](quickstart.md) - Entry point for understanding the remote job search assistant — a LangGraph agent with FastAPI backend, Next.js frontend, optional n8n automation, LangSmith evals, and a voice interface.
- [Source Map](source-map.md) - Map of all entry points, supporting files, and the voice agent subsystem in the repository, with responsibilities and suggested edit order.
- [Testing and Evals](testing.md) - Testing strategy for the job search agent — LangSmith eval runner, what the evals measure, manual checks, and regression targets after changes.
- [Voice Agent](voice-agent.md) - Voice interface for the job search agent using Pipecat, Deepgram STT, ElevenLabs TTS, and Daily WebRTC transport. Shares the same LangGraph brain as the REST API but uses in-memory state and local result caching for faster feedback loops.
- [Workflows](workflows.md) - User-visible and maintenance workflows for the job search agent — keyword search, feedback loop, CV upload, n8n digest, and eval pipeline — with change guidance for each.
