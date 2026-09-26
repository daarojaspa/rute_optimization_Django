import pytest
from django.db.utils import OperationalError

from stations.models import City, Station

pytestmark = pytest.mark.django_db(databases=["default", "cities"])


def test_city_is_stored_in_cities_database() -> None:
    City.objects.create(city="Tomah", city_key="TOMAH", state="WI", latitude=1.0, longitude=2.0)

    assert City.objects.using("cities").count() == 1
    with pytest.raises(OperationalError):
        City.objects.using("default").count()


def test_station_is_stored_in_default_database() -> None:
    Station.objects.create(
        opis_id=1,
        name="A",
        address="B",
        city="C",
        state="WI",
        latitude=1.0,
        longitude=2.0,
        retail_price=3.0,
    )

    assert Station.objects.using("default").count() == 1
