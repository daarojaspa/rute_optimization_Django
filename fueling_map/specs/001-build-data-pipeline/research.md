# Research: Build Station Location Data

## Decision 1: Module structure
- **Decision**: One deep pure module `stations/pipeline.py`, thin command (human chose Design A).
- **Rationale**: Constitution I and III favor a small interface over hidden logic; all cleaning
  rules share one row schema, so splitting would leak it. Testable in milliseconds without a DB.
- **Alternatives**: B, per-step modules (normalize, dedupe, join, shift, gate): smaller files but
  shallow interfaces and duplicated schema knowledge.

## Decision 2: Storage
- **Decision**: Django ORM with two aliases (human chose Design B): `default` =
  `stations_locations.sqlite3`, `cities` = `cities.sqlite3`; router sends `City` to `cities`.
- **Rationale**: Same models the API will read later; migrations manage the schema.
- **Alternatives**: stdlib `sqlite3` with temp file + atomic rename (simpler byte-identical files).
- **Consequences and mitigations**:
  - Reload = inside `transaction.atomic(using=alias)`: delete all rows, `bulk_create` in
    ascending `opis_id` order with explicit primary keys. The gate runs before any write, so a
    failed gate touches nothing.
  - No timestamps or auto fields in the tables. Coordinates are rounded to 6 decimals in the
    pipeline so float text is stable.
  - Byte-identical is verified by exporting the table ordered by `opis_id` and comparing hashes;
    raw file identity is not guaranteed by SQLite after deletes (free pages), so the test compares
    table contents.
  - Two databases means two transactions; write cities first, then stations. If the second
    fails, the run exits non-zero and is safe to rerun (truncate-and-reload).

## Decision 3: Deterministic 5-mile shift
- **Decision**: Within a matched city, the lowest OPIS ID keeps the city coordinates. For every
  other station take `sha256(str(opis_id))`; two 32-bit fractions give an angle in [0, 2π) and a
  radius fraction. Radius = fraction × 4.9 miles (margin under the 5-mile cap). Convert to
  degrees with 69.0 miles per degree of latitude and `69.17 × cos(lat)` per degree of longitude.
- **Rationale**: pure function of station identity and city coordinates, no run-to-run state, no
  random seed to manage. The equirectangular approximation error at this scale is far below the
  0.1-mile margin.
- **Alternatives**: seeded `random` (hides ordering dependence); ring layout by rank (more
  logic, same value).

## Decision 4: Cleaning details
- **Matching key**: uppercase the cleaned city; split on whitespace; replace tokens `ST.`, `ST`
  → `SAINT`, `FT.`, `FT` → `FORT`, `MT.` → `MOUNT`. Per spec, bare `MT` is not expanded.
- **Order**: normalize → drop bad price → drop bad state → dedupe by OPIS ID (min price, first
  on ties) → collapse cities → join. Price filtering before dedupe means a bad low price can
  never win a group.
- **Canonical states**: 50 states plus DC. The fuel file also contains Canadian provinces (AB, BC,
  MB, NB, NS, ON, QC, SK, YT), which are dropped and counted by code.
- **Cities CSV columns**: `CITY`, `STATE_CODE`, `LATITUDE`, `LONGITUDE` (plus `COUNTY`, `ID`,
  `STATE_NAME`, unused). A `POPULATION` column, if present, is preferred over first-row order.
- **Match rate** = matched / stations that survived cleaning and dedupe.
- **Spread check**: log any same-key city group whose rows lie more than 50 miles apart.

## Decision 5: Unknowns resolved
- Python/Django versions: pin through `uv`; confirm the latest Django's minimum Python at setup.
- CSV location: default paths come from `--fuel-csv` / `--cities-csv`; the quickstart passes the
  files at the repository root explicitly, so no data file is copied or moved.
