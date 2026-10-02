# Data Model: Route Lookup and Orchestration

No new persistent tables. Everything below is in memory (plain Python dataclasses and one dict).
Coordinates are decimal degrees `(lat, lon)`; distances are miles; OSRM distances arrive in metres.

## CityKey

`tuple[str, str]` = `(city_key, state)`, produced only by `normalize_city_key(city, state)`.

- `state`: trimmed, uppercased.
- `city_key`: trimmed, internal whitespace collapsed, uppercased, whole tokens `ST.`/`ST` to
  `SAINT`, `FT.`/`FT` to `FORT`, `MT.`/`MT` to `MOUNT`.
- Pure and idempotent: normalizing an already normalized pair returns it unchanged.

## CityIndex

`dict[CityKey, tuple[float, float]]` mapping to `(lat, lon)`.

- Source: `City` rows in the `cities` database (`city_key`, `state`, `latitude`, `longitude`).
- One instance per process; built at most once; read-only afterwards.
- Invariant: never empty. Absent database or zero rows raises `CitiesDataMissing` naming `build_data`.

## Route

| Field | Type | Notes |
|---|---|---|
| `geometry` | `list[tuple[float, float]]` | `(lat, lon)` in route order, decoded from precision-5 polyline |
| `total_miles` | `float` | `routes[0].distance / 1609.344` |

This is the cached value. Cache key: `route:{start_key}:{start_state}:{finish_key}:{finish_state}`,
TTL 86400 s, direction-sensitive.

## RouteResult (handoff to the algorithm)

| Field | Type | Notes |
|---|---|---|
| `geometry` | `list[tuple[float, float]]` | from Route |
| `total_miles` | `float` | from Route |
| `start_coord` | `tuple[float, float]` | from CityIndex |
| `finish_coord` | `tuple[float, float]` | from CityIndex |
| `stops` | `list` | empty when `total_miles <= 500`; filled by the algorithm otherwise |
| `total_cost` | `float` | `0.0` when `total_miles <= 500` |

## Errors (`routing/errors.py`)

| Exception | HTTP | Raised when |
|---|---|---|
| `InvalidParameter` | 400 | missing or unsplittable `start`/`finish`; names the parameter |
| `SameEndpoints` | 400 | normalized start equals finish |
| `CityNotFound` | 404 | key absent from CityIndex; carries the parsed `(city_key, state)` |
| `OsrmRejected` | 502 | `code != "Ok"`; carries the OSRM code |
| `OsrmUnavailable` | 504 | connect/read timeout or transport error |
| `CitiesDataMissing` | 503 | cities DB absent or empty; message names `build_data` |
| `PlannerNotAvailable` | 501 | route over 500 miles and no algorithm wired yet |

## State transitions

`CityIndex`: unbuilt, then (first request, under lock) built. It never returns to unbuilt outside
tests.
Route cache entry: absent, then present (TTL 24 h), then expired, which behaves as absent.
