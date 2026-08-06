# Job Search AI Agent

An AI-powered remote job search assistant. Type in your desired job keywords and the agent searches, filters, and presents the best matches for you. Talk to it instead, if you'd rather — see [Voice AI](#️-voice-ai).

**[▶ Try it live](https://job-search-agent-blond.vercel.app)** — no signup, no API key.

⚡ Instant results | 💰 $0 per search — searching and filtering are fully deterministic | 📊 [~0.8 relevance](#evals) across 22 eval cases

> The backend runs on a free Render instance that sleeps after 15 minutes of inactivity. If the demo has been idle, the first search takes about a minute — roughly 50s to wake the server, then 15s to query four job APIs. Every search after that is instant.

If you find this useful, give it a ⭐️ — it helps others discover the project!

---

## What it does

The agent connects to 4 job APIs simultaneously:

- [RemoteOK API](https://remoteok.com/api)
- [Himalayas API](https://himalayas.app/jobs/api)
- [Remotive API](https://remotive.com/api/remote-jobs)
- [Jobicy.com](https://jobicy.com/api/v2/remote-jobs)

Results are scored, ranked and filtered in plain Python — no model in the search path. An LLM is still used where judgement genuinely helps: turning your spoken feedback into filter keywords, reading your CV, and scoring listings for the n8n digest.

### Why no LLM in the search path

The agent originally passed every fetched listing through Gemini to decide relevance. That worked, but it hid a bug: irrelevant results (Marketing, Janitor) were never filtered out at fetch time — the model just declined to print them. The moment you asked for them a second way, they came back.

Filtering at the source instead fixed the bug, removed the cost, and made results reproducible. Quality is measured — see [Evals](#evals).

---

## How it works

Built with **LangGraph** at its core. The graph uses a **fan-out architecture** — the agent spawns parallel fetch nodes using LangGraph's `Send` API. Results are deduplicated, scored for relevance against your query, ranked, and stored.

```mermaid
flowchart TD
    START([START]) --> fan_out{fan_out}

    fan_out -->|Send API| fetch_jobs[fetch_jobs]
    fan_out -->|Send API| fetch_sjobs[fetch_sjobs]
    fan_out -->|Send API| fetch_tjobs[fetch_tjobs]
    fan_out -->|Send API| fetch_fjobs[fetch_fjobs]

    fetch_jobs --> collect_results[collect_results\ndedupe · score · rank]
    fetch_sjobs --> collect_results
    fetch_tjobs --> collect_results
    fetch_fjobs --> collect_results

    collect_results --> END([END])

    classDef startEnd fill:#a78bfa,stroke:#7c3aed,stroke-width:2px,color:#000;
    classDef nodeStyle fill:#f3e8ff,stroke:#9333ea,stroke-width:1px,color:#000;
    classDef condStyle fill:#faf5ff,stroke:#c084fc,stroke-width:2px,color:#000;

    class START,END startEnd;
    class fetch_jobs,fetch_sjobs,fetch_tjobs,fetch_fjobs,collect_results nodeStyle;
    class fan_out condStyle;
```

### Relevance scoring

A job scores on where your query words appear. A hit in the **title** outweighs any number of hits in the description, so `title_hits * 10 + description_hits` sorts real matches to the top.

Four details that matter in practice:

Short query words have to match a whole word. Searching `ai` should not hit `p-ai-d media specialist`. Words of four characters or more still match inside a word, so `python` finds `python3`.

A listing needs a title hit to qualify at all. Mentioning your keywords somewhere in the body text is not enough. Description hits still count, but only to break ties between listings that already earned their place.

The agent returns what matched, up to a cap of 12, and it will happily return three listings or none. An earlier version guaranteed a minimum of eight; on narrow queries, seven of those eight turned out to be noise.

Generic words are dropped. `developer`, `engineer`, `remote`, `role` and the rest show up in half of all job titles, so they can't rank anything. If a query is nothing but generic words, they get used anyway rather than matching the entire board.

RemoteOK's tags are not trusted. The API is still queried by tag, but every listing that comes back is re-checked against its own title. Across 101 listings that's an average of 23.6 tags each, a nursing role tagged `python`, `sql`, `postgres` and `golang`, and three unrelated listings sharing an identical 36-tag list. The tags are SEO filler. The title isn't.

### Feedback and memory

Tell the agent what to filter out — "no MERN", "no senior roles", "no usa" — and it stores your preferences in **PostgreSQL via LangGraph's PostgresSaver**. Filters persist across searches and across days.

Seniority words (`senior`, `junior`, `lead`, `principal`, …) are matched against the **title only**. Every posting says "work with senior engineers" somewhere in its body; that shouldn't disqualify a mid-level role. Everything else — technologies, locations — is matched against title, description and location.

Active filters are shown at the bottom of every response. Say **"reset filters"** to clear them.

The agent reads everything the four APIs return and shows the top 12 after ranking (`MAX_RESULTS`, at the top of `agent.py`). RemoteOK is the exception: it is asked to match on the title before it replies, so its own ten are already ten that matched.

> **LangSmith tracing is enabled.** Graph runs are fully observable — every node execution, its latency and its output. Note that the search path no longer makes LLM calls, so token usage now appears only for feedback extraction, CV upload and the n8n evaluator.

---

## 🎙️ Voice AI

Talk to the agent instead of typing. Same LangGraph brain (`agent.py`, unmodified) — a new interface built with [Pipecat](https://pipecat.ai): Deepgram (STT), ElevenLabs (TTS), Daily (real-time transport).

Feedback works over voice too — say "no senior roles" mid-conversation and the agent filters the results it already found, live, with no repeated API calls. Ask "tell me more about the first one" for details on a specific listing. Voice sessions are intentionally stateless (in-memory only, no Postgres) since a single call is short-lived, unlike the text agent's persistent memory across days.

See [`voice/README.md`](./voice/README.md) for architecture details and setup instructions.

---

## 🔌 MCP Server

A third interface onto the same brain: [`mcp_server.py`](./mcp_server.py) exposes the agent over the [Model Context Protocol](https://modelcontextprotocol.io), so Claude Desktop, Claude Code and any other MCP client can search jobs directly inside a conversation.

**No API keys required.** Since the search path is fully deterministic, this server needs no `GEMINI_API_KEY`, no database and no network config — clone, install, point your client at it.

One read-only tool:

```python
search_remote_jobs(query: str, exclude_keywords: list[str] = []) -> list[dict]
```

It returns the normalized job shape (`position`, `company`, `location`, `salary`, `description`, `apply_url`) rather than formatted text, so the calling model can filter and rank the results itself.

The tool is designed around **intent, not endpoints**: `exclude_keywords` is a parameter rather than a separate feedback call, which means no thread state and no Postgres here. The client's own conversation is the memory — say "no senior roles" and it simply calls the tool again with a fuller exclusion list, extracting the keywords itself instead of spending a Gemini call.

Fan-out results are cached in-process per query for 4 hours, so refinements filter locally and never re-hit the job boards.

**Setup** — add to `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\`, macOS: `~/Library/Application Support/Claude/`):

```json
{
  "mcpServers": {
    "jobsearch": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

Use absolute paths to the virtualenv's interpreter — the client starts the process directly, with no shell and no activated environment. Restart the client fully; logs land in `logs/mcp-server-jobsearch.log`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent | LangGraph (fan-out with `Send` API) |
| Memory | PostgreSQL via `PostgresSaver` |
| Voice | Pipecat (Daily transport, Deepgram STT, ElevenLabs TTS) |
| MCP | Official Python SDK (`mcp`), stdio transport |
| LLM | Google Gemini 2.5 Flash — feedback extraction, CV parsing, n8n scoring |
| LLM Integration | LangChain `init_chat_model` |
| Backend | FastAPI |
| Frontend | Next.js 15 + ReactMarkdown + remark-gfm |
| Job APIs | RemoteOK, Himalayas, Remotive, Jobicy |
| Evals | LangSmith dataset + LLM-as-judge (Gemini 2.5 Flash) — ~0.8 across 22 cases |

---

## Getting Started

```bash
# Backend
pip install -r requirements.txt
cp .env.example .env  # add your API keys
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Voice AI (optional, see voice/README.md for details)
cd voice/server
uv sync
uv run bot.py
```

---

## Database Setup

This project uses PostgreSQL for persistent memory via LangGraph's `PostgresSaver`.

**Option 1 — Supabase (recommended, free)**
1. Create a free account at [supabase.com](https://supabase.com)
2. Create a new project
3. Copy the connection string from Connect → **Session pooler, port 5432**
4. Add it to your `.env` as `DATABASE_URL`

Use the session pooler, not the transaction pooler on port 6543. `PostgresSaver`
relies on prepared statements, which the transaction pooler does not keep across
queries — the failures are intermittent rather than clean.

**Option 2 — Local PostgreSQL**
1. Install PostgreSQL locally
2. Create a database: `CREATE DATABASE jobsearch_memory;`
3. Add connection string to `.env`

## Environment Variables

See `.env.example` for all required variables:

```env
GEMINI_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com  # if outside US
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/jobsearch_memory
ALLOWED_ORIGINS=http://localhost:3000  # comma-separated list of browser origins allowed to call the API
```

For Voice AI environment variables, see [`voice/README.md`](./voice/README.md).

---

## Deployment

The backend deploys to Render from the checked-in `render.yaml` (New → Blueprint).
It declares the build and start commands, pins Python, and lists the secrets to
fill in from the dashboard. The frontend deploys to Vercel with **Root Directory
set to `frontend`** and `NEXT_PUBLIC_API_BASE` pointing at the Render URL.

Two details cost real time if you get them wrong:

- `NEXT_PUBLIC_API_BASE` takes **no trailing slash** — the client appends `/ask`.
- `ALLOWED_ORIGINS` takes **no trailing slash** either. The browser's `Origin`
  header is scheme, host and port only, and the match is exact. A stray `/` makes
  every request fail CORS while the page itself loads fine, so the only symptom
  is an error hidden in the browser console.

---

## CV Upload

Upload your PDF resume and the agent automatically extracts your skills and finds matching remote jobs — no keywords needed.

- `POST /upload` — accepts a PDF up to 5MB and returns matching job listings

Only the first five pages reach the model, and only to compress the CV into a
single line of keywords. That line becomes the search query; the listings that
come back are then filtered and formatted by the same deterministic code that
serves `/ask`.

## n8n Automation (Optional)

The included `n8n_workflow.json` adds automated job alerts every 12 hours — no manual searches needed.

### What the workflow does
![n8n Workflow](assets/n8n_workflow.png)
```
Schedule (every 12h)
  → Search Settings   (query + thread_id — the only node you edit)
  → Wake node         (GET /docs; expected to fail on a sleeping instance)
  → Wait 60s
  → POST /ask         (returns the formatted digest)
  → Send digest email via Gmail
```
![Email Digest](assets/email_digest.png)

The workflow holds **no filtering logic of its own**. Earlier versions duplicated the keyword matching across five JavaScript Code nodes, which meant every fix to the Python scoring had to be made twice — and never was. Now n8n only schedules, calls the API and mails the result, so the digest gets the same deduplication, mojibake repair and relevance ranking as every other interface.

### Setup

1. Import `n8n_workflow.json` into your n8n instance
2. Configure your Gmail credentials in the Gmail node and set your address in `Send a message`
3. In **Search Settings**, set `query` to whatever you are looking for
4. In **Search Settings**, replace `YOUR_UNIQUE_THREAD_ID` with a value only you know — `python -c "import uuid;print(uuid.uuid4())"`. Anyone who learns this value can change that thread's filters, so do not publish it
5. Point both HTTP nodes at your own backend (`http://host.docker.internal:8002` from Docker, `http://localhost:8002` without it)

**Why the wake node and the 60-second wait.** On a sleeping free-tier instance the first request is answered with an immediate `503`, not a slow response — so a longer timeout does not help, and n8n's retry ceiling (5 tries, 5s apart) covers only ~25s of a ~50s cold start. The wake node exists purely to trigger the boot and is set to `On Error: Continue`, since failing is its normal outcome. Drop both nodes if your backend is always on.

**Optional — persistent filters.** The thread outlives the workflow, so exclusions only need to be set once: call `POST /feedback` with the same `thread_id` and something like `no senior, no staff`. Every later run reuses them. The response footer lists the filters that were actually stored, which is worth reading — the extraction is done by an LLM and may generalise more than you intended.

---

## API Endpoints

| Endpoint | Method | Calls an LLM | Description |
|----------|--------|--------------|-------------|
| `/ask` | POST | no | Search jobs with keywords + applies memory filters |
| `/reset` | POST | no | Clear all stored filters and return the unfiltered results |
| `/feedback` | POST | yes | Turn feedback ("no MERN", "no senior") into filter keywords. Input capped at 100 characters |
| `/upload` | POST | yes | Upload PDF resume — agent extracts skills and finds matching jobs. Max 5MB, first 5 pages |
| `/evaluate` | POST | yes | AI scoring of job listings. Requires the `x-api-key` header |

Every endpoint is rate limited to 10 requests per minute per IP.

**On the LLM surface.** Search costs nothing: since the scoring became deterministic, `/ask` and `/reset` make no model calls at all. Three endpoints still do, and they are constrained differently. `/evaluate` accepts arbitrary text and is therefore closed — set `EVALUATE_TOKEN` in `.env` and send the same value as `x-api-key`; the exported workflow carries a `YOUR_EVALUATE_TOKEN` placeholder, and without it the endpoint answers 401. `/feedback` and `/upload` stay open because the public demo needs them, so they are bounded by size instead: 100 characters of feedback, 5MB and 5 pages of PDF. Bounded is not the same as free — if you deploy this somewhere that matters, put a budget alert on the API key.

---

## Evals

There are two, and they answer different questions. The LangSmith eval asks *how relevant are the results in a live market*, and a model judges the answer. The [Harbor](https://www.harborframework.com) eval asks *does the filter still do exactly what I think it does*, and nothing judges anything — the listings are frozen and the output is asserted.

### Relevance — LangSmith, ~0.8

The agent scores **0.82 across 22 test cases**, measured 6 August against a control run of the previous code the same morning, which scored 0.76. Roughly four out of every five listings it returns are relevant to the query, and fifteen of the cases score a clean 1.0.

Treat that as a range, not a reading. The same code scored **0.765** five days later without a line changing — the job boards had moved. A single case can swing half a point on its own: `rust` went from 1.0 to 0.5 across those five days, and the query has no moving parts in the code at all.

So changes here are judged against a **control run of the unchanged code on the same day**, never against a number from last week. Comparing a new run to a stored baseline measures the market as much as the change, and the market is louder.

The market was not the only thing moving. Two runs an hour apart returned the **same nine listings** for `Python developer` and scored them 0.889 and 0.222; `react developer` returned the same eight and scored 1.0 and 0.625. The aggregate barely moved — 0.82 both times — because the disagreements cancelled out, which is worse than an obviously unstable number. Chasing it down is written up under [Making the judge repeatable](#making-the-judge-repeatable).

The setup is a LangSmith dataset where each query carries a written description of what a good answer looks like, plus a Gemini 2.5 Flash judge that counts how many returned listings meet it. Score is relevant divided by returned, so padding a response with weak matches costs you.

The queries include narrow niches (`rust`, `blockchain solidity`), vague ones (`remote job`), one where the right answer is probably nothing at all (`COBOL mainframe developer`), and misspellings. Typos are not corrected on purpose. Search for `pyton developer` and you get nothing back; the reference answer says that is correct.

```bash
python eval_runner.py   # posts to localhost:8002/ask, change the port if your backend runs elsewhere
```

#### How it got there

Most of the gain came from taking things out. Every step below was measured against the same 22 cases:

| Change | Score |
|---|---|
| Starting point | 0.558 |
| Stopped trusting RemoteOK's tags, matched on titles | 0.575 |
| Removed the guaranteed minimum of 8 results | 0.679 |
| Treated `developer` and `engineer` as meaningful words | 0.584, reverted |
| Fixed the reference answers for the typo queries | 0.751 |
| Fixed a missing comma in the generic-word list | 0.812 |

Five days later the same code scored 0.765, so everything after that point is quoted against a control run of the unchanged code on the same morning:

| Change | Control | Score |
|---|---|---|
| Let the query's generic word break ties in the title | 0.765 | 0.780 |
| Scored descriptions on how often a word appears, and stopped truncating each source to ten | 0.76 | **0.82** |

The big jump came from deleting a rule that guaranteed at least 8 results. On a query like `rust` the agent would find one genuine match and then pad the list with seven listings that happened to mention the word somewhere in their body text. Three good results beat twelve mediocre ones.

The missing comma is worth a mention because Python never complained about it. Two adjacent string literals in a set silently became one, which quietly dropped `engineer` and `remote` from the generic-word list. It only surfaced because a nonsense query started returning listings with "Remote" in the title.

#### What the number doesn't cover

It measures the first response only. Users narrow results by talking to the agent ("no support roles", "no senior"), and none of the 22 cases exercise that path, so day-to-day use is better than the number suggests.

That path is no longer untravelled. The scheduled digest reuses one thread, so its stored exclusions are applied twice a day against whatever the boards are advertising, and the MCP tool takes exclusions as an argument on every call. It now has a number too, though not from here — see below.

It also moves. The agent queries live job boards, so two runs an hour apart see different listings and individual cases wobble by a lot. The aggregate is the signal, not any single row.

#### Making the judge repeatable

Scoring the same listings twice and getting 0.889 and 0.222 makes every comparison meaningless, so the run was treated as the thing under test rather than the agent. Three changes, in order of how much they bought:

**Stop asking the model questions that have one answer.** Five queries are ones where returning nothing is acceptable — the two deliberate misspellings, and niches like `COBOL mainframe developer` that the boards may simply not be advertising. Those examples now carry an `empty_ok` flag, and an empty response short-circuits to 1.0 before the judge is called. Four of the five already said so in their reference text; the model had the instruction and applied it unevenly. A rule you can state in one sentence does not need a model.

**Say what the grader is grading.** The instructions asked it to "count how many of the given jobs match the reference criteria" without ever saying whether a bad listing costs one point or voids the response. Both readings were live, which is exactly the 0.889/0.222 split. The prompt now states that grading covers only what was returned, that a rejected listing subtracts one and nothing more, and that criteria which are silent about a listing count in its favour.

**Write reference criteria that can be decided.** `Python developer` said "mid-level or senior, no Junior or Entry-level" and left "Senior General QA (Python)" undecidable. `remote job` said any "legitimate remote software role" for a query that names no field at all. Ten of the twenty-two were rewritten as "a listing is relevant when… and is not relevant when…", resolved against the listings the agent actually returns.

Two consecutive runs then agreed on eighteen of the nineteen cases whose criteria had not changed. The one that still moved — `django backend developer` — turned out to be another silent spec: nothing said what to do with a "Backend Engineer" listing that never names a language. The fix was to decide, and write it down.

The number moved from 0.82 to roughly 0.85 along the way. That is not the agent improving; it is the criteria finally saying what was always meant, and it makes every earlier number incomparable.

#### Known limitation

One title match is enough to admit a listing. That is fine when the distinctive word in a query is unambiguous, and it falls apart when it isn't: `data` pulls in Data Analysts, `wordpress` pulls in WordPress Support Specialists.

The obvious fix, requiring two matching words, was tried and rejected because it threw away correct results like `Software Engineer (Go, Python, TS)`. Measurement showed why it could never have worked. Specific terms like `sql`, `aws` and `pytorch` appear in **0%** of returned job titles, because titles say "DevOps Engineer", not "DevOps Kubernetes AWS Engineer". There is only ever one word to match on.

Half of it has since been chased down, from the other end. Dropping the generic word does not only fail to admit the right listings — it makes the ones already admitted indistinguishable. Search `AI engineer` and the query becomes `ai`, so an AI Engineer and an AI Sales Executive score identically; measured on 47 listings, 18 of 19 that passed the gate scored the same, and the cap then cut them by the order the four APIs happen to sit in `fan_out`. A generic word now adds a point when it appears in the title, which cannot admit anything on its own but does separate the role from the industry. Same-day control: 0.765 to 0.780, three cases up and none down.

The other half was the description, and it needed two changes that each look worthless alone. Relevance to the body text was scored by asking *whether* a word appeared, never *how often*, so a listing naming Python once ranked level with one naming it forty times: across 32 listings for `AI engineer`, that produced exactly one distinct score. Counting occurrences produces sixteen. On its own, that changed one case out of 22 — the other 21 came back identical, because a better order cannot help when there is nothing spare to order. Each source was also truncated to ten listings before anything read them, a leftover from when an LLM read the results and every listing cost money; for that same query Jobicy returned 100, of which 32 were relevant, and eight of the twelve best-scoring were never reachable. Removing the truncation alone had been tried the day before and scored as noise, for the mirror-image reason. Together, against a same-day control: 0.76 to 0.82, five cases up and none down.

The description's contribution is capped below the weight of a title match, so it can only reorder listings, never admit one — the same discipline as the generic-word point.

The admission rule itself is untouched: one title match still admits a listing, and a Support Specialist can still get in on the strength of the word alone. It just no longer outranks a real match by accident.

`WordPress developer` is the one case in the set that none of this moved, and checking why was more useful than fixing it would have been. On the morning of 6 August the four boards returned **no listing at all** with "wordpress" in its title, so the agent correctly returned nothing — and scored 0.0 for it. That is the same failure as `COBOL mainframe developer`: the judge is unreliable when the right answer is an empty list, which is why the next eval here is a deterministic check rather than another query.

The old 0.90 baseline is gone. It was measured against LLM-based filtering on a different dataset and was never comparable to this one.

### Filtering — Harbor, asserted

Both problems above share a root: the number moves for reasons that have nothing to do with the code. Live listings shift hourly, and the same input scored 0.333 and then 0.167 because a model was doing the scoring.

So the filter is measured somewhere else. One capture of all four job boards is frozen into the repository, the container runs with its network disabled, and the expected result is five listings written out by hand. Same input, same number, every time.

```bash
uv tool install harbor

PYTHONPATH=$(pwd) harbor run -p evals -i "*filter-exclusion-senior*" \
  -a evals.harbor_agents.pipeline_agent:PipelineAgent \
  -e docker -o evals/jobs \
  --extra-docker-compose evals/configs/no-network.yaml \
  --job-name local -y

python evals/check_reward.py evals/jobs/local
```

Docker is the only requirement. No API key, because nothing in this path calls a model — the harness is the repository's own MCP tool, running unmodified against fixture files instead of the internet. That is also why it can sit on every pull request: it costs a runner minute and no tokens.

The query is `python developer`, excluding `senior`, `game` and `canonical`. Three terms rather than one, so that both halves of the filter are exercised: `senior` through the title-only seniority rule, `canonical` through the full-text rule, where the word appears in descriptions and in no title at all. Five listings survive, five don't. Leaving one in and dropping one too many both score zero.

The expected set is written by hand, which is the whole point. A verifier that recomputed it by calling `filter_jobs` would be comparing the code against itself and would pass forever.

It bites: collapsing the filter so every keyword is matched against titles only takes the score from 1.0 to 0.0, and the failing test names the two listings that leaked through. Notably, deleting `senior` from the seniority list does **not** — the word would still match the same title as an ordinary keyword. Controls that fail to fail are worth knowing about.

What it does not cover: one query, one moment in the market, and no listing in the capture carries "senior" in its description alone — so the rule that seniority is judged on titles only is never tested in the one shape that separates it from ordinary matching. The fixtures are real captured data and were not edited to manufacture that case.

Design notes and the full reasoning live in [`evals/specs/`](./evals/specs).

### Next

Relevance is the remaining defect, and it now has somewhere to be measured. The scaffolding above is reusable as-is: freeze a capture, label which listings genuinely answer the query, assert. Whatever the fix turns out to be, it has to lean on descriptions — the measurement above shows there is rarely a second title word to ask for.

## Project Structure

```
job-search-agent/
├── agent.py           # LangGraph agent — fan-out, scoring, filtering
├── voice_agent.py     # VoiceSession — stateless wrapper around the same graph
├── mcp_server.py      # MCP server (stdio) — same graph, one read-only tool
├── main.py            # FastAPI backend + all endpoints
├── eval_runner.py     # LangSmith evaluation pipeline
├── requirements.txt
├── .env.example
├── n8n_workflow.json  # n8n automation workflow
├── evals/             # Harbor eval — frozen fixtures, deterministic verifier
│   ├── filter-exclusion-senior/   # the task: instruction, environment, tests
│   ├── harbor_agents/             # adapter that runs the pipeline as the agent
│   ├── specs/                     # design notes: harness, environment, task
│   └── check_reward.py            # turns a Harbor job into a build verdict
├── frontend/          # Next.js 15 frontend
└── voice/             # Voice AI interface (Pipecat) — see voice/README.md
    └── server/
        ├── bot.py
        └── langgraph_processor.py
```
