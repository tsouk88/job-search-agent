---
type: Reference
title: Domain Concepts
description: Core domain concepts — job source aggregation, normalization and mojibake repair, title-weighted scoring, signal tokens, thread memory and the seniority/full-text filter split, query interpretation, resume-derived search, and evaluation semantics.
tags: [domain, concepts, agent, memory, evaluation, scoring, filtering]
---

# Domain concepts

## Job source aggregation

The core domain object is a remote job listing gathered from four public APIs:

- **RemoteOK** — queried by first keyword as a tag, but listings re-checked against their own title (tags are SEO filler)
- **Himalayas** — full query search, worldwide, sorted by recent
- **Remotive** — full query search
- **Jobicy** — full query as a tag

Each source uses a different schema. The [normalization](#normalization-and-mojibake-repair) step unifies them into a canonical shape.

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

Deduplication is by a hash of `company + position` (lowercased, non-alphanumeric stripped). A second dedup by `apply_url` happens in `collect_results`.

`fix_mojibake` attempts `text.encode("latin-1").decode("utf-8")` and falls back silently on failure — some APIs return UTF-8 content mis-declared as Latin-1.

`strip_html` (used in `collect_results`, not `normalize_jobs`) removes HTML tags with regex and unescapes entities via `html.unescape`. It truncates to 500 characters. `clean_description` (used in `normalize_jobs`) is a separate HTML-strip + `textwrap.shorten` to 150 characters. The two truncation lengths exist because `collect_results` runs first inside the graph (500 chars for scoring/dedup), then `normalize_jobs` runs later in the interface layer (150 chars for display).

Salary is cleaned with `re.sub(r'[\s\-0]', '', f"{salary}")` — whitespace, hyphens, and zeros are stripped to check if there is any actual salary value. If the result is empty, it becomes "Salary not listed" (commit `6b55df8`).

## Title-weighted scoring

A job scores on where the query words appear:

```python
score = title_hits * TITLE_WEIGHT + description_hits
```

`TITLE_WEIGHT = 10`. A single title hit (10) outweighs any number of description hits. `collect_results` keeps only jobs with `score >= TITLE_WEIGHT` — **a title hit is required for admission**. Description hits only break ties between listings that already earned their place.

### Signal tokens

Generic words (`developer`, `engineer`, `remote`, `role`, `position`, `specialist`, `manager`, etc.) are stripped from the query before scoring. If the query is nothing but generic words, they are used anyway (so `developer job` still matches).

### Short vs. long token matching

Words shorter than 4 characters must match a whole word — `ai` should not hit `said`. Words of 4+ characters may match inside a word — `python` hits `python3`.

## Thread memory (avoid-keywords)

Memory is the main behavioral feature. Users say what to avoid, and those exclusions are stored per `thread_id`. The filter is a **hard exclusion** applied after the graph runs — it removes matching jobs from the cached results.

### The seniority / full-text split

`filter_jobs` matches keywords differently depending on whether any word in the keyword is in the `SENIORITY` set:

- **Seniority words** (`senior`, `junior`, `lead`, `principal`, `staff`, `head`, `director`, `vp`, `chief`, and Portuguese variants) → matched against **title words only**
- **Everything else** (technologies, locations, company names) → matched against **title + description + location** (full text)

This exists because every posting says "work with senior engineers" somewhere in its body — that shouldn't disqualify a mid-level role.

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

- **LangSmith eval** — LLM judge scores whether returned jobs match reference criteria. `relevant / total` ratio. First response only, live data.
- **Harbor eval** — Deterministic set equality. `filter_jobs` output must exactly match a hand-written expected set. Frozen data, no judge.

Neither grades description quality. Surface phrasing can change a lot without affecting the actual business goal.

## Source references

- `agent.py` — scoring, filtering, normalization
- `main.py` — endpoint routing, memory update
- `voice_agent.py` — voice memory model
- `mcp_server.py` — explicit-arg exclusion
- `eval_runner.py` — LangSmith eval
- `evals/` — Harbor eval
- Commits `3fca572` (removed LLM from search), `6b55df8` (salary cleanup), `dd282ff` (filter at fetch time)
