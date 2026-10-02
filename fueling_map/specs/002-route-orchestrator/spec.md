# Feature Specification: Route Lookup and Orchestration

**Feature Branch**: `orchestrator_and_api`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Lookup layer and route orchestrator. A request gives a start and a finish as 'City, ST'. The system resolves both to coordinates using the prepared cities data, obtains the driving route from the free routing service with exactly one call, caches it, and hands route geometry, total miles and both endpoint coordinates to the fuel-stop algorithm. Depends on the data-preparation feature having been run. Out of scope: station indexing, corridor matching, fuel-stop selection and cost — all belong to the algorithm spec."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Get a route between two cities (Priority: P1)

A caller sends a start and a finish, each written "City, ST", to the route endpoint. The system finds both cities, asks the routing service for the driving route, and returns a route ready for fuel planning: its shape in travel order, its length in miles, and the two endpoint coordinates.

**Why this priority**: Every fuel plan starts from a route. Without a resolved, correctly ordered route nothing downstream can run.

**Independent Test**: Request a route between two known lower-48 cities with the routing service stubbed; confirm the result carries geometry in travel order, total miles converted from metres, and both coordinates, and that exactly one routing call was made.

**Acceptance Scenarios**:

1. **Given** the prepared data exists, **When** a caller requests a route from "Dallas, TX" to "Denver, CO", **Then** the system returns the route geometry (latitude/longitude pairs in travel order), total miles, and the start and finish coordinates.
2. **Given** a city written with irregular spacing, lowercase, or abbreviated tokens ("st. louis", "Ft.  Worth"), **When** it is used as start or finish, **Then** it resolves to the same city as its spelled-out form ("SAINT LOUIS", "FORT WORTH").
3. **Given** a route request, **When** the routing service is called, **Then** the coordinates are sent longitude first, the full-detail route shape is requested, and only one call is made.
4. **Given** the routing service reports distance in metres, **When** the route is returned, **Then** the distance is in miles (metres / 1609.344).

---

### User Story 2 - Clear errors for bad input and unroutable trips (Priority: P1)

A caller who sends a malformed request, an unknown city, identical endpoints, or a trip that cannot be driven receives a specific, actionable error rather than a wrong route or a generic failure.

**Why this priority**: A reversed or wrong coordinate yields a plausible-looking but wrong route; explicit rejection of bad input is what keeps results trustworthy.

**Independent Test**: Send each bad request in turn and confirm the status code and the message content match the table below.

**Acceptance Scenarios**:

1. **Given** a request missing `start` or `finish`, or a value with no comma, **When** it is sent, **Then** the response is 400 and names the offending parameter.
2. **Given** a well-formed city that is absent from the prepared cities, **When** it is sent, **Then** the response is 404 and echoes the normalized city and state that were looked up.
3. **Given** start and finish that normalize to the same city, **When** sent, **Then** the response is 400 with the message "start and finish must differ".
4. **Given** the routing service answers with a non-success code (for example no route between the lower 48 and Alaska, Hawaii or Puerto Rico), **When** the route is requested, **Then** the response is 502 and passes the routing service's code through.
5. **Given** the routing service is slow or unreachable, **When** the timeouts elapse, **Then** the request fails with a clear upstream error and no retry is attempted.

---

### User Story 3 - Repeat requests are served without the routing service (Priority: P2)

A caller repeats a request for the same city pair. The system answers from memory with no routing call, keeping latency low and staying within the routing service's usage limits.

**Why this priority**: Latency is a first-class requirement and the free routing service must not be called often, but the first uncached request already delivers the core value.

**Independent Test**: Make the same request twice with the routing service stubbed and confirm one call total; make the same request with differently written but equivalent city names and confirm still one call.

**Acceptance Scenarios**:

1. **Given** a route was computed within the last 24 hours, **When** the same start/finish pair is requested (however spelled), **Then** zero routing calls are made and the result is identical.
2. **Given** a cached route is older than 24 hours, **When** requested again, **Then** it is fetched afresh.
3. **Given** the same pair in the reverse direction, **When** requested, **Then** it is treated as a different route (different cache entry).

---

### User Story 4 - Short trips need no fuel stops (Priority: P2)

A caller requests a trip of 500 miles or less. Because the vehicle departs with a full tank, no fill-up is needed: the hand-off to the algorithm short-circuits to an empty stop list and a total cost of 0.0.

**Why this priority**: It is a defined boundary in the planner's contract, but the main value lies in longer trips.

**Independent Test**: Stub a route of exactly 500 miles and one of 500.1 miles; confirm the first returns no stops and 0.0 cost, and the second proceeds to the algorithm.

**Acceptance Scenarios**:

1. **Given** a route of 500 miles or less, **When** planning is requested, **Then** the stop list is empty and the total cost is 0.0.
2. **Given** a route over 500 miles, **When** planning is requested, **Then** the route hand-off is passed to the fuel-stop algorithm.

---

### User Story 5 - Fail loudly when data has not been built (Priority: P2)

An operator starts the service without having run the data build. The first request fails with a message that names the data build as the fix, rather than returning misleading "city not found" answers for every city.

**Why this priority**: An empty lookup would make every request 404 with no hint of the real cause.

**Independent Test**: Point the service at a missing or empty cities database and confirm the first request fails with a message naming the data-build command.

**Acceptance Scenarios**:

1. **Given** the cities database file is absent, **When** the first request arrives, **Then** it fails with a message naming the data build as the fix.
2. **Given** the cities table is empty, **When** the first request arrives, **Then** the same failure occurs; an empty lookup is never used.
3. **Given** many simultaneous first requests, **When** the lookup is loaded, **Then** it is built once only and every request sees the complete lookup.

---

### Edge Cases

- City names with multiple internal spaces, trailing whitespace, lowercase state codes, or "ST."/"FT."/"MT." tokens must normalize to the same key as their spelled-out forms.
- A comma inside the state half, or extra commas: only the first comma splits city from state.
- Start and finish that differ only in spelling (for example "St. Louis, MO" and "Saint Louis, mo") are the same city and are rejected as identical.
- AK, HI and PR are valid city keys but not drivable from the lower 48; the routing service's no-route answer becomes a 502, not a 404.
- A route of exactly 500 miles counts as needing no fuel stops.
- The routing service returns geometry as an encoded string; a malformed or empty route list must not crash the request silently.
- The cache is per worker process and empty after a restart; behavior must be correct with a cold cache.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single shared function that normalizes a (city, state) pair into a lookup key: state trimmed and uppercased; city trimmed, internal whitespace collapsed, uppercased, with `ST.`/`ST` → `SAINT`, `FT.`/`FT` → `FORT`, `MT.`/`MT` → `MOUNT` expanded as whole tokens.
- **FR-002**: The data-preparation feature and the request path MUST use that same normalizer, so a city that exists in the prepared data can never fail to resolve because of divergent rules.
- **FR-003**: The system MUST build an in-memory city lookup, keyed by (normalized city, state) and yielding (latitude, longitude), from the prepared cities database, read once, lazily on the first request and shared for the life of the process.
- **FR-004**: Concurrent first requests MUST NOT build the lookup more than once, and no request may observe a partially built lookup.
- **FR-005**: If the cities database is absent or the cities table is empty, the first request MUST fail with a message naming the data-build command as the fix; the system MUST never serve from an empty lookup.
- **FR-006**: The system MUST expose `GET /api/route/` taking `start` and `finish`, each "City, ST", split on the first comma with both halves trimmed.
- **FR-007**: A missing or unsplittable `start` or `finish` MUST yield 400 naming the offending parameter.
- **FR-008**: A city key not present in the lookup MUST yield 404 echoing the normalized city and state.
- **FR-009**: Start and finish that are equal after normalization MUST yield 400 with the message "start and finish must differ".
- **FR-010**: Each uncached request MUST make exactly one call to the routing service, requesting driving directions with coordinates in longitude,latitude order, full-detail route shape, and no steps, annotations or alternatives.
- **FR-011**: The routing call MUST use a 3-second connect timeout and a 10-second read timeout and MUST NOT be retried.
- **FR-012**: A non-success routing code MUST yield 502 carrying that code; an unreachable or timed-out routing service MUST yield a distinct upstream-failure response.
- **FR-013**: The route distance MUST be converted from metres to miles by dividing by 1609.344.
- **FR-014**: The encoded route shape MUST be decoded (5-digit precision) into (latitude, longitude) pairs in route order.
- **FR-015**: The system MUST cache each computed route (decoded geometry and total miles) for 24 hours, keyed by the normalized start and finish, direction-sensitive; a cache hit MUST make zero routing calls.
- **FR-016**: The cache MUST be process-local (per worker, lost on restart); the README MUST say so and note that production would use a shared store.
- **FR-017**: The orchestrator MUST hand the fuel-stop algorithm the geometry, total miles, start coordinate and finish coordinate.
- **FR-018**: When total miles is 500 or less, the orchestrator MUST return an empty stop list and a total cost of 0.0 without invoking the algorithm.
- **FR-019**: Tests MUST NOT call the real routing service; it is stubbed at the network boundary.

### Key Entities

- **City lookup**: Read-only mapping from (normalized city, state) to a coordinate pair; built once per process from the prepared cities data.
- **Route request**: A start and finish pair, each city and state, after normalization.
- **Route**: Ordered latitude/longitude geometry plus total miles; cached per normalized start/finish pair.
- **Planning hand-off**: Geometry, total miles, start coordinate and finish coordinate passed to the fuel-stop algorithm.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A repeated route request is answered with zero calls to the routing service in 100% of cases within the 24-hour window.
- **SC-002**: Any single request causes at most one routing call, verified across all success and error paths.
- **SC-003**: 100% of cities in the prepared data resolve when written in their stored form, and equivalent spellings (case, spacing, ST./FT./MT.) resolve to the same city.
- **SC-004**: Every invalid request class (missing parameter, unknown city, identical endpoints, no route, missing data) returns its specified status and a message that identifies the cause without reading logs.
- **SC-005**: A cached route is served in under 50 ms; an uncached route adds no more than the routing service's own response time plus 100 ms.
- **SC-006**: Routes of 500 miles or less return with an empty stop list and zero cost in 100% of cases.

## Assumptions

- The data-preparation feature (001) has been run, so both prepared databases exist before the first request.
- Station indexing, corridor matching, fuel-stop selection and cost are out of scope (algorithm spec).
- `start == finish` after normalization is rejected as 400 (a chosen default, not specified by the brief).
- The tank starts full and only fuel purchased en route is billed, so trips of 500 miles or less cost 0.0 (a chosen default; pricing consumed fuel would change the algorithm's contract). The 500-mile figure is the full-tank range (50 gal × 10 mpg); it differs from the 460-mile usable range between fill-ups in the constitution because the algorithm's reserve does not apply to a trip with no stops.
- **Existing-code divergence**: the data-preparation feature currently has its own normalizer inside its pipeline module, and its bare `MT` token is not expanded. Adopting one shared normalizer (FR-001, FR-002) requires that pipeline to import it and its stored keys to be rebuilt; this is a separate, reviewable change from the request path.
- Authentication is out of scope; the endpoint is open. Only US cities in the prepared data are supported.
- The free public routing service is used; per-worker in-memory caching is acceptable for the MVP.
