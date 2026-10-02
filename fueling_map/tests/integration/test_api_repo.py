"""api/repo.py::load_cities is the one ORM read the request path performs (Principle I)."""

import pytest

from api.repo import load_cities
from stations.models import City

pytestmark = pytest.mark.django_db(databases=["default", "cities"])


def test_load_cities_returns_rows_from_cities_database() -> None:
    City.objects.using("cities").create(
        city="Dallas", city_key="DALLAS", state="TX", latitude=32.78, longitude=-96.80
    )

    rows = list(load_cities())

    assert rows == [("DALLAS", "TX", 32.78, -96.80)]


def test_load_cities_returns_empty_list_when_table_is_empty() -> None:
    assert list(load_cities()) == []
