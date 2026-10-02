"""Parses, resolves and fetches a route: the orchestrator behind `GET /api/route/`.

Interface: ``plan_route(start, finish, cities, cache, http, planner=None) -> RouteResult``.
Takes the already-built CityIndex and an httpx.Client as plain arguments; no ORM, no Django
settings (Principle I). Resolves both endpoints (FR-006..FR-009), fetches or reuses a cached
route (FR-015), and plans its stops: a short trip needs none, a longer one is handed to the
injected fuel-stop algorithm, not yet wired in (FR-017, FR-018).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from routing.city_index import CityIndex
from routing.errors import CityNotFound, InvalidParameter, PlannerNotAvailable, SameEndpoints
from routing.normalize import normalize_city_key
from routing.osrm import Route, fetch_route


class RouteCache(Protocol):
    """The two-method protocol `plan_route` needs; Django's cache framework satisfies it."""

    def get(self, key: str) -> Route | None: ...

    def set(self, key: str, value: Route, timeout: int) -> None: ...


@dataclass(frozen=True)
class RouteResult:
    """Everything `api/views.py` needs to answer: the resolved endpoints, route, and plan."""

    start_city: str
    start_state: str
    finish_city: str
    finish_state: str
    start_coord: tuple[float, float]
    finish_coord: tuple[float, float]
    route: Route
    stops: list[object]
    total_cost: float


def _parse_endpoint(raw: str) -> tuple[str, str]:
    """Split "City, ST" on the first comma; both halves trimmed (FR-006).

    Deliberately does not validate: a missing comma or an empty half is reported by the
    caller, where the parameter's name (`start` or `finish`) is known.
    """
    city, _, state = raw.partition(",")
    return city.strip(), state.strip()


def _resolve_endpoint(
    raw: str, param_name: str, cities: CityIndex
) -> tuple[str, str, tuple[float, float]]:
    """Parse, validate and resolve one endpoint (FR-006..FR-008).

    Raises InvalidParameter if the parameter is missing, has no comma, or either half is
    empty after trimming; CityNotFound if the normalized key is absent from the CityIndex.
    """
    city, state = _parse_endpoint(raw)
    if not city or not state:
        raise InvalidParameter(param_name)
    city_key, normalized_state = normalize_city_key(city, state)
    coord = cities.get((city_key, normalized_state))
    if coord is None:
        raise CityNotFound(city_key, normalized_state)
    return city_key, normalized_state, coord


_CACHE_TTL_SECONDS = 86400  # 24 h (FR-015)


def _cache_key(start_city: str, start_state: str, finish_city: str, finish_state: str) -> str:
    return f"route:{start_city}:{start_state}:{finish_city}:{finish_state}"


def _fetch_cached_route(
    cache: RouteCache | None,
    key: str,
    start_coord: tuple[float, float],
    finish_coord: tuple[float, float],
    http: httpx.Client,
) -> Route:
    """A cache hit costs zero OSRM calls; a miss fetches and stores (FR-015). No cache (None)
    always fetches -- used by callers (and early-phase tests) that don't need caching yet."""
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            return cached
    route = fetch_route(start_coord, finish_coord, http)
    if cache is not None:
        cache.set(key, route, _CACHE_TTL_SECONDS)
    return route


_SHORT_TRIP_MAX_MILES = 500.0  # full-tank range, 50 gal x 10 mpg (research.md D8)

Planner = Callable[[Route, tuple[float, float], tuple[float, float]], tuple[list[object], float]]


def _plan_stops(
    route: Route,
    start_coord: tuple[float, float],
    finish_coord: tuple[float, float],
    planner: Planner | None,
) -> tuple[list[object], float]:
    """Trips of 500 miles or less need no fill-up (FR-018): a full tank already covers them.

    Longer trips hand off geometry, total miles and both coordinates to the fuel-stop
    algorithm (FR-017); until that feature exists, an explicit PlannerNotAvailable is
    correct, not a silently wrong empty plan (research.md D8).
    """
    if route.total_miles <= _SHORT_TRIP_MAX_MILES:
        return [], 0.0
    if planner is None:
        raise PlannerNotAvailable()
    return planner(route, start_coord, finish_coord)


def plan_route(
    start: str,
    finish: str,
    cities: CityIndex,
    cache: RouteCache | None,
    http: httpx.Client,
    planner: Planner | None = None,
) -> RouteResult:
    """Resolve both endpoints, reject bad input, fetch their route, and plan its stops."""
    start_city, start_state, start_coord = _resolve_endpoint(start, "start", cities)
    finish_city, finish_state, finish_coord = _resolve_endpoint(finish, "finish", cities)
    if (start_city, start_state) == (finish_city, finish_state):
        raise SameEndpoints()

    key = _cache_key(start_city, start_state, finish_city, finish_state)
    route = _fetch_cached_route(cache, key, start_coord, finish_coord, http)
    stops, total_cost = _plan_stops(route, start_coord, finish_coord, planner)

    return RouteResult(
        start_city=start_city,
        start_state=start_state,
        finish_city=finish_city,
        finish_state=finish_state,
        start_coord=start_coord,
        finish_coord=finish_coord,
        route=route,
        stops=stops,
        total_cost=total_cost,
    )
