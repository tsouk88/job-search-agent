---
type: Reference
title: Testing and Evals
description: Two eval systems — the deterministic Harbor eval (frozen fixtures, CI, exact-set assertions) and the LangSmith eval (live job boards, LLM judge, 0.812 baseline). No classic unit test suite.
tags: [testing, evals, harbor, langsmith, regression, quality, ci]
---

# Testing and evals

This repository has no classic unit-test suite. Quality is measured by two complementary eval systems:

| System | What it measures | Data | Verifier | CI | Current |
|---|---|---|---|---|---|
| [Harbor eval](evals/harbor-eval.md) | `filter_jobs` exclusion logic | Frozen fixtures (captured 04/08/2026) | Deterministic pytest assertions | Yes (every push to `agent.py`/`mcp_server.py`/`evals/`) | 1 trial passes |
| [LangSmith eval](evals/langsmith-eval.md) | End-to-end search quality | Live job boards | Gemini 2.5 Flash judge | No (manual) | 0.812 over 22 cases |

## Harbor eval — deterministic

The Harbor eval is the CI gate. It runs on every push or PR that touches `agent.py`, `mcp_server.py`, `evals/**`, or `.github/workflows/eval.yml`. A red build means the filter changed behavior.

- **Task:** `filter-exclusion-senior` — query `python developer`, exclude `["senior", "game", "canonical"]`
- **Environment:** Docker, no network, frozen API fixtures, no LLM, no database
- **Entry under test:** `mcp_server.search_remote_jobs(query, exclude_keywords)`
- **Pass condition:** `output.json` `apply_url` set exactly equals `expected.json` `keep` set
- **Evidence:** `prefilter.json` (pre-filter) + `output.json` (post-filter) + `result.json` (reward)
- **CI:** `.github/workflows/eval.yml` → `harbor run` → `check_reward.py` (exit 0/1/2)

→ Full details: [Harbor eval](evals/harbor-eval.md)

### Running locally

```bash
harbor run \
  -p evals \
  -i "*filter-exclusion-senior*" \
  -a evals.harbor_agents.pipeline_agent:PipelineAgent \
  -e docker \
  -o evals/jobs \
  --extra-docker-compose evals/configs/no-network.yaml \
  --job-name local-test -y

python evals/check_reward.py evals/jobs/local-test
```

Requires Docker and `uv tool install harbor`.

## LangSmith eval — live quality measurement

The LangSmith eval measures end-to-end quality against live job boards. It is run manually, not in CI, because the data moves.

- **Dataset:** `job-search-eval` (22 queries with reference answers)
- **Judge:** Gemini 2.5 Flash with structured output (`relevant` / `total`)
- **Score:** `relevant / total` per query, averaged
- **Baseline:** 0.812 (12 cases score 1.0)
- **Port:** `localhost:8002` (commit `6ef4e7c`)

→ Full details: [LangSmith eval](evals/langsmith-eval.md)

### Running

```bash
# Start the backend on port 8002
uvicorn main:app --port 8002

# In another terminal
python eval_runner.py
```

Requires `LANGSMITH_API_KEY` and `GEMINI_API_KEY`.

## Manual checks after changes

1. **Search:** `POST /ask` with a basic keyword query (e.g., `python developer`)
2. **Feedback:** Send `no MERN` and confirm `/feedback` updates memory (check the "Active filters" footer)
3. **Reset:** Send `reset filters` and confirm `/reset` clears exclusions
4. **Upload:** Upload a small PDF CV and verify `/upload` returns job listings
5. **MCP:** Start the MCP server and call `search_remote_jobs` from an MCP client
6. **n8n:** If in use, confirm `/evaluate` accepts the workflow payload with the correct `x-api-key`
7. **Harbor:** If `agent.py` or `mcp_server.py` changed, run the Harbor eval

## Good regression targets

- `filter_jobs` behavior changes (run Harbor eval)
- Scoring formula changes (run both evals)
- Source API changes or removal (re-run LangSmith, update Harbor fixtures if needed)
- Output format changes that break markdown rendering
- Memory persistence between requests
- Eval score drops after scoring or source edits

## Source references

- `eval_runner.py` — LangSmith harness
- `evals/` — Harbor task, adapter, verifier, CI
- `.github/workflows/eval.yml` — Harbor CI
- Commits `df2b58a` (CI), `60d33bc` (0.812 baseline), `bc47271` (frozen fixtures)
