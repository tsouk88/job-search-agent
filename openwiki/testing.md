---
type: Reference
title: Testing and Evals
description: Testing strategy for the job search agent — LangSmith eval runner, what the evals measure, manual checks, and regression targets after changes.
tags: [testing, evals, langsmith, regression, quality]
---

# Testing and evals

This repository does not expose a classic unit-test suite in the inspected files; the main quality gate is the LangSmith eval pipeline plus manual end-to-end verification.

## LangSmith eval runner

`eval_runner.py`:

- posts sample queries to `POST /ask`
- captures streamed output as text
- compares the output against reference expectations with a Gemini-based judge
- reports correctness as `0.0`, `0.5`, or `1.0`

This is the best place to update when the agent prompt, source set, or result format changes.

## What the evals are measuring

The current evaluation logic is mostly checking:

- whether the returned jobs match the expected query intent
- whether irrelevant jobs are excluded
- whether the output is empty when jobs should exist

It intentionally does not grade description quality.

## Manual checks worth running after changes

1. `GET` is not used; test the actual endpoints.
2. Call `POST /ask` with a basic keyword query.
3. Send an exclusion message such as `no MERN` and confirm `/feedback` updates memory.
4. Upload a small PDF CV and verify `/upload` streams results.
5. If n8n is in use, confirm `/evaluate` still accepts the workflow payload.

## Good regression targets

- backend streaming regressions
- source API changes or rate limiting
- output format changes that break markdown rendering
- memory persistence between requests
- eval score drops after prompt or source edits

## Eval baseline status

The previous ~0.90 baseline was measured against the old LLM-based filtering and no longer reflects how the agent works (the search path is now LLM-free, with pure keyword scoring). New eval cases — empty results, ambiguous queries, typos — are being generated from fresh traces. Treat any historical eval score as stale until the dataset is rebuilt.

## Source references

- `eval_runner.py`
- `main.py`
- `frontend/app/page.tsx`
- `README.md`
- git commits `b3738bc`, `662d71d`
