"""Behavior spec for routing/pipeline.py (spec FR-006; data-model.md RouteResult).

`fetch_route` is mocked at this layer (strict mocking boundary, Principle V): osrm.py's own
behavior is proven in test_osrm.py.
"""

from collections.abc import Iterator

import httpx
import pytest
from pytest_mock import MockerFixture

from routing.errors import CityNotFound, InvalidParameter, SameEndpoints
from routing.osrm import Route
from routing.pipeline import RouteCache, _parse_endpoint, plan_route

CITIES = {("DALLAS", "TX"): (32.78, -96.80), ("DENVER", "CO"): (39.74, -104.99)}


@pytest.fixture
def http() -> Iterator[httpx.Client]:
    with httpx.Client() as client:
        yield client


def _stub_route() -> Route:
    return Route(geometry=[(32.78, -96.80), (39.74, -104.99)], total_miles=801.3)


class _DictCache:
    """A minimal RouteCache (get/set), standing in for Django's LocMemCache in unit tests."""

    def __init__(self) -> None:
        self.store: dict[str, Route] = {}

    def get(self, key: str) -> Route | None:
        return self.store.get(key)

    def set(self, key: str, value: Route, timeout: int) -> None:
        self.store[key] = value


class _AlwaysExpiredCache:
    """A RouteCache whose entries are always already gone -- the same observable shape a real
    TTL expiry produces, so pipeline.py needs no special-cased expiry logic of its own."""

    def get(self, key: str) -> Route | None:
        return None

    def set(self, key: str, value: Route, timeout: int) -> None:
        pass


# --- FR-006: parsing -----------------------------------------------------------------------


def test_start_and_finish_are_split_on_first_comma_and_trimmed() -> None:
    assert _parse_endpoint("  Dallas ,  TX  ") == ("Dallas", "TX")


# --- US1b: happy path ------------------------------------------------------------------------


def test_plan_route_resolves_start_and_finish_via_city_index(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())

    result = plan_route("Dallas, TX", "Denver, CO", CITIES, None, http)

    assert result.start_coord == (32.78, -96.80)
    assert result.finish_coord == (39.74, -104.99)
    fetch.assert_called_once()


def test_plan_route_passes_city_coordinates_to_fetch_route(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())

    plan_route("Dallas, TX", "Denver, CO", CITIES, None, http)

    args, _ = fetch.call_args
    assert args[0] == (32.78, -96.80)
    assert args[1] == (39.74, -104.99)


def test_plan_route_returns_geometry_in_lat_lon_order(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())

    result = plan_route("Dallas, TX", "Denver, CO", CITIES, None, http)

    assert result.route.geometry == [(32.78, -96.80), (39.74, -104.99)]


def test_equivalent_spellings_resolve_to_the_same_city(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())

    result = plan_route("dallas,  tx", "DENVER, co", CITIES, None, http)

    assert (result.start_city, result.start_state) == ("DALLAS", "TX")
    assert (result.finish_city, result.finish_state) == ("DENVER", "CO")


# --- US2: errors, before any OSRM call -------------------------------------------------------


def test_missing_or_unsplittable_param_raises_InvalidParameter(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route")

    with pytest.raises(InvalidParameter) as exc_info:
        plan_route("Dallas TX", "Denver, CO", CITIES, None, http)  # no comma

    assert exc_info.value.detail == "start"
    fetch.assert_not_called()

    with pytest.raises(InvalidParameter) as exc_info:
        plan_route("", "Denver, CO", CITIES, None, http)

    assert exc_info.value.detail == "start"


def test_equal_normalized_endpoints_raise_SameEndpoints(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route")

    cities = {**CITIES, ("SAINT LOUIS", "MO"): (0.0, 0.0)}
    with pytest.raises(SameEndpoints):
        plan_route("st. louis, mo", "Saint Louis, MO", cities, None, http)

    fetch.assert_not_called()


def test_unknown_city_raises_CityNotFound_with_parsed_key(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route")

    with pytest.raises(CityNotFound) as exc_info:
        plan_route("Nowhere, ZZ", "Denver, CO", CITIES, None, http)

    assert (exc_info.value.city_key, exc_info.value.state) == ("NOWHERE", "ZZ")
    fetch.assert_not_called()


# --- US3: cache --------------------------------------------------------------------------------


def test_second_identical_request_makes_zero_osrm_calls(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())
    cache: RouteCache = _DictCache()

    plan_route("Dallas, TX", "Denver, CO", CITIES, cache, http)
    plan_route("Dallas, TX", "Denver, CO", CITIES, cache, http)

    fetch.assert_called_once()


def test_reverse_direction_is_a_separate_cache_entry(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())
    cache: RouteCache = _DictCache()

    plan_route("Dallas, TX", "Denver, CO", CITIES, cache, http)
    plan_route("Denver, CO", "Dallas, TX", CITIES, cache, http)

    assert fetch.call_count == 2


def test_equivalent_spellings_share_one_cache_entry(
    mocker: MockerFixture, http: httpx.Client
) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())
    cache: RouteCache = _DictCache()

    plan_route("dallas,  tx", "DENVER, co", CITIES, cache, http)
    plan_route("Dallas, TX", "Denver, CO", CITIES, cache, http)

    fetch.assert_called_once()


def test_expired_cache_entry_is_refetched(mocker: MockerFixture, http: httpx.Client) -> None:
    fetch = mocker.patch("routing.pipeline.fetch_route", return_value=_stub_route())
    cache: RouteCache = _AlwaysExpiredCache()

    plan_route("Dallas, TX", "Denver, CO", CITIES, cache, http)
    plan_route("Dallas, TX", "Denver, CO", CITIES, cache, http)

    assert fetch.call_count == 2
