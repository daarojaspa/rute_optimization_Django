# Research: Route Lookup and Orchestration

No `NEEDS CLARIFICATION` remained after the spec. The decisions below resolve design forks and
integration details.

## D1. Module structure (human-selected: A)

- **Decision**: Design A. A pure `routing/` package (`city_index`, `osrm`, `pipeline`, `errors`,
  `normalize`) with injected cache and city loader, plus a thin `api/` view and one ORM function
  in `api/repo.py`.
- **Rationale**: Constitution Principle I; routing logic is unit-testable in milliseconds without
  a database or Django settings; the later algorithm modules join `routing/` unchanged.
- **Alternatives considered**: Design B, one `api/route_service.py` importing Django cache and ORM
  directly. Fewer files but needs Django to test and would have to be split later.

## D2. Normalizer home (human-selected: `routing/normalize.py`)

- **Decision**: One `normalize_city_key` in `routing/normalize.py`; `stations/pipeline.py` imports
  it in a separate PR that also adds the bare `MT` token and rebuilds the stored keys.
- **Rationale**: A single definition removes the divergence risk (every affected city would 404
  silently). Today `stations/pipeline.py` has its own `_TOKEN_EXPANSIONS` without bare `MT`.
- **Alternatives considered**: `stations/normalize.py`, importable by both; rejected because
  `routing/` would depend on a Django app package.

## D3. CityIndex construction

- **Decision**: Module-level `_index` and `threading.Lock` in `routing/city_index.py`;
  `get_city_index(loader)` checks, locks, checks again, builds. The loader is a callable returning
  `(city_key, state, lat, lon)` rows, supplied by `api/repo.py`. An empty result or a missing
  database raises `CitiesDataMissing` naming `build_data`. A `reset_city_index()` helper exists for
  tests.
- **Rationale**: Read-only after construction, so no Django cache entry; check-lock-check prevents
  double builds; failing on empty prevents 404s for every city.
- **Alternatives considered**: Building at app start (`AppConfig.ready`): breaks tests and
  `manage.py` commands that run before `build_data`.

## D4. OSRM client

- **Decision**: `httpx.Client` passed into `fetch_route`; timeout `httpx.Timeout(10.0, connect=3.0)`;
  one `GET`; query `overview=full&geometries=polyline&steps=false&annotations=false&alternatives=false`;
  coordinates as `lon,lat;lon,lat`. Base URL from `OSRM_BASE_URL` (default
  `https://router.project-osrm.org`). `code != "Ok"` raises `OsrmRejected(code)`; `httpx.TimeoutException`
  and `httpx.TransportError` raise `OsrmUnavailable` `from err`. No retry loop exists at all.
- **Rationale**: The call budget counts calls; an injectable client makes respx assertions on call
  count trivial.
- **Alternatives considered**: `requests`/`urllib`: no split timeouts or clean mock (urllib), extra
  dependency not in the constitution (requests).

## D5. Polyline decoding

- **Decision**: Hand-written decoder, precision 5, returning `(lat, lon)` in order.
- **Rationale**: About 15 lines with a golden test from the published encoding example
  (`_p~iF~ps|U_ulLnnqC_mqNvxq`@` decodes to `(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)`).
  Avoids a dependency the constitution asks us to justify.
- **Alternatives considered**: `polyline` package.

## D6. Route cache

- **Decision**: Django `LocMemCache`, key `route:{start_key}:{start_state}:{finish_key}:{finish_state}`,
  value `Route(geometry, total_miles)`, TTL 86400 s. `pipeline.plan_route` receives a two-method
  protocol (`get`, `set`) so `routing/` never imports Django. Direction-sensitive keys.
- **Rationale**: Matches the brief; per-worker and lost on restart, stated in README and Loom note;
  production would use Redis.
- **Alternatives considered**: `functools.lru_cache` (no TTL); process dict (reimplements TTL).

## D7. Error to HTTP mapping

- **Decision**: `routing/errors.py` defines `RouteError` subclasses carrying `status` and a
  message: `InvalidParameter` 400, `SameEndpoints` 400, `CityNotFound` 404, `OsrmRejected` 502
  (with `osrm_code`), `OsrmUnavailable` 504, `CitiesDataMissing` 503, `PlannerNotAvailable` 501.
  One `except RouteError` in the view builds the JSON body.
- **Rationale**: Principle IV, one handler high in the stack; status carried as plain data keeps
  `routing/` free of Django.

## D8. Handoff and the planner boundary

- **Decision**: `plan_route` returns `RouteResult(route, start_coord, finish_coord, stops, total_cost)`.
  At 500 miles or less it returns `stops=[]`, `total_cost=0.0` without calling a planner. Above 500
  it calls an injected `planner(route_handoff)`; until the algorithm feature exists none is wired,
  so it raises `PlannerNotAvailable` (501) rather than returning a fake plan.
- **Rationale**: The algorithm is out of scope, but the seam is explicit and testable now. The
  500-mile threshold is the full-tank range (50 gal x 10 mpg).
- **Alternatives considered**: Returning an empty plan for long trips, which would present a
  wrong answer as a success.

## D9. Parsing

- **Decision**: Split on the first comma, strip both halves; either half empty or no comma is 400
  naming the parameter; normalize; look up; reject equal keys.
- **Rationale**: Straight from the spec; only the first comma splits, so "City, ST" is the only
  accepted shape.
