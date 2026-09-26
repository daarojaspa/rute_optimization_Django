# Spotter — Fuel-Stop Route Planner

An API that takes a **start** and a **finish** city in the USA and returns the route map, the
**cost-optimal fuel stops** along it, the fuel bought and money spent at each stop, and the total
fuel bill. Latency is a first-class requirement: the expensive work (cleaning, geocoding, indexing)
happens offline or once per process, never per request.

> **Status: design-complete, implementation not started.** The constitution, architecture, first
> feature spec and raw data exploration exist. No Django project, routing code or tests exist yet.
> See [Project status](#project-status).

## Vehicle model

| Parameter | Value |
|---|---|
| Tank | 50 gal, starts **full** (that initial fuel is not billed) |
| Efficiency | 10 mpg |
| Minimum in tank | 1 gal, never empty |
| Detour reserve | `offset_mi × detour_legs × safety_factor / mpg` (10 mi × 2 × 1.5 / 10 = 3 gal) |
| Usable range | `(tank − reserve − minimum) × mpg` → **460 mi** between fill-ups with the defaults |

Detour miles are covered by the reserve and are excluded from consumption and from fuel billed.

## Fuel policy (look-ahead greedy)

At each station buy only enough to reach the **nearest cheaper** station within usable range. If none
is in range, fill the tank and drive to the cheapest reachable station. Ties break by lower route
mile, then lower detour, then lower OPIS ID (deterministic). If no station is within range the
request fails with **HTTP 422** and a machine-readable reason. The planner is to be validated against
exhaustive search on small random instances. Full rules: [constitution](fueling_map/.specify/memory/constitution.md).

## Architecture (C4)

Legend: 🟩 built (document/spec/data exists) · 🟨 specified, code not written · ⬜ planned, not yet specified.
Mermaid C4 renders natively on GitHub.

### Level 1 — System Context

```mermaid
C4Context
    title Spotter — System Context

    Person(driver, "Client / Driver", "Requests a route between two US cities (Postman, Leaflet page)")
    System(spotter, "Spotter API", "Returns route map, optimal fuel stops, fuel and cost per stop, total cost. ⬜ NOT BUILT")
    System_Ext(osrm, "OSRM Public API", "Free routing service: route geometry and distance. 1 call per request, 3 max")
    SystemDb_Ext(fuelcsv, "Fuel prices CSV", "8,151 truckstop rows (OPIS ID, name, city, state, price). 🟩 PROVIDED")
    SystemDb_Ext(citiescsv, "us_cities.csv", "29,880 US cities with lat/lon. 🟩 PROVIDED")

    Rel(driver, spotter, "GET route?start=&end=", "HTTPS / JSON")
    Rel(spotter, osrm, "Fetches route geometry", "HTTPS / httpx")
    Rel(fuelcsv, spotter, "Loaded offline (build_data)")
    Rel(citiescsv, spotter, "Loaded offline (build_data)")

    UpdateElementStyle(spotter, $bgColor="#c9a227", $fontColor="#000000")
    UpdateElementStyle(fuelcsv, $bgColor="#2e7d32", $fontColor="#ffffff")
    UpdateElementStyle(citiescsv, $bgColor="#2e7d32", $fontColor="#ffffff")
```

### Level 2 — Containers

```mermaid
C4Container
    title Spotter — Containers

    Person(driver, "Client", "Postman / optional static Leaflet page")

    System_Boundary(spotter, "Spotter (Django + uvicorn, Docker)") {
        Container(api, "API layer", "Django view + serializers", "Thin: parse → call pipeline → serialize. ~30 lines max. ⬜ PLANNED")
        Container(routing, "Routing core", "Plain Python, zero Django imports", "OSRM client, corridor filter, planner, pricing, pipeline orchestrator. ⬜ PLANNED")
        Container(indexes, "In-memory indexes", "dict + numpy + KD-tree", "CityIndex (city,state)→coords; StationIndex (arrays + KD-tree). Built once per process. ⬜ PLANNED")
        Container(build, "build_data command", "Django management command (stations app)", "Offline: clean, dedupe, geocode by city, quality gate, write SQLite. 🟨 SPECIFIED (spec.md)")
        ContainerDb(stationsdb, "stations_locations", "SQLite", "opis_id, name, address, city, state, latitude, longitude, retail_price. 🟨 SPECIFIED")
        ContainerDb(citiesdb, "cities DB", "SQLite", "Deduplicated cities with coordinates. 🟨 SPECIFIED")
    }

    System_Ext(osrm, "OSRM API", "Route geometry")
    SystemDb_Ext(csv, "Raw CSVs", "fuel prices + us_cities. 🟩 PROVIDED")

    Rel(driver, api, "Start & end city", "JSON/HTTPS")
    Rel(api, routing, "Calls pipeline")
    Rel(api, indexes, "Repository function loads arrays at startup")
    Rel(routing, indexes, "Reads")
    Rel(routing, osrm, "1 call per request", "httpx")
    Rel(csv, build, "Reads")
    Rel(build, stationsdb, "Truncate & reload")
    Rel(build, citiesdb, "Truncate & reload")
    Rel(indexes, stationsdb, "Loaded once from")
    Rel(indexes, citiesdb, "Loaded once from")

    UpdateElementStyle(api, $bgColor="#6b6b6b", $fontColor="#ffffff")
    UpdateElementStyle(routing, $bgColor="#6b6b6b", $fontColor="#ffffff")
    UpdateElementStyle(indexes, $bgColor="#6b6b6b", $fontColor="#ffffff")
    UpdateElementStyle(build, $bgColor="#c9a227", $fontColor="#000000")
    UpdateElementStyle(stationsdb, $bgColor="#c9a227", $fontColor="#000000")
    UpdateElementStyle(citiesdb, $bgColor="#c9a227", $fontColor="#000000")
    UpdateElementStyle(csv, $bgColor="#2e7d32", $fontColor="#ffffff")
```

### Level 3 — Components of the Routing core

Request flow: `views → pipeline → (city lookup) → osrm ‖ prefilter → corridor → planner → pricing → serializer`.

```mermaid
C4Component
    title Spotter — Routing core components (routing/)

    Container(api, "API layer", "views.py + serializers.py", "Parse → pipeline → serialize")
    Container(indexes, "Indexes", "CityIndex / StationIndex", "In-memory, built once")
    System_Ext(osrm, "OSRM API", "Route geometry")

    Container_Boundary(routing, "routing/ (pure Python, no ORM)") {
        Component(pipeline, "pipeline.py", "Orchestrator", "Resolves cities, runs 2→3→4→5→6, returns a dataclass. ⬜ PLANNED")
        Component(osrmc, "osrm.py", "httpx client", "Single call: geometry + distance. Mocked with respx in tests. ⬜ PLANNED")
        Component(prefilter, "prefilter", "Bounding filter", "Drops stations obviously off route (NY→NH needs no Texas stop). ⬜ PLANNED")
        Component(corridor, "corridor.py", "Projection", "Per station: nearest route mile, offset, detour length; keeps those within the offset corridor. ⬜ PLANNED")
        Component(planner, "planner.py", "Look-ahead greedy", "Chooses stops and fuel per stop; 422 on infeasible. Design draft only in v1.py. 🟨 DRAFT")
        Component(pricing, "pricing.py", "Cost calculation", "gallons × price per stop, total bill; rounds only at serialization. ⬜ PLANNED")
    }

    Rel(api, pipeline, "start, end, station arrays")
    Rel(pipeline, indexes, "City → coords; station candidates")
    Rel(pipeline, osrmc, "Route request")
    Rel(osrmc, osrm, "HTTPS")
    Rel(pipeline, prefilter, "Candidates")
    Rel(prefilter, corridor, "Nearby stations")
    Rel(corridor, planner, "Stations with price, mile, offset")
    Rel(planner, pricing, "Stops + fuel")
    Rel(pricing, api, "Result dataclass")

    UpdateElementStyle(planner, $bgColor="#c9a227", $fontColor="#000000")
    UpdateElementStyle(pipeline, $bgColor="#6b6b6b", $fontColor="#ffffff")
    UpdateElementStyle(osrmc, $bgColor="#6b6b6b", $fontColor="#ffffff")
    UpdateElementStyle(prefilter, $bgColor="#6b6b6b", $fontColor="#ffffff")
    UpdateElementStyle(corridor, $bgColor="#6b6b6b", $fontColor="#ffffff")
    UpdateElementStyle(pricing, $bgColor="#6b6b6b", $fontColor="#ffffff")
```

## Project status

| Area | State | Where |
|---|---|---|
| Constitution v1.0.0 (principles, correctness rules, stack, governance) | ✅ Done | [`fueling_map/.specify/memory/constitution.md`](fueling_map/.specify/memory/constitution.md), draft in `drafts/constitution.md` |
| Architecture and data flow | ✅ Done | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Agent safety rules and human gates | ✅ Done | [`CLAUDE.md`](CLAUDE.md) |
| Spec Kit scaffolding (skills, templates) | ✅ Done | `.claude/skills/`, `fueling_map/.specify/` |
| Raw data exploration | ✅ Done | `exploration.ipynb` |
| Feature 001 spec: `build_data` pipeline (4 user stories, 17 requirements, clarified) | ✅ Spec written | [`fueling_map/specs/001-build-data-pipeline/spec.md`](fueling_map/specs/001-build-data-pipeline/spec.md) |
| Feature 001 plan | 🟡 Unfilled template | `.../plan.md` |
| Feature 001 tasks | ❌ Not generated | run `/speckit-tasks` |
| Django project (`config/`, `stations/`, `api/`) | ❌ Not started | no code yet |
| `build_data` command and SQLite tables | ❌ Not started | |
| Routing core: OSRM client, corridor, planner, pricing, pipeline | ❌ Not started | greedy sketch in `v1.py` is non-runnable pseudocode |
| CityIndex / StationIndex | ❌ Not started | |
| API endpoint and serializers | ❌ Not started | |
| Tests (pytest, respx, brute-force planner check), ruff, mypy | ❌ Not started | |
| CI (GitHub Actions), Docker, Sentry | ❌ Not started | |
| Leaflet map page | ❌ Optional | |
| Postman check and demo video | ❌ Not started | |

### Suggested next steps

1. Fill `plan.md` for feature 001 (`/speckit-plan`), then `/speckit-tasks`.
2. Implement `build_data` in PRs of at most 300 lines.
3. Build the pure routing core against in-memory arrays (no DB needed to test it).
4. Wire the thin API view, then Docker and CI.

## Known limitations

- **City-level coordinates.** Stations are located at their city's coordinates, not their real
  position. To avoid stacking, all but one station per city are shifted deterministically by at most
  5 miles. This is a spreading heuristic, not a real location, so **reported costs are estimates, not
  quotes**.
- Names must come from `us_cities.csv`; no fuzzy matching (a misspelled city is reported in
  `unmatched.csv`). Cities in the 50 states plus DC only.
- Open items: exact terminal-leg billing (`TODO(TERMINAL_LEG)` in the constitution) and the CI config.

## Planned stack

Django (latest) · uv · uvicorn · httpx · SQLite · pytest, pytest-mock, respx · ruff, mypy · Docker · Sentry · GitHub Actions. OSRM supplies route geometry
([docs](https://project-osrm.org/docs/v5.24.0/api/#route-service)). No auth (MVP).

## Data

| File | Rows | Columns |
|---|---|---|
| `fuel-prices-for-be-assessment.csv` | ~8,150 | OPIS Truckstop ID, Truckstop Name, Address, City, State, Rack ID, Retail Price |
| `us_cities.csv` | ~29,880 | ID, STATE_CODE, STATE_NAME, CITY, COUNTY, LATITUDE, LONGITUDE |

## Working agreements

Spec Kit flow (specify → plan → tasks → implement); one logical change per PR, ≤300 lines;
conventional commits `type(scope): summary`; green ruff/mypy/pytest before review; the human approves
every push and merge. Details in the constitution and `CLAUDE.md`.
