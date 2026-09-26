# Constitution

## Goal of the project

An API that takes as inputs a start and a finish location, both within the USA.

It returns a map of the route along with the optimal locations to fuel up along
the way — "optimal" mostly means cost-effective, based on fuel prices. The API
should return results quickly; the quicker the better.

Assume the tank has a capacity of 50 gallons and that the vehicle travels 10
miles per gallon the tank starts Full at the beggining of the trip, this fuel is not count in the total bill.
The tank must never be completely empty, for mechanical and
travel-safety reasons, so at least 1 gallon must always remain. A further fuel
reserve must be accounted for to cover detours, because of the corridor
surrounding the main route, which we define using an offset (the maximum
perpendicular distance between the route and a point off the route).

Example: with an offset of 10 miles, the detour is driven at least twice, and
with a safety factor of 1.5 the reserve must be 3.0 times the offset. This means
that if we can travel 10 miles off the route to refuel, the tank reserve is 3
gallons. Together with the 1-gallon minimum, 4 gallons are never available for
range, limiting the maximum distance between fill-ups to 460 miles.
reserve_gal   = offset_mi × detour_legs × safety_factor / mpg
unusable_gal  = reserve_gal + minimum_gal
usable_range  = (tank_gal − unusable_gal) × mpg

because dtour miles are counted in the reserve this are not counted d tour miles for fuel recharge are excluded from cumsumption.
The API returns the total money spent on fuel, together with the amount of fuel
and the money spent at each stop.

### Architecture

No templates: the API returns JSON. Rendering the map means one static HTML page
with Leaflet consuming the endpoint — optional polish, not part of the
architecture.

Models are input to the pipeline, not used by it. `routing/` receives arrays of
stations as arguments and never queries the ORM; a single repository function at
the boundary performs the query. This is what makes modules 3–5 unit-testable in
milliseconds without a database, which matters when tuning a greedy algorithm.

The view holds no logic. If `views.py` grows past roughly 30 lines, pipeline
concerns have leaked into the HTTP layer.

For more detail, see `ARCHITECTURE.md`.

### Correctness guarantees

### Correctness guarantees

- **Fuel policy.** Look-ahead: at each station, buy only enough fuel to reach the
  nearest *cheaper* station within usable range. If no cheaper station is in
  range, fill to capacity and drive to the cheapest reachable station.
- **Nearest cheaper, not cheapest.** The look-ahead target is the first station
  in range priced below the current one, never a cheaper station further along.
- **Origin tank state.** The vehicle departs with a full tank 
  
- **Terminal leg.** At the final stop the vehicle buys enough fuel to fuel the tank, fuel in thetank is fuel charged
- **Range boundary.** A station at exactly `usable_range` miles is reachable
  (`<=`).
- **Detour fuel.** 3 galons
- **Determinism.** Equal prices are broken by lower route mile, then lower
  detour, then lower OPIS ID. Identical input always yields identical output.
- **Infeasibility.** If no station lies within usable range of the current
  position, the request fails with HTTP 422 and a machine-readable reason. This
  is an expected outcome, not an error.
- **Monotonicity.** Selected stops are strictly increasing in route mile; no stop
  is visited twice.
- **Unit discipline.** Miles and US gallons throughout. Prices are USD per
  gallon, rounded only at serialization, never during computation.
- **Verification.** The planner is validated against exhaustive search on
  randomly generated small instances; the two must agree on total cost.
## Out of scope

### Authentication and authorization

This is an MVP; the API has no authorization or authentication on its endpoints.

### Limited external API calls

The API must not call the free map/routing API too often. One call is ideal; two
or three are acceptable.

### Multiple countries

Only states and cities within US territory.

## Stack

- Latest version of Django, and the Python version it entails
- `uv` for Python versions, virtual environments and dependencies
- uvicorn
- httpx
- SQLite

### Testing

- Unit tests in `pytest`, covering failure paths and edge cases, and verifying
  that the code raises the correct exceptions
- Strict mocking boundaries: `pytest-mock` / `unittest.mock` isolate network
  requests, database queries and system clocks. A test never makes a real API
  call.
- `respx`
- `mypy`
- `ruff` for formatting and linting
- PEP 8 conventions; SOLID principles

### Ops

- Docker
- Sentry

### Third-party software

- OSRM provides the route geometry.
  Documentation: https://project-osrm.org/docs/v5.24.0/api/#route-service
- No new dependency is added without a one-line written justification (in the
  plan or the commit message) explaining why the standard library is
  insufficient.

### Version control and CI/CD

- Git for version control
- GitHub best practices: feature branches, pull requests, issue management
- CI/CD via GitHub Actions

## Security

### Secrets and confidential data

- API keys, security tokens and any confidential information that represents a
  security risk MUST live in `.env` files, or in files listed in `.gitignore`.
  They are never committed.
- `settings.py` must contain the code needed to read those environment
  variables.
  ### Security limits for agents 
inside claude.md at the root 

## Philosophy of software design
- Design patterns only where they improve readability, never for their own sake.
- No single pull request changes more than **300 lines.**
- Every class and module must have a single clearly nameable responsibility. If you cannot state its reason to exist in one line it should not be a separate class or module; inline or merge it.

### Module & Interface Design
- Prefer deep modules: substantial functionality behind a small interface. A module's public surface (methods, parameters, things a caller must know) should be small relative to the implementation it hides.
- Interfaces make the common case trivial. Push special cases, configuration, and rarely-needed options behind sensible defaults, not into the signature.
- Red flag — shallow module: if a class's public interface is nearly as complex as its implementation, or it mostly forwards calls to another object, merge or deepen it.
- Red flag — information leakage: if the same design decision (a format, a schema, an assumption) appears in two modules, that's one module wearing a disguise. Consolidate.
- Split code only when it reduces total complexity — never to hit a line count. Length alone is not a reason to split.
- Every module/class states its responsibility in one sentence. If you can't, it shouldn't exist separately.

### Comments
- Comment the non-obvious. Comments exist to capture what code cannot: rationale (why), invariants, units, valid ranges, cross-module assumptions.
- Every public function/class has an interface comment describing WHAT it does and at what abstraction — never restating HOW the code works line by line.
- If a comment merely repeats the code, delete it or the code is under-abstracted.
- Prefer writing the interface comment before the implementation.

### Error Handling
- Never catch generic exceptions. `except Exception:` and bare `except:` are forbidden. Catch named exceptions only (e.g. `except KeyError:`).
- Raise specific, domain-named exceptions. When translating a lower-level error, use `raise DomainError(...) from err` to preserve the traceback.
- Aggregate handling. Prefer one handler high in the call stack that covers many failures over many small handlers scattered at each call site. A `try` should wrap the smallest span that lets a *single, meaningful* handler act — not necessarily one line.
- Before adding a handler, ask whether the error can be designed away (see Design Errors Away section).

### Design Errors Away
- Before adding an exception, ask whether the API can be defined so the condition is normal rather than exceptional. Examples: return an empty result for "not found" instead of raising; clamp or ignore an out-of-range index instead of raising.
- This never means swallowing real errors. It means fewer special cases in the interface, so callers have less to handle. Genuine, unrecoverable failures still raise (Error Handling section).
