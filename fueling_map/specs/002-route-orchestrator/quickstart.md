# Quickstart: Validate Route Lookup and Orchestration

Run from `fueling_map/`. Contracts: [contracts/route-api.md](contracts/route-api.md). Types:
[data-model.md](data-model.md).

## Prerequisites

1. Dependencies installed with `uv sync` (adds `httpx`; dev adds `respx`, `pytest-mock`).
2. Data built: `uv run python manage.py build_data` (both SQLite databases must exist).

## Automated validation (no network)

```bash
uv run pytest tests/unit/routing tests/integration/test_route_endpoint.py
uv run ruff check . && uv run ruff format --check . && uv run mypy .
```

Expected: green. The suite stubs OSRM with `respx`; a real network call fails the test run.

## Scenarios the tests must prove

| # | Scenario | Expected |
|---|---|---|
| 1 | `st. louis, mo` and `Saint  Louis, MO` | resolve to the same CityIndex key |
| 2 | Valid pair, OSRM stubbed | 200, miles = metres / 1609.344, geometry in `(lat, lon)` order, one OSRM call, URL has `lon,lat` |
| 3 | Same request twice | second makes zero OSRM calls |
| 4 | Reverse pair | separate cache entry, one new call |
| 5 | Missing `finish`, or no comma | 400 naming the parameter |
| 6 | Unknown city | 404 echoing parsed `(city_key, state)` |
| 7 | `st. louis, mo` vs `Saint Louis, MO` as start and finish | 400 `start and finish must differ` |
| 8 | OSRM `NoRoute` | 502 with `osrm_code: NoRoute`, one call, no retry |
| 9 | OSRM timeout | 504, one call |
| 10 | Route of exactly 500 miles | 200, `stops: []`, `total_cost: 0.0`, no planner call |
| 11 | Route of 500.1 miles, no planner wired | 501 `planner_not_available` |
| 12 | Missing or empty cities DB | 503 naming `build_data` |
| 13 | 32 threads hit an unbuilt index | loader called exactly once |
| 14 | Polyline golden value | the published example string in research.md D5 decodes to `(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)` |

## Manual smoke test (optional, makes one real OSRM call)

```bash
uv run python manage.py runserver
curl 'http://127.0.0.1:8000/api/route/?start=Dallas,%20TX&finish=Denver,%20CO'
```

Repeat the same curl: the second answer must come back with no outbound call (check by running
with `OSRM_BASE_URL` pointed at an unreachable host; the cached reply still succeeds).
