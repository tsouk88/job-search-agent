---
type: Reference
title: Testing and Evals
description: Two eval systems — the deterministic Harbor eval (frozen fixtures for five sources, CI, exact-set assertions) and the LangSmith eval (live job boards, LLM judge, ~0.90 baseline over 24 cases). No classic unit test suite.
tags: [testing, evals, harbor, langsmith, regression, quality, ci]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-01T12:03:35.670Z
sources:
  - id: openwiki-source-9ea7004cd60fc78ed888a032
    resource: repo://.github/workflows/eval.yml
  - id: openwiki-source-f1644da1c1a64a6a6567706b
    resource: repo://eval_runner.py
  - id: openwiki-source-1d64a0979a354ad458b3519a
    resource: repo://evals/check_reward.py
  - id: openwiki-source-a68f947821d6952a6d4a07df
    resource: repo://evals/configs/no-network.yaml
  - id: openwiki-source-4ea2d16d70ad274641c7935e
    resource: repo://evals/filter-exclusion-senior/environment/frozen_apis.py
  - id: openwiki-source-ab20f2fabcf9dffc06e9a9a7
    resource: repo://evals/filter-exclusion-senior/tests/expected.json
  - id: openwiki-source-6f3a365387ad1dfc55a94d24
    resource: repo://evals/filter-exclusion-senior/tests/test_outputs.py
  - id: openwiki-source-1691a76fbd7a6781b3420f6c
    resource: repo://evals/harbor_agents/run_pipeline.py
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "openwiki/0.6.1", at: "2026-10-01T12:03:35.670Z" }
---

# Testing and evals

This repository has **no classic unit-test suite**. The two eval systems below are the entire quality gate — there is no `pytest` collection of agent internals, no `unittest` modules. One eval is deterministic and runs in CI; the other measures live quality by hand. They answer different questions and neither subsumes the other.

| System | What it measures | Data | Verifier | CI | Current |
|---|---|---|---|---|---|
| [Harbor eval](evals/harbor-eval.md) | `filter_jobs` exclusion logic | Frozen fixtures for **five** sources (RemoteOK, Himalayas, Remotive, Jobicy, Workable), captured 04/08/2026 | Deterministic pytest assertions (exact set) | Yes (push/PR touching `agent.py`/`mcp_server.py`/`evals/**`/`eval.yml`) | 1 trial passes |
| [LangSmith eval](evals/langsmith-eval.md) | End-to-end search quality | Live job boards (24 queries) | Gemini 2.5 Flash LLM judge | No (manual) | ~0.90 over 24 cases (16 August) |

## CI workflow

<!-- openwiki: broken internal link [.github/workflows/eval.yml] file ".github/workflows/eval.yml" does not exist. Fix the href or restore the target, then delete this comment. -->
Quality is gated in CI by [`.github/workflows/eval.yml`](.github/workflows/eval.yml), the *Filtering eval* workflow. It triggers on `pull_request` and on `push` to `main` whenever the changed paths include `agent.py`, `mcp_server.py`, `evals/**`, or `.github/workflows/eval.yml` (plus `workflow_dispatch` for manual runs).

The job installs Harbor with `uv tool install harbor`, then runs the one Harbor task with `PYTHONPATH` set to the workspace, and converts the Harbor job into a build verdict with `check_reward.py`:

```bash
harbor run \
  -p evals \
  -i "*filter-exclusion-senior*" \
  -a evals.harbor_agents.pipeline_agent:PipelineAgent \
  -e docker -o evals/jobs \
  --extra-docker-compose evals/configs/no-network.yaml \
  --job-name ci-${{ github.run_id }} -y

python evals/check_reward.py evals/jobs/ci-${{ github.run_id }}
```

`check_reward.py` distinguishes three outcomes by exit code: **0 pass**, **1 eval failed** (the filter changed behavior — a reward was not 1.0), **2 infrastructure error** (the harness never ran, e.g. errored/cancelled trials or a missing `result.json`). Harbor itself always exits 0 whether the code passed or failed, so this step is what turns a green Harbor run red when the assertion breaks. The run evidence under `evals/jobs/` is uploaded as a build artifact on every run (success or failure) and kept for 14 days.

No LangSmith eval runs in CI — it hits live job boards and costs LLM tokens, so it is run by hand.

## Harbor eval — deterministic

The Harbor eval is the CI gate. It freezes one capture of every job source, runs the repository's own search pipeline against those fixtures with the network disabled, and asserts the output set by hand. A red build means the filter changed behavior — there is no model and no judgement in this path.

- **Task:** `filter-exclusion-senior` — query `python developer`, exclude `["senior", "game", "canonical"]`
- **Environment:** Docker container with `network_mode: none`, frozen API fixtures, no LLM, no database, no credentials
- **Entry under test:** `mcp_server.search_remote_jobs(query, exclude_keywords)` — the production MCP tool, chosen over the REST `/ask` path because it takes exclusions as an explicit parameter (no Postgres, no LLM extraction)
- **Adapter:** `evals/harbor_agents/pipeline_agent.py` uploads `agent.py` and `mcp_server.py` **unmodified** plus `run_pipeline.py`, then records what the pipeline produced
- **Pass condition:** the `apply_url` set in `output.json` equals the hand-written `keep` set in `expected.json` exactly (7 kept, 5 dropped)
- **Evidence:** `prefilter.json` (pipeline output *before* `filter_jobs`) + `output.json` (post-filter) + `result.json` (reward)
- **Verifier:** `evals/filter-exclusion-senior/tests/test_outputs.py` — pytest, run via `tests/test.sh`, never calls `filter_jobs` itself

The verifier asserts four things: it saw the frozen listings at all (`test_the_filter_saw_the_frozen_listings`, which guards the environment against a fan-out or fixture change), no excluded seniority term survived in a title, no excluded free keyword survived anywhere, nothing valid was dropped, and the result set is exact. The expected sets are written by hand from the fixtures — a verifier that recomputed the answer with `filter_jobs` would be grading the code against itself and pass forever.

→ Full details: [Harbor eval](evals/harbor-eval.md)

### Five sources, including Workable

The frozen environment now knows **five** hosts. Four are JSON APIs (`remoteok.com`, `himalayas.app`, `remotive.com`, `jobicy.com`) routed by `evals/filter-exclusion-senior/environment/frozen_apis.py` to one captured response each. Workable is different: it is HTML, fetched in two rounds (one search page for the links, then a page per listing), and its captured pages are kept down to the schema.org `ItemList`/`JobPosting` blocks the parser actually reads.

Adding Workable is what turned the eval red before anything shipped. The frozen environment knew four hosts and refused the fifth, because the fan-out had changed and every assertion after it would have been measuring something else. The expected set was rewritten by hand from the new fixtures: three Workable listings joined the kept set, its senior listing joined the dropped set, and a Jobicy listing left both, because twelve places are still twelve and a fifth source competes for them.

### What it does not cover

One query, one moment in the market, and no listing in the capture carries "senior" in its description alone — so the rule that seniority is judged on titles only is never tested in the one shape that separates it from ordinary matching. The fixtures are real captured data and were not edited to manufacture that case. A useful negative control: deleting `senior` from the seniority list does **not** fail, because the word would still match the same title as an ordinary keyword. The control that does fail is collapsing the branch selection in `filter_jobs` so every keyword is matched against titles only — that takes the reward from 1.0 to 0.0.

### Running locally

```bash
uv tool install harbor

PYTHONPATH=$(pwd) harbor run -p evals -i "*filter-exclusion-senior*" \
  -a evals.harbor_agents.pipeline_agent:PipelineAgent \
  -e docker -o evals/jobs \
  --extra-docker-compose evals/configs/no-network.yaml \
  --job-name local -y

python evals/check_reward.py evals/jobs/local
```

`PYTHONPATH=$(pwd)` is required so Harbor can import `evals.harbor_agents.pipeline_agent:PipelineAgent`. Docker is the only other requirement — no API key, because nothing in this path calls a model.

## LangSmith eval — live quality measurement

The LangSmith eval measures end-to-end quality against live job boards. It is run manually, not in CI, because the data moves: two runs an hour apart can return different listings and individual cases wobble by a lot. The aggregate is the signal, not any single row.

- **Dataset:** `job-search-eval` — 24 queries, each carrying a written `referenceOutput` (what a good answer looks like) and an optional `empty_ok` flag
- **Harness:** `eval_runner.py` posts each query to `http://localhost:8002/ask` with a fresh UUID `thread_id` (no memory carried between cases), 180s timeout
- **Judge:** Gemini 2.5 Flash with structured output (`reason`, `relevant`, `total`; `total` must be ≥ 1)
- **Score:** `relevant / total` per query, averaged — padding a response with weak matches lowers the score
- **Baseline:** ~0.90 across 24 cases (16 August); before the two real-user queries were added it was ~0.85, and before the judge was fixed it was 0.82 over 22 cases
- **Port:** `localhost:8002` — start the backend there before running

→ Full details: [LangSmith eval](evals/langsmith-eval.md)

### Making the judge repeatable

The baseline was not trusted until the judge itself was audited and rewritten, because two runs scored the *same* nine listings 0.889 and 0.222 (and the aggregate barely moved, which is worse than an obviously unstable number). Three changes, in order of how much they bought:

1. **`empty_ok` short-circuit.** ~five queries have a correct answer of *nothing* (deliberate misspellings like `pyton developer`, niches like `COBOL mainframe developer` the boards may not be advertising). Those examples now carry an `empty_ok` flag, and an empty response short-circuits to 1.0 before the judge is called. Four of the five already said so in their reference text; the model had the instruction and applied it unevenly.
2. **Explicit grading.** The prompt now states that grading covers only what was returned, that a rejected listing subtracts one and nothing more (it never invalidates the others), and that criteria silent about a listing count in its favour. Both readings had been live, which was exactly the 0.889/0.222 split.
3. **Decidable reference criteria.** Ten of the cases were rewritten as "a listing is relevant when… and is not relevant when…", resolved against the listings the agent actually returns, so the model is never asked to decide an underspecified case.

### Control-run methodology

Changes here are judged against a **control run of the unchanged code on the same day**, never against a number from last week. The same code scored 0.765 five days later without a line changing — the job boards had moved — so comparing a new run to a stored baseline measures the market as much as the change, and the market is louder. A single case can swing half a point on its own (`rust` went 1.0 → 0.5 across five days on a query with no moving parts in the code). Treat the ~0.90 figure as a range, not a reading.

### Running

```bash
# Start the backend on port 8002
uvicorn main:app --port 8002

# In another terminal
python eval_runner.py
```

Requires `LANGSMITH_API_KEY` and `GEMINI_API_KEY` in the environment. The runner posts to `localhost:8002/ask`; change the port in `eval_runner.py` if your backend runs elsewhere.

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

- `eval_runner.py` — LangSmith harness (posts to `/ask`, Gemini judge, `empty_ok` short-circuit)
- `evals/` — Harbor task, adapter, verifier, fixtures, CI
- `evals/check_reward.py` — turns a Harbor job into a build verdict (exit 0/1/2)
- `evals/filter-exclusion-senior/` — the task: `instruction.md`, `task.toml`, environment, fixtures, tests
- `evals/harbor_agents/pipeline_agent.py` — adapter that runs the pipeline as the Harbor agent
- `.github/workflows/eval.yml` — Harbor CI
- `evals/specs/` — design notes for the harness, environment, and task
