---

description: "Task list for the route lookup and orchestration endpoint"
---

# Tasks: Route Lookup and Orchestration

**Input**: Design documents from `specs/002-route-orchestrator/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/route-api.md, quickstart.md

**Tests**: Included. The constitution (Principle V) requires behavior-named tests that act as the specification. Write each story's tests first and confirm they fail.

**Organization**: Grouped by user story (US1–US5 from spec.md). Paths are relative to `fueling_map/`. Each `PR` marker matches the nine-commit delivery split in plan.md: the 300-changed-line cap binds each **commit**, not the PR as a whole (constitution v2.0.0, amended 2026-10-02); a PR may bundle adjacent phases, but each phase below is sized to land as one commit.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependencies)
- **[Story]**: US1 to US5, from spec.md

## Phase 1: Setup (PR 1: `refactor(stations)` — shared normalizer)

- [X] T001 [P] Add `httpx` to runtime dependencies and `respx`, `pytest-mock` to the dev group in `pyproject.toml`; `uv sync`
- [X] T002 Create the `routing/` package (`routing/__init__.py`), plain Python, no Django import anywhere under it
- [X] T003 [P] `tests/unit/routing/test_normalize.py`: `test_state_is_trimmed_and_uppercased`, `test_city_whitespace_collapsed_and_uppercased`, `test_st_ft_mt_tokens_expand_as_whole_tokens_including_bare_mt`, `test_normalizing_an_already_normalized_pair_is_idempotent`
- [X] T004 `routing/normalize.py`: `normalize_city_key(city, state) -> tuple[str, str]` per FR-001/data-model.md `CityKey` (depends on T003)
- [X] T005 `stations/pipeline.py`: replace the local `_TOKEN_EXPANSIONS`/`_city_key` with an import of `normalize_city_key` from `routing.normalize`; keep `_display_city` for the stored display form (depends on T004)
- [X] T006 Rebuild any test fixtures or golden keys in `tests/unit/test_pipeline.py` / `tests/integration/test_build_data_command.py` affected by the new bare-`MT` expansion; add `test_stations_pipeline_and_routing_share_the_identical_normalize_function` (asserts `stations.pipeline.normalize_city_key is routing.normalize.normalize_city_key`, closing FR-002's cross-module coverage gap); rerun `uv run python manage.py build_data` and confirm the match rate is unchanged (research.md D2)
- [X] T007 Run `ruff check .`, `ruff format --check .`, `mypy .`, `pytest tests/unit/test_pipeline.py tests/unit/routing/test_normalize.py` — commit 1 green before continuing

**Checkpoint**: one shared normalizer; the data pipeline still builds with the same match rate.

---

## Phase 2: Foundational (PR 2: `feat(routing)` — errors, city index, repo)

**Purpose**: The lookup and error types every user story depends on.

- [X] T008 [P] `routing/errors.py`: `RouteError` base (carries `status: int` and a message) and subclasses `InvalidParameter` (400), `SameEndpoints` (400), `CityNotFound` (404, carries `city_key`/`state`), `OsrmRejected` (502, carries `osrm_code`), `OsrmUnavailable` (504), `CitiesDataMissing` (503, names `build_data`), `PlannerNotAvailable` (501), per data-model.md
- [X] T009 [P] `tests/unit/routing/test_city_index.py`: `test_lookup_returns_coordinates_for_known_key`, `test_missing_database_raises_CitiesDataMissing_naming_build_data`, `test_empty_table_raises_CitiesDataMissing`, `test_concurrent_first_requests_build_the_lookup_exactly_once` (quickstart #13), `test_reset_city_index_allows_rebuild_in_tests`
- [X] T010 `routing/city_index.py`: module-level `_index` + `threading.Lock`; `get_city_index(loader)` check-lock-check-build; `reset_city_index()` test helper (depends on T008, T009)
- [X] T011 [P] `api/__init__.py`, `api/apps.py` — the `api` Django app
- [X] T012 `api/repo.py`: `load_cities()` — the single ORM read, returns `(city_key, state, lat, lon)` rows from `City` (depends on T010)
- [X] T013 [P] `tests/integration/test_api_repo.py`: `test_load_cities_returns_rows_from_cities_database`, `test_load_cities_returns_empty_list_when_table_is_empty` (uses the real `City` model against a temp cities DB)
- [X] T014 Register the `api` app in `config/settings.py` `INSTALLED_APPS` (depends on T011)

**Checkpoint**: `CityIndex` builds from the DB once, thread-safe, fails loudly on missing or empty data.

---

## Phase 3: User Story 1a — OSRM client (Priority: P1, part of the P1 MVP) (PR 3: `feat(routing)` — `osrm.py`)

**Goal**: A single, injectable OSRM call that decodes the route and converts units.

**Independent Test**: quickstart scenario 14 (polyline golden value) and the `fetch_route` unit tests, no Django and no network.

### Tests for User Story 1a (write first)

- [X] T015 [P] [US1] `tests/unit/routing/test_osrm.py`: `test_decode_polyline_matches_published_example` (research.md D5 golden string)
- [X] T016 [P] [US1] `tests/unit/routing/test_osrm.py`: `test_fetch_route_sends_coordinates_as_lon_lat`, `test_fetch_route_requests_full_overview_no_steps_annotations_alternatives`, `test_fetch_route_converts_metres_to_miles`, `test_fetch_route_makes_exactly_one_call` (respx)
- [X] T017 [P] [US1] `tests/unit/routing/test_osrm.py`: `test_fetch_route_uses_3s_connect_10s_read_timeout`, `test_fetch_route_does_not_retry`, `test_non_ok_code_raises_OsrmRejected_with_code`, `test_timeout_raises_OsrmUnavailable_from_err`

### Implementation for User Story 1a

- [X] T018 [US1] `routing/osrm.py`: hand-written polyline decoder, precision 5, `(lat, lon)` in order (depends on T015)
- [X] T019 [US1] `routing/osrm.py`: `fetch_route(start_coord, finish_coord, client) -> Route` — one `httpx` GET, query string from research.md D4, raises `OsrmRejected`/`OsrmUnavailable` (depends on T016, T017, T018, T008)

**Checkpoint**: OSRM integration is fully tested in isolation; `routing/` still imports nothing from Django.

---

## Phase 4: User Story 1b — Get a route between two cities (Priority: P1) 🎯 MVP (PR 4: `feat(api)` — pipeline happy path + endpoint)

**Goal**: `GET /api/route/` resolves two "City, ST" strings and returns a real route.

**Independent Test**: quickstart scenarios 1 and 2 — a valid pair, OSRM stubbed, returns geometry, miles and one call.

### Tests for User Story 1b (write first)

- [X] T020 [P] [US1] `tests/unit/routing/test_pipeline.py`: `test_start_and_finish_are_split_on_first_comma_and_trimmed` (FR-006), `test_plan_route_resolves_start_and_finish_via_city_index`, `test_plan_route_passes_city_coordinates_to_fetch_route`, `test_plan_route_returns_geometry_in_lat_lon_order`, `test_equivalent_spellings_resolve_to_the_same_city` (quickstart #1)
- [X] T021 [P] [US1] `tests/integration/test_route_endpoint.py`: `test_valid_request_returns_200_with_miles_geometry_and_one_osrm_call`, `test_response_echoes_start_and_finish_city_state_lat_lon`

### Implementation for User Story 1b

- [X] T022 [US1] `routing/pipeline.py`: `_parse_endpoint(raw) -> tuple[str, str]` — split `start`/`finish` on the first comma, trim both halves (FR-006); this is the shared parsing step US2 (T029) builds its validation on, so it lands here, before the happy path needs it
- [X] T023 [US1] `routing/pipeline.py`: `plan_route(start, finish, cities, cache, http, planner) -> RouteResult` happy path — call `_parse_endpoint` on both ends, normalize, resolve via `CityIndex`, call `fetch_route`, build `RouteResult` (depends on T010, T019, T022)
- [X] T024 [US1] `api/views.py`: `route_view` — parse query params, call `plan_route`, serialize the success body per contracts/route-api.md; keep it under 30 lines (depends on T023)
- [X] T025 [US1] `api/urls.py`: `path("route/", route_view)`; include it from `config/urls.py` under `api/` (depends on T014, T024)
- [X] T026 [US1] `config/settings.py`: `CACHES` (LocMemCache) and `OSRM_BASE_URL` from the environment, default `https://router.project-osrm.org`

**Checkpoint**: `GET /api/route/` returns a real route for a valid city pair with exactly one OSRM call (respx-confirmed). **MVP complete.**

---

## Phase 5: User Story 2 — Clear errors for bad input and unroutable trips (Priority: P1) (PR 5: `feat(api)` — parsing and error responses)

**Goal**: Every bad-input and upstream-failure path returns its specified status and message.

**Independent Test**: quickstart scenarios 5–9.

### Tests for User Story 2 (write first)

- [ ] T027 [P] [US2] `tests/unit/routing/test_pipeline.py`: `test_missing_or_unsplittable_param_raises_InvalidParameter`, `test_equal_normalized_endpoints_raise_SameEndpoints`, `test_unknown_city_raises_CityNotFound_with_parsed_key`
- [ ] T028 [P] [US2] `tests/integration/test_route_endpoint.py`: `test_missing_start_returns_400_naming_parameter`, `test_value_with_no_comma_returns_400`, `test_unknown_city_returns_404_echoing_parsed_city_and_state`, `test_identical_endpoints_returns_400_start_and_finish_must_differ`, `test_osrm_no_route_returns_502_with_osrm_code`, `test_osrm_timeout_returns_504`

### Implementation for User Story 2

- [ ] T029 [US2] `routing/pipeline.py`: on top of `_parse_endpoint` (T022), raise `InvalidParameter` when a half is missing or there is no comma, `SameEndpoints` when the normalized start equals finish, `CityNotFound` when the key is absent from `CityIndex` — all before any OSRM call (depends on T022, T023)
- [ ] T030 [US2] `api/views.py`: one `except RouteError` handler building `{"error", "detail", ...}` per contracts/route-api.md's status table (depends on T024, T029)

**Checkpoint**: every error class in the contract returns its documented status and body.

---

## Phase 6: User Story 3 — Repeat requests are served without the routing service (Priority: P2) (PR 6: `feat(api)` — route cache)

**Goal**: A 24-hour, direction-sensitive cache; zero OSRM calls on a hit.

**Independent Test**: quickstart scenarios 3 and 4.

### Tests for User Story 3 (write first)

- [ ] T031 [P] [US3] `tests/unit/routing/test_pipeline.py`: `test_second_identical_request_makes_zero_osrm_calls`, `test_reverse_direction_is_a_separate_cache_entry`, `test_equivalent_spellings_share_one_cache_entry`, `test_expired_cache_entry_is_refetched`
- [ ] T032 [P] [US3] `tests/integration/test_route_endpoint.py`: `test_repeated_request_hits_cache_and_makes_no_osrm_call`, `test_reverse_pair_makes_a_new_osrm_call`

### Implementation for User Story 3

- [ ] T033 [US3] `routing/pipeline.py`: wrap `fetch_route` with the injected two-method cache protocol (`get`/`set`), key `route:{start_key}:{start_state}:{finish_key}:{finish_state}`, TTL 86400 s (depends on T029)
- [ ] T034 [US3] `api/views.py`: inject Django's `cache` (configured LocMemCache) into `plan_route` at the view boundary (depends on T026, T033)

**Checkpoint**: repeated and reversed requests behave exactly per quickstart #3/#4.

---

## Phase 7: User Story 4 — Short trips need no fuel stops (Priority: P2) (PR 7: `feat(api)` — short-circuit and planner seam)

**Goal**: ≤500 mi short-circuits to `stops: []`, `total_cost: 0.0`; >500 mi reaches the planner seam.

**Independent Test**: quickstart scenarios 10 and 11.

### Tests for User Story 4 (write first)

- [ ] T035 [P] [US4] `tests/unit/routing/test_pipeline.py`: `test_route_of_exactly_500_miles_returns_no_stops_and_zero_cost`, `test_route_over_500_miles_calls_the_injected_planner`, `test_route_over_500_miles_without_planner_raises_PlannerNotAvailable`
- [ ] T036 [P] [US4] `tests/integration/test_route_endpoint.py`: `test_500_mile_route_returns_empty_stops_and_zero_cost_with_no_planner_call`, `test_over_500_mile_route_returns_501_planner_not_available`

### Implementation for User Story 4

- [ ] T037 [US4] `routing/pipeline.py`: the 500-mile short-circuit and the injected-`planner` seam building `RouteResult` per data-model.md / research.md D8 (depends on T033)
- [ ] T038 [US4] `api/views.py`: include `stops`/`total_cost` in the success body; let `PlannerNotAvailable` flow through the existing error handler (depends on T030, T037)

**Checkpoint**: threshold and planner seam behave exactly per quickstart #10/#11.

---

## Phase 8: User Story 5 — Fail loudly when data has not been built (Priority: P2) (PR 8: `test(api)` — fail-loudly proof)

**Goal**: Prove, at the HTTP layer, the Foundational `CityIndex` guarantee from Phase 2.

**Independent Test**: quickstart scenario 12.

- [ ] T039 [US5] `tests/integration/test_route_endpoint.py`: `test_missing_cities_database_returns_503_naming_build_data`, `test_empty_cities_table_returns_503`
- [ ] T040 [US5] Wire `api/repo.py::load_cities` as the loader passed to `get_city_index` at the view/pipeline boundary; confirm `CitiesDataMissing` reaches the view's error handler unchanged (depends on T012, T030)

**Checkpoint**: an un-built or empty data store fails every request with one unambiguous, tested message.

---

## Phase 9: Polish & Cross-Cutting (PR 9: `chore` — polish)

- [ ] T041 [P] Write the README note in `fueling_map/README.md`: the cache is per-worker and lost on restart (FR-016), and the 500-mile short-circuit is the full-tank range
- [ ] T042 [P] Add a no-network guard for `tests/unit/routing/` and `tests/integration/test_route_endpoint.py` (block real sockets; same pattern as the 001 pipeline's no-network test) confirming FR-019
- [ ] T043 Run `ruff check .`, `ruff format --check .`, `mypy .`, `pytest` — full suite green
- [ ] T044 Run `quickstart.md` end to end, including the manual smoke test; record actual cached/uncached latencies against SC-005 and confirm SC-001–SC-006 in the PR description

---

## Dependencies & Execution Order

- Phase 1 (PR 1) then Phase 2 (PR 2) block everything else; Phase 2 also blocks on Phase 1 only through `routing/normalize.py` existing.
- Phase 3 (US1a, PR 3) depends on Phase 2 (`routing/errors.py`) and can be built in parallel with nothing else — it has no Django dependency.
- Phase 4 (US1b, PR 4) is the MVP checkpoint: depends on Phase 2 (city index, repo) and Phase 3 (OSRM client). Its own `_parse_endpoint` step (T022) lands here precisely because the happy path cannot resolve a city without it — US2 (Phase 5) only adds validation on top of it.
- Phases 5–8 (US2–US5, PRs 5–8) all depend on Phase 4's `plan_route`/`route_view` and build on each other in the same two files (`routing/pipeline.py`, `api/views.py`), so they are sequential even though the user stories are independently testable once each phase lands.
- Phase 9 (PR 9, Polish) depends on all desired user stories being complete.

### Parallel example (Phase 2, Foundational)

Run T008, T009, T011, T013 together (separate files); then T010, T012, T014 in dependency order.

### Parallel example (Phase 3, US1a)

Run T015, T016, T017 together (one test file, separate test functions); then T018, T019 in order.

## Implementation Strategy

1. **MVP**: Phases 1–4 (PRs 1–4): a working `GET /api/route/` that resolves a known city pair to a real, OSRM-backed route, including the comma-split parsing it needs (T022).
2. Add US2 (errors), US3 (cache), US4 (short-trip/planner seam), US5 (fail-loudly proof) as PRs 5–8, in priority order.
3. Validate with quickstart.md; every commit/PR states what changed, why, how it was tested, and the rejected design alternative (research.md D1/D2 already record those for PRs 1–2).
