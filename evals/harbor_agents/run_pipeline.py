import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/app/frozen")
sys.path.insert(0, "/app")

import frozen_apis  # noqa: F401  patches requests.get before the fetchers load

import mcp_server
from mcp_server import search_remote_jobs

block = re.search(
    r"```json\s*(\{.*?\})\s*```",
    Path("/app/instruction.md").read_text(encoding="utf-8"),
    re.DOTALL,
)
request = json.loads(block.group(1))
query = request["query"]
exclude = request["exclude"]

output = search_remote_jobs(query, exclude)
prefilter = mcp_server._cache[query.strip().lower()][1]


def dump(name, payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    for directory in ("/app", "/logs/agent"):
        Path(directory, name).write_text(text, encoding="utf-8")


dump("prefilter.json", prefilter)
dump("output.json", output)

print(f"query={query!r} exclude={exclude} prefilter={len(prefilter)} output={len(output)}")
