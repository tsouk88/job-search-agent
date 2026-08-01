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
- reports correctness as the ratio `relevant / total` (continuous, e.g. 0.812)

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

## Eval baseline

Current baseline is **0.812 across 22 cases** (LangSmith dataset `job-search-eval`, Gemini 2.5 Flash judge). Roughly four in five returned listings are relevant and twelve cases score a clean 1.0. The score is `relevant / total`, so padding a response with weak matches lowers it.

The dataset covers narrow niches (`rust`, `blockchain solidity`), vague queries (`remote job`), a query whose right answer is empty (`COBOL mainframe developer`), and intentional misspellings — typos are not corrected on purpose, so `pyton developer` correctly returns nothing.

### How the score moved

All steps measured against the same 22 cases; most gains came from removing rules:

| Change | Score |
|---|---|
| Starting point | 0.558 |
| Stop trusting RemoteOK's tags, match on titles | 0.575 |
| Remove the guaranteed minimum of 8 results | 0.679 |
| Treat `developer` and `engineer` as meaningful words | 0.584, reverted |
| Fix reference answers for typo queries | 0.751 |
| Fix a missing comma in the generic-word list | 0.812 |

The largest jump came from deleting the rule that guaranteed at least 8 results; the missing-comma fix mattered because two adjacent string literals in a Python set silently became one and dropped `engineer` and `remote` from the generic-word list.

### What the number does not cover

- First response only — none of the 22 cases exercise conversational filtering (`no support roles`, `no senior`), so real usage is better than 0.812 suggests.
- Live data — the agent queries live job boards, so individual cases wobble between runs; the aggregate is the signal.
- Known limitation: one title match is enough to admit a listing, so `data` pulls in Data Analysts and `wordpress` pulls in WordPress Support Specialists. Requiring two matching words was tried and rejected because specific terms like `sql`, `aws`, and `pytorch` appear in ~0% of returned job titles.

### Next

The hard cases are planned to be rebuilt as Harbor tasks with LangChain's eval-engineering skill, where listings are fixed and verification is deterministic instead of judged. That is also where the conversational filtering path gets its first real test.

The old ~0.90 baseline is gone. It was measured against LLM-based filtering on a different dataset and was never comparable to this one.

## Source references

- `eval_runner.py`
- `main.py`
- `frontend/app/page.tsx`
- `README.md`
- git commits `b3738bc`, `662d71d`
