# Task — filter-exclusion-senior

## Capability

Apply a user exclusion to a fixed result set: drop every listing whose
**title** carries the excluded seniority term, and keep every other listing.

One capability, both directions. Over-inclusion (a senior job survives) and
over-filtering (a valid job is dropped) are both failures — the second is the
one a keyword spot-check would miss.

## Request

`instruction.md` carries the request and a fenced JSON block:

```json
{"query": "python developer", "exclude": ["senior", "game", "canonical"]}
```

Three exclusions, chosen from the frozen listings so that both branches of
`filter_jobs` are taken and the split is 5 kept / 5 dropped:

| term | drops | branch |
|---|---|---|
| `senior` | "Senior Software Engineer - Python/MongoDB" | title only |
| `game` | the two Panda3D listings | full text |
| `canonical` | two listings where the word appears **only in the description** | full text |

"Junior Python Game Developer" is dropped by `game`, not by `junior` — which
was never excluded. Exclusion is per keyword, not per category.

## Initial conditions

- Frozen fixtures for the four sources (see `environment.md`).
- No network, no credentials, no database.
- Cold process; MCP cache empty.

## Pass condition

Pass iff the set of `apply_url` values in `output.json` is exactly the set in
`tests/expected.json`.

## Verifier evidence

Deterministic, code only. Success here is an objective set, not a semantic
judgement — no LLM judge, which is the whole reason this task exists next to
the 0.812 LangSmith number.

1. `output.json` parses as a list of objects.
2. No surviving listing has "senior" in its `position`.
3. Every listing in `prefilter.json` without "senior" in its `position`
   survives.
4. Set equality with `expected.json`.

Reward 1 if all four hold, else 0.

`expected.json` is written **by hand** from `prefilter.json`. The verifier
never calls `filter_jobs`, or it would be grading itself against itself.

## Accepted alternatives

Order is not graded — only membership. Field values other than `apply_url`
are not graded; normalization is a separate concern with its own history.

## Known limitation

No listing in the frozen set carries "senior" in its description only, so the
title-only rule is never tested in the one shape that distinguishes it from
plain full-text matching. The fixtures are real captured data and were not
edited to manufacture that case.

## Negative control — run 04/08

Removing `"senior"` from `agent.SENIORITY` is **not** a valid control: the term
would simply be matched as an ordinary keyword and drop the same listing by its
title, leaving the reward at 1.

The control actually used is the realistic regression: collapse the branch
selection in `filter_jobs` so every keyword is matched against the title only.

| run | reward |
|---|---|
| `baseline-2` — current code | 1.0 |
| `baseline-3` — same input, repeated | 1.0 |
| `negative-control` — title-only regression | 0.0 |

The failing run named the two Canonical listings in
`test_no_free_keyword_match_survived`, which is the branch the regression
removed.
