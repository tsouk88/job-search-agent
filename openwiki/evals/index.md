# Files

- [Harbor Eval](harbor-eval.md) - The deterministic Harbor eval in evals/ — frozen job API fixtures for FIVE sources (RemoteOK, Himalayas, Remotive, Jobicy, Workable), no network, no LLM, no database. Tests filter_jobs exclusion logic against hand-written expected sets. Runs in CI on every push to agent.py or mcp_server.py.
- [LangSmith Eval](langsmith-eval.md) - LangSmith-based regression harness that posts 24 queries to the /ask endpoint and scores the ratio of relevant/returned listings with a Gemini 2.5 Flash judge. Current baseline ~0.90 (16 August). Runs against live job boards so the aggregate is the signal, not any single case.
