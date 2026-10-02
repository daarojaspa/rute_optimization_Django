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
