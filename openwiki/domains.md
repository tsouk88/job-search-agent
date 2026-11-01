---
type: Reference
title: Domain Concepts
description: Core domain concepts — five-source job aggregation, normalization and mojibake repair, alias-based query canonicalization, title-weighted scoring with frequency-based description contribution and generic-word tie-breaking, signal tokens, thread memory and the seniority/full-text filter split, country/location matching, age filtering, resume-derived search intent, and evaluation semantics.
tags: [domain, concepts, agent, memory, evaluation, scoring, filtering, canonicalization]
sources:
  - id: openwiki-source-eca60e2ced68ba99bd0ac710
    resource: repo://agent.py
  - id: openwiki-source-f1644da1c1a64a6a6567706b
    resource: repo://eval_runner.py
  - id: openwiki-source-ab20f2fabcf9dffc06e9a9a7
    resource: repo://evals/filter-exclusion-senior/tests/expected.json
  - id: openwiki-source-6f3a365387ad1dfc55a94d24
    resource: repo://evals/filter-exclusion-senior/tests/test_outputs.py
  - id: openwiki-source-18837785d6eee548467c07ac
    resource: repo://evals/harbor_agents/pipeline_agent.py
  - id: openwiki-source-1691a76fbd7a6781b3420f6c
    resource: repo://evals/harbor_agents/run_pipeline.py
  - id: openwiki-source-185f850c083bac055a13cd37
    resource: repo://helper.py
  - id: openwiki-source-833e692518af9eeaf8564cc6
    resource: repo://main.py
  - id: openwiki-source-3ea4f69fcc0222dbd310ddfc
    resource: repo://tasks.py
verified:
  - by: openwiki/0.6.1
    at: 2026-11-01T14:50:14.085Z
generated: { by: "openwiki/0.6.1", at: "2026-11-01T14:50:14.085Z" }
---

# Domain concepts

## Job source aggregation

The core domain object is a remote job listing gathered from **five public sources**, each queried differently:

- **RemoteOK** — tag-based: the `distinctive_tokens` of the query are tried as `?tags=` one at a time, stopping as soon as a tag returns `ENOUGH` (50) listings. The fetched page is then **re-checked against its own title** (tags are SEO filler), via `title_hit` over `signal_tokens`. The first keyword alone costs one request in the common case.
- **Himalayas** — full query search (`q=`), worldwide, sorted by recent. A 429 returns nothing rather than retrying.
- **Remotive** — a **cached feed, not a search**: `remotive_feed()` holds a module-level `_REMOTIVE` dict for `REMOTIVE_TTL = 6h`. Their edge cache does not vary on the query string, so every "search" returns the same fixed list — hence one fetch per six hours, filtered locally by `title_hit` on `signal_tokens`. A failed refresh keeps the previous list rather than emptying it.
- **Jobicy** — tag-based with geo: `distinctive_tokens` as `tag=` plus the requested country as `geo=`. A country Jobicy does not know answers 400, so the call is retried without the geo and `location_ok` sorts out who is really open to whom. Falls back to the untagged feed when nothing comes back.
- **Workable** — a **two-round crawl of schema.org LD+JSON**. First, `workable_urls(token, country)` fetches a `/search/{where}/remote-{token}-jobs` page and parses its `<script type="application/ld+json">` ItemList for posting URLs (the page renders client-side but the schema is plain JSON). `workable_title` reads the title out of the URL slug *before* opening the page — so the per-listing requests are spent only on postings that already passed a `title_hit` filter. Second, `workable_job(url)` opens each surviving posting and parses its `JobPosting` block for the full fields. The country sits in the path and is not optional; an unrecognized country answers 200 with an empty list, retried worldwide.

All five fetchers fan out concurrently from `START` via `fan_out` and converge on `collect_results`. Each source uses a different schema; the [normalization](#normalization-and-mojibake-repair) step unifies them into a canonical shape.

Git history shows that Arbeitnow was removed after proving unreliable for remote filtering and hurting eval quality (commit `b3738bc`).

## Normalization and mojibake repair

`normalize_jobs` in `agent.py` maps source-specific field names to a canonical shape:

| Canonical field | Source fields tried |
|---|---|
| `company` | `company`, `companyName`, `company_name` |
| `position` | `title`, `position`, `jobTitle` |
| `location` | `location`, `jobGeo`, `candidate_required_location`, `locationRestrictions` (joined) |
| `description` | `description`, `excerpt`, `jobExcerpt` — cleaned via `clean_description` (HTML stripped with regex, then `textwrap.shorten` to 150 chars with `...` placeholder) |
| `salary` | `salary`, or `salary_min - salary_max`, or `minSalary - maxSalary` |
| `apply_url` | `apply_url`, `url`, `applicationLink` |

Deduplication is by a hash of `company + position` (lowercased, non-alphanumeric stripped) — a role open in six cities is posted six times with six different links, so the URL is not the identity. `collect_results` deduplicates the same way (via `job_company` + `job_title`) before scoring, because duplicates would otherwise take up places in the top `MAX_RESULTS`.

`fix_mojibake` attempts `text.encode("latin-1").decode("utf-8")` and falls back silently on failure — some APIs return UTF-8 content mis-declared as Latin-1.

`strip_html` (used in `collect_results`, not `normalize_jobs`) removes HTML tags with regex and unescapes entities via `html.unescape`. It truncates to 500 characters. `clean_description` (used in `normalize_jobs`) is a separate HTML-strip + `textwrap.shorten` to 150 characters. The two truncation lengths exist because `collect_results` runs first inside the graph (500 chars for scoring/dedup), then `normalize_jobs` runs later in the interface layer (150 chars for display).

Salary is cleaned with `re.sub(r'[\s\-0]', '', f"{salary}")` — whitespace, hyphens, and zeros are stripped to check if there is any actual salary value. If the result is empty, it becomes "Salary not listed" (commit `6b55df8`).

## Alias-based query canonicalization

`canon()` applies the `ALIASES` dictionary so that synonyms map to one spelling and a single token can match all of them:

> `large language models → llm`, `natural language processing → nlp`, `artificial intelligence → ai`, `machine learning → ml`, `full stack / full-stack → fullstack`, `front end / front-end → frontend`, `back end / back-end → backend`, `postgresql → postgres`, `kubernetes → k8s`, `javascript → js`, `developer → engineer`

Without this, "ml engineer" and "machine learning engineer" were disjoint result sets (4 vs 10 listings, none shared). `canon()` is applied to both the query (in `signal_tokens`, `score_job`, and `job_title`) and each job's title (in `job_title`), so a query word and a source word written as different synonyms still match. `distinctive_tokens` does **not** canonize — it operates on the raw lowercased query, because the tag APIs expect the spelled-out word, not the alias.

## Title-weighted scoring

A job scores on where the query words appear. `score_job(job, query)` computes three contributions and combines them:

1. **Title hits** — `title_hits * TITLE_WEIGHT` (10) for each `signal_token` that matches the title via `title_hit`.
2. **Description contribution** — `desc_hits + generic-word title hits + frequency bonus`, where the frequency bonus is `freq / 8` (`freq` = total occurrences of signal tokens in the description). This whole term is **capped at 9**, strictly below `TITLE_WEIGHT` (10).
3. **Generic-word tie-breaking** — generic words that also appear in the title add a point, but they can never admit a listing on their own. If the query is *entirely* generic words, `gen_hits` is forced to 0 so the cap is not gamed.

`collect_results` keeps only jobs with `score >= TITLE_WEIGHT` — **a title hit is required for admission**. Because the description contribution is capped below `TITLE_WEIGHT`, it can only reorder listings that already earned their place by matching in the title, never admit one that did not. Generic words add a tie-breaking point when they appear in the title but, like description hits, cannot admit a listing alone. When the query itself contains `engineer`, `collect_results` additionally requires a `title_hit("engineer", ...)` on the job title, so a generic "engineer" query does not admit every listing.

### Signal tokens

`signal_tokens` strips `GENERIC` words (`developer`, `engineer`, `remote`, `role`, `position`, `specialist`, `manager`, etc.) from the query (after `canon`) before scoring. If the query is nothing but generic words, they are used anyway (so `developer job` still matches). These are the tokens that count toward title hits and the description cap.

### `title_hit` — whole-word with optional suffix

`title_hit(token, title)` matches the regex `r'\b{token}(?:js|s|\d+)?\b'` — a whole word with an optional suffix (plural `s`, version digits, or `js`). `python` hits `python3`; `react` hits `reactjs`; `agent` hits `agents`. **Prefixes are not allowed**, so `rust` does not match `anti-trust` and `java` does not match `javascript`. This replaced the earlier rule that treated tokens shorter than 4 characters as whole-word and allowed substring matching for longer ones.

## Country / location matching

`location_ok(job, country)` decides whether a listing is open to someone in `country`. Empty `country` means no filtering at all. Otherwise a listing counts as open if it:

- names the country directly;
- names a **containing region** from the `REGIONS` dict (`greece → europe/emea/eu`, `germany → europe/emea/eu`, `united-states → north america/americas/usa/us`, `australia → apac/oceania`, `india → apac/asia`, …);
- says **worldwide / anywhere / global / world wide** (the `GLOBAL_WORDS` set); or
- **says nothing** about location (most boards do this when the answer is "anywhere") — absence is not a restriction.

**`Remote` is deliberately not a match**: it says *how* the job is done, not *where* it is open, so a listing that says only "Remote" is not accepted as open to a specific country. All matching uses `title_hit` over the `job_location` text and the accepted-word list.

## Age filtering

`job_is_recent(job)` keeps a listing only if it was posted within `MAX_AGE_DAYS = 120`. It reads the date from `date`, `pubDate`, `publication_date`, `datePosted`, or `epoch`, accepting both ISO strings and epoch seconds. **Absence is not age** — a listing with no date is kept (returns `True`). A date that fails to parse is also kept. Workable in particular keeps filled roles on its board long after they close, and a stale or dead link is worse than one fewer result.

## Thread memory (avoid-keywords)

Memory is the main behavioral feature. Users say what to avoid, and those exclusions are stored per `thread_id`. The filter is a **hard exclusion** applied after the graph runs — it removes matching jobs from the cached results.

### The seniority / full-text split

`filter_jobs` matches keywords differently depending on whether any word in the keyword is in the `SENIORITY` set:

- **Seniority words** (`senior`, `sr`, `junior`, `júnior`, `jr`, `lead`, `principal`, `staff`, `mid`, `entry`, `pleno`, `sênior`, `estágio`, `head`, `director`, `vp`, `chief`) → matched against **title words only**
- **Everything else** (technologies, locations, company names) → matched against **title + description + location** (full text)

This exists because every posting says "work with senior engineers" somewhere in its body — that shouldn't disqualify a mid-level role. `filter_jobs` also removes jobs without an `apply_url` or whose `position` is empty / `Unknown`.

### Accumulation and reset

Memory is a `list[str]` stored in the LangGraph checkpointer state. Each feedback call appends a comma-separated keyword string. The `add_or_reset` reducer returns `[]` when `new` is `None` — that is how `/reset` clears the list.

Active filters are shown at the bottom of every response. Say "reset filters" (or POST `/reset`) to clear them.

### Interface differences

| Interface | Where memory lives | How it persists |
|---|---|---|
| REST (`/ask`, `/feedback`) | PostgreSQL `PostgresSaver` | Across days, keyed by `thread_id` |
| MCP | Explicit `exclude_keywords` arg | Per call — the client's conversation is the memory |
| Voice | `VoiceSession.memory` (in-memory) | For the duration of one call only |

## Query interpretation

The system distinguishes between two kinds of text input:

- **Search intent**: `python backend remote`, `ML engineer`
- **Exclusion intent**: `no MERN`, `skip senior roles`, `no usa`

The frontend routes by prefix: `reset` → `/reset`, `no `/`skip ` → `/feedback`, anything else → `/ask`. The voice agent has a wider set: `no`/`skip`/`without`/`not`/`exclude` → feedback, `tell me more`/`details` → listing detail, `reset` → clear, anything else → search.

Wording matters — changes to the UX should keep the routing rules obvious to users.

## Resume-derived search intent

The `/upload` flow turns a CV into a compressed keyword summary, not a full résumé analysis. It is now **asynchronous**: `/upload` reads the PDF (first 5 pages), then hands the text to a Celery task (`filework` in `tasks.py`) so the blocking LLM and graph work run off the request's event loop. The caller polls `/jobs/{job_id}` for the result.

The CV-to-search path inside `filework` is unchanged in behavior: Gemini (via `helper.llmchain` with `for_upload=True`) produces a `CVKeywords` structured output — an ordered keyword list starting with the role title, then the core skills. That list is joined into the search query and fed to the same `graph` + `normalize_jobs` + `filter_jobs` pipeline that serves `/ask`. The listings that come back are filtered by the same deterministic code, not re-analyzed.

## Evaluation semantics

Two eval systems measure different things:

- **LangSmith eval** — an LLM-judge regression harness that posts 24 queries (live data, first response only) and scores the ratio of relevant/returned listings. The current baseline is ~0.90, but because it runs against live boards that shift hourly the aggregate is the signal, not any single case — treat the number as a range, not a hard target.

  The runner (`eval_runner.py`) no longer posts to `/ask`. It posts each query to **`/askeval`** with the `EVALS` `x-api-key`, which returns `{md, jobs}` — the markdown string and the raw job list. Four evaluators score that response:

  | Evaluator | Judge | Scope | Notes |
  |---|---|---|---|
  | `gemini_full_correctness` | Gemini 2.5 Flash (structured `Output`) | The full markdown | `relevant / total` over all listings in `md` |
  | `gemini_listing_correctness` | Gemini (structured `JobOutput`, per-listing) | Each listing individually | `relevant / len(results)`; empty non-`empty_ok` → 0 |
  | `jev_correctness` | OpenRouter `typesafe/jev-1.13` | Each listing individually | probability ≥ **0.5** threshold; empty non-`empty_ok` → 0 |
  | `laya_correctness` | local `laya serve` (`/v1/systemone`, model `multilingual`) | Each listing individually | probability ≥ **0.5** threshold; empty non-`empty_ok` → 0 |

  Every evaluator carries an `empty_ok` short-circuit: when the example expects no results and `jobs` is empty, it asserts a perfect **1.0** without calling any judge. The Gemini judges (`gemini_grade`, `askgemini`) use an explicit, decidable grading prompt — count what is there, never lower the score because an expected listing is missing, and when the criteria are silent about a listing count it as relevant. The per-listing evaluators (`jev_correctness`, `laya_correctness`) call `askjev` / `asklaya` once per job and threshold the returned probability.

  The live experiment is `client.evaluate(..., evaluators=[jev_correctness, gemini_listing_correctness], experiment_prefix="geminijevperjob")` — the full-correctness and laya evaluators exist and run but are not the two wired into the current experiment call.

- **Harbor eval** — a **deterministic set equality**. The `filter-exclusion-senior` task runs the production `mcp_server.search_remote_jobs(query, exclude_keywords)` against **five frozen sources** (RemoteOK, Himalayas, Remotive, Jobicy, Workable fixtures). `filter_jobs` output must exactly match a hand-written `expected.json` — now **6 keep / 6 drop** (not the earlier 7/5). No judge, no network, no database, no LLM in the path. The verifier never calls `filter_jobs` itself, or it would be grading the code against itself.

Neither grades description quality. Surface phrasing can change a lot without affecting the actual business goal.

## Source references

- `agent.py` — scoring, filtering, normalization, fetchers, canonicalization
- `main.py` — endpoint routing, memory update, `/askeval`
- `tasks.py` — Celery `filework` for the async `/upload` path
- `helper.py` — `llmchain` / `CVKeywords`, `format_jobs_markdown`
- `voice_agent.py` — voice memory model
- `mcp_server.py` — explicit-arg exclusion
- `eval_runner.py` — LangSmith eval
- `evals/` — Harbor eval (frozen fixtures, deterministic verifier)
- Commits `3fca572` (removed LLM from search), `6b55df8` (salary cleanup), `dd282ff` (filter at fetch time)
