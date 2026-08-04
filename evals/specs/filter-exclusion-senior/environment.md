# Environment — filter-exclusion-senior

## Dependencies

| Dependency | Mode | Why |
|---|---|---|
| RemoteOK API | frozen | Read-only, but the listing set moves hourly — the exact thing this eval exists to stop. |
| Himalayas API | frozen | Same, plus it 429s under repeated use. |
| Remotive API | frozen | Same. |
| Jobicy API | frozen | Same. |
| Postgres checkpointer | absent | Not on the MCP path. |
| Gemini | absent | Not on any path under test. |

Network policy: the container runs with **no network**, enforced by a Docker
Compose overlay (`evals/configs/no-network.yaml`, `network_mode: none` on the
`main` service), passed with `--extra-docker-compose`.

`task.toml` declares `network_mode = "public"` because Harbor's own
`no-network` policy is **not available on this host**: Docker Desktop's WSL2
kernel lacks `CONFIG_NFT_FIB_INET`, so Harbor disables egress control and
rejects the task outright. The declaration in `task.toml` is therefore not the
enforcement — the overlay is.

Enforcement was **verified, not assumed**: the first run's verifier log shows
`Temporary failure resolving 'deb.debian.org'` from inside the container.

Second line of defence, independent of Docker: `frozen_apis.py` replaces every
`requests` entry point other than the frozen `get` with a function that raises,
including `Session.request`. A call that escaped the stub would fail in-process
even on a networked host.

## Frozen data

Captured 04/08/2026 for query `python developer`, raw and pre-filter:

```
environment/fixtures/{remoteok,himalayas,remotive,jobicy}.json
```

Counts as captured — listings / titles containing "senior":
remoteok 101/2, himalayas 20/3, remotive 31/5, jobicy 69/23.

Each file is the verbatim `response.json()` of the URL the corresponding
fetcher builds (`agent.py:143,163,179,209`), written UTF-8.

## Frozen service

`environment/frozen_apis.py` replaces `requests.get` with a host router:

- `remoteok.com` → `remoteok.json`
- `himalayas.app` → `himalayas.json`
- `remotive.com` → `remotive.json`
- `jobicy.com` → `jobicy.json`
- anything else → raise

It returns a stub exposing `.json()` and `.status_code = 200` — the two
attributes the fetchers touch. The fetchers themselves are untouched Harness
code; only the service behind them is frozen.

Query string is ignored: one task, one query, stated in `instruction.md`.

## State and reset

Read-only. No mutable state, no writes, nothing to reset between trials. The
only mutable thing in the process is the MCP in-memory `_cache`, which dies
with the process.

## Validation gate before the task is considered built

The pipeline does not see all 221 listings: three sources are cut to `[:10]`
raw, and `collect_results` keeps only title matches up to `MAX_RESULTS = 12`.

Required before writing `expected.json`: run the adapter once and inspect
`prefilter.json`. It must contain enough excluded and kept listings that the
exclusion actually bites in both directions.

**Measured 04/08:** `prefilter.json` holds 10 listings, of which exactly one
carries "senior" in its title. One excluded listing is too thin a hinge, so the
request was widened to three exclusions over the same fixtures — 5 kept, 5
dropped. See `task.md`.

## Fidelity limits

- One query only. Nothing here says anything about how the filter behaves on
  other vocabulary.
- Frozen at a point in time; these listings will not exist in a month. That is
  the point — the eval measures the code, not the market.
