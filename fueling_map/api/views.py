"""GET /api/route/: parse -> call plan_route -> serialize (Principle I, kept under 30 lines).

Error mapping (one `except RouteError` handler) is added in Phase 5 (US2); until then an
invalid request surfaces as an unhandled exception, same as any other not-yet-built phase.
"""

import httpx
from django.http import HttpRequest, JsonResponse

from api.repo import load_cities
from routing.city_index import get_city_index
from routing.pipeline import plan_route

_http_client = httpx.Client()  # module-level: one pooled client per worker process


def route_view(request: HttpRequest) -> JsonResponse:
    cities = get_city_index(load_cities)
    result = plan_route(
        request.GET.get("start", ""),
        request.GET.get("finish", ""),
        cities,
        cache=None,
        http=_http_client,
    )
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
