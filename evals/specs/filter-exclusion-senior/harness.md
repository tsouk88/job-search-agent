# Harness — filter-exclusion-senior

## What Harbor runs as the Agent

The repository's own job-search pipeline. No LLM is in this path: search and
filtering became fully deterministic on 29-30/07 when `chain.invoke()` was
removed from the search flow.

Entrypoint under test: `mcp_server.search_remote_jobs(query, exclude_keywords)`
(`mcp_server.py:33`). This is the production MCP tool, chosen over the REST
`/ask` path because it takes the exclusion list as an explicit parameter
instead of reading it from a Postgres checkpointer — no database, no keys,
no LLM extraction step.

Reachable code, unchanged:

- `agent.graph` — fan-out to four fetchers (`agent.py:245`), then
  `collect_results` (`agent.py:219`): dedup by apply URL, `score_job`,
  keep only `>= TITLE_WEIGHT` (title match), sort, cut at `MAX_RESULTS = 12`.
- `agent.normalize_jobs` (`agent.py:101`) — field unification, salary and
  mojibake cleanup, hash dedup.
- `agent.filter_jobs` (`agent.py:28`) — **the capability under test**.
  Seniority terms are matched against the title only (`title_only=SENIORITY`);
  every other keyword is matched against title + description + location.

## Adapter

`evals/harbor_agents/pipeline_agent.py`

1. Imports `environment/frozen_apis.py` first, which patches `requests.get`
   before `agent` is imported.
2. Reads the fenced JSON block from `instruction.md` — the request, not a
   decision. The adapter chooses nothing: query and exclusions come from the
   instruction, results come from the pipeline.
3. Calls `search_remote_jobs(query, exclude_keywords)`.
4. Writes the returned list verbatim to `/workspace/output.json`, plus
   `/workspace/prefilter.json` (the pipeline output *before* `filter_jobs`)
   as Harness-recorded evidence of what the filter was given.

The adapter contains no answer, no expected set, and no filtering logic.

## Credentials

None. `GEMINI_API_KEY`, `DATABASE_URL` and `EVALUATE_TOKEN` are not read on
this path and must not be present in the container.

## Reconstruction differences from production

- Production reaches four live HTTP APIs; here they are frozen (see
  `environment.md`).
- Production MCP caching (`_cache`, 4h TTL, `mcp_server.py:15`) is cold on
  every trial — one process, one call, so the cache never returns.
- `agent.py`, `mcp_server.py` are copied into the image **unmodified**. A
  change to either invalidates prior run evidence; record their digest
  outside the task directory.
