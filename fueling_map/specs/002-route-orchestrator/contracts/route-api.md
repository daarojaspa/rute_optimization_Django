# Contract: `GET /api/route/`

## Request

```
GET /api/route/?start=<City, ST>&finish=<City, ST>
```

Both parameters are required, in the form `City, ST`. Split on the first comma; both halves are
trimmed. Matching is case-, spacing- and `ST.`/`FT.`/`MT.`-insensitive.

## Outbound call (exactly one per uncached request)

```
GET {OSRM_BASE_URL}/route/v1/driving/{lon1},{lat1};{lon2},{lat2}
    ?overview=full&geometries=polyline&steps=false&annotations=false&alternatives=false
```

Timeouts: 3 s connect, 10 s read. No retries. Coordinate order is `lon,lat`. A cache hit makes
no call.

## Success: 200

```json
{
  "start":  {"city": "DALLAS", "state": "TX", "lat": 32.78, "lon": -96.80},
  "finish": {"city": "DENVER", "state": "CO", "lat": 39.74, "lon": -104.99},
  "total_miles": 801.3,
  "geometry": [[32.78, -96.80], "..."],
  "stops": [],
  "total_cost": 0.0
}
```

`geometry` is `[lat, lon]` pairs in route order. For routes of 500 miles or less, `stops` is `[]`
and `total_cost` is `0.0`. Fields beyond `stops`/`total_cost` content for longer routes are defined
by the algorithm spec.

## Errors

Body shape: `{"error": "<code>", "detail": "<message>"}` plus the extras noted.

| Status | `error` | When | Extra |
|---|---|---|---|
| 400 | `invalid_parameter` | `start` or `finish` missing or has no comma | `detail` names the parameter |
| 400 | `same_endpoints` | endpoints equal after normalization | `detail`: `start and finish must differ` |
| 404 | `city_not_found` | key not in CityIndex | `city_key`, `state` echoed as parsed |
| 501 | `planner_not_available` | over 500 miles before the algorithm is wired | none |
| 502 | `osrm_rejected` | OSRM `code != "Ok"` (for example `NoRoute`) | `osrm_code` passed through |
| 503 | `cities_data_missing` | cities DB absent or empty | `detail` names `build_data` |
| 504 | `osrm_unavailable` | OSRM timeout or unreachable | none |

## Behavioral guarantees

- At most one OSRM call per request; zero on a cache hit within 24 h.
- Reverse direction (`start` and `finish` swapped) is a separate cache entry.
- A request never returns a route computed from swapped coordinates: order is asserted in tests.
