# Implementation Plan: Route Lookup and Orchestration

**Branch**: `orchestrator_and_api` (spec dir `002-route-orchestrator`) | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-route-orchestrator/spec.md`

## Summary

`GET /api/route/?start=&finish=` resolves two "City, ST" strings through a shared normalizer and a
lazily built in-memory `CityIndex`, makes exactly one OSRM call (cached 24 h), and produces a
handoff (geometry, total miles, start/finish coordinates) for the later fuel-stop algorithm. Trips
of 500 miles or less short-circuit to no stops and cost 0.0. The human selected (2026-09-26):
**Design A** for structure (pure `routing/` package, thin `api/` view, one ORM repository
function at the boundary) and **`routing/normalize.py`** as the single normalizer, imported by
`stations/pipeline.py`.

## Technical Context

**Language/Version**: Python 3.12+ (per `pyproject.toml`), Django 6.1.

**Primary Dependencies**: Django (already), `httpx` (OSRM client; named in the constitution stack,
stdlib `urllib` lacks the split connect/read timeouts and respx-mockable transport). Dev:
`pytest-mock`, `respx` (constitution Principle V). Polyline decoding is hand-written (about 15
lines, precision 5) rather than adding the `polyline` package.

**Storage**: Reads the `cities` SQLite database (City table) once per process. Route cache is
Django `LocMemCache`, 24 h TTL. No new tables or migrations.

**Testing**: `pytest` + `pytest-django`, `respx` for OSRM, `ruff`, `mypy`. `routing/` tests need no
Django and no database; the view test uses the Django test client with a temporary cities DB.

**Target Platform**: Linux, one or more worker processes (cache and index are per worker).

**Project Type**: Django web service (JSON API).

**Performance Goals**: cached request under 50 ms; uncached adds at most 100 ms over OSRM's own
latency (SC-005).

**Constraints**: One OSRM call per uncached request, none on a hit, no retries; timeouts 3 s
connect / 10 s read; tests never touch the network.

**Scale/Scope**: about 29,880 city rows (about 20k distinct keys) held in a dict; a few hundred KB.

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1.*

| Principle | Status | Note |
|---|---|---|
| I. Pure routing core | Pass | `routing/` has no Django imports and never touches the ORM. Cache and city loader are injected. The view is parse, call, serialize (under 30 lines). The only ORM read is `api/repo.py::load_cities`. |
| II. Correctness guarantees | N/A | Planner rules belong to the algorithm feature. Units are miles and metres converted with `/ 1609.344`; the 500-mile no-stop rule is the full-tank range and is recorded in the spec assumptions. |
| III. Simple, deep modules | Pass | Two designs compared (research.md D1, D2); human chose A. Each module has a one-sentence responsibility (below). |
| IV. Errors and comments | Pass | Domain exceptions in `routing/errors.py`, translated to HTTP in one handler in `api/`. No generic `except`. `raise ... from err` for httpx errors. |
| V. Tests as spec | Pass | Behavior-named tests; respx for OSRM; a test fixture blocks real network. |
| VI. Safety and gates | Pass | Outbound call goes only to the OSRM host named in the constitution; no credentials; no push or merge without the human. |
| Dependencies | Pass | `httpx` justified above; dev-only `respx`, `pytest-mock`. |
| Commit size at most 300 lines | Plan | The cap binds commits, not PRs (constitution v2.0.0, amended 2026-10-02 to resolve the prior PR/commit ambiguity). Split into nine commit-sized units (below), one per tasks.md phase. |

Post-design re-check: still passes. Noted tension: the normalizer move touches the already-merged
data pipeline, so it is isolated in its own commit with a key rebuild.

## Project Structure

### Documentation (this feature)

```text
specs/002-route-orchestrator/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── route-api.md
└── tasks.md             # /speckit-tasks, not created here
```

### Source Code (repository root: `fueling_map/`)

```text
routing/                     # plain Python, zero Django imports
├── __init__.py
├── normalize.py             # normalize_city_key(city, state) -> (key, state)
├── errors.py                # RouteError hierarchy (status carried as data)
├── city_index.py            # CityIndex + get_city_index(loader), lock, check-lock-check
├── osrm.py                  # fetch_route(start, finish, client) -> Route; decode_polyline
└── pipeline.py              # plan_route(start, finish, cities, cache, http, planner) -> RouteResult
api/
├── __init__.py
├── apps.py
├── urls.py                  # path("route/", route_view)
├── views.py                 # parse -> pipeline -> JSON; single exception handler
└── repo.py                  # load_cities(): only ORM read
config/
├── settings.py              # + "api" app, CACHES (LocMem), OSRM_BASE_URL from env
└── urls.py                  # + path("api/", include("api.urls"))
stations/pipeline.py         # PR1 only: import normalize_city_key from routing.normalize
tests/
├── unit/routing/            # normalize, city_index, osrm, pipeline (no DB, no Django)
└── integration/             # test_route_endpoint.py (client + temp cities DB + respx)
```

**Structure Decision**: The `routing/` plus thin `api/` layout from `ARCHITECTURE.md`. Module
responsibilities: `normalize` builds one lookup key from a city and state; `city_index` owns
the once-per-process coordinate lookup; `osrm` turns two coordinates into one decoded route;
`pipeline` orchestrates parse-to-handoff and enforces the call budget; `api.views` translates HTTP
to and from the pipeline.

**Delivery split (each item is one commit, at most 300 changed lines per constitution v2.0.0;
a PR may bundle several adjacent commits — one per tasks.md phase)**:

1. `refactor(stations)`: add `routing/normalize.py`, switch `stations/pipeline.py` to import it,
   add bare `MT`, rebuild stored keys. Nothing else. (tasks.md Phase 1)
2. `feat(routing)`: `city_index.py`, `errors.py`, `api/repo.py`. (Phase 2)
3. `feat(routing)`: `osrm.py` with polyline decode. (Phase 3, US1a)
4. `feat(api)`: `pipeline.py` happy path, view, urls, settings — the MVP. (Phase 4, US1b)
5. `feat(api)`: parsing and error responses (`InvalidParameter`, `SameEndpoints`,
   `CityNotFound`) wired into `pipeline.py` and the view's error handler. (Phase 5, US2)
6. `feat(api)`: the 24 h, direction-sensitive route cache. (Phase 6, US3)
7. `feat(api)`: the 500-mile short-circuit and the planner seam. (Phase 7, US4)
8. `test(api)`: fail-loudly proof at the HTTP layer for missing/empty cities data. (Phase 8, US5)
9. `chore`: README note on the per-worker cache, no-network test guard, and the quickstart
   validation run. (Phase 9, Polish)

## Complexity Tracking

No constitution violations to justify.
