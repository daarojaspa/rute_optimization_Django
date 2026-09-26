# Quickstart: Build Station Location Data

Prerequisites: `uv sync`, then `uv run python manage.py migrate` and
`uv run python manage.py migrate --database=cities`.

1. Build with the supplied files (paths relative to `fueling_map/`):
   `uv run python manage.py build_data --fuel-csv ../fuel-prices-for-be-assessment.csv --cities-csv ../us_cities.csv`
   Expect: summary printed, match rate at or above 0.95, `unmatched.csv` written, exit code 0.
2. Repeat step 1 and compare an export of the station table ordered by `opis_id` (for example
   `sqlite3 stations_locations.sqlite3 "select * from stations_station order by opis_id" | sha256sum`).
   Expect identical hashes and identical match rates.
3. Force the gate: add `--fail-under 1.0`. Expect a non-zero exit, `unmatched.csv` present, and
   the databases unchanged (same hash as step 2).
4. Missing file: `--fuel-csv nope.csv`. Expect a non-zero exit naming the file, nothing written.
5. Checks on the stored data (spec SC-004, SC-004a): no duplicate `opis_id`, prices in (0, 10.00],
   states inside the 50 states plus DC, every station within 5 miles of its city's coordinates.
6. Tests: `uv run pytest`; lint and types: `uv run ruff check . && uv run mypy .`.

Details: [data model](data-model.md), [CLI contract](contracts/build_data-cli.md).
