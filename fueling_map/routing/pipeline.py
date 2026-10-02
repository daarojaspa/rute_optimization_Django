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


def plan_route(
    start: str,
    finish: str,
    cities: CityIndex,
    cache: RouteCache | None,
    http: httpx.Client,
    planner: Callable[[RouteResult], object] | None = None,
) -> RouteResult:
    """Resolve both endpoints and fetch their route.

    Short-trip/planner branching (FR-017, FR-018) is layered on top by US4; this phase always
    returns an empty stop list and zero cost, which is correct for the trips tested here and
    will be replaced, not patched around, once the threshold lands.
    """
    start_city, start_state = _parse_endpoint(start)
    finish_city, finish_state = _parse_endpoint(finish)
    start_key = normalize_city_key(start_city, start_state)
    finish_key = normalize_city_key(finish_city, finish_state)

    start_coord = cities[start_key]
    finish_coord = cities[finish_key]

    route = fetch_route(start_coord, finish_coord, http)

    return RouteResult(
        start_city=start_key[0],
        start_state=start_key[1],
        finish_city=finish_key[0],
        finish_state=finish_key[1],
        start_coord=start_coord,
        finish_coord=finish_coord,
        route=route,
        stops=[],
        total_cost=0.0,
    )
