---
type: Quickstart
title: Quickstart & Task Routing
description: Primary entry point, operational overview, task routing guide, and developer onboarding instructions for the job search assistant.
tags: [quickstart, overview, routing, navigation, onboarding]
verified:
  - by: openwiki/0.9.0
    at: 2026-11-05T16:18:10.477Z
sources:
  - id: openwiki-source-eca60e2ced68ba99bd0ac710
    resource: repo://agent.py
  - id: openwiki-source-f1644da1c1a64a6a6567706b
    resource: repo://eval_runner.py
  - id: openwiki-source-1d64a0979a354ad458b3519a
    resource: repo://evals/check_reward.py
  - id: openwiki-source-185f850c083bac055a13cd37
    resource: repo://helper.py
  - id: openwiki-source-833e692518af9eeaf8564cc6
    resource: repo://main.py
  - id: openwiki-source-7a041713b68b973227e27f3e
    resource: repo://mcp_server.py
  - id: openwiki-source-3ea4f69fcc0222dbd310ddfc
    resource: repo://tasks.py
  - id: openwiki-source-3a30c14a947fb74b6b9d65b7
    resource: repo://voice_agent.py
generated: { by: "openwiki/0.9.0", at: "2026-11-05T16:18:10.477Z" }
---

# Quickstart & Task Routing

A remote job search assistant that queries six job sources in parallel, scores and filters listings using deterministic Python without an LLM in the retrieval path, and exposes three user interfaces: a FastAPI REST backend, a Model Context Protocol (MCP) stdio server, and a real-time conversational voice agent.

<!-- openwiki: mermaid parse failed and this diagram was converted to a text fence so it does not break rendering. Fix the diagram source and restore the mermaid fence. Parser error: Heuristic: an unescaped angle bracket inside a label breaks rendering; rephrase the label. -->
```text
flowchart TD
    subgraph Interfaces["Client Interfaces"]
        REST["FastAPI REST Backend<br/>(PostgreSQL Checkpointer)"]
        MCP["Stdio MCP Server<br/>(Stateless Tool, In-Process Cache)"]
        VOICE["Pipecat Voice Agent<br/>(In-Memory Session)"]
    end

    subgraph LLM_Tasks["LLM Services (google_genai:gemini-3.5-flash-lite)"]
        CV["CV Parsing Worker (Celery)"]
        FEED["Feedback Parsing (/feedback)"]
        DIGEST["Digest Fit Scoring (/evaluate)"]
    end

    subgraph LangGraph_Core["LangGraph Agent Core (agent.py)"]
        START_NODE([START]) --> FAN_OUT{fan_out}
        FAN_OUT -->|"Send API"| S1["fetch_jobs (RemoteOK)"]
        FAN_OUT -->|"Send API"| S2["fetch_sjobs (Himalayas)"]
        FAN_OUT -->|"Send API"| S3["fetch_tjobs (Remotive)"]
        FAN_OUT -->|"Send API"| S4["fetch_fjobs (Jobicy)"]
        FAN_OUT -->|"Send API"| S5["fetch_wjobs (Workable)"]
        FAN_OUT -->|"Send API"| S6["fetch_gjobs (Getro: 9 VC Funds)"]

        S1 --> COLLECT["collect_results<br/>(Deduplicate, Country Filter, Title-Weighted Score, Rank Top 12)"]
        S2 --> COLLECT
        S3 --> COLLECT
        S4 --> COLLECT
        S5 --> COLLECT
        S6 --> COLLECT
        COLLECT --> END_NODE([END])
    end

    REST -->|"Query / Ask"| START_NODE
    MCP -->|"search_remote_jobs"| START_NODE
    VOICE -->|"Voice search"| START_NODE

    REST -.->|"Extract avoid keywords"| FEED
    REST -.->|"Resume upload"| CV
    REST -.->|"Scheduled digest"| DIGEST
```
*System architecture showing three client interfaces, the deterministic 6-source LangGraph core, and isolated LLM utility tasks.*

---

## Wiki Navigation Map

The documentation is organized by domain and operational responsibility. Use the table below to navigate to detailed guides:

| Document | Area & Purpose | Key Highlights |
|---|---|---|
| [System Architecture Overview](architecture/overview.md) | High-level system topology | Three entry surfaces, LangGraph state machine, persistence models, external service boundaries. |
| [Agent Graph Architecture](architecture/agent-graph.md) | LangGraph retrieval engine | `Send` API fan-out across 6 sources, Getro thread pool, `collect_results`, deduplication, and ranking. |
| [Backend API & Lifecycle](architecture/backend-api.md) | FastAPI web service | Endpoints (`/ask`, `/feedback`, `/reset`, `/upload`, `/evaluate`), Redis cache, rate limiting, and Celery CV processing. |
| [Domain Concepts & Scoring](domains.md) | Business logic & ranking rules | Title-weighted scoring (`title_hits * 10 + description_hits`), seniority title-only matching, synonym normalization, and country filtering. |
| [External Integrations](integrations.md) | Third-party services & APIs | Protocols, schemas, and rate limits for RemoteOK, Himalayas, Remotive, Jobicy, Workable, Getro, Redis, PostgreSQL, and Gemini. |
| [MCP Server](mcp-server.md) | Local AI assistant integration | Model Context Protocol stdio tool (`search_remote_jobs`), client-managed exclusion arguments, and zero-API-key local setup. |
| [Voice Agent](voice-agent.md) | Real-time conversational interface | Pipecat pipeline (Daily WebRTC, Deepgram STT, ElevenLabs TTS), command routing, and ephemeral session memory. |
| [n8n Automation](operations/n8n-automation.md) | Scheduled job digest workflow | Automated daily/weekly candidate digests integrating `/digest` and `/evaluate` via webhook triggers. |
| [Operations & Runbook](operations.md) | Deployment & administration | Environment variables, Redis/PostgreSQL management, Docker deployment, and production failure runbooks. |
| [Testing & Quality Assurance](testing.md) | System verification strategy | Dual evaluation philosophy, regression test workflows, and manual test validation procedures. |
| [Harbor Deterministic Evaluation](evals/harbor-eval.md) | Hermetic CI benchmark | Zero-token, hermetic regression suite with frozen HTTP fixtures testing seniority and exclusion filtering. |
| [Repository Source Map](source-map.md) | Codebase directory guide | File-by-file responsibilities, architectural dependencies, and safe edit sequencing rules. |
| [Developer Workflows](workflows.md) | Contributor guides & recipes | Step-by-step procedures for adding job boards, tuning ranking heuristics, running evaluations, and debugging. |

---

## Core System Characteristics

1. **Parallel 6-Source Retrieval**: Queries RemoteOK, Himalayas, Remotive, Jobicy, Workable, and 9 VC portfolio boards via Getro concurrently using LangGraph's `Send` API.
2. **Deterministic Ranking & Zero Search Tokens**: Scores listings using title-weighted keyword matching (`title_hits * 10 + description_hits`) in pure Python (`agent.py`). No LLM is invoked during retrieval.
3. **Targeted Seniority & Exclusion Filtering**: Filters listings against user exclusions. Seniority keywords (`senior`, `junior`, `lead`, `principal`, etc.) match title words strictly, preventing mid-level roles from being disqualified by generic body text.
4. **Three Distinct Persistence Profiles**:
   - **REST API**: Persistent thread state saved in PostgreSQL via `PostgresSaver`.
   - **Voice Agent**: Ephemeral in-memory state via `InMemorySaver` for transient calls.
   - **MCP Server**: Fully stateless server where the LLM client maintains memory by passing `exclude_keywords` arguments.
5. **Specialized LLM Role (`google_genai:gemini-3.5-flash-lite`)**: Generative AI is strictly isolated to utility tasks where human nuance is needed:
   - Feedback extraction: Parsing user feedback in `/feedback` to determine negative filter keywords.
   - CV parsing: Structured extraction of candidate job title and skill keywords from uploaded resumes in `tasks.py`.
   - Digest evaluation: Scoring listings against candidate profile preferences in `/evaluate`.
   - Quality benchmark: Model-based evaluation in `eval_runner.py`.

---

## Main Runtime Components

| Component / Path | Primary Role | Related Documentation |
|---|---|---|
| `agent.py` | LangGraph core graph: 6-source fan-out, deduplication, seniority filtering, and scoring. | [Agent Graph](architecture/agent-graph.md), [Domain Concepts](domains.md) |
| `main.py` | FastAPI backend application: REST endpoints, PostgreSQL checkpointer, Redis caching, and rate limiting. | [Backend API](architecture/backend-api.md), [Operations](operations.md) |
| `helper.py` | Gemini model initialization (`google_genai:gemini-3.5-flash-lite`), prompt chains, agent runner, and markdown formatter. | [Backend API](architecture/backend-api.md), [Integrations](integrations.md) |
| `tasks.py` | Celery asynchronous worker: PDF resume text processing and structured keyword extraction. | [Backend API](architecture/backend-api.md), [Operations](operations.md) |
| `mcp_server.py` | Model Context Protocol stdio server providing the read-only `search_remote_jobs` tool with in-process query caching. | [MCP Server](mcp-server.md) |
| `voice_agent.py` | Voice session wrapper implementing `InMemorySaver` and result caching for conversational queries. | [Voice Agent](voice-agent.md) |
| `voice/server/bot.py` | Pipecat pipeline implementation integrating Deepgram, ElevenLabs, and Daily WebRTC transport. | [Voice Agent](voice-agent.md) |
| `voice/server/langgraph_processor.py` | Conversational frame processor routing spoken feedback, search queries, and listing details. | [Voice Agent](voice-agent.md) |
| `eval_runner.py` | LangSmith evaluation harness executing model-graded benchmarks against test query datasets. | [Testing & QA](testing.md) |
| `evals/` | Harbor deterministic evaluation suite using frozen HTTP fixtures and network-isolated Docker containers. | [Harbor Eval](evals/harbor-eval.md), [Testing & QA](testing.md) |
| `n8n_workflow.json` | Scheduled workflow automation definition for candidate job digest emails. | [n8n Automation](operations/n8n-automation.md) |

---

## Developer Onboarding & Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend web client)
- PostgreSQL (for REST thread persistence)
- Redis (for caching, rate limiting, and Celery task broker)
- Docker (optional, required for running Harbor evaluations)

### 1. Environment Configuration

Clone the repository and set up environment variables:

```bash
cp .env.example .env
```

Ensure the following core variables are configured in `.env`:

```ini
# Database & Cache
DATABASE_URL=postgresql://user:password@localhost:5432/jobsearch
REDIS_URL=redis://localhost:6379/0

# LLM Configuration (google_genai:gemini-3.5-flash-lite)
GEMINI_API_KEY=your_gemini_api_key

# Security & CORS
ALLOWED_ORIGINS=http://localhost:3000
EVALS=internal_eval_token
```

### 2. Backend & Worker Startup

Install dependencies in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Start the FastAPI application:

```bash
uvicorn main:app --reload --port 8000
```

Start the Celery worker for processing CV uploads:

```bash
celery -A tasks.celery_app worker --loglevel=info
```

### 3. Frontend Web Interface

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`.

### 4. Running the MCP Server

The MCP server connects local AI clients (such as Claude Desktop or Claude Code) via stdio. It operates completely independently of PostgreSQL or Gemini API keys:

```bash
# Test run stdio server directly
python mcp_server.py
```

To configure Claude Desktop, add the server to `claude_desktop_config.json`:

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

### 5. Running the Voice Agent

The voice interface requires API credentials for Daily, Deepgram, and ElevenLabs:

```bash
cd voice/server
uv sync
uv run bot.py
```

### 6. Executing Evaluation Suites

#### Deterministic Harbor CI Benchmark
Runs fully offline in Docker using frozen network fixtures:

```bash
uv tool install harbor
PYTHONPATH=$(pwd) harbor run -p evals -i "*filter-exclusion-senior*" \
  -a evals.harbor_agents.pipeline_agent:PipelineAgent \
  -e docker -o evals/jobs \
  --extra-docker-compose evals/configs/no-network.yaml \
  --job-name local -y

python evals/check_reward.py evals/jobs/local
```

#### LangSmith Live Dataset Evaluation
Runs query-level and per-listing evaluations using `google_genai:gemini-3.5-flash-lite`:

```bash
# Ensure backend is running on port 8002 or target URL configured in eval_runner.py
python eval_runner.py
```

---

## Task Routing Guide

Use this table to determine where to start reading, which files to modify, and how to validate your changes:

| Developer Goal | Start Here | Implementation Flow | Validation Method |
|---|---|---|---|
| **Tune relevance scoring or ranking** | [Domain Concepts](domains.md), [Agent Graph](architecture/agent-graph.md) | Edit `agent.py` (`collect_results`, scoring weights, `GENERIC` words) | Run Harbor evaluation and check score output on test queries |
| **Modify seniority or keyword exclusions** | [Domain Concepts](domains.md), [Harbor Eval](evals/harbor-eval.md) | Edit `agent.py` (`filter_jobs`, `SENIORITY` set) | `python evals/check_reward.py` against frozen fixtures |
| **Add or update a job board source** | [External Integrations](integrations.md), [Agent Graph](architecture/agent-graph.md) | Add fetch node in `agent.py`, update `fan_out`, update `helper.py` `SOURCES` | Run test query across all interfaces; update fixtures if needed |
| **Update REST API contracts or caching** | [Backend API](architecture/backend-api.md) | Edit `main.py` (`/ask`, `/feedback`, `/upload`), adjust Redis TTLs | Integration test via curl / Postman; frontend browser check |
| **Change CV parsing or LLM prompt behavior** | [Backend API](architecture/backend-api.md), [External Integrations](integrations.md) | Edit `helper.py` (`llmchain`), `tasks.py`, or `/feedback` in `main.py` | Upload test PDF resume and verify extracted keywords in worker logs |
| **Adjust MCP tool interface** | [MCP Server](mcp-server.md) | Edit `mcp_server.py` (`search_remote_jobs` signature and schema) | Test tool execution via Claude Desktop or MCP CLI |
| **Modify voice interaction or speech pipeline** | [Voice Agent](voice-agent.md) | Edit `voice_agent.py`, `voice/server/langgraph_processor.py` | Execute test voice call via Daily WebRTC session |
| **Update scheduled digest automation** | [n8n Automation](operations/n8n-automation.md) | Edit `n8n_workflow.json` or `/digest` endpoint in `main.py` | Trigger manual test run within n8n workflow editor |
| **Deploy or change server environment** | [Operations](operations.md), [Workflows](workflows.md) | Edit Dockerfile, docker-compose, or environment variables | Perform health check on `/ask` and verify checkpointer connectivity |
