# Feature Specification: Build Station Location Data

**Feature Branch**: `001-build-data-pipeline`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "`build_data` management command: offline pipeline that reads the raw fuel-price CSV and the US cities CSV, cleans and normalizes both, attaches city-center coordinates to each station, and writes the results to SQLite tables. No network access. Out of scope: spatial indexes and any distance math."

## Clarifications

### Session 2026-09-26

- Q: When several rows share one OPIS Truckstop ID, which row supplies the surviving station's fields? → A: The lowest-priced row supplies every field; ties go to the first row in file order.
- Q: Cities with the same name and state but different coordinates (122 of 125 duplicated names; median gap about 4 miles, largest about 48) — which coordinates apply? → A: Rows with identical coordinates collapse; otherwise the first row in file order is used. (The stations file has no county, so county cannot join.)
- Q: Many stations share one city and would get identical coordinates; should they be spread? → A: Yes. Within a city, the station with the lowest OPIS ID keeps the city coordinates; every other station gets a deterministic shift of at most 5 miles.
- Q: When the gate passes, are unmatched stations stored? → A: No. They are left out of the station table and appear only in `unmatched.csv`; the summary reports how many were left out.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a clean, located station table (Priority: P1)

A developer runs the build command once, pointing it at the raw fuel-price CSV and the US cities CSV. The command cleans both files, gives every station a coordinate, and stores the result so the routing API can later read stations with prices and locations without touching the raw files.

**Why this priority**: Without located, deduplicated stations there is nothing for the route planner to choose from; every later feature depends on this table.

**Independent Test**: Run the command on the supplied CSVs and inspect the resulting station table: one row per station, each with a price and coordinates, and a printed summary.

**Acceptance Scenarios**:

1. **Given** the two CSVs and an empty database, **When** the command runs with defaults, **Then** a station table is written with columns opis_id, name, address, city, state, latitude, longitude, retail_price and a summary is printed.
2. **Given** a station row whose city text has extra spaces, mixed case, or abbreviated tokens (ST., FT., MT.), **When** the command runs, **Then** it is matched to the same city as its spelled-out form and keeps its cleaned display name.
3. **Given** several rows sharing one OPIS Truckstop ID, **When** the command runs, **Then** exactly one row remains: the group's lowest-priced row, with all its fields intact.
4. **Given** stations whose names differ but whose OPIS IDs differ too (e.g. "PILOT TRAVEL CENTER #1243" and "PILOT #1243" with different IDs), **When** the command runs, **Then** they are not merged on name.

---

### User Story 2 - Refuse to load poorly matched data (Priority: P1)

A developer needs to know when too many stations could not be placed on the map. The command reports the match rate, lists unmatched stations, and refuses to write anything if the rate is below a threshold.

**Why this priority**: Silently loading a table where many stations lack coordinates would corrupt every route the API later plans.

**Independent Test**: Run with `--fail-under` above the achievable match rate and confirm a non-zero exit, an `unmatched.csv`, and an unchanged database.

**Acceptance Scenarios**:

1. **Given** a match rate at or above `--fail-under` (default 0.95), **When** the command finishes, **Then** it prints the match rate, writes `unmatched.csv`, and stores the data.
2. **Given** a match rate below `--fail-under`, **When** the command finishes, **Then** it exits non-zero with an error message, writes `unmatched.csv`, and leaves any existing database contents untouched.
3. **Given** stations with no city match, **When** the command runs, **Then** every such station's name, city and state appears in `unmatched.csv`.
4. **Given** a passing match rate, **When** the data is stored, **Then** unmatched stations are absent from the station table and every stored station has coordinates.

---

### User Story 3 - Repeatable rebuilds (Priority: P2)

A developer re-runs the command after changing a CSV or just to verify. Each run replaces prior contents entirely, and the same inputs always give the same result.

**Why this priority**: Reproducibility makes the pipeline trustworthy and testable, but the first successful build already delivers the core value.

**Independent Test**: Run the command twice on the same inputs and compare the station tables and match rates.

**Acceptance Scenarios**:

1. **Given** a successful earlier run, **When** the command runs again with identical inputs, **Then** the station table is byte-identical and the match rate is the same.
2. **Given** an earlier run with different inputs, **When** the command runs, **Then** old rows no longer present in the inputs are gone (no appending).

---

### User Story 4 - Choose input files and threshold (Priority: P3)

A developer supplies alternative CSV paths and a different threshold from the command line.

**Why this priority**: Convenience; defaults cover the standard case.

**Independent Test**: Run with `--fuel-csv`, `--cities-csv`, and `--fail-under` set to non-default values and confirm they take effect.

**Acceptance Scenarios**:

1. **Given** custom paths and threshold, **When** the command runs, **Then** those files are read and that threshold governs the gate.
2. **Given** a path that does not exist, **When** the command runs, **Then** it exits non-zero with a message naming the missing file and writes nothing.

---

### Edge Cases

- Retail price is empty, non-numeric, zero, negative, or above 10.00: the row is dropped and counted.
- State code is outside the 50 states plus DC (e.g. territories or Canadian provinces): the row is dropped and counted per code.
- Duplicate city names within one state in the cities file: collapsed to one row so stations are never duplicated by the join.
- A city appears in both abbreviated ("St. Louis") and spelled-out ("Saint Louis") form: both resolve to the same matching key.
- No fuzzy matching: a misspelled city stays unmatched and appears in `unmatched.csv`.
- Zero stations survive cleaning: the command exits non-zero with a clear error rather than dividing by zero.
- A failed run (gate, missing file) must not leave a partially written or emptied database.
- Two rows in one OPIS group with equal prices: the first in file order is kept, so the result is deterministic across runs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a command `build_data` accepting optional `--fuel-csv`, `--cities-csv`, and `--fail-under` (default 0.95).
- **FR-002**: The system MUST operate offline: no network calls of any kind.
- **FR-003**: The system MUST normalize both datasets using only this closed list: state is trimmed and uppercased; city is trimmed, internal whitespace collapsed, and title-cased; truckstop name and address are trimmed with whitespace collapsed; retail price is coerced to a number.
- **FR-004**: The system MUST derive a matching key for cities by expanding the tokens ST./ST to SAINT, FT./FT to FORT, and MT. to MOUNT on the uppercased form, while retaining the cleaned display form.
- **FR-005**: The system MUST NOT apply any other typo correction or fuzzy matching.
- **FR-006**: The system MUST drop station rows whose retail price is missing, not positive, or above 10.00, and log the count.
- **FR-007**: The system MUST drop rows whose normalized state is not one of the 50 state codes or DC, log counts per dropped code, and assert that every surviving state is in that set (without assuming exactly 51 distinct values).
- **FR-008**: The system MUST deduplicate stations by OPIS Truckstop ID, keeping the single lowest-priced row of each group as the whole station record (name, address, city, state and price all come from that row; equal prices go to the first row in file order), never deduplicating on name, and log rows in, rows out, and groups collapsed.
- **FR-009**: The system MUST collapse the cities data to one row per (city matching key, state), keeping the first row in file order (rows with identical coordinates are exact duplicates; rows with different coordinates are the same-name city in another county, and only the first is used), tolerating and preferring a largest-population row if a population column is ever present, and log how many rows were collapsed.
- **FR-010**: The system MUST left-join stations to cities on (city matching key, state), assigning each station its matched city's coordinates; unmatched stations have no coordinates and, when the gate passes, MUST be left out of the stored station table (they remain listed in `unmatched.csv`).
- **FR-010a**: Among matched stations sharing one city, the station with the lowest OPIS Truckstop ID MUST keep the city's coordinates unchanged. Every other station MUST receive coordinates shifted from the city's by at most 5 miles. The shift MUST be a deterministic function of the station's identity and the city coordinates only, so identical inputs give identical coordinates; no randomness may vary between runs.
- **FR-011**: The system MUST compute match rate as matched stations divided by total stations, print it, and write every unmatched station's name, city and state to `unmatched.csv` in the working directory.
- **FR-012**: If the match rate is below `--fail-under`, the system MUST exit non-zero with an error and write nothing to the databases.
- **FR-013**: On success, the system MUST store stations in a SQLite database named `stations_locations` as a single table with columns opis_id, name, address, city, state, latitude, longitude, retail_price, and store the cities in their own SQLite database, with the source name unchanged.
- **FR-014**: Each successful run MUST replace prior contents (truncate and reload, no append); identical inputs MUST yield a byte-identical station table and the same match rate.
- **FR-015**: The system MUST print a summary with rows read, rows dropped by reason, groups deduplicated, city rows collapsed, match rate, stations left out as unmatched, and rows written.
- **FR-016**: The system MUST NOT build spatial indexes or in-memory lookup structures, and MUST NOT perform distance math other than the bounded per-station shift in FR-010a.
- **FR-017**: The project README MUST state that station coordinates are city-level approximations (a city's coordinates, with a deterministic shift of at most 5 miles for all but one station per city), so reported fuel costs are estimates, not quotes.

### Key Entities

- **Raw Station Row**: a line of the fuel-price file: OPIS Truckstop ID, truckstop name, address, city, state, rack ID, retail price.
- **Station**: one physical truckstop after cleaning and deduplication, with its lowest retail price and city-center coordinates. Identified by OPIS Truckstop ID.
- **City**: one named place in one state with a latitude and longitude, unique per (matching key, state) after collapse.
- **Unmatched Report**: the list of stations (name, city, state) that found no city.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the supplied CSVs, at least 95% of stations end up with coordinates on a default run.
- **SC-002**: Two consecutive runs on identical inputs produce byte-identical station tables and identical match rates in 100% of trials.
- **SC-003**: A run that fails the match-rate gate leaves the pre-existing data unchanged in 100% of trials.
- **SC-004a**: No station's stored coordinates lie more than 5 miles from its matched city's coordinates, and exactly one station per city (the lowest OPIS ID) sits exactly at them.
- **SC-004**: After a successful run, the station table contains no duplicate OPIS IDs, no price outside (0, 10.00], and no state outside the 50 states plus DC.
- **SC-005**: A developer can read the printed summary and account for every input row (kept or dropped by a named reason).
- **SC-006**: A full build on the supplied data completes in under one minute on a developer laptop.

## Assumptions

- The command lives in the data-only `stations` app, per the constitution's architecture rules; the routing core is untouched.
- The supplied `us_cities.csv` currently uses columns ID, STATE_CODE, STATE_NAME, CITY, COUNTY, LATITUDE, LONGITUDE and has no population column (county is unique per city row but is not in the stations file, so it is not a join key), so the "first row" rule applies; the loader must map these columns and tolerate a population column if one is later added.
- The "cities database" is a separate SQLite database from `stations_locations`, holding the collapsed cities table under the source's name.
- Recommended defaults from the description are adopted: dedupe key is OPIS Truckstop ID and the price tie-break is the minimum.
- The 5-mile shift is a spreading heuristic, not a real location; it is the human's decision (session 2026-09-26) and the README must say so.
- The "first row" and equal-price tie-breaks follow file order, so results are deterministic.
- The command is run by developers as part of setup, not by API users, and only occasionally.
- Failed-gate behavior applies to the databases; `unmatched.csv` is still written so the failure can be diagnosed.
- Out of scope: spatial indexes, CityIndex/StationIndex, route distance math, geocoding of actual truckstop addresses, any HTTP call.
