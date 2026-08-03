from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from agent import graph, normalize_jobs, filter_jobs
from datetime import datetime


compiled = graph.compile()
mcp = MCPServer(
    "jobsearch",
    instructions="Live remote job listings from RemoteOK, Himalayas, Remotive "
                 "and Jobicy, with deterministic relevance filtering.",
)

CACHE_TTL = 14400
_cache: dict[str, tuple[datetime, list]] = {}

def fetch_fresh(query:str) -> list:
    keyq = (query.strip()).lower()
    if keyq not in _cache or (datetime.now() - _cache[keyq][0]).total_seconds() > CACHE_TTL:
        result = compiled.invoke(
                {"user_input": query, "fetched_jobs": []}
            )
        clean_jobs = normalize_jobs(result.get("clean_jobs" , []))
        _cache[keyq] = (datetime.now() , clean_jobs)
        return clean_jobs
    else:
        return _cache[keyq][1]
    


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
    return filter_jobs(jobs , exclude_keywords)

if __name__ == "__main__":
    mcp.run(transport="stdio")