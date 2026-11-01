---
type: Subsystem
title: LangSmith Eval
description: LangSmith-based regression harness that posts queries to the /askeval endpoint and scores the ratio of relevant/returned listings with a Gemini 2.5 Flash judge. Current baseline ~0.90 (16 August). Runs against live job boards so the aggregate is the signal, not any single case.
tags: [evals, langsmith, llm-judge, regression, quality]
verified:
  - by: openwiki/0.6.1
    at: 2026-11-01T15:48:11.877Z
sources:
  - id: openwiki-source-f1644da1c1a64a6a6567706b
    resource: repo://eval_runner.py
  - id: openwiki-source-23775c3de52f3ab95a13cb8b
    resource: repo://README.md
generated: { by: "openwiki/0.6.1", at: "2026-11-01T15:48:11.877Z" }
---

# LangSmith Eval

`eval_runner.py` is a LangSmith-backed regression harness that measures end-to-end search quality. It runs against live job boards, so individual cases wobble between runs — the aggregate is the signal.

## How it works

```mermaid
sequenceDiagram
    participant E as eval_runner.py
    participant LS as LangSmith
    participant B as Backend (/askeval)
    participant J as Gemini Judge

    E->>LS: client.evaluate(dataset="job-search-eval")
    LS-->>E: examples (input, reference, empty_ok?)
    loop each query
        E->>B: POST /askeval {input, thread_id}
        B-->>E: json {md, jobs}
        alt empty_ok and no jobs
            E->>E: score = 1.0 (asserted, not judged)
        else
            E->>J: structured_llm(prompt with query, output, reference)
            J-->>E: {reason, relevant, total}
            E->>E: score = relevant / total
        end
    end
    E->>LS: experiment results
```

*The eval runner posts each query to `/askeval`, receives both a Markdown summary and the raw jobs list, and asks a Gemini judge to count how many returned listings match the reference criteria.*

## Implementation

The grading logic uses a Pydantic-structured LLM to ensure consistent counting:

```python
class Output(BaseModel):
    reason : str
    relevant : int
    total : int = Field(ge=1)

structured_llm = llm.with_structured_output(Output)
```

The grading prompt defines the judge's behavior:

1.  **Strict Counting**: Total is the number of listings returned; relevant is the number that satisfy the reference criteria.
2.  **Listing Isolation**: Rejected listings only subtract from the score and do not invalidate others.
3.  **Default Inclusion**: When criteria are silent about a listing, it is counted as relevant.
4.  **Empty Assertions**: If no jobs are returned and the query is marked `empty_ok`, the score is automatically 1.0.

### Test execution
Each query is assigned a random `uuid` as a `thread_id` to ensure stateless execution. The runner enforces a 180-second timeout per query.

## Running

```bash
python eval_runner.py
```

Requires `LANGSMITH_API_KEY` and `GEMINI_API_KEY` in the environment. The runner posts to `http://localhost:8002/askeval` by default.

## Methodology

Changes to the agent are judged against a control run of the unchanged code on the same day. Because live job boards shift content frequently, a single code version can produce different scores on different days. Aggregate performance across the 24 cases is the primary metric for regressions.
