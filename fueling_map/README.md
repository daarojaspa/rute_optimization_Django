# Fueling Map

 API that plans cost-effective fuel stops along a US route. This part of the project builds the
station data the planner reads.

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

## Development

```bash
uv run pytest && uv run ruff check . && uv run mypy .
```
