"""Integration test for `GET /api/route/` (quickstart scenarios 1-2; contracts/route-api.md).

Real Django test client, real `City` rows, OSRM stubbed with respx. `routing.city_index`'s
module-level cache is reset around every test so one test's seeded cities never leak into the
next.
"""

from collections.abc import Iterator

import httpx
import pytest
import respx
from django.test import Client

from routing.city_index import reset_city_index
from stations.models import City

pytestmark = pytest.mark.django_db(databases=["default", "cities"])

OSRM_URL = "https://router.project-osrm.org"


@pytest.fixture(autouse=True)
def _reset_index() -> Iterator[None]:
    reset_city_index()
    yield
    reset_city_index()


@pytest.fixture(autouse=True)
def _pin_osrm_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OSRM_BASE_URL", OSRM_URL)


def _seed_cities() -> None:
    City.objects.using("cities").create(
        city="Dallas", city_key="DALLAS", state="TX", latitude=32.78, longitude=-96.80
    )
    City.objects.using("cities").create(
        city="Denver", city_key="DENVER", state="CO", latitude=39.74, longitude=-104.99
    )


def _mock_osrm(distance_m: float = 160_934.4) -> respx.Route:
    return respx.get(url__startswith=f"{OSRM_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(
            200, json={"code": "Ok", "routes": [{"distance": distance_m, "geometry": "_p~iF~ps|U"}]}
        )
    )


@respx.mock
def test_valid_request_returns_200_with_miles_geometry_and_one_osrm_call(client: Client) -> None:
    _seed_cities()
    route = _mock_osrm(distance_m=160_934.4)  # 100 miles

    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Denver, CO"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_miles"] == pytest.approx(100.0)
    assert body["geometry"][0] == [38.5, -120.2]
    assert route.calls.call_count == 1


@respx.mock
def test_response_echoes_start_and_finish_city_state_lat_lon(client: Client) -> None:
    _seed_cities()
    _mock_osrm()

    response = client.get("/api/route/", {"start": "dallas, tx", "finish": "DENVER, co"})

    body = response.json()
    assert body["start"] == {"city": "DALLAS", "state": "TX", "lat": 32.78, "lon": -96.80}
    assert body["finish"] == {"city": "DENVER", "state": "CO", "lat": 39.74, "lon": -104.99}


# --- US2: error responses ----------------------------------------------------------------------


def test_missing_start_returns_400_naming_parameter(client: Client) -> None:
    _seed_cities()

    response = client.get("/api/route/", {"finish": "Denver, CO"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "invalid_parameter"
    assert body["detail"] == "start"


def test_value_with_no_comma_returns_400(client: Client) -> None:
    _seed_cities()

    response = client.get("/api/route/", {"start": "Dallas TX", "finish": "Denver, CO"})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_parameter"


def test_unknown_city_returns_404_echoing_parsed_city_and_state(client: Client) -> None:
    _seed_cities()

    response = client.get("/api/route/", {"start": "Nowhere, ZZ", "finish": "Denver, CO"})

    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "city_not_found"
    assert body["city_key"] == "NOWHERE"
    assert body["state"] == "ZZ"


def test_identical_endpoints_returns_400_start_and_finish_must_differ(client: Client) -> None:
    _seed_cities()

    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "dallas, tx"})

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "same_endpoints"
    assert body["detail"] == "start and finish must differ"


@respx.mock
def test_osrm_no_route_returns_502_with_osrm_code(client: Client) -> None:
    _seed_cities()
    respx.get(url__startswith=f"{OSRM_URL}/route/v1/driving/").mock(
        return_value=httpx.Response(200, json={"code": "NoRoute", "routes": []})
    )

    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Denver, CO"})

    assert response.status_code == 502
    body = response.json()
    assert body["error"] == "osrm_rejected"
    assert body["osrm_code"] == "NoRoute"


@respx.mock
def test_osrm_timeout_returns_504(client: Client) -> None:
    _seed_cities()
    respx.get(url__startswith=f"{OSRM_URL}/route/v1/driving/").mock(
        side_effect=httpx.ReadTimeout("too slow")
    )

    response = client.get("/api/route/", {"start": "Dallas, TX", "finish": "Denver, CO"})

    assert response.status_code == 504
    assert response.json()["error"] == "osrm_unavailable"
