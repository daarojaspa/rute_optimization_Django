"""The once-per-process (city, state) -> coordinate lookup (spec FR-003, FR-004, FR-005;
data-model.md CityIndex; research.md D3).

Interface: ``get_city_index(loader)`` builds the index on the first call and returns the same
read-only dict on every later call, in this or any other process worker. ``loader`` is a plain
callable returning ``(city_key, state, lat, lon)`` rows; it is supplied by ``api/repo.py`` so
this module never imports Django or touches the ORM (Principle I). ``reset_city_index()`` exists
only for tests.
"""

import threading
from collections.abc import Callable, Iterable

from routing.errors import CitiesDataMissing

CityIndex = dict[tuple[str, str], tuple[float, float]]
CityRow = tuple[str, str, float, float]

_index: CityIndex | None = None
_lock = threading.Lock()


def get_city_index(loader: Callable[[], Iterable[CityRow]]) -> CityIndex:
    """Return the process-wide CityIndex, building it on the first call only.

    Check-lock-check: the common case (already built) takes no lock. Raises
    ``CitiesDataMissing`` if ``loader`` yields no rows at all — a missing database and an
    empty table look identical from here, and neither is ever served as an empty lookup.
    """
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        rows = list(loader())
        if not rows:
            raise CitiesDataMissing()
        _index = {(city_key, state): (lat, lon) for city_key, state, lat, lon in rows}
        return _index


def reset_city_index() -> None:
    """Clear the built index so the next call to get_city_index rebuilds it. Tests only."""
    global _index
    with _lock:
        _index = None
