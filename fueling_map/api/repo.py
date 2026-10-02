"""The one ORM read the request path performs (constitution Principle I).

`routing/` never touches the database; it is handed rows by a loader callable built here, at
the boundary.
"""

from collections.abc import Iterator

from django.db.utils import OperationalError

from stations.models import City


def load_cities() -> Iterator[tuple[str, str, float, float]]:
    """Yield every (city_key, state, latitude, longitude) row for routing.city_index.

    A missing cities database raises `OperationalError` from sqlite; that is caught here and
    turned into an empty result, which `get_city_index` already treats the same as an empty
    table — one `CitiesDataMissing` outcome for both causes (FR-005).
    """
    try:
        rows = list(
            City.objects.using("cities").values_list("city_key", "state", "latitude", "longitude")
        )
    except OperationalError:
        return iter(())
    return iter(rows)
