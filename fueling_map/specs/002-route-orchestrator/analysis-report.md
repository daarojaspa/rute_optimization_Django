# Specification Analysis Report — `002-route-orchestrator`

**Generated**: 2026-10-02 by `/speckit-analyze`
**Scope**: Cross-artifact consistency check across `spec.md`, `plan.md`, `data-model.md`, `research.md`, `contracts/route-api.md`, `quickstart.md`, `tasks.md`, and the project constitution, run after `/speckit-tasks` produced `tasks.md`.
**Status**: Read-only analysis. No files were modified by the analysis itself; the findings below are pending review.

Artifacts loaded: `spec.md` (19 FR, 6 SC, 5 user stories), `plan.md`, `data-model.md`, `research.md` (D1–D9), `contracts/route-api.md`, `quickstart.md` (14 scenarios), `tasks.md` (43 tasks), and the project constitution (`fueling_map/.specify/memory/constitution.md`). No `.specify/extensions.yml` was present, so no analyze hooks ran.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| F1 | Inconsistency / Constitution | **CRITICAL** | `plan.md:108-114` (Delivery split) vs `tasks.md` Phases 4–9 (PR 4a–4f) | plan.md names exactly **4** PRs, with "PR 4" = `pipeline.py, view, urls, settings, README/Loom note` as one unit. tasks.md splits that into six sub-labels (4a–4f, T020–T043, ~24 tasks touching `routing/pipeline.py` and `api/views.py` repeatedly). If PR 4 is actually submitted as one PR per plan.md, it will almost certainly exceed the constitution's hard **300-changed-line cap** (root `CLAUDE.md` and this project's constitution, "Security & Development Workflow"). The two artifacts disagree on how many PRs this feature actually ships as. | Pick one: (a) amend `plan.md`'s delivery split to declare 6 real PRs matching tasks.md's 4a–4f boundaries (update "4 PRs" language and re-run the Constitution Check's PR-size row), or (b) collapse tasks.md's labels back to the literal 4 PRs and verify each stays ≤300 lines by moving some US-phase work across PR boundaries. Do this before `/speckit-implement` starts cutting PRs. |
| F2 | Inconsistency (task ordering) | HIGH | `tasks.md:85` (T022), `tasks.md:107` (T028), `tasks.md:180-181` (Dependencies) | FR-006 parsing ("City, ST" split on first comma, trim) is implemented in **T028**, phase 5 (US2) — but **T022**, phase 4 (US1b, the MVP), already needs parsed city/state strings to call `normalize_city_key` and resolve via `CityIndex`. tasks.md's own dependency note has T028 depend on T022, i.e. the MVP checkpoint requires a step scheduled two phases after it. | Move FR-006's split/trim into Phase 4 as part of T022 (or a new T022a), so the MVP can actually parse `start`/`finish`. Narrow T028 to just the *validation* additions (`SameEndpoints`, `CityNotFound` wiring/messaging) layered on already-parsed input. |
| E1 | Coverage gap | MEDIUM | `spec.md` SC-005; `tasks.md` T043 | SC-005 (cached <50 ms, uncached ≤ OSRM latency + 100 ms) has no automated test — only a manual latency note in the final quickstart run (T043). Mirrors 001's precedent (manual timing in the PR description), so not a new deviation, but it's still unverified by CI. | Optional: add a lightweight timing assertion in `tests/integration/test_route_endpoint.py` using `time.perf_counter` around a cached request if you want CI enforcement; otherwise accept manual verification, consistent with feature 001. |
| E2 | Coverage gap | MEDIUM | `spec.md` FR-002; `tasks.md` T005–T006 | FR-002 requires the data-preparation feature and the request path to use *the same* normalizer so a city can never diverge between the two. T005/T006 do the refactor and rebuild fixtures, but no task asserts cross-module identity (e.g., that `stations.pipeline` really imports the one function in `routing.normalize` rather than a copy). | Add `test_stations_pipeline_and_routing_share_the_identical_normalize_function` (assert `stations.pipeline.normalize_city_key is routing.normalize.normalize_city_key` or equivalent) to T006's scope. |
| L1 | Informational (not a defect) | LOW | `tasks.md` T041 (Phase 9) | The no-network guard lands in Polish, after Phases 3–8 already wrote respx-backed tests. Relies on respx's own interception until then. Exactly mirrors 001's tasks.md structure (`T030`), so this is consistent project convention, not a new gap. | No action required; noting for awareness only. |

## Coverage Summary Table

| Requirement Key | Has Task? | Task IDs | Notes |
|---|---|---|---|
| FR-001 shared normalizer | ✅ | T003, T004 | |
| FR-002 pipeline + request path share normalizer | ⚠️ | T005, T006 | see E2 |
| FR-003 in-memory city lookup, lazy, once | ✅ | T009, T010, T012 | |
| FR-004 concurrent build-once | ✅ | T009, T010 | |
| FR-005 fail loudly on missing/empty data | ✅ | T009, T010, T038, T039 | |
| FR-006 endpoint + "City, ST" parsing | ⚠️ | T022, T024, T028 | see F2 |
| FR-007 400 on missing/unsplittable param | ✅ | T026, T027 | |
| FR-008 404 unknown city | ✅ | T026, T027 | |
| FR-009 400 identical endpoints | ✅ | T026, T027 | |
| FR-010 one OSRM call, lon/lat, full detail | ✅ | T016, T019 | |
| FR-011 3s/10s timeouts, no retry | ✅ | T017, T019 | |
| FR-012 502/upstream-failure mapping | ✅ | T016, T019, T027 | |
| FR-013 metres→miles | ✅ | T016, T019 | |
| FR-014 polyline decode, precision 5 | ✅ | T015, T018 | |
| FR-015 24h direction-sensitive cache | ✅ | T030, T031, T032 | |
| FR-016 cache is per-worker, README notes it | ✅ | T025, T040 | |
| FR-017 hand-off fields to algorithm | ✅ | T022, T036 | |
| FR-018 ≤500mi short-circuit | ✅ | T034, T035, T036 | |
| FR-019 tests never hit real network | ✅ | T041 (+ respx throughout) | see L1 |
| SC-001 repeat request, zero calls | ✅ | T030, T031 | |
| SC-002 ≤1 call per request, all paths | ✅ | T016, T021, T027 | |
| SC-003 100% resolution incl. spelling variants | ✅ | T003, T020 | |
| SC-004 every invalid class → correct status | ✅ | T026, T027, T038 | |
| SC-005 latency bounds | ⚠️ | T043 (manual only) | see E1 |
| SC-006 ≤500mi → empty stops, $0 | ✅ | T034–T036 | |

## Constitution Alignment Issues

F1 (PR-size principle — potential conflict pending clarification of plan.md's delivery split). No other MUST-principle conflicts found; Principles I (pure routing core), IV (named exceptions, `from err` chaining tested), V (behavior-named tests, respx mocking boundary), and VI (no credentials, no auto-push) are all represented correctly in tasks.md.

## Unmapped Tasks

T002 (`routing/` package skeleton), T011/T014 (`api` app registration), T042 (lint/type/test run) — all infrastructure/process tasks with no single FR/SC, same pattern as 001's tasks.md. Not a problem.

## Metrics

- Total Requirements: 25 (19 FR + 6 SC)
- Total Tasks: 43
- Coverage: 25/25 have ≥1 task (100%); 2 flagged ⚠️ for partial/manual-only coverage (E1, E2)
- Ambiguity Count: 0
- Duplication Count: 0
- Critical Issues Count: 1 (F1)

## Next Actions

**F1 is CRITICAL and should be resolved before `/speckit-implement`** — it's a direct constitution-compliance risk (PR size), not just a documentation nit. F2 (HIGH) will cause the implementer to hit a wall at the MVP checkpoint if followed literally, so fix it too before implementing Phase 4. E1/E2 are optional hardening, not blockers.

Suggested commands:
- Manually edit `plan.md`'s Delivery split (and its Constitution-Check PR-size row) to match tasks.md's 4a–4f structure — fastest fix for F1.
- Manually edit `tasks.md` T022/T028 to move the comma-split parsing into Phase 4 — fixes F2.
- Then proceed with `/speckit-implement`.

## Remediation

Not yet drafted. If concrete diffs for F1 and F2 are wanted (the `plan.md` delivery-split rewording, and the T022/T028 re-split with a new T022a and an updated dependency line), ask for them explicitly — this report does not apply any edits.

## Resolution Log (2026-10-02)

Human decisions recorded in `analysis report answers.md`; applied as follows:

| ID | Decision | Applied in |
|---|---|---|
| F1 | Amend the constitution: the 300-line cap binds commits, not PRs, for this solo project; the agent may commit on its own with meaningful messages. Also implement suggestion (a) — declare real delivery units matching tasks.md's phase boundaries. | `fueling_map/.specify/memory/constitution.md` bumped 1.0.0 → 2.0.0 (Security & Development Workflow section, Sync Impact Report); `plan.md` Delivery split rewritten to 9 commit-sized units, one per tasks.md phase; `tasks.md` PR labels renamed `PR 1`–`PR 9` (dropping the `4a`–`4f` sub-lettering) |
| F2 | Move FR-006's split/trim into Phase 4 (T022), narrow the old T028 to validation only. | `tasks.md` renumbered: new `T022` (`_parse_endpoint`) added to Phase 4 ahead of `plan_route`; everything from the old T022 onward shifted by one (old T022→T023, …, old T043→T044); the old T028 is now `T029`, scoped to `InvalidParameter`/`SameEndpoints`/`CityNotFound` only, depending on T022 and T023 |
| E1 | Accept manual verification, consistent with feature 001. | No change — `tasks.md` T044 (was T043) still records latency manually against SC-005 |
| E2 | Add a test asserting `stations.pipeline.normalize_city_key is routing.normalize.normalize_city_key`. | `tasks.md` T006 now includes `test_stations_pipeline_and_routing_share_the_identical_normalize_function` |
| L1 | Informational; no action requested. | No change |

Status: all findings closed. Ready for `/speckit-implement` on the updated `tasks.md`.
