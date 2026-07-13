# Workflows

This repo has four user-visible workflows and one maintenance workflow that matter for future edits.

## 1. Keyword job search

Flow:

1. User types a keyword query in the frontend.
2. The frontend POSTs to `/ask` with a stable `thread_id`.
3. `main.py` loads any stored memory for that thread.
4. The LangGraph agent fans out to multiple job APIs in parallel.
5. The backend deduplicates and reshapes jobs.
6. Gemini streams a final filtered list back to the browser.

Important detail: the prompt includes user memory as a hard exclusion list, so previous negative feedback changes future searches.

## 2. Feedback loop / HITL

Flow:

1. User sends feedback such as `no MERN` or `skip senior roles`.
2. The frontend routes that text to `/feedback` instead of `/ask`.
3. The backend asks Gemini to extract avoid-keywords only.
4. The graph resumes from its interrupt with the new memory.
5. Later searches exclude those keywords.

The agent loop continues until the user submits `done`.

## 3. CV upload search

Flow:

1. User uploads a PDF from the frontend.
2. `/upload` reads the file into memory.
3. `pdfplumber` extracts the text from all pages.
4. Gemini compresses the CV into a short keyword summary.
5. The agent searches for jobs using that summary.
6. Results are streamed back like a normal search.

This workflow is useful when the user does not want to type search keywords manually.

## 4. n8n digest / evaluation workflow

The repository includes `n8n_workflow.json`, which schedules a periodic digest job.
The README and workflow assets indicate the flow is:

- every 12 hours
- fetch jobs from multiple APIs
- filter by keywords
- call `/evaluate`
- send an email digest through Gmail

The automation depends on the backend staying available and the `/evaluate` contract remaining stable.

## 5. Eval workflow

`eval_runner.py` is a LangSmith-backed regression harness.
It posts sample queries to `/ask`, captures the streaming response text, and scores the result with a Gemini-based evaluator.
This was added after the job source set and prompt behavior stabilised enough to measure quality.

## Change guidance

- If you change the UI message flow, keep the special `no ...` / `skip ...` handling in sync with `/feedback`.
- If you change streaming behavior, test both `/ask` and `/upload` because both rely on the same incremental rendering path.
- If you change the output format, update the n8n digest consumer and the frontend markdown rendering assumptions.
- If you add or remove a source API, revisit both the graph fan-out and the eval dataset.

## Source references

- `frontend/app/page.tsx`
- `main.py`
- `agent.py`
- `eval_runner.py`
- `n8n_workflow.json`
- `assets/n8n_workflow.png`
- `assets/email_digest.png`
