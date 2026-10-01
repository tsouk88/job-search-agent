---
type: Reference
title: Domain Concepts
description: Core domain concepts — five-source job aggregation, normalization and mojibake repair, alias-based query canonicalization, title-weighted scoring with frequency-based description contribution and generic-word tie-breaking, signal tokens, thread memory and the seniority/full-text filter split, country/location matching, age filtering, and evaluation semantics.
tags: [domain, concepts, agent, memory, evaluation, scoring, filtering, canonicalization]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-01T12:03:35.670Z
sources:
  - id: openwiki-source-eca60e2ced68ba99bd0ac710
    resource: repo://agent.py
  - id: openwiki-source-f1644da1c1a64a6a6567706b
    resource: repo://eval_runner.py
  - id: openwiki-source-6f3a365387ad1dfc55a94d24
    resource: repo://evals/filter-exclusion-senior/tests/test_outputs.py
  - id: openwiki-source-18837785d6eee548467c07ac
    resource: repo://evals/harbor_agents/pipeline_agent.py
  - id: openwiki-source-1691a76fbd7a6781b3420f6c
    resource: repo://evals/harbor_agents/run_pipeline.py
  - id: openwiki-source-46c84c82a35e96f529aef1f3
    resource: repo://evals/specs/filter-exclusion-senior/environment.md
generated: { by: "openwiki/0.6.1", at: "2026-10-01T12:03:35.670Z" }
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

> `machine learning → ml`, `large language models → llm`, `natural language processing → nlp`, `artificial intelligence → ai`, `full stack / full-stack → fullstack`, `front end / front-end → frontend`, `back end / back-end → backend`, `postgresql → postgres`, `kubernetes → k8s`, `javascript → js`

Without this, "ml engineer" and "machine learning engineer" were disjoint result sets (4 vs 10 listings, none shared). `canon()` is applied to both the query (in `signal_tokens`, `distinctive_tokens`, and `score_job`) and each job's title (in `job_title`), so a query word and a source word written as different synonyms still match.

## Title-weighted scoring

A job scores on where the query words appear. `score_job(job, query)` computes three contributions and combines them:

1. **Title hits** — `title_hits * TITLE_WEIGHT` (10) for each `signal_token` that matches the title via `title_hit`.
2. **Description contribution** — `desc_hits + generic-word title hits + frequency bonus`, where the frequency bonus is `freq / 8` (`freq` = total occurrences of signal tokens in the description). This whole term is **capped at 9**, strictly below `TITLE_WEIGHT` (10).
3. **Generic-word tie-breaking** — generic words that also appear in the title add a point, but they can never admit a listing on their own.

`collect_results` keeps only jobs with `score >= TITLE_WEIGHT` — **a title hit is required for admission**. Because the description contribution is capped below `TITLE_WEIGHT`, it can only reorder listings that already earned their place by matching in the title, never admit one that did not. Generic words add a tie-breaking point when they appear in the title but, like description hits, cannot admit a listing alone.

### Signal tokens

`signal_tokens` strips `GENERIC` words (`developer`, `engineer`, `remote`, `role`, `position`, `specialist`, `manager`, etc.) from the query (after `canon`) before scoring. If the query is nothing but generic words, they are used anyway (so `developer job` still matches). These are the tokens that count toward title hits and the description cap.

### `title_hit` — whole-word with optional suffix

`title_hit(token, title)` matches the regex `r'\b{token}(?:js|s|\d+)?\b'` — a whole word with an optional suffix (plural `s`, version digits, or `js`). `python` hits `python3`; `react` hits `reactjs`; `agent` hits `agents`. **Prefixes are not allowed**, so `rust` does not match `anti-trust` and `java` does not match `javascript`. This replaced the earlier rule that treated tokens shorter than 4 characters as whole-word and allowed substring matching for longer ones.

## Country / location matching

`location_ok(job, country)` decides whether a listing is open to someone in `country`. Empty `country` means no filtering at all. Otherwise a listing counts as open if it:

- names the country directly;
- names a **containing region** from the `REGIONS` dict (`greece → europe/emea/eu`, `germany → europe/emea/eu`, `united-states → north america/americas/usa/us`, `australia → apac/oceania`, `india → apac/asia`, …);
- says **worldwide / anywhere / global** (the `GLOBAL_WORDS` set); or
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

The `/upload` flow turns a CV into a compressed keyword summary, not a full résumé analysis. Gemini extracts "one sentence with all the keywords max 20 words" from the first 5 pages of the PDF. That line becomes the search query; the listings that come back are then filtered by the same deterministic code that serves `/ask`.

## Evaluation semantics

Two eval systems measure different things:

- **LangSmith eval** — an LLM judge scores whether returned jobs match reference criteria, as a `relevant / total` ratio over **24 cases** (~0.90 baseline). First response only, live data. The judge was rewritten for repeatability: an `empty_ok` flag on examples that expect no results short-circuits to a perfect score (no judge call), the prompt carries explicit grading instructions, and the criteria are decidable — count what is there, never lower the score because an expected listing is missing, and when the criteria are silent about a listing count it as relevant.
- **Harbor eval** — a **deterministic set equality**. The `filter-exclusion-senior` task runs the production `mcp_server.search_remote_jobs(query, exclude_keywords)` against **five frozen sources** (RemoteOK, Himalayas, Remotive, Jobicy, Workable fixtures). `filter_jobs` output must exactly match a hand-written `expected.json`. No judge, no network, no database, no LLM in the path. The verifier never calls `filter_jobs` itself, or it would be grading the code against itself.

Neither grades description quality. Surface phrasing can change a lot without affecting the actual business goal.

## Source references

- `agent.py` — scoring, filtering, normalization, fetchers, canonicalization
- `main.py` — endpoint routing, memory update
- `voice_agent.py` — voice memory model
- `mcp_server.py` — explicit-arg exclusion
- `eval_runner.py` — LangSmith eval
- `evals/` — Harbor eval (frozen fixtures, deterministic verifier)
- Commits `3fca572` (removed LLM from search), `6b55df8` (salary cleanup), `dd282ff` (filter at fetch time)
