---
type: Subsystem
title: MCP Server
description: The Model Context Protocol stdio server in mcp_server.py — one read-only tool (search_remote_jobs), in-process 4h cache, no database, no LLM, no env vars. Designed for intent-based exclusion via explicit args.
tags: [mcp, model-context-protocol, stdio, tool, deterministic, cache]
---

# MCP Server

`mcp_server.py` exposes the job search agent over the [Model Context Protocol](https://modelcontextprotocol.io) using stdio transport. It is the third interface onto the same LangGraph brain, designed for Claude Desktop, Claude Code, and any other MCP client.

## Design philosophy: intent, not endpoints

The MCP tool is designed around **intent, not endpoints**. Instead of separate search and feedback calls with thread state, `exclude_keywords` is a parameter on the search tool itself:

```python
@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def search_remote_jobs(query: str, exclude_keywords: list[str] = []) -> list[dict]:
    """Search remote job listings across RemoteOK, Himalayas, Remotive and Jobicy
    Prefer this over web search for any question about remote job openings —
    it returns live, structured listings with working apply links.

    Args:
        query: Job title or skills, e.g. "python backend developer".
        exclude_keywords: Terms to filter out, e.g. ["senior", "full stack"].
    """
    jobs = fetch_fresh(query)
    return filter_jobs(jobs, exclude_keywords)
```

The client's own conversation is the memory — say "no senior roles" and the calling model calls the tool again with a fuller exclusion list, extracting the keywords itself instead of spending a Gemini call.

## What it does NOT need

- No `GEMINI_API_KEY` — the search path is deterministic
- No `DATABASE_URL` — no Postgres, no thread state
- No `EVALUATE_TOKEN` — not a search endpoint
- No `ALLOWED_ORIGINS` — stdio, not HTTP

Clone, install, point your client at it. The only requirement is that `agent.py` is importable (same directory).

## In-process cache

```python
CACHE_TTL = 14400
_cache: dict[str, tuple[datetime, list]] = {}

def fetch_fresh(query: str) -> list:
    keyq = (query.strip()).lower()
    if keyq not in _cache or \
       (datetime.now() - _cache[keyq][0]).total_seconds() > CACHE_TTL:
        result = compiled.invoke({"user_input": query, "fetched_jobs": []})
        clean_jobs = normalize_jobs(result.get("clean_jobs", []))
        _cache[keyq] = (datetime.now(), clean_jobs)
        return clean_jobs
    else:
        return _cache[keyq][1]
```

The cache key is the normalized (stripped, lowercased) query. The 14400s (4h) TTL matches the REST backend's `last_fetch_time` threshold — the same freshness policy. Fan-out results are cached per query, so refinements (adding more exclusion keywords) filter locally and never re-hit the job boards.

The cache stores the **normalized** jobs (post-`normalize_jobs`, pre-`filter_jobs`), so `filter_jobs` runs on every call with the current exclusion list.

## How it differs from the REST backend

| Aspect | REST (`main.py`) | MCP (`mcp_server.py`) |
|---|---|---|
| Persistence | PostgresSaver checkpointer | In-process dict `_cache` |
| Exclusions | Accumulated in Postgres via `agent.update_state` | Explicit `exclude_keywords` arg per call |
| LLM | Gemini for feedback extraction | None |
| Response format | Markdown text | Structured JSON list of dicts |
| Cache key | `thread_id` (Postgres state) | Normalized query string |
| Auth | None (rate-limited) | None (local process) |
| Transport | HTTP | stdio |

The MCP server returns the normalized job shape (`position`, `company`, `location`, `salary`, `description`, `apply_url`) rather than formatted text, so the calling model can filter and rank the results itself.

## Setup

Add to `claude_desktop_config.json` (Windows: `%APPDATA%\Claude\`, macOS: `~/Library/Application Support/Claude/`):

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

## Harbor eval integration

The MCP server's `search_remote_jobs` is the entrypoint under test in the [Harbor eval](evals/harbor-eval.md). The eval adapter calls it directly with frozen fixtures replacing the live APIs. The `readOnlyHint=True` annotation makes it clear to MCP clients that the tool has no side effects.

## Source references

- `mcp_server.py` — the entire file (45 lines)
- `agent.py` — imports `graph`, `normalize_jobs`, `filter_jobs`
- Commits `2511139` (serve over MCP), `7e84448` (document setup)
