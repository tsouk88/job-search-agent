import json
from pathlib import Path
from urllib.parse import urlparse

import requests

FIXTURES = Path(__file__).parent / "fixtures"

HOSTS = {
    "remoteok.com": "remoteok.json",
    "himalayas.app": "himalayas.json",
    "remotive.com": "remotive.json",
    "jobicy.com": "jobicy.json",
}

# Workable is HTML rather than JSON, and it takes two rounds of requests: one
# search page for the links, then a page per listing. The captured pages are
# kept down to the schema.org blocks the parser actually reads, so the fixtures
# stay legible and the parser behaves exactly as it does against the live site.
WORKABLE = "jobs.workable.com"

# Getro is a POST search: the answer depends on the VC in the path and on the
# query in the body, so the fixture is keyed by both. A pair that was never
# captured answers with no jobs, as Getro does for a query that finds nothing.
GETRO = "api.getro.com"


class FrozenResponse:
    status_code = 200

    def __init__(self, payload=None, text=""):
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def workable_fixture(path):
    """The captured page for one Workable path, search or listing."""
    if path.startswith("/search/"):
        return FIXTURES / "workable" / "search-python.html"
    if path.startswith("/view/"):
        job_id = path.split("/view/")[1].split("/")[0]
        return FIXTURES / "workable" / f"view-{job_id}.html"
    raise RuntimeError(f"unfrozen workable path: {path}")


def frozen_get(url, *args, **kwargs):
    parts = urlparse(url)
    host = parts.hostname or ""
    if host == WORKABLE:
        fixture = workable_fixture(parts.path)
        if not fixture.exists():
            raise RuntimeError(f"unfrozen workable page: {parts.path}")
        return FrozenResponse(text=fixture.read_text(encoding="utf-8"))
    if host not in HOSTS:
        raise RuntimeError(f"unfrozen host: {host}")
    payload = json.loads((FIXTURES / HOSTS[host]).read_text(encoding="utf-8"))
    return FrozenResponse(payload=payload)


def frozen_post(url, *args, **kwargs):
    parts = urlparse(url)
    if parts.hostname != GETRO:
        raise RuntimeError(f"unfrozen host: {parts.hostname}")
    vc = parts.path.split("/collections/")[1].split("/")[0]
    query = (kwargs.get("json") or {}).get("query") or ""
    captured = json.loads((FIXTURES / "getro.json").read_text(encoding="utf-8"))
    jobs = captured.get(vc, {}).get(query, [])
    return FrozenResponse(payload={"results": {"jobs": jobs, "count": len(jobs)}})


def blocked(*args, **kwargs):
    raise RuntimeError("live network access is not available in this environment")


requests.get = frozen_get
requests.post = frozen_post
for name in ("put", "patch", "delete", "head", "options", "request"):
    setattr(requests, name, blocked)
requests.Session.request = blocked
requests.sessions.Session.request = blocked
