---
type: Reference
title: Domain Concepts
description: Core domain concepts for the job search agent — job source aggregation, deduplication, two-pass ranking, thread memory (avoid-keywords), query interpretation, resume-derived search, and evaluation semantics.
tags: [domain, concepts, agent, memory, evaluation]
---

# Domain concepts

## Job source aggregation

The core domain object is a remote job listing gathered from multiple public APIs.
Each source uses a different schema, so the backend and prompt logic normalize fields such as:

- company name
- title / position
- location
- description
- salary
- application URL

The current source set is:

- RemoteOK
- Himalayas
- Remotive
- Jobicy

Git history shows that Arbeitnow was removed after it proved unreliable for remote filtering and hurt evaluation quality.

## Deduplication

The backend deduplicates jobs before prompting the model.
The current heuristic builds a hash from company + position.
This is simple, but it avoids repeating the same job when different APIs or fetch paths surface similar records.

## Thread memory (avoid-keywords)

Memory is the main behavioral feature of the agent.
Users say what to avoid, and those exclusions are stored per `thread_id` in PostgreSQL-backed LangGraph state.
Memory is not injected into a prompt; instead `filter_jobs` removes matching jobs from the cached `clean_jobs` before they are returned. Seniority keywords (`senior`, `junior`, `lead`, …) are matched against the title only; other keywords are matched against title + description + location. Send `reset filters` (or POST `/reset`) to clear the list.

Important consequence: the assistant is not just ranking jobs; it is accumulating exclusions over time for each conversation thread, and the search graph itself never re-runs for feedback.

## Query interpretation

The system distinguishes between two kinds of text input:

- search intent: `python backend remote`, `ML engineer`, etc.
- exclusion intent: `no MERN`, `skip senior`, etc.

The frontend uses a simple prefix rule to route exclusions to `/feedback`.
That means wording matters, and changes to the UX should keep the rule obvious to users.

## Resume-derived search intent

The upload flow turns a CV into a compressed keyword summary, not a full résumé analysis.
That summary is then used as a search query.
This keeps the system lightweight while still letting a candidate search without typing a full keyword list.

## Evaluation semantics

The eval pipeline scores correctness by whether the returned jobs match the expected job-title/company criteria.
It intentionally ignores description quality and focuses on whether the right jobs are included.
That matters when editing prompts: surface phrasing can change a lot without affecting the actual business goal.

## Source references

- `agent.py`
- `main.py`
- `eval_runner.py`
- `README.md`
- Recent commits `b3738bc`, `662d71d`, `6e0cf7f`
