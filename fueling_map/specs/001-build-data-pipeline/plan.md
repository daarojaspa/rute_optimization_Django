# Implementation Plan: Build Station Location Data

**Branch**: `001-build-data-pipeline` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-build-data-pipeline/spec.md`

## Summary

An offline `build_data` management command reads the fuel-price and US-cities CSVs, cleans and
deduplicates them, joins stations to city coordinates, spreads same-city stations by a
deterministic shift of at most 5 miles, enforces a match-rate gate, and writes two SQLite
databases. The human selected (2026-09-26): **Design A** for module structure (one deep, pure
`stations/pipeline.py` behind a thin command) and **Django ORM with two database aliases** for
storage.

## Technical Context

**Language/Version**: Latest Django and the Python it requires (expected Python 3.12+, pinned
with `uv`; verify at implementation because the system Python is 3.10).

**Primary Dependencies**: Django only at runtime; standard-library `csv`, `hashlib`, `math`,
`logging`. No pandas (justification: ~30k and ~8k rows fit trivially in the standard library, so a
data-frame library adds weight without need).

**Storage**: SQLite via Django ORM: alias `default` = `stations_locations.sqlite3` (Station
table); alias `cities` = `cities.sqlite3` (City table), routed by a small database router.

**Testing**: `pytest` + `pytest-django`, `ruff`, `mypy`. Pipeline tests need no database; command
tests use temporary databases and temp CSV files. No network is used anywhere.

**Target Platform**: Linux developer machine and Docker later.

**Project Type**: Django project (management command in the data-only `stations` app).

**Performance Goals**: Full build under 1 minute on the supplied data (SC-006).

**Constraints**: Offline; deterministic output; no writes when the gate fails; PRs of at most 300
changed lines.

**Scale/Scope**: about 29,880 city rows and 8,151 station rows (6,738 distinct stations).

## Constitution Check

*GATE: passed before Phase 0; re-checked after Phase 1.*

| Principle | Status | Note |
|---|---|---|
| I. Pure routing core | Pass | `pipeline.py` is plain Python with no Django imports and no ORM; only the command touches the ORM. `routing/` is untouched. |
| II. Correctness guarantees | N/A | Planner rules are a later feature. Determinism and unit discipline are honored here. |
| III. Design twice | Pass | Two designs each for module structure and storage; human chose (see research.md). |
| IV. Errors and comments | Pass | Domain exceptions (`DataBuildError`, `MatchRateTooLow`), no generic `except`. |
| V. Tests as spec | Pass | Behavior-named tests, no real I/O beyond temp files. |
| VI. Safety and gates | Pass | Filesystem writes stay in the project; no network; no push/merge without the human. |
| Dependencies | Pass | No new dependency beyond Django and the test tooling in the constitution. |
| PR size ≤ 300 lines | Plan | Work split into three PRs (see below). |

Post-design re-check: still passes. One noted tension: the ORM path makes a byte-identical **file**
harder than raw `sqlite3`, so the spec's guarantee is met at the **table content** level (rows
exported in primary-key order are identical) plus explicit rules below.

## Project Structure

### Documentation (this feature)

```text
specs/001-build-data-pipeline/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── build_data-cli.md
└── tasks.md             # created later by /speckit-tasks
```

### Source Code (repository root: `fueling_map/`)

```text
manage.py
config/                          # settings (two DATABASES, router), urls
stations/
├── models.py                    # Station, City
├── db_router.py                 # City -> "cities", everything else -> "default"
├── pipeline.py                  # pure: clean, dedupe, join, shift, gate -> BuildResult
├── management/commands/build_data.py   # thin: read CSVs, call pipeline, write DBs, print
└── migrations/
tests/
├── unit/test_pipeline.py        # no DB
└── integration/test_build_data_command.py
```

**Structure Decision**: matches ARCHITECTURE.md (`stations/` is data-only). `pipeline.py` exposes
one entry point, `build(fuel_rows, city_rows, fail_under) -> BuildResult`, plus a small
`DataBuildError` family; everything else is private. The command owns all I/O.

### Delivery in reviewable PRs

1. Django skeleton, settings with two databases, router, models and migrations.
2. `pipeline.py` with unit tests.
3. `build_data` command, integration tests, README note (city-level approximation, 5-mile shift).

## Complexity Tracking

No constitution violations to justify.
