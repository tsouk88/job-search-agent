---
type: Runbook
title: Operations & Runbook
description: Deployment, configuration, background workers, storage operations, and operational runbook for running the system in production and locally.
tags: [operations, runbook, deployment, configuration, celery, redis, render, vercel, langsmith]
---

# Operations & Runbook

This runbook covers the operational lifecycle of the job search system across local development and production environments. It details startup procedures, environment variables, background worker execution, Redis failure tolerance, cache lifecycle, database persistence optimizations, logging configuration, and deployment topology on Render and Vercel.

## System Topology & Runtime Components

The production runtime consists of a FastAPI web backend, an asynchronous Celery task worker, an in-memory Redis instance, and a PostgreSQL database.

```mermaid
flowchart TD
    Client["Client Request (/ask)"] --> CheckConditions{"Freshness check:\nEmpty state OR\nQuery changed OR\nCountry changed OR\nFetch age > 4h?"}

    CheckConditions -->|No: Cache valid| ReturnState["Return filtered jobs from memory"]
    CheckConditions -->|Yes: Fetch required| CheckMeta{"Is Eval\n(metadata present)?"}

    CheckMeta -->|Yes: Bypass cache| RunAgent["Run LangGraph Agent\n(PostgresSaver, durability='exit')"]
    CheckMeta -->|No: Production search| ReadRedis["Read Redis cache\njobs:{query}:{country}"]

    ReadRedis -->|Cache Hit| UpdateState["Update graph state\nwith cached jobs"]
    ReadRedis -->|Cache Miss or RedisError| RunAgent

    RunAgent --> SaveCache{"Metadata is None\nAND clean jobs present?"}
    SaveCache -->|Yes| WriteRedis["Write Redis cache\nTTL = 14400s (4h)"]
    SaveCache -->|No| Finalize["Filter and format markdown"]
    WriteRedis -->|Success or RedisError caught| Finalize
    UpdateState --> Finalize
    Finalize --> Response["Return PlainTextResponse"]
```
Cache evaluation, Redis failure degradation, and graph execution flow for search requests.

### Runtime Responsibilities

- **FastAPI / Uvicorn Backend (`main.py`)**: Exposes REST and search endpoints (`/ask`, `/feedback`, `/reset`, `/upload`, `/jobs/{job_id}`, `/digest`, `/evaluate`, `/askeval`, `/health`). Manages CORS, slowapi rate limiting, request validation, and access log filtering.
- **Celery Worker (`tasks.py`)**: Asynchronously executes CV ingestion (`filework`), parsing uploaded resumes, invoking Gemini structured keyword extraction, and querying the job search graph.
- **Redis (`REDIS_URL`)**: Provides multi-tenant infrastructure for slowapi rate limiting, job query caching with a 4-hour TTL, Celery message brokering / result storage, and daily Gemini quota enforcement.
- **PostgreSQL (`DATABASE_URL`)**: Provides durable conversational memory via LangGraph's `PostgresSaver` checkpointer and stores deduplication state for automated digest dispatches in the `n8njobs` table.
- **LangSmith**: Traces LLM calls, graph execution steps, and eval runs configured against an EU regional endpoint.

For API contract details and routing behavior, see the [Backend API](architecture/backend-api.md). For automated scheduling, see [n8n Automation](operations/n8n-automation.md). For a high-level developer introduction, see the [Quickstart](quickstart.md).

---

## Local Operational Runbook

Local execution requires running Redis and PostgreSQL locally (or via Docker), followed by the Celery worker and Uvicorn API server.

### Prerequisites

1. **Python 3.11+** with dependencies installed from `requirements.txt`.
2. **Node.js 18+** for the frontend application.
3. **Redis server** running on `localhost:6379`.
4. **PostgreSQL** database accessible via `DATABASE_URL`.

### Step-by-Step Execution

#### 1. Start Redis
```bash
# Via native service
redis-server

# Or via Docker
docker run -d --name jobsearch-redis -p 6379:6379 redis:alpine
```

#### 2. Start Celery Worker
The Celery worker handles asynchronous CV uploads. Execute in a dedicated terminal using the `solo` pool mode:

```bash
cp .env.example .env   # configure GEMINI_API_KEY, DATABASE_URL, REDIS_URL
celery -A tasks worker --pool=solo -l info
```

#### 3. Start Uvicorn API Server
In a second terminal, start the FastAPI application:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 4. Start Next.js Frontend
In a third terminal, start the user interface:

```bash
cd frontend
npm install
npm run dev
```

The frontend listens on `http://localhost:3000` and proxies requests to `NEXT_PUBLIC_API_BASE` (defaults to `http://localhost:8000`).

#### 5. Optional Voice Server
If using the voice assistant interface (WSL2 required on Windows):

```bash
cd voice/server
uv sync
cp .env.example .env   # populate voice keys: Deepgram, ElevenLabs, Gemini
uv run bot.py
```

---

## Environment Variables & Configuration

The application reads configuration from `.env` locally and from platform environment variables in production.

| Variable | Required | Default / Example | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | `AIzaSy...` | Powers Gemini 3.5 Flash-Lite for feedback parsing, CV parsing (`CVKeywords`), and `/evaluate` |
| `DATABASE_URL` | Yes | `postgresql://user:pass@host:5432/dbname` | Backs `PostgresSaver` checkpointer and `n8njobs` deduplication table |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Storage for rate limiting, job-result cache, Gemini counters, and Celery broker/backend |
| `ALLOWED_ORIGINS` | Yes | `http://localhost:3000` | Comma-separated CORS allowed origins without trailing slashes |
| `LANGSMITH_TRACING` | Optional | `true` | Enables LangSmith execution tracing |
| `LANGSMITH_API_KEY` | Optional | `lsv2_pt_...` | API key for LangSmith project ingestion |
| `LANGSMITH_PROJECT` | Optional | `jobsearch-agent` | LangSmith destination project name |
| `LANGSMITH_ENDPOINT` | Optional | `https://eu.api.smith.langchain.com` | Regional LangSmith ingestion endpoint (EU region) |
| `EVALUATE_TOKEN` | Protected | `secret-token` | Header `x-api-key` secret for `/evaluate` endpoint |
| `N8N_DEDUPE` | Protected | `secret-token` | Header `x-api-key` secret for `/digest` and `/digest/sent` endpoints |
| `EVALS` | Protected | `secret-token` | Header `x-api-key` secret for `/askeval` test endpoint |
| `OPENROUTER_API_KEY` | Protected | `sk-or-...` | OpenRouter key used by the `jev` judge in `eval_runner.py` |

### Render Secret Omissions & Authentication

`render.yaml` explicitly declares synced placeholders only for `GEMINI_API_KEY`, `DATABASE_URL`, `REDIS_URL`, `ALLOWED_ORIGINS`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT`, while hardcoding `LANGSMITH_TRACING` and `LANGSMITH_ENDPOINT`.

Crucially, `render.yaml` does **not** declare `EVALUATE_TOKEN`, `EVALS`, `N8N_DEDUPE`, or `OPENROUTER_API_KEY`. If any protected endpoints are invoked without configuring these tokens manually in the Render dashboard:
- The endpoint dependency `keycheck(envname)` reads `os.getenv(envname)`.
- Because the variable is empty or unset, `keycheck` immediately raises `HTTPException(status_code=401, detail="Unauthorized")`.
- When set, incoming `x-api-key` headers are verified using constant-time comparison via `secrets.compare_digest(key, x_api_key)`.

### EU LangSmith Regional Configuration

Observability is configured for European data residency. Production sets `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` with `LANGSMITH_TRACING="true"`.

When eval suites run via `POST /askeval`, the backend attaches run metadata:
```python
metadata = {"run_type": "eval"}
```
This metadata flows through LangGraph into LangSmith run traces, allowing operators to filter and isolate automated evaluation executions from live end-user queries within the LangSmith console.

---

## Redis Operations & Failure Tolerance

The backend relies on Redis for multiple operational concerns, configured with a 2-second timeout to avoid event loop stalls:

```python
r = redis.Redis.from_url(os.getenv("REDIS_URL"), socket_connect_timeout=2, socket_timeout=2)
```

### Graceful Degradation Under Redis Outages

The system continues serving core search requests even if Redis goes down:

1. **Rate Limiting Fallback**: SlowAPI is initialized with `Limiter(key_func=my_key, storage_uri=os.getenv("REDIS_URL"), in_memory_fallback_enabled=True)`. When Redis is unavailable, rate limits silently fall back to an in-memory dictionary instead of rejecting user requests.
2. **Job Cache Read Failure**: In `searchhelper()`, reading from the cache is wrapped in an exception block:
   ```python
   try:
       cache = r.get(savedjobs)
   except redis.exceptions.RedisError as e:
       logging.warning(e)
       cache = None
   ```
   If Redis is unreachable or times out, the error is recorded with `logging.warning(e)`, `cache` is treated as `None`, and the request falls back seamlessly to executing `run_agent()`.
3. **Job Cache Write Failure**: Writing to the cache is similarly guarded:
   ```python
   try:
       r.set(savedjobs, cached, ex=14400)
   except redis.exceptions.RedisError as e:
       logging.warning(e)
   ```
   Write exceptions are logged at warning level without surfacing to the client.
4. **Health Check Tolerance**: The `/health` endpoint executes `r.ping()` and `celery_app.control.ping(...)`. If Redis is down, the caught exception resets `last_ping = time.monotonic()`, logs `logging.warning(e)`, and still returns `{"status": "ok"}`. The endpoint only raises HTTP 503 (`Timed Out`) if Celery control pings succeed without exception but return empty worker lists for greater than `PING_TIME = 90` seconds.

### Cache Lifecycle & Invalidation Logic

The search cache stores scraped and scored listings to protect upstream job APIs from excessive polling:
- **Key Normalization**: `jobcache(query, country)` normalizes whitespace and lowercases query terms: `jobs:{" ".join(query.lower().split())}:{country}`.
- **TTL**: Keys expire after `14400` seconds (4 hours).
- **Four-Condition Freshness Check**: The graph state tracks `last_fetch_time`, `user_input`, and `country`. A search re-evaluates the cache and upstream boards only if:
  1. `not last_known_fetch` (no prior search executed in this thread),
  2. `current_query != input.user_input` (query text changed),
  3. `current_country != input.country` (location filter changed), or
  4. `(datetime.now() - datetime.fromisoformat(last_known_fetch)).total_seconds() > 14400` (cache TTL expired).
  If none of these conditions are met, the API re-filters the previously cached listings from state in memory without making network calls.
- **Evaluation Cache Bypass**: When `metadata` is present (such as during `/askeval`), `cache` is explicitly forced to `None` and writing to Redis is skipped, preventing synthetic eval data from polluting user caches or masking live board regressions.

### Gemini Budget Enforcement

To prevent quota exhaustion on Gemini APIs, Redis maintains daily usage counters:
```python
def check_gemini_budget(name, limit):
    now = datetime.now()
    date = f"{now.year}-{now.month}-{now.day}"
    key = f"gemini_calls:{name}:{date}"
    n = r.incr(key)
    if n == 1:
        r.expire(key, 86400)
    if n > limit:
        raise HTTPException(status_code=429, detail="Gemini calls are out")
    return n
```
- **Quotas**: `/evaluate` enforces `check_gemini_budget("eval", 5)` (5 calls/day). `/upload` and `/feedback` enforce `check_gemini_budget("site", 100)` (100 calls/day across CV uploads and spoken feedback).
- **Reset**: Counters automatically expire after 86,400 seconds (24 hours).

---

## Celery Background Worker Setup

Background execution handles computationally and network-intensive PDF extraction and CV analysis outside of the FastAPI request loop.

### Celery Configuration (`tasks.py`)

Celery is configured to use Redis for both broker and backend:
```python
REDIS_URL = os.getenv("REDIS_URL")
celery_app = Celery(broker=REDIS_URL, backend=REDIS_URL)
```

The worker is launched with `--pool=solo`:
```bash
celery -A tasks worker --pool=solo -l info
```
The `solo` execution pool runs tasks sequentially inside the main worker process. This eliminates process-forking overhead and connection pool corruption with PostgreSQL (`psycopg`) and HTTPS connection pools in constrained environments such as Render free-tier instances.

### Asynchronous CV Pipeline (`/upload` & `/jobs/{job_id}`)

1. **File Validation**: `POST /upload` validates that the uploaded file has `content_type == "application/pdf"` and does not exceed 5MB (`5 * 1024 * 1024` bytes).
2. **Off-Thread Extraction**: To keep FastAPI's async event loop non-blocking:
   - PDF text extraction (`pdfread`) is dispatched to a worker thread: `await asyncio.to_thread(pdfread, file)`. `pdfplumber` extracts text from the first 5 pages (`pages[:5]`).
   - Gemini site budget is verified off-thread: `await asyncio.to_thread(check_gemini_budget, "site", SITE_LIMIT)`.
   - Celery task submission is dispatched off-thread: `job = await asyncio.to_thread(filework.delay, text, thread_id, country)`.
   - The endpoint returns `{"job_id": job.id}`.
3. **Task Execution (`filework`)**:
   - Dispatches CV text to Gemini with structured schema `CVKeywords` (`llmchain(..., upload=True)`), returning up to 10 prioritized skill keywords.
   - Compiles LangGraph against `PostgresSaver.from_conn_string(DATABASE_URL)`.
   - Runs `run_agent()` with extracted keywords, normalizes results, applies active filters, and returns markdown.
4. **Client Polling**: The client polls `GET /jobs/{job_id}`:
   - `res.status == "SUCCESS"`: Returns `{"status": "done", "result": res.result}`.
   - `res.status == "FAILURE"`: Logs error via `logging.warning(res.result)`. If `isinstance(res.result, httpx.TimeoutException)`, returns `{"status": "failed", "detail": "The CV reader is slow right now, please try again in a minute"}`. Otherwise returns generic failure detail.
   - Any other state: Returns `{"status": "pending"}`.

---

## Storage Operations & Persistence Optimizations

### Checkpointer Optimization: `durability="exit"`

In `helper.py`, `run_agent()` executes the LangGraph workflow using:
```python
result = agent.invoke(
    {"user_input": user_input, "country": country, "fetched_jobs": []},
    config=config, durability="exit"
)
```

By default, persistent checkpointers like `PostgresSaver` attempt to record checkpoint state after each individual node or superstep execution. In the agent graph, six search nodes (`fetch_jobs`, `fetch_sjobs`, `fetch_tjobs`, `fetch_fjobs`, `fetch_wjobs`, `fetch_gjobs`) fan out in parallel.

Specifying `durability="exit"` alters LangGraph checkpointer persistence:
- Checkpoints are saved **only when graph execution exits**, rather than after each intermediate node transition.
- This dramatically reduces PostgreSQL write amplification, lowers transaction contention on connection pools, and shortens end-to-end search latency.

### Database Connection Pooler Configuration

- **PostgreSQL / Supabase**: Always connect via the **session pooler** (port `5432`), not the transaction pooler (port `6543`). `PostgresSaver` uses prepared statements. Transaction poolers route successive queries across different backend connections, discarding prepared statements and generating intermittent SQL execution errors.
- **Deduplication Table**: The `n8njobs` table must exist in the database to record links dispatched by `/digest/sent` via `ON CONFLICT (joblink) DO NOTHING`.

---

## Logging & Diagnostics Configuration

Application logging is initialized at module load in `main.py`:
```python
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s")
```

### Access Log Filtering

Automated container platforms and uptime monitors ping `/health` frequently. To prevent log saturation, a custom logging filter intercepts and drops `/health` requests from Uvicorn's access logger:

```python
class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        if "GET /health " not in record.getMessage():
            return True

logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
```

### Operational Warning Logging

The application uses `logging.warning()` systematically across degradation boundaries:
- Redis cache lookup exceptions (`logging.warning(e)`).
- Redis cache write failures (`logging.warning(e)`).
- PDF extraction parsing errors (`logging.warning(e)`).
- Celery task failure payloads (`logging.warning(res.result)`).
- Health check ping network exceptions (`logging.warning(e)`).

All warnings include ISO-style timestamps to facilitate cross-referencing with external log aggregators and LangSmith traces.

---

## Production Deployment

### Backend on Render (`render.yaml`)

The backend deploys as a single web service via Render Blueprints:

```yaml
services:
  - type: web
    name: jobsearch-api
    runtime: python
    plan: free
    region: frankfurt
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A tasks worker --pool=solo -l info & uvicorn main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: GEMINI_API_KEY
        sync: false
      - key: DATABASE_URL
        sync: false
      - key: REDIS_URL
        sync: false
      - key: ALLOWED_ORIGINS
        sync: false
      - key: LANGSMITH_API_KEY
        sync: false
      - key: LANGSMITH_PROJECT
        sync: false
      - key: LANGSMITH_TRACING
        value: "true"
      - key: LANGSMITH_ENDPOINT
        value: https://eu.api.smith.langchain.com
```

Key deployment characteristics:
- **Single Process Group**: Celery and Uvicorn share the same container process space. The start command forks the Celery worker into the background (`celery ... &`) and executes Uvicorn in the foreground.
- **Port Binding**: Uvicorn binds to `0.0.0.0` and Render's dynamic `$PORT` environment variable.
- **Region**: Frankfurt (`frankfurt`), matching European low-latency data access to Supabase and EU LangSmith endpoints.

### Frontend on Vercel

The frontend is a Next.js application deployed to Vercel:
- **Root Directory**: `frontend`
- **Environment Variable**: `NEXT_PUBLIC_API_BASE` set to the Render production URL (e.g. `https://jobsearch-api.onrender.com`).

### Critical Deployment Gotchas

1. **No Trailing Slashes**:
   - `NEXT_PUBLIC_API_BASE`: Must have **no trailing slash**. Client routes append `/ask`, `/upload`, etc. A trailing slash generates double-slash paths (e.g. `https://api.com//ask`).
   - `ALLOWED_ORIGINS`: Must have **no trailing slash**. Browsers send the `Origin` header as `scheme://host[:port]`. If `ALLOWED_ORIGINS` includes a trailing slash, FastAPI's CORS middleware fails to match, resulting in silent browser CORS rejections.
2. **Render Cold-Start Dynamics**:
   - Render's free tier spins down services after 15 minutes of inactivity. Cold starts take approximately 50 seconds to boot the container, followed by 15 seconds to complete initial search fan-out.
   - The automated n8n workflow mitigates cold-start timeouts by issuing an initial wake request to `GET /docs` (with `OnError: Continue`), waiting 120 seconds, and only then dispatching `POST /digest`.

---

## Operational Troubleshooting Runbook

| Symptom | Probable Cause | Verification & Remediation |
|---|---|---|
| API fails during startup | Database unreachable | Check `DATABASE_URL`. `PostgresSaver.setup()` runs inside `lifespan()` on startup. |
| Rate limits do not persist across restarts | Redis unreachable | Check `REDIS_URL`. SlowAPI falls back silently to in-memory mode when Redis is down. |
| `/upload` jobs stay indefinitely in `pending` | Celery worker dead or not running | Verify worker process is running: `celery -A tasks worker --pool=solo -l info`. Check Redis broker connectivity. |
| `/evaluate` returns 401 Unauthorized | Missing token | Set `EVALUATE_TOKEN` in Render dashboard or `.env`. Token is not in `render.yaml`. |
| `/askeval` returns 401 Unauthorized | Missing eval token | Set `EVALS` in Render dashboard or `.env`. Token is not in `render.yaml`. |
| `/digest` or `/digest/sent` returns 401 | Missing dedupe token | Set `N8N_DEDUPE` in Render dashboard or `.env`. Verify n8n HTTP Header Auth sends `x-api-key`. |
| 429 "Gemini calls are out" | Daily budget limit exceeded | Check Redis keys `gemini_calls:eval:<date>` (cap 5) or `gemini_calls:site:<date>` (cap 100). Resets at midnight. |
| Browser shows CORS error | Trailing slash in origin | Check `ALLOWED_ORIGINS`. Ensure origins like `https://example.vercel.app` contain no trailing `/`. |
| Intermittent Postgres connection errors | Supabase transaction pooler used | Ensure `DATABASE_URL` connects to port 5432 (session pooler), not port 6543 (transaction pooler). |
| `/health` returns 503 Service Unavailable | Celery worker unresponsive | Worker has not answered `control.ping()` for >90s (`PING_TIME`). Inspect worker process memory and crash logs. |
| Search results ignore exclusions | Keyword extraction prompt cap | Feedback extraction input is capped at 100 characters (`Field(max_length=100)`). Ensure instructions are concise. |

---

## CI Workflows & Operational Automation

- **Harbor Eval (`.github/workflows/eval.yml`)**: Triggered on changes to `agent.py`, `mcp_server.py`, or `evals/**`. Executes containerized evals (`filter-exclusion-senior`) in a network-isolated environment, verifies reward thresholds, and uploads test artifacts.
- **OpenWiki Docs Automation (`.github/workflows/openwiki-update.yml`)**: Runs monthly via cron (`0 6 1 * *`) and on manual dispatch to keep documentation synchronized with source code changes.
