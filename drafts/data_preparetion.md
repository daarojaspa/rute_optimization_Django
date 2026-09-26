Spec A — build_data management command

Purpose: Read the raw fuel-price CSV and the US cities CSV, clean and normalize, attach coordinates, write to SQLite. Offline only: no HTTP calls, no network. Produces tables, not in-memory objects.

Command: python manage.py build_data
Optional flags: --fuel-csv <path>, --cities-csv <path>, --fail-under <float, default 0.95>

Inputs
fuel-prices-for-be-assessment.csv — columns as given (OPIS Truckstop ID, Truckstop Name, Address, City, State, Rack ID, Retail Price)
us_cities.csv — city, state, latitude, longitude
Processing order

1. Normalize text (closed list — do nothing beyond this)
Applied to both datasets before any matching:

State: strip, uppercase
City: strip, collapse internal whitespace to single spaces, title-case
City token expansion: ST./ST → SAINT, FT./FT → FORT, MT. → MOUNT (applied on the uppercased form used for matching only; keep a display form too)
Truckstop Name, Address: strip, collapse whitespace
Retail Price: coerce to float; drop rows where it is null, ≤ 0, or > 10.00 (log the count)

No other typo correction. No fuzzy matching.

2. Validate states
Canonical set = 50 state codes + DC. Rows whose normalized State is outside the set are dropped and counted by code in the log. Do not assume the result is exactly 50 distinct values — assert only that every surviving value is in the canonical set.

3. Deduplicate stations
Group key: [DECIDE — recommend OPIS Truckstop ID].
Price tie-break within a group: [DECIDE — recommend min, since the algorithm wants the cheapest achievable price].
Do not dedupe on Truckstop Name — the sample shows one site listed as both PILOT TRAVEL CENTER #1243 and PILOT #1243; name-based dedup would merge distinct sites elsewhere.
Log: rows in, rows out, groups collapsed.

4. Deduplicate cities
Before the join, collapse us_cities to one row per (city_key, state). Without this, a duplicated city name fans out station rows. Tie-break: keep the row with the largest population if available, otherwise the first. Log how many were collapsed.

5. Join
Left join stations → cities on (city_key, state). Station coordinates are the city-center coordinates, not the truckstop's actual position.

Accepted limitation, to be stated in the README: city-center approximation introduces error on the order of a few miles per station. Acceptable given a 500-mile vehicle range and a wide route corridor; it means the reported total cost is an estimate, not a quote.

6. Join quality gate

Compute match_rate = matched_stations / total_stations
Print it at the end of the run
Write every unmatched (name, city, state) to unmatched.csv in the working directory
If match_rate < --fail-under, exit non-zero with an error; write nothing to the DB

7. Write to DB

Stations → SQLite DB stations_locations, one table, columns: opis_id, name, address, city, state, latitude, longitude, retail_price
Cities → its own SQLite DB, name unchanged
Truncate-and-reload, not append. Running the command twice in a row must produce a byte-identical station table and the same match rate.
Output (stdout summary)

Rows read, rows dropped by reason, groups deduped, city rows collapsed, match rate, rows written.

Explicitly out of scope

KD-tree construction, CityIndex, StationIndex, any distance math