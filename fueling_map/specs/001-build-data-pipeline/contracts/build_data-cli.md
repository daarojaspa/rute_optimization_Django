# Contract: `python manage.py build_data`

## Arguments

| Flag | Default | Meaning |
|---|---|---|
| `--fuel-csv PATH` | project default path | Raw fuel-price CSV |
| `--cities-csv PATH` | project default path | US cities CSV |
| `--fail-under FLOAT` | `0.95` | Minimum match rate in [0, 1] |

## Inputs

- Fuel CSV columns: `OPIS Truckstop ID, Truckstop Name, Address, City, State, Rack ID, Retail Price`.
- Cities CSV columns used: `CITY, STATE_CODE, LATITUDE, LONGITUDE`; optional `POPULATION`.

## Outputs

- Databases: `stations_locations.sqlite3` (table of Station) and `cities.sqlite3` (table of City).
- `unmatched.csv` in the working directory: columns `name, city, state`, one row per unmatched
  station; written on every run that reaches the join, including gate failures.
- stdout summary: rows read, rows dropped by reason (bad price, non-canonical state by code),
  groups deduplicated, city rows collapsed, match rate, stations left out as unmatched, rows
  written.

## Exit codes

| Code | Condition | Database effect |
|---|---|---|
| 0 | Success | Both tables replaced |
| non-zero | Missing/unreadable input, no surviving stations, or match rate below `--fail-under` | Unchanged |

## Guarantees

Offline; identical inputs give identical table contents and match rate; the same run twice gives
byte-identical exports of the station table ordered by `opis_id`.
