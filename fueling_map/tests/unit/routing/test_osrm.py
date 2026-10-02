"""Behavior spec for the OSRM client (spec FR-010..FR-014; research.md D4, D5).

No Django, no real network: every HTTP test uses respx to intercept httpx.Client.
"""

import httpx
import pytest
import respx

from routing.errors import OsrmRejected, OsrmUnavailable
from routing.osrm import decode_polyline, fetch_route

BASE_URL = "https://osrm.test"
DALLAS = (32.78, -96.80)
DENVER = (39.74, -104.99)


def _ok_response(distance_m: float = 801_300.0, geometry: str = "_p~iF~ps|U") -> dict[str, object]:
    return {"code": "Ok", "routes": [{"distance": distance_m, "geometry": geometry}]}


# --- T015: polyline golden value -------------------------------------------------------------


def test_decode_polyline_matches_published_example() -> None:
    # The example string published in OSRM/Google's polyline encoding documentation.
    assert decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@") == [
        (38.5, -120.2),
        (40.7, -120.95),
        (43.252, -126.453),
    ]


# --- T016: the one call's shape ------------------------------------------------------------


@respx.mock
def test_fetch_route_sends_coordinates_as_lon_lat() -> None:
    route = respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json=_ok_response())
    )
    with httpx.Client() as client:
        fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    request = route.calls.last.request
    assert request.url.path == "/route/v1/driving/-96.8,32.78;-104.99,39.74"


@respx.mock
def test_fetch_route_requests_full_overview_no_steps_annotations_alternatives() -> None:
    route = respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json=_ok_response())
    )
    with httpx.Client() as client:
        fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    params = route.calls.last.request.url.params
    assert params["overview"] == "full"
    assert params["geometries"] == "polyline"
    assert params["steps"] == "false"
    assert params["annotations"] == "false"
    assert params["alternatives"] == "false"


@respx.mock
def test_fetch_route_converts_metres_to_miles() -> None:
    respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json=_ok_response(distance_m=16_093.44))
    )
    with httpx.Client() as client:
        result = fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    assert result.total_miles == pytest.approx(10.0)


@respx.mock
def test_fetch_route_makes_exactly_one_call() -> None:
    route = respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json=_ok_response())
    )
    with httpx.Client() as client:
        fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    assert route.calls.call_count == 1


# --- T017: timeouts, no retry, error mapping --------------------------------------------------


@respx.mock
def test_fetch_route_uses_3s_connect_10s_read_timeout() -> None:
    route = respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json=_ok_response())
    )
    with httpx.Client() as client:
        fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout["connect"] == 3.0
    assert timeout["read"] == 10.0


@respx.mock
def test_fetch_route_does_not_retry() -> None:
    route = respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        side_effect=httpx.ConnectError("refused")
    )
    with httpx.Client() as client, pytest.raises(OsrmUnavailable):
        fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    assert route.calls.call_count == 1


@respx.mock
def test_non_ok_code_raises_OsrmRejected_with_code() -> None:
    respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json={"code": "NoRoute", "routes": []})
    )
    with httpx.Client() as client, pytest.raises(OsrmRejected) as exc_info:
        fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    assert exc_info.value.osrm_code == "NoRoute"


@respx.mock
def test_timeout_raises_OsrmUnavailable_from_err() -> None:
    respx.get(url__startswith=f"{BASE_URL}/route/v1/driving/").mock(
        side_effect=httpx.ReadTimeout("too slow")
    )
    with httpx.Client() as client, pytest.raises(OsrmUnavailable) as exc_info:
        fetch_route(DALLAS, DENVER, client, base_url=BASE_URL)

    assert isinstance(exc_info.value.__cause__, httpx.ReadTimeout)
