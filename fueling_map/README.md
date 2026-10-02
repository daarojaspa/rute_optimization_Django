# Fueling Map

API that plans cost-effective fuel stops along a US route. This part of the project builds the
station data the planner reads and resolves routes between two cities.

## Build the station data

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py migrate --database=cities
uv run python manage.py build_data \
    --fuel-csv ../fuel-prices-for-be-assessment.csv --cities-csv ../us_cities.csv
```

`build_data` is offline. It cleans both CSVs, deduplicates stations by OPIS Truckstop ID
(lowest price wins), attaches coordinates, writes `stations_locations.sqlite3` (table
`stations`) and `cities.sqlite3` (table `us_cities`), and lists stations it could not place in
`unmatched.csv`. It exits non-zero and writes nothing to the databases when the match rate is
below `--fail-under` (default 0.95). Details: `specs/001-build-data-pipeline/`.

## Accuracy: coordinates are approximations

The fuel file has no coordinates, so each station gets the coordinates of its **city**, not of
the truck stop. Expect an error of a few miles per station, more in large cities. To keep
stations in one city from sharing a single point, all but one station per city (the lowest OPIS
ID) is moved by a deterministic offset of at most 5 miles. This is a spreading heuristic, not a
real location. Given a 500-mile range this is acceptable, but fuel costs the API reports are
**estimates, not quotes**.

## Route endpoint

```
GET /api/route/?start=City,%20ST&finish=City,%20ST
```

Resolves both cities against the prepared `cities` database, fetches the driving route from
OSRM (one call per uncached request), and returns the route's geometry, total miles, and the
cost-optimal fuel stops. Trips of 500 miles or less (the full-tank range: 50 gal x 10 mpg) need
no fill-up and return `"stops": []`, `"total_cost": 0.0` without involving the fuel-stop
algorithm at all. Details: `specs/002-route-orchestrator/`.

**The route cache is per-worker and lost on restart.** Repeated requests for the same city pair
(in the same direction) are served from an in-memory cache for 24 hours, so the free OSRM API is
called at most once per uncached request. That cache lives in the Django worker process's
memory (`LocMemCache`): it is not shared between workers and does not survive a restart.
Production would use a shared store (e.g. Redis) instead; acceptable here, since this is an MVP.

## Development

```bash
uv run pytest && uv run ruff check . && uv run mypy .
```
