"""Behavior spec for the once-per-process city lookup (spec FR-003, FR-004, FR-005;
data-model.md CityIndex; research.md D3). No Django, no database: the loader is a plain
callable.
"""

import threading
from collections.abc import Callable, Generator

import pytest

from routing.city_index import CityRow, get_city_index, reset_city_index
from routing.errors import CitiesDataMissing


@pytest.fixture(autouse=True)
def _reset() -> Generator[None]:
    """Every test starts from an unbuilt index; the module-level cache is otherwise global."""
    reset_city_index()
    yield
    reset_city_index()


def _loader(*rows: CityRow) -> Callable[[], list[CityRow]]:
    def load() -> list[CityRow]:
        return list(rows)

    return load


def test_lookup_returns_coordinates_for_known_key() -> None:
    index = get_city_index(_loader(("DALLAS", "TX", 32.78, -96.80)))
    assert index[("DALLAS", "TX")] == (32.78, -96.80)


def test_missing_database_raises_CitiesDataMissing_naming_build_data() -> None:
    # From the index's point of view a missing database and an empty table look identical:
    # the loader returns no rows either way (api/repo.py is where that translation happens).
    with pytest.raises(CitiesDataMissing, match="build_data"):
        get_city_index(_loader())


def test_empty_table_raises_CitiesDataMissing() -> None:
    with pytest.raises(CitiesDataMissing):
        get_city_index(_loader())


def test_concurrent_first_requests_build_the_lookup_exactly_once() -> None:
    calls = 0
    call_lock = threading.Lock()

    def counting_loader() -> list[tuple[str, str, float, float]]:
        nonlocal calls
        with call_lock:
            calls += 1
        return [("DALLAS", "TX", 32.78, -96.80)]

    threads = [threading.Thread(target=get_city_index, args=(counting_loader,)) for _ in range(32)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert calls == 1


def test_reset_city_index_allows_rebuild_in_tests() -> None:
    first = get_city_index(_loader(("DALLAS", "TX", 32.78, -96.80)))
    assert ("DENVER", "CO") not in first

    reset_city_index()

    second = get_city_index(_loader(("DENVER", "CO", 39.74, -104.99)))
    assert ("DENVER", "CO") in second
    assert ("DALLAS", "TX") not in second
