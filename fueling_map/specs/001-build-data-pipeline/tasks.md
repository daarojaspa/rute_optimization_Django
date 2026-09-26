---

description: "Task list for the build_data station location pipeline"
---

# Tasks: Build Station Location Data

**Input**: Design documents from `specs/001-build-data-pipeline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/build_data-cli.md, quickstart.md

**Tests**: Included. The constitution (Principle V) requires behavior-named tests that act as the specification. Write each story's tests first and confirm they fail.

**Organization**: Grouped by user story. Paths are relative to `fueling_map/`. Each `PR` marker is a review boundary (constitution: one logical change, at most 300 changed lines).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependencies)
- **[Story]**: US1 to US4, from spec.md

## Phase 1: Setup (PR 1: Django skeleton)

- [X] T001 Initialize the project with `uv` (pin the latest Django and the Python version it requires) and create `pyproject.toml` with runtime dependency Django and dev dependencies pytest, pytest-django, ruff, mypy
- [X] T002 Create the Django project `config/` (settings, urls, wsgi/asgi) and `manage.py`; create the `stations` app in `stations/`
- [X] T003 [P] Configure ruff, mypy and pytest-django in `pyproject.toml`; add `.gitignore` entries for `*.sqlite3`, `unmatched.csv`, `.env`

---

## Phase 2: Foundational (PR 1, continued)

**Purpose**: Storage that every story writes to.

- [X] T004 Configure `DATABASES` in `config/settings.py`: alias `default` = `stations_locations.sqlite3`, alias `cities` = `cities.sqlite3`; read paths from the environment with defaults
- [X] T005 [P] Define `Station` (pk `opis_id`, name, address, city, state, latitude, longitude, retail_price) in `stations/models.py` per data-model.md
- [X] T006 [P] Define `City` (city, city_key, state, latitude, longitude; unique on `city_key`+`state`) in `stations/models.py`
- [X] T007 Create `stations/db_router.py` routing `City` to `cities` and register it in `config/settings.py`
- [X] T008 Create and apply migrations for both databases (`stations/migrations/`)
- [X] T009 [P] Write `tests/integration/test_db_routing.py`: `test_city_is_stored_in_cities_database`, `test_station_is_stored_in_default_database`

**Checkpoint**: both databases migrate; routing test passes.

---

## Phase 3: User Story 1 - Build a clean, located station table (Priority: P1) MVP (PR 2: pipeline, PR 3: command)

**Goal**: Clean, deduplicate, locate and store stations; print the summary.

**Independent Test**: Run the command on the supplied CSVs and inspect the station table (quickstart steps 1 and 5).

### Tests for User Story 1 (write first)

- [X] T010 [P] [US1] `tests/unit/test_pipeline.py`: normalization tests: `test_state_is_trimmed_and_uppercased`, `test_city_whitespace_collapsed_and_title_cased`, `test_st_ft_mt_tokens_expand_only_in_match_key`, `test_display_city_keeps_original_form`
- [X] T011 [P] [US1] `tests/unit/test_pipeline.py`: filtering tests: `test_price_null_zero_negative_or_over_10_is_dropped_and_counted`, `test_state_outside_50_plus_dc_is_dropped_and_counted_by_code`, `test_canadian_province_rows_are_dropped`
- [X] T012 [P] [US1] `tests/unit/test_pipeline.py`: dedupe tests: `test_group_keeps_lowest_priced_row_with_all_its_fields`, `test_equal_prices_keep_first_row`, `test_different_names_with_different_ids_are_not_merged`, `test_stats_report_rows_in_rows_out_groups_collapsed`
- [X] T013 [P] [US1] `tests/unit/test_pipeline.py`: city and join tests: `test_identical_coordinate_city_rows_collapse`, `test_same_name_different_coordinates_uses_first_row`, `test_population_column_preferred_when_present`, `test_station_joins_on_city_key_and_state`, `test_unmatched_station_is_left_out_and_listed`
- [X] T014 [P] [US1] `tests/unit/test_pipeline.py`: shift tests: `test_lowest_opis_id_in_city_keeps_city_coordinates`, `test_other_stations_shift_at_most_5_miles_haversine`, `test_shift_is_a_pure_function_of_identity_and_city`
- [X] T015 [P] [US1] `tests/integration/test_build_data_command.py`: `test_command_writes_stations_and_cities_and_prints_summary`, `test_no_station_has_duplicate_id_bad_price_or_bad_state`

### Implementation for User Story 1

- [X] T016 [US1] `stations/pipeline.py`: interface comment, `DataBuildError`, row and `BuildResult` dataclasses, and the normalization helpers (state, city display and key, name/address, price)
- [X] T017 [US1] `stations/pipeline.py`: price and state filtering with per-reason counts (depends on T016)
- [X] T018 [US1] `stations/pipeline.py`: station deduplication by OPIS ID (lowest price, first on ties) and city collapse per research decision 4; log any same-key city group spread over 50 miles
- [X] T019 [US1] `stations/pipeline.py`: join, matched/unmatched split, and the deterministic shift (research decision 3), exposed through `build(fuel_rows, city_rows, fail_under) -> BuildResult` (the gate itself is US2)
- [X] T020 [US1] `stations/management/commands/build_data.py`: read both CSVs, call `build`, write cities then stations with `transaction.atomic` (delete, then `bulk_create` in ascending `opis_id`), print the summary, write `unmatched.csv`

**Checkpoint**: US1 tests pass; the command builds the tables from the supplied CSVs.

---

## Phase 4: User Story 2 - Refuse to load poorly matched data (Priority: P1)

**Goal**: Report the match rate and block writes below the threshold.

**Independent Test**: Quickstart step 3.

- [X] T021 [P] [US2] `tests/unit/test_pipeline.py`: `test_match_rate_is_matched_over_surviving_stations`, `test_match_rate_below_fail_under_raises_MatchRateTooLow`, `test_match_rate_equal_to_fail_under_passes`, `test_zero_surviving_stations_raises_DataBuildError`
- [X] T022 [P] [US2] `tests/integration/test_build_data_command.py`: `test_gate_failure_exits_nonzero_and_leaves_databases_unchanged`, `test_gate_failure_still_writes_unmatched_csv`, `test_unmatched_csv_lists_name_city_state`, `test_unmatched_stations_are_absent_from_station_table`
- [X] T023 [US2] `stations/pipeline.py`: add `MatchRateTooLow` and enforce the gate before any write (depends on T019)
- [X] T024 [US2] `stations/management/commands/build_data.py`: map `DataBuildError`/`MatchRateTooLow` to a non-zero exit (`CommandError`), write `unmatched.csv` before failing, print the match rate

---

## Phase 5: User Story 3 - Repeatable rebuilds (Priority: P2)

**Goal**: Identical inputs give identical table contents and match rate; each run replaces the old data.

**Independent Test**: Quickstart step 2.

- [X] T025 [P] [US3] `tests/integration/test_build_data_command.py`: `test_second_run_gives_identical_station_table_export_and_match_rate`, `test_rows_missing_from_new_input_are_removed`
- [X] T026 [US3] Verify and fix determinism in `stations/pipeline.py` and the command: stable ordering (ascending `opis_id`), 6-decimal rounding, no timestamps or auto fields

---

## Phase 6: User Story 4 - Choose input files and threshold (Priority: P3)

**Goal**: `--fuel-csv`, `--cities-csv`, `--fail-under` work; a missing file fails cleanly.

**Independent Test**: Quickstart step 4.

- [X] T027 [P] [US4] `tests/integration/test_build_data_command.py`: `test_custom_paths_and_threshold_are_used`, `test_missing_csv_exits_nonzero_naming_file_and_writes_nothing`, `test_fail_under_outside_0_to_1_is_rejected`
- [X] T028 [US4] `stations/management/commands/build_data.py`: add the three arguments with defaults and validation; raise `DataBuildError` for missing or unreadable files

---

## Phase 7: Polish & Cross-Cutting

- [X] T029 [P] Write the README note in `README.md`: city-level approximation, 5-mile same-city shift is a spreading heuristic, and costs are estimates, not quotes (FR-017)
- [X] T030 [P] Add a no-network test in `tests/integration/test_build_data_command.py` (`test_command_makes_no_network_calls`) that blocks sockets
- [X] T031 Run `ruff check .`, `ruff format --check .`, `mypy .`, `pytest`; then run quickstart.md end to end on the supplied CSVs
- [X] T032 Check the summary against spec SC-001 to SC-006 and record the actual match rate and run time in the PR description (recorded: match rate 0.9982, 6,614 stations written, 12 unmatched, about 14 s including uv startup, station-table hash identical across two runs, max 4.903 miles from city)

---

## Dependencies & Execution Order

- Phase 1 then Phase 2 block everything.
- US1 is the MVP. US2 depends on US1's `build` (T019). US3 and US4 depend on US1 and can run in parallel with US2 after T020.
- Within US1, tests T010 to T015 are parallel (one file, so coordinate edits); T016 to T019 are sequential in one file; T020 follows T019.
- Because `pipeline.py` and the command are single files, few implementation tasks are parallel.

### Parallel example (US1 tests)

Run T010 to T015 together (separate test classes or files), then implement T016 to T020 in order.

## Implementation Strategy

1. **MVP**: Phases 1 to 3 (PRs 1 to 3): a working build that stores clean, located stations.
2. Add US2 (the gate), US3 (repeatability), US4 (flags) as small follow-up PRs.
3. Validate with quickstart.md; every PR states what changed, why, how tested, and the rejected design alternative.
