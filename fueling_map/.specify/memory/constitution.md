<!--
Sync Impact Report
Version change: 1.0.0 → 2.0.0
Modified principles: Security & Development Workflow — the 300-changed-line cap is redefined
  from a per-PR limit to a per-commit limit, resolving TODO(PR_SIZE_CONFLICT) below. A PR may
  now bundle several commits for one feature; each commit still states one logical change and
  stays under 300 lines. This project is solo-maintained, so the agent may author and make
  these commits itself with meaningful, conventional messages; pushes and PR merges still
  require human approval (Principle VI, unchanged).
Added sections: none
Removed sections: none
Resolved TODOs:
  - TODO(PR_SIZE_CONFLICT): resolved by this amendment (human decision, 2026-10-02, recorded in
    specs/002-route-orchestrator/analysis report answers.md, item F1). The cap binds commits;
    CLAUDE.md's "one logical change per PR" and this constitution's commit-level cap no longer
    describe the same unit, so there is no remaining conflict.
Open follow-up TODOs (unchanged):
  - TODO(TERMINAL_LEG): the source text for the terminal-leg rule was ambiguous ("buys enough
    fuel to fuel the tank, fuel in the tank is fuel charged"). Recorded conservatively in
    Principle II; the human must confirm exact billing at the destination.
  - TODO(CI_CONFIG): no GitHub Actions workflow exists yet; Principle V and Development
    Workflow bind once it is created.
Sources: user-supplied constitution draft (2026-09-26), CLAUDE.md, ARCHITECTURE.md; amendment
  source: specs/002-route-orchestrator/analysis-report.md (finding F1) and the human's answers
  in specs/002-route-orchestrator/analysis report answers.md (2026-10-02).
-->
# Fueling Map (Spotter) Constitution

## Purpose & Scope

An API takes a start and a finish location, both within the USA, and returns the route map
plus the cost-optimal places to fuel along the way, the fuel bought and money spent at each
stop, and the total spent. Responses MUST be fast; latency is a first-class requirement.

Vehicle model: 50 gallon tank, 10 mpg, tank full at origin (that initial fuel is not billed).
At least 1 gallon MUST always remain in the tank.

Out of scope for the MVP: authentication and authorization (endpoints are open), locations
outside US territory, and template rendering (the API returns JSON; a single static Leaflet
page is optional polish, not architecture). The free routing API MUST NOT be called often:
one call per request is ideal, three is the maximum.

## Core Principles

### I. Pure Routing Core
`routing/` is plain Python with zero Django imports and never touches the ORM. It receives
station arrays as arguments; a single repository function at the boundary performs the query.
The view holds no logic: parse → call pipeline → serialize. If `views.py` grows past roughly
30 lines, pipeline concerns have leaked into the HTTP layer. Expensive work (station
cleaning, geocoding, index building) happens offline or once per process, never per request.
Rationale: this makes modules 3–5 unit-testable in milliseconds without a database, which
matters when tuning a greedy algorithm. See `ARCHITECTURE.md`.

### II. Correctness Guarantees (NON-NEGOTIABLE)
- **Reserve and range.** `reserve_gal = offset_mi × detour_legs × safety_factor / mpg`;
  `unusable_gal = reserve_gal + minimum_gal`; `usable_range = (tank_gal − unusable_gal) × mpg`.
  Example: offset 10 mi, 2 detour legs, safety 1.5 → reserve 3 gal; with the 1 gal minimum,
  4 gal are never available, so the maximum distance between fill-ups is 460 miles.
- **Detour fuel.** Detour miles are covered by the reserve and are excluded from consumption
  and from fuel purchased.
- **Fuel policy.** Look-ahead: at each station buy only enough fuel to reach the nearest
  cheaper station within usable range. If none is in range, fill to capacity and drive to the
  cheapest reachable station.
- **Nearest cheaper, not cheapest.** The look-ahead target is the first station in range
  priced below the current one, never a cheaper one further along.
- **Origin tank state.** The vehicle departs with a full tank; that fuel is not in the bill.
- **Terminal leg.** At the final stop the vehicle refuels the tank and that fuel is charged
  (see TODO(TERMINAL_LEG) in the Sync Impact Report).
- **Range boundary.** A station at exactly `usable_range` miles is reachable (`<=`).
- **Determinism.** Equal prices are broken by lower route mile, then lower detour, then lower
  OPIS ID. Identical input MUST yield identical output.
- **Infeasibility.** If no station lies within usable range of the current position, the
  request fails with HTTP 422 and a machine-readable reason. This is an expected outcome,
  not an error.
- **Monotonicity.** Selected stops are strictly increasing in route mile; none is visited
  twice.
- **Unit discipline.** Miles and US gallons throughout. Prices are USD per gallon, rounded
  only at serialization, never during computation.
- **Verification.** The planner is validated against exhaustive search on randomly generated
  small instances; both MUST agree on total cost.

### III. Simple, Deep Modules
- Design patterns only where they improve readability, never for their own sake.
- Every class and module has one clearly nameable responsibility, stated in one sentence; if
  it cannot be, merge or inline it.
- Prefer deep modules: substantial functionality behind a small interface. The common case
  is trivial; special cases and rare options sit behind defaults, not in the signature.
- Red flag, shallow module: a public interface nearly as complex as its implementation, or a
  class that mostly forwards calls. Merge or deepen it.
- Red flag, information leakage: the same design decision (format, schema, assumption) in two
  modules is one module in disguise. Consolidate.
- Split code only to reduce total complexity, never to hit a line count.
- New interfaces or module boundaries require at least two designs with trade-offs stated;
  the human selects (trivial changes exempt).

### IV. Errors and Comments
- `except Exception:` and bare `except:` are forbidden; catch named exceptions only.
- Raise specific, domain-named exceptions; translate lower-level errors with
  `raise DomainError(...) from err`.
- Prefer one handler high in the call stack over many scattered ones; a `try` wraps the
  smallest span a single meaningful handler can act on.
- Before adding an exception, ask whether the API can make the condition normal (empty result
  for "not found", clamping) — without swallowing genuine, unrecoverable failures.
- Comments capture what code cannot: rationale, invariants, units, valid ranges, cross-module
  assumptions. Every public function/class has an interface comment stating WHAT and at what
  abstraction, ideally written before the implementation. A comment that repeats the code is
  deleted, or the code is under-abstracted.

### V. Tests as Specification
- Unit tests in `pytest` cover failure paths and edge cases, and verify that the correct
  exceptions are raised.
- Strict mocking boundaries: `pytest-mock` / `unittest.mock` isolate network, database and
  system clock; `respx` mocks httpx. A test MUST NEVER make a real API call.
- Test names state behavior (e.g. `test_missing_file_raises_ConfigNotFound`); the test file
  is the review entry point.
- `ruff` (format and lint), `mypy`, and tests MUST be green before human review.

### VI. Safety and Human Gates
The absolute prohibitions, consent-gated actions, and credential rules in the root `CLAUDE.md`
are binding and incorporated here by reference; no spec, plan, or task may override them. The
human controls all GitHub credentials, and every push and PR merge requires human approval.

## Stack & Tooling

- Latest Django and the Python version it requires; `uv` for Python versions, virtual
  environments, and dependencies; uvicorn; httpx; SQLite.
- OSRM provides route geometry (https://project-osrm.org/docs/v5.24.0/api/#route-service).
- Docker and Sentry for operations; Git with GitHub feature branches, pull requests, and
  issue management; CI/CD via GitHub Actions.
- PEP 8 and SOLID conventions.
- No new dependency without a one-line written justification (in the plan or commit message)
  explaining why the standard library is insufficient.

## Security & Development Workflow

- API keys, tokens, and any confidential data MUST live in `.env` files or files listed in
  `.gitignore` and are never committed. `settings.py` MUST read them from the environment.
- One logical change per commit; no commit changes more than 300 lines; no drive-by refactors
  or formatting noise in a commit that also touches `src/` logic. A pull request MAY bundle
  several such commits for one feature; each commit still states exactly one change and stays
  under the cap (resolves the prior PR-vs-commit ambiguity; see Sync Impact Report, v2.0.0).
- Commits follow `type(scope): summary`, body explaining why, not what. The agent may author
  and make these commits itself on this solo project, with meaningful, conventional messages.
- Every PR description states what changed, why, how it was tested, and the design
  alternative rejected.
- Work proceeds through Spec Kit (specify → plan → tasks → implement); plans include a
  Constitution Check against Principles I–VI.

## Governance

This constitution supersedes other practices. Amendments require a written change, human
approval, and a semantic version bump: MAJOR for removed or redefined principles, MINOR for
added or materially expanded guidance, PATCH for clarifications. Every PR and review MUST
verify compliance; violations are fixed or explicitly justified and approved by the human.
Complexity beyond the simplest viable design MUST be justified in the plan. `CLAUDE.md` is the
runtime guidance file and MUST NOT contradict this document.

**Version**: 2.0.0 | **Ratified**: 2026-09-26 | **Last Amended**: 2026-10-02
