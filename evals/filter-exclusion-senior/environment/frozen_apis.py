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


class FrozenResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def frozen_get(url, *args, **kwargs):
    host = urlparse(url).hostname or ""
    if host not in HOSTS:
        raise RuntimeError(f"unfrozen host: {host}")
    payload = json.loads((FIXTURES / HOSTS[host]).read_text(encoding="utf-8"))
    return FrozenResponse(payload)


def blocked(*args, **kwargs):
    raise RuntimeError("live network access is not available in this environment")


requests.get = frozen_get
for name in ("post", "put", "patch", "delete", "head", "options", "request"):
    setattr(requests, name, blocked)
requests.Session.request = blocked
requests.sessions.Session.request = blocked
