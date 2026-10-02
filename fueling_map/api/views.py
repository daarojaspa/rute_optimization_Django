"""GET /api/route/: parse -> call plan_route -> serialize (Principle I, kept under 30 lines).

One `except RouteError` handler covers every error class contracts/route-api.md defines
(Principle IV): the status and `error` code are carried on the exception itself; only
CityNotFound and OsrmRejected add extra fields to the body.
"""

import httpx
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse

from api.repo import load_cities
from routing.city_index import get_city_index
from routing.errors import CityNotFound, OsrmRejected, RouteError
from routing.pipeline import plan_route

_http_client = httpx.Client()  # module-level: one pooled client per worker process


def route_view(request: HttpRequest) -> JsonResponse:
    try:
        cities = get_city_index(load_cities)
        result = plan_route(
            request.GET.get("start", ""),
            request.GET.get("finish", ""),
            cities,
            cache=cache,
            http=_http_client,
        )
    except RouteError as err:
        return JsonResponse(_error_body(err), status=err.status)

    return JsonResponse(
        {
            "start": _endpoint(result.start_city, result.start_state, result.start_coord),
            "finish": _endpoint(result.finish_city, result.finish_state, result.finish_coord),
            "total_miles": result.route.total_miles,
            "geometry": result.route.geometry,
            "stops": result.stops,
            "total_cost": result.total_cost,
        }
    )


def _endpoint(city: str, state: str, coord: tuple[float, float]) -> dict[str, object]:
    return {"city": city, "state": state, "lat": coord[0], "lon": coord[1]}


def _error_body(err: RouteError) -> dict[str, object]:
    body: dict[str, object] = {"error": err.code, "detail": err.detail}
    if isinstance(err, CityNotFound):
        body["city_key"] = err.city_key
        body["state"] = err.state
    elif isinstance(err, OsrmRejected):
        body["osrm_code"] = err.osrm_code
    return body
