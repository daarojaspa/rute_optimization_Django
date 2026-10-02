"""Parses, resolves and fetches a route: the orchestrator behind `GET /api/route/`.

Interface: ``plan_route(start, finish, cities, cache, http, planner=None) -> RouteResult``.
Takes the already-built CityIndex and an httpx.Client as plain arguments; no ORM, no Django
settings (Principle I). FR-006..FR-018 land here incrementally, one user story per phase: this
phase (US1b) resolves a known city pair to a real route; later phases (US2-US4) add validation,
caching and the short-trip/planner seam on top of these same two functions.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from routing.city_index import CityIndex
from routing.errors import CityNotFound, InvalidParameter, SameEndpoints
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


def plan_route(
    start: str,
    finish: str,
    cities: CityIndex,
    cache: RouteCache | None,
    http: httpx.Client,
    planner: Callable[[RouteResult], object] | None = None,
) -> RouteResult:
    """Resolve both endpoints, reject bad input, and fetch their route.

    Short-trip/planner branching (FR-017, FR-018) is layered on top by US4; this phase always
    returns an empty stop list and zero cost, which is correct for the trips tested here and
    will be replaced, not patched around, once the threshold lands.
    """
    start_city, start_state, start_coord = _resolve_endpoint(start, "start", cities)
    finish_city, finish_state, finish_coord = _resolve_endpoint(finish, "finish", cities)
    if (start_city, start_state) == (finish_city, finish_state):
        raise SameEndpoints()

    route = fetch_route(start_coord, finish_coord, http)

    return RouteResult(
        start_city=start_city,
        start_state=start_state,
        finish_city=finish_city,
        finish_state=finish_state,
        start_coord=start_coord,
        finish_coord=finish_coord,
        route=route,
        stops=[],
        total_cost=0.0,
    )
