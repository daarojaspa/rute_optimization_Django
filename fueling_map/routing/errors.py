"""Domain exceptions for the route lookup and orchestration request path (spec data-model.md).

Each `RouteError` carries its own HTTP `status` as plain data, so `routing/` stays free of
Django and the view (api/views.py) can map any of them with one `except RouteError` handler
(constitution Principle IV: one handler high in the stack, named exceptions only).
"""


class RouteError(Exception):
    """Base for every error the request path can raise. Carries the HTTP status to report."""

    status: int = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidParameter(RouteError):
    """`start`/`finish` is missing or has no comma (FR-007). `detail` names the parameter."""

    status = 400


class SameEndpoints(RouteError):
    """Start and finish normalize to the same city (FR-009)."""

    status = 400

    def __init__(self) -> None:
        super().__init__("start and finish must differ")


class CityNotFound(RouteError):
    """The parsed (city_key, state) is absent from the CityIndex (FR-008)."""

    status = 404

    def __init__(self, city_key: str, state: str) -> None:
        super().__init__(f"city not found: {city_key}, {state}")
        self.city_key = city_key
        self.state = state


class OsrmRejected(RouteError):
    """OSRM answered with a non-"Ok" code, e.g. NoRoute (FR-012)."""

    status = 502

    def __init__(self, osrm_code: str) -> None:
        super().__init__(f"routing service rejected the request: {osrm_code}")
        self.osrm_code = osrm_code


class OsrmUnavailable(RouteError):
    """OSRM timed out or was unreachable; never retried (FR-011, FR-012)."""

    status = 504

    def __init__(self) -> None:
        super().__init__("routing service is unavailable")


class CitiesDataMissing(RouteError):
    """The cities database is absent or empty (FR-005). Never served from an empty lookup."""

    status = 503

    def __init__(self) -> None:
        super().__init__("cities data has not been built; run `manage.py build_data` first")


class PlannerNotAvailable(RouteError):
    """The trip is over 500 miles but no fuel-stop algorithm is wired in yet (research.md D8)."""

    status = 501

    def __init__(self) -> None:
        super().__init__("the fuel-stop planner is not available yet")
