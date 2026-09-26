## Lookup layer and route orchestrator

**Depends on:** Data preparation (`build_data`) having been run; both SQLite DBs must exist before the first request.
**Out of scope:** `StationIndex`, corridor matching, fuel-stop selection, cost — all belong to the algorithm spec.

---

### 1. Shared normalizer — `data/normalize.py`

```
normalize_city_key(city: str, state: str) -> tuple[str, str]
```

- `state`: strip, uppercase
- `city`: strip, collapse internal whitespace, uppercase
- Token expansion on city: `ST.` / `ST ` → `SAINT`, `FT.` / `FT ` → `FORT`, `MT.` / `MT ` → `MOUNT`
- Returns `(city_key, state)`

Spec A imports this same function. Build this file before Spec A. If the two ever diverge, every affected city 404s at request time with no error anywhere in the loader.

---

### 2. CityIndex

- Type: `dict[tuple[str, str], tuple[float, float]]` → `(lat, lon)`
- Source: cities SQLite DB, read once
- Built lazily on first request, as a module-level singleton (not a Django cache entry — it is read-only after construction)
- Construction guarded by a module-level `threading.Lock` with check-lock-check, so two threads in one worker cannot both build it
- If the DB file is absent or the table is empty, raise on first request with a message naming `build_data` as the fix. Never return an empty index

---

### 3. Endpoint

```
GET /api/route/?start=<string>&finish=<string>
```

Both parameters are `"City, ST"`. Split on the first comma; strip both halves; pass through `normalize_city_key`; look up in `CityIndex`.

| Condition | Status | Body |
|---|---|---|
| Missing or unsplittable parameter | 400 | names the offending parameter |
| Key absent from `CityIndex` | 404 | echoes the parsed `(city_key, state)` |
| `start == finish` after normalization | 400 | `"start and finish must differ"` |

---

### 4. OSRM call — exactly one per request

```
GET https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}
    ?overview=full&geometries=polyline&steps=false&annotations=false&alternatives=false
```

- Coordinate order is `lon,lat`. Reversed order returns a plausible route through the wrong place, not an error
- `overview=full` is mandatory; `simplified` geometry is too coarse for corridor matching and cannot be refined without a second call
- Timeouts: 3s connect, 10s read
- No retries. A retry is a second call, and the brief counts calls
- `code != "Ok"` → `502`, passing the OSRM code through. `NoRoute` is a real case: AK, HI and PR are in the state set but are not drivable from the lower 48
- `routes[0].distance` is metres → miles via `/ 1609.344`
- Decode `routes[0].geometry` as polyline precision 5

---

### 5. Cache

- Backend: `django.core.cache.backends.locmem.LocMemCache`
- Key: `route:{start_key}:{start_state}:{finish_key}:{finish_state}`
- Value: decoded geometry + `total_miles`
- TTL: 24h
- A cache hit means zero OSRM calls

README and Loom note: per-worker, lost on restart; production would use Redis.

---

### 6. Handoff to the fuel-stop algorithm

```
geometry:    list[tuple[float, float]]   # (lat, lon), route order
total_miles: float
start_coord: tuple[float, float]
finish_coord: tuple[float, float]
```

If `total_miles <= 500`: no fill-up is required. Return an empty stop list and `total_cost = 0.0`.

---

Two defaults I filled in rather than leave open: `start == finish` → 400, and sub-500-mile routes → zero cost. Both are defensible, but the second one is the likelier interview question — the honest answer is that the tank starts full and the brief only asks for fuel purchased en route. If you'd rather price the fuel consumed, say so now, because it changes the algorithm's contract too.