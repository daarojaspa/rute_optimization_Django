# Data Model: Build Station Location Data

## Station (database `stations_locations`, table `stations_station`)

| Field | Type | Rule |
|---|---|---|
| opis_id | integer, primary key | OPIS Truckstop ID; unique; rows written in ascending order |
| name | text | trimmed, whitespace collapsed |
| address | text | trimmed, whitespace collapsed |
| city | text | display form: trimmed, collapsed, title-cased |
| state | 2-letter text | uppercase; one of the 50 states or DC |
| latitude | float | 6 decimals; city latitude, or shifted (at most 5 miles) |
| longitude | float | 6 decimals; same rule |
| retail_price | float | greater than 0 and at most 10.00 |

Only stations that matched a city are stored (spec, clarification 3). Table name follows the
Django app label unless overridden to `stations` in the model options.

## City (database `cities`, table `cities_city` unless overridden)

| Field | Type | Rule |
|---|---|---|
| city | text | display form |
| city_key | text | matching key (uppercase, tokens expanded) |
| state | 2-letter text | uppercase |
| latitude, longitude | float | from the first source row of the group |

Unique on (`city_key`, `state`).

## Transient (pipeline only, not stored)

- **RawStation / RawCity**: parsed CSV rows.
- **BuildResult**: `stations`, `cities`, `unmatched`, `stats` (rows read, dropped by reason,
  groups collapsed, city rows collapsed, matched count, match rate, left out as unmatched).
- **Errors**: `DataBuildError` (base, includes missing/invalid input), `MatchRateTooLow`.

## State transitions

Input CSV rows → cleaned rows → deduplicated stations → matched/unmatched → shifted → written.
A failed gate stops before any write; a run replaces all previous rows in both tables.
