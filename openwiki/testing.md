---
type: Guide
title: Testing & Quality Assurance
description: Comprehensive testing and quality assurance guide covering deterministic Harbor evaluations, live LangSmith benchmarks, same-day control discipline, and manual verification.
tags: [testing, evals, harbor, langsmith, regression, quality, ci, getro]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-05T16:18:10.477Z
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
generated: { by: "openwiki/0.9.0", at: "2026-11-05T16:18:10.477Z" }
---

# Testing & Quality Assurance

This repository has **no classic unit-test suite** — there is no `pytest` collection testing agent internals or isolated `unittest` modules. Instead, quality assurance is split between two distinct, complementary evaluation frameworks that answer fundamentally different questions. Neither suite subsumes the other:

1. **Harbor offline deterministic evaluation**: Measures exact filtering and keyword exclusion correctness (`filter_jobs`) using static, frozen HTTP responses across six job sources inside a network-isolated container (`network_mode: none`). It incurs zero token costs, executes in continuous integration on every push and pull request, and asserts exact listing membership with hand-verified expected sets.
2. **LangSmith live regression evaluation**: Measures end-to-end search relevance against live external job boards across 24 realistic benchmark queries. It evaluates complete agent pipelines using LLM-as-a-judge models (Gemini 3.5 Flash-Lite and Jev), guided by same-day control runs to distinguish code regressions from external market drift.

<!-- openwiki: mermaid parse failed and this diagram was converted to a text fence so it does not break rendering. Fix the diagram source and restore the mermaid fence. Parser error: Heuristic: an unescaped angle bracket inside a label breaks rendering; rephrase the label. -->
```text
flowchart TD
    subgraph Harbor["Harbor Eval (Offline Deterministic CI Gate)"]
        H1["mcp_server.search_remote_jobs"] --> H2["Frozen API Fixtures<br/>6 sources in Docker<br/>network_mode: none"]
        H2 --> H3["Artifacts:<br/>prefilter.json and output.json"]
        H3 --> H4["test_outputs.py pytest<br/>5 deterministic assertions"]
        H4 --> H5["check_reward.py<br/>Exit 0 pass, 1 eval fail, 2 infra error"]
    end

    subgraph LangSmith["LangSmith Eval (Live Quality Measurement)"]
        L1["eval_runner.py<br/>POST localhost:8002/askeval<br/>unique thread_id, EVALS key"] --> L2["Live Job Boards<br/>6 sources queried live"]
        L2 --> L3["Agent Response<br/>Formatted listings"]
        L3 --> L4["empty_ok Short-Circuit<br/>1.0 if empty is valid"]
        L3 --> L5["LLM Judges<br/>Gemini 3.5 Flash-Lite and Jev"]
        L4 --> L6["Aggregate Score<br/>Evaluated against same-day control"]
        L5 --> L6
    end
```
*Dual quality assurance architecture: deterministic offline filtering assertions in CI vs. live LLM-judged regression evaluation.*

## Evaluation Strategy Comparison

| Dimension | Harbor Evaluation ([harbor-eval.md](evals/harbor-eval.md)) | LangSmith Evaluation ([langsmith-eval.md](evals/langsmith-eval.md)) |
|---|---|---|
| **What it measures** | Filter exclusion logic (`filter_jobs`), seniority gating, and candidate admission invariants | End-to-end relevance, query parsing, and result quality across live job markets |
| **Target under test** | `mcp_server.search_remote_jobs(query, exclude_keywords)` (unmodified production MCP tool) | `POST /askeval` FastAPI endpoint (unmodified agent graph, memory disabled, cache bypassed) |
| **Data source** | Static frozen API fixtures (6 sources) captured in repository files | Live job boards (RemoteOK, Himalayas, Remotive, Jobicy, Workable, Getro) |
| **Execution environment** | Docker container with `network_mode: none` and monkey-patched `requests` stubs | Local process posting to `localhost:8002` with external network and LLM access |
| **Verifier / Judge** | Deterministic `pytest` assertions in `test_outputs.py` against hand-written `expected.json` | Gemini 3.5 Flash-Lite structured output judge + Jev classifier (OpenRouter) |
| **Execution frequency** | CI gate on every push/PR touching `agent.py`, `mcp_server.py`, or `evals/**` | On-demand manual runs when modifying ranking algorithms, query parsing, or prompts |
| **Cost & Dependencies** | 0 tokens, no API keys, no database; requires Docker and `uv` | Consumes LLM API tokens; requires `LANGSMITH_API_KEY`, `GEMINI_API_KEY`, and `EVALS` key |
| **Pass condition** | Exact set match: reward 1.0 (6 kept, 6 dropped listings) | Precision score ($\text{relevant} / \text{total}$) benchmarked against same-day control (~0.90 baseline) |

---

## Harbor Deterministic Evaluation (Offline CI Gate)

The Harbor evaluation framework lives in `evals/`. It freezes one snapshot of every job source, executes the repository's production MCP tool (`search_remote_jobs`) against those fixtures with all network calls disabled, and evaluates the resulting set. Because there is no LLM and no live network in this path, the test produces the identical verdict every time.

- **Task directory:** `evals/filter-exclusion-senior/`
- **Standard test query:** `python developer`, with exclusions `["senior", "game", "canonical"]`
- **Pass condition:** The `apply_url` set in `output.json` matches the hand-written `keep` set in `expected.json` exactly (6 kept, 6 dropped).
- **CI enforcement:** Executed by `.github/workflows/eval.yml` and validated by `evals/check_reward.py`.

### Six Frozen Sources in `frozen_apis.py`

The evaluation environment routes all HTTP traffic through `evals/filter-exclusion-senior/environment/frozen_apis.py`. The harness supports **six** distinct sources:

```python
HOSTS = {
    "remoteok.com": "remoteok.json",
    "himalayas.app": "himalayas.json",
    "remotive.com": "remotive.json",
    "jobicy.com": "jobicy.json",
}
WORKABLE = "jobs.workable.com"
GETRO = "api.getro.com"
```

1. **JSON API GET sources (`HOSTS`)**: RemoteOK, Himalayas, Remotive, and Jobicy match hostnames directly to captured JSON files in `environment/fixtures/`.
2. **Workable HTML scraping (`WORKABLE`)**: Workable requires two rounds of requests. `workable_fixture(parts.path)` routes `/search/...` requests to `fixtures/workable/search-python.html` and `/view/<id>/...` detail requests to `fixtures/workable/view-{job_id}.html`. The fixture files are reduced to the schema.org `ItemList` and `JobPosting` JSON-LD blocks that `agent.py` actually parses.
3. **Getro VC search POST source (`GETRO`)**: Handled via `frozen_post` as described below.

### How Getro Mock Responses are Tested

Getro (`api.getro.com`) searches across portfolio companies of 9 venture capital funds (`GETRO_VCS`). Unlike the other five sources, Getro uses HTTP POST requests with JSON payloads containing search terms and remote filters (`filters: {"work_mode": ["remote"]}`).

In `evals/filter-exclusion-senior/environment/frozen_apis.py`, `frozen_post(url, *args, **kwargs)` implements mock response dispatch:

```python
def frozen_post(url, *args, **kwargs):
    parts = urlparse(url)
    if parts.hostname != GETRO:
        raise RuntimeError(f"unfrozen host: {parts.hostname}")
    vc = parts.path.split("/collections/")[1].split("/")[0]
    query = (kwargs.get("json") or {}).get("query") or ""
    captured = json.loads((FIXTURES / "getro.json").read_text(encoding="utf-8"))
    jobs = captured.get(vc, {}).get(query, [])
    return FrozenResponse(payload={"results": {"jobs": jobs, "count": len(jobs)}})
```

- **Extraction**: The stub extracts the fund collection ID (`vc`) from the URL path (`/collections/{vc}/search/jobs`) and the query term from `kwargs["json"]["query"]`.
- **Fixture lookup**: Responses are loaded from `fixtures/getro.json`, which indexes job listings hierarchically by fund ID and query string (`captured.get(vc, {}).get(query, [])`).
- **Default fallback**: If a fund or query was not captured, `frozen_post` returns `{"results": {"jobs": [], "count": 0}}`, mirroring Getro's live API behavior for non-matching queries.
- **In-process network blocking**: `frozen_apis.py` patches `requests.get = frozen_get` and `requests.post = frozen_post`. All other HTTP methods (`put`, `patch`, `delete`, `head`, `options`, `requests.Session.request`) are reassigned to `blocked()`, which raises `RuntimeError("live network access is not available in this environment")`.
- **Invariant on `expected.json`**: When Getro was added as the 6th source, `requests.post` had to be mocked. However, both captured Getro listings score lower than the top 12 listings during `collect_results` ranking (Getro listings provide skill tags rather than full descriptions, generating fewer bonus hits). Because neither listing penetrates the top 12 cut (`MAX_RESULTS = 12`), Getro's integration did not displace any listings in `expected.json`. The test confirms that adding Getro executes cleanly inside the fan-out graph without perturbing existing exclusions.

### Title Match Test Updates ('developer' matching 'engineer')

Technical job listings treat "developer" and "engineer" as equivalent, but exact token matching previously split searches into disjoint sets. To unify them, `agent.py` configures `ALIASES`:

```python
ALIASES = {
    ...
    "developer": "engineer",
}
```

This aliasing directly governs candidate admission in `collect_results`:

```python
wants_engineer = title_hit("engineer", canon(query))
matched = [pair for pair in scored if pair[0] >= TITLE_WEIGHT and (not wants_engineer or title_hit("engineer", job_title(pair[1])))]
```

When evaluating the query `python developer`:
1. `canon("python developer")` normalizes the query to `"python engineer"`.
2. `wants_engineer` evaluates to `True` (`title_hit("engineer", "python engineer")`).
3. Candidate jobs must satisfy `title_hit("engineer", job_title(job))`.
4. Because `job_title(job)` runs `canon()` on listing titles, a posting titled `"Python Developer"` canonicalizes to `"python engineer"` and passes the check. Crucially, postings titled `"Python Engineer"` or `"Senior Software Engineer"` also canonicalize to contain `"engineer"` and pass the admission gate.

#### Role in Harbor Verification

In the Harbor test fixtures, Jobicy provides three listings:
- `"Python Engineer"` (#149543)
- `"Python and Kubernetes Software Engineer"` (#149563)
- `"Senior Software Engineer - Python/MongoDB"` (#149974)

Because `"developer"` matches `"engineer"`, all three Jobicy engineer listings pass the `wants_engineer` admission gate and enter the 12 candidate listings in `prefilter.json`. Inside `filter_jobs`:
- The senior listing is dropped by the title-only rule (`"senior"` in `SENIORITY`).
- The two other Jobicy listings are dropped by the full-text rule because `"canonical"` appears in their descriptions.

Without the `'developer'` $\to$ `'engineer'` equivalence, Jobicy's engineer listings would be rejected during admission, causing `prefilter.json` to miss expected listings and failing the environment integrity check in `test_outputs.py`.

### Verifier Assertions and Hand-Written Expected Sets

`evals/filter-exclusion-senior/tests/test_outputs.py` runs under pytest and executes five deterministic checks:

| Assertion | Guarded Invariant |
|---|---|
| `test_the_filter_saw_the_frozen_listings` | `urls(prefilter) == set(expected["keep"]) \| set(expected["drop"])`. Guards against environment drift; confirms all 12 expected listings entered the filter. |
| `test_no_seniority_match_in_a_title_survived` | All output listings have no `"senior"` in `position`. Tests the title-only exclusion branch for `SENIORITY` terms. |
| `test_no_free_keyword_match_survived` | All output listings have no `"game"` or `"canonical"` in full text (`title + description + location`). Tests full-text exclusions. |
| `test_nothing_valid_was_dropped` | `set(expected["keep"]) - urls(output) == set()`. Guards against over-filtering valid roles. |
| `test_exact_result_set` | `urls(output) == set(expected["keep"])`. Verifies exact equality with the 6 kept listings. |

The expected set in `evals/filter-exclusion-senior/tests/expected.json` is written entirely by hand from fixture inspection (6 kept, 6 dropped). The verifier never executes `filter_jobs` to generate expectations, preventing the test from grading the code against itself.

### CI Workflow and Exit Codes

Continuous integration is handled by `.github/workflows/eval.yml`. The workflow triggers on push to `main` and on pull requests when changes touch `agent.py`, `mcp_server.py`, `evals/**`, or `.github/workflows/eval.yml`.

Harbor outputs a reward of `1.0` (all tests passed) or `0.0` (assertion failure) into `result.json`. Because the Harbor runner itself always exits with status code 0, CI invokes `evals/check_reward.py` to translate the trial reward into a build verdict:

- **Exit 0 (Pass)**: All trial rewards equal `1.0`. Build turns green.
- **Exit 1 (Eval Failed)**: A trial reward was not `1.0` (filter logic regression or over/under-filtering). `check_reward.py` prints failed pytest assertions and stack traces; build turns red.
- **Exit 2 (Infrastructure Error)**: Container failed to run, trial was cancelled/errored, or `result.json` was never created. Build turns red.

Trial artifacts under `evals/jobs/` are uploaded to GitHub Actions on every run and retained for 14 days.

### Harbor Execution Instructions

To execute the deterministic Harbor evaluation locally:

```bash
# 1. Install Harbor CLI tool via uv
uv tool install harbor

# 2. Execute the evaluation task inside Docker with network disabled
PYTHONPATH=$(pwd) harbor run \
  -p evals \
  -i "*filter-exclusion-senior*" \
  -a evals.harbor_agents.pipeline_agent:PipelineAgent \
  -e docker \
  -o evals/jobs \
  --extra-docker-compose evals/configs/no-network.yaml \
  --job-name local -y

# 3. Inspect trial reward and verify exit status
python evals/check_reward.py evals/jobs/local
```

`PYTHONPATH=$(pwd)` allows Harbor to import the `evals.harbor_agents.pipeline_agent:PipelineAgent` adapter. Docker is required; no API keys, credentials, or databases are needed.

---

## LangSmith Live Regression Evaluation

The LangSmith evaluation framework measures end-to-end relevance against live job boards. It is executed manually rather than in CI because live job listings shift continuously, meaning individual query scores fluctuate naturally between runs.

- **Dataset:** `job-search-eval` (24 queries in LangSmith).
- **Harness:** `eval_runner.py` sends POST requests to `http://localhost:8002/askeval`.
- **Target endpoint:** `/askeval` runs the production agent fan-out graph while bypassing the 4-hour Redis search cache (`jobs:*`) and providing a fresh UUID `thread_id` per query to avoid memory leakage.
- **Judge models:** Gemini 3.5 Flash-Lite (`model="google_genai:gemini-3.5-flash-lite"`) and Jev (`typesafe/jev-1.13` classifier on OpenRouter, threshold 0.5).
- **Metric:** Precision score ($\text{relevant} / \text{total}$) averaged across all 24 cases.

### Evaluator Architecture in `eval_runner.py`

`eval_runner.py` configures two active evaluators executed in parallel for every test query:

```python
client.evaluate(
    run_agent,
    data="job-search-eval",
    evaluators=[jev_correctness, gemini_listing_correctness],
    experiment_prefix="gemini35lite-jev-perjob",
)
```

1. **`gemini_listing_correctness`**: Invokes Gemini 3.5 Flash-Lite with structured output (`JobOutput(reason: str, relevant: bool)`). It grades each listing individually against reference criteria, explicitly accounting for subtleties: company product mentions do not disqualify a role, and full-stack positions with backend leanings remain valid full-stack roles.
2. **`jev_correctness`**: Queries the OpenRouter decisions endpoint (`https://openrouter.ai/api/alpha/decisions`) using `typesafe/jev-1.13`. It returns a probability per listing; any listing scoring $\ge 0.5$ is marked relevant.
3. **`gemini_full_correctness` (Baseline)**: Evaluates the whole markdown response at once using `Output(reason: str, relevant: int, total: int)` with Pydantic validation.
4. **`laya_correctness` (Local Alternative)**: Posts to a local container running Laya multilingual classifier (`http://127.0.0.1:8000/v1/systemone`). In benchmark trials, Laya was rejected due to excessive leniency (accepting 203 of 225 listings, including Freight Broker for LangChain agent).

### Repeatability and Judge Calibration

Before judge calibration, identical result sets scored 0.889 and 0.222 on consecutive runs. Three design invariants established judge repeatability:

1. **`empty_ok` Short-Circuit**: Five test cases have a correct response of zero listings (intentional typos such as `pyton developer`, or obscure niches like `COBOL mainframe developer`). These examples carry `empty_ok: true` in the dataset. If the agent returns zero listings, `eval_runner.py` immediately awards a score of `1.0` without invoking an LLM judge.
2. **Strict Grading Constraints**: The prompt instructs the judge that evaluation is strictly confined to returned listings: a non-matching listing subtracts one point without invalidating other matches, and silent reference criteria count in the listing's favor.
3. **Decidable Criteria Contracts**: Benchmark references are phrased as explicit contracts ("a listing is relevant when... and is not relevant when..."), eliminating subjective judgment on ambiguous roles.

### Same-Day Control Discipline

Because external job boards update constantly, changes must **never be evaluated against a historical baseline from a previous week**. The same unchanged code can score 0.82 one morning and 0.765 five days later purely due to external board turnover. A single query like `rust` can swing from 1.0 to 0.5 across five days with zero code changes.

When evaluating an algorithm or heuristic change:
1. Run `python eval_runner.py` on the **unmodified base branch** (control run).
2. Run `python eval_runner.py` on the **feature branch** on the same day.
3. Compare the delta between the two same-day runs. An aggregate increase indicates genuine algorithm improvement.

### Historical Benchmark Progressions

Every algorithmic refinement in the search graph was measured against live boards. Most of the overall precision gain came from removing artificial padding and tightening candidate admission:

| Refinement Phase | Benchmark / Control Score | Resulting Score | Key Insight / System Invariant |
|---|---|---|---|
| **Initial Starting Point** | — | **0.558** | Baseline precision across original 22 test cases. |
| **Untrusted RemoteOK Tags** | 0.558 | **0.575** | Switched from trusting noisy platform tags to matching words in job titles. |
| **Removed 8-Result Minimum** | 0.575 | **0.679** | Eliminated padding where a single genuine match like `rust` pulled in 7 body-text mentions. |
| **Treated Dev/Eng as Distinct** | 0.679 | *0.584 (reverted)* | Treating "developer" and "engineer" as distinct words severely degraded recall; reverted and unified via `ALIASES`. |
| **Typo Reference Corrections** | 0.679 | **0.751** | Explicitly flagged typo queries (`pyton developer`) as expecting 0 listings (`empty_ok: true`). |
| **Generic Word Set Comma Fix** | 0.751 | **0.812** | Fixed missing comma between string literals in Python set that dropped `"engineer"` and `"remote"`. |
| **Market Turnover Drift Check** | 0.812 (Aug 6) | *0.765 (Aug 11)* | Unmodified code dropped to 0.765 purely from board turnover, establishing same-day control rule. |
| **Title Tie-Breaking Generic Word** | 0.765 (Control) | **0.780** | Generic words in queries break score ties among admitted listings (+3 cases up, 0 down). |
| **Description Frequency & Source Truncation** | 0.760 (Control) | **0.820** | Scored body text on word frequency rather than presence; removed 10-listing source cap (+5 cases up). |
| **Dataset Expansion (24 Cases)** | 0.820 | **~0.900** | Added real user queries from logs (`Remote React jobs`, `Fullstack react remote jobs`). |
| **Gemini 3.5 Flash-Lite Migration** | 0.840 (2.5 Flash) | **0.833** | Replaced retiring 2.5 Flash with 3.5 Flash-Lite (consistent 0.833 across 3 repeated runs; 195/195 agreed). |

### LangSmith Execution Instructions

To execute the live LangSmith evaluation suite:

```bash
# Terminal 1: Launch backend API server on port 8002
uvicorn main:app --port 8002

# Terminal 2: Run LangSmith evaluation harness
python eval_runner.py
```

#### Required Environment Variables

```bash
export LANGSMITH_API_KEY="lsv2_pt_..."       # LangSmith tracing and dataset access
export GEMINI_API_KEY="AIzaSy..."           # Google Gemini judge model
export EVALS="your-evals-api-key"           # Passed as x-api-key to /askeval
export OPENROUTER_API_KEY="sk-or-..."       # Required for Jev classifier judge
```

#### Optional Local Laya Classifier

`eval_runner.py` includes support for `laya_correctness`, a local multilingual classifier:

```bash
docker build -t laya laya
docker run --name laya -p 127.0.0.1:8000:8000 -v laya-hf:/root/.cache/huggingface laya
```

---

## Manual Verification Runbook

In addition to automated evaluations, run these manual validation steps after modifying API integrations or runtime components:

1. **Basic Search:** `POST /ask` with `{"user_input": "python developer", "thread_id": "test-1"}` and confirm formatted markdown listings return.
2. **Negative Feedback:** Send `{"user_input": "no senior roles", "thread_id": "test-1"}` and confirm `/feedback` updates thread memory (verified in the "Active filters" footer).
3. **Filter Reset:** Send `{"user_input": "reset filters", "thread_id": "test-1"}` and confirm `/reset` clears thread memory.
4. **CV Upload:** Upload a PDF resume to `/upload` and ensure parsed skills trigger matching job recommendations.
5. **MCP Server:** Run `python mcp_server.py` and invoke `search_remote_jobs(query="rust developer")` from Claude Desktop or Claude Code.
6. **n8n Automation:** Confirm `/evaluate` accepts candidate evaluation payloads when supplied with a valid `x-api-key`.
7. **Harbor Regression Check:** Run local Harbor evaluation if edits touched `agent.py`, `mcp_server.py`, or ranking heuristics.

---

## Regression Target Matrix

| Changed Component | Primary Risk | Verification Step |
|---|---|---|
| `filter_jobs` | Over-filtering or exclusion leakage | Run deterministic Harbor evaluation (`harbor run`) |
| `collect_results` / Scoring | Ranking distortion or title gate rejection | Run Harbor eval (verifies 12-listing prefilter) and same-day LangSmith control run |
| `ALIASES` / `canon()` | Disjoint role matches ('developer' vs 'engineer') | Harbor eval prefilter assertion (`urls(prefilter)`) and LangSmith evaluation |
| Source API fetchers (`fetch_*`) | Schema changes or missing fields | Harbor eval (guards against fan-out errors) and manual endpoint testing |
| New Job Source Addition | Fan-out crashes or network leaks | Add fixture to `frozen_apis.py`, update `expected.json` if top 12 cut changes, run Harbor eval |
| Memory / `PostgresSaver` | Filter state persistence breakdown | Manual conversation testing (`/feedback` followed by search) |
| Output Formatting | Broken markdown links or card layouts | Manual chat UI inspection |

---

## Source & Fixture File Map

- `evals/filter-exclusion-senior/` — Harbor task configuration:
  - `task.toml` — Harbor task definition, timeouts, and entry commands.
  - `instruction.md` — Test specification instructing the agent to search `python developer` with exclusions `["senior", "game", "canonical"]`.
  - `environment/Dockerfile` — Container definition for offline execution.
  - `environment/frozen_apis.py` — Mock request router patching `requests.get` and `requests.post` with fixtures and blocking all other network access.
  - `environment/fixtures/` — Static captured responses:
    - `remoteok.json`, `himalayas.json`, `remotive.json`, `jobicy.json`
    - `workable/search-python.html` and `workable/view-*.html`
    - `getro.json` — Nested fund and query responses for VC portfolio search.
  - `tests/expected.json` — Hand-written 6 kept and 6 dropped listing URLs.
  - `tests/test_outputs.py` — Deterministic pytest verifier with 5 assertions.
  - `tests/test.sh` — Pytest test runner writing `1` or `0` to reward file.
- `evals/harbor_agents/` — Adapters and harnesses:
  - `pipeline_agent.py` — BaseAgent adapter uploading `agent.py` and `mcp_server.py` unmodified.
  - `run_pipeline.py` — Container harness invoking `mcp_server.search_remote_jobs` and writing `prefilter.json` and `output.json`.
- `evals/configs/no-network.yaml` — Docker Compose overlay enforcing `network_mode: none`.
- `evals/check_reward.py` — Build verdict validator converting Harbor output into exit codes 0, 1, or 2.
- `.github/workflows/eval.yml` — GitHub Actions CI definition for Harbor evaluation.
- `eval_runner.py` — LangSmith test harness (posts to `/askeval`, runs Gemini 3.5 Flash-Lite and Jev judges).

---

## Related Documentation

- [Harbor Offline Evaluation](evals/harbor-eval.md) — Exhaustive technical breakdown of the Harbor deterministic evaluation harness, Docker isolation, and verifier logic.
- [LangSmith Evaluation](evals/langsmith-eval.md) — Comprehensive guide to live regression testing, judge calibration history, and per-listing classifier comparisons.
- [Workflows](workflows.md) — End-to-end user workflows, API contracts, and n8n background execution.
- [Domain Heuristics](domains.md) — Specification of token canonicalization, scoring weights, and seniority filtering rules.
- [Agent Graph](architecture/agent-graph.md) — LangGraph fan-out architecture across the six search sources.
- [MCP Server](mcp-server.md) — Design and integration of the Model Context Protocol search tool under test.
