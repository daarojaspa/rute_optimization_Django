"""One OSRM call per uncached request: route geometry and distance (spec FR-010..FR-014;
research.md D4, D5).

Interface: ``fetch_route(start_coord, finish_coord, client) -> Route``. ``client`` is an
injected ``httpx.Client`` so tests assert the call count with respx; this module never builds
its own client or retries. Geometry is requested as GeoJSON (``overview=simplified``), so
vertices arrive as ``[lon, lat]`` pairs and are flipped to ``(lat, lon)``; no polyline decoding.
"""

import os
from dataclasses import dataclass

import httpx

from routing.errors import OsrmRejected, OsrmUnavailable

_DEFAULT_BASE_URL = "https://router.project-osrm.org"
# 3 s to connect, 10 s to read; never retried (FR-011).
_TIMEOUT = httpx.Timeout(10.0, connect=3.0)
_METRES_PER_MILE = 1609.344


@dataclass(frozen=True)
class Route:
    """The cached value: geometry in travel order, total distance in miles."""

    geometry: list[tuple[float, float]]
    total_miles: float


def fetch_route(
    start_coord: tuple[float, float],
    finish_coord: tuple[float, float],
    client: httpx.Client,
    base_url: str | None = None,
) -> Route:
    """One GET to OSRM's driving-route endpoint; raises on rejection or transport failure."""
    base = base_url or os.environ.get("OSRM_BASE_URL", _DEFAULT_BASE_URL)
    start_lat, start_lon = start_coord
    finish_lat, finish_lon = finish_coord
    url = f"{base}/route/v1/driving/{start_lon},{start_lat};{finish_lon},{finish_lat}"
    params = {
        "overview": "simplified",
        "geometries": "geojson",
        "steps": "false",
        "annotations": "false",
        "alternatives": "false",
    }
    try:
        response = client.get(url, params=params, timeout=_TIMEOUT)
    except (httpx.TimeoutException, httpx.TransportError) as err:
        raise OsrmUnavailable() from err

    body = response.json()
    code = body["code"]
    if code != "Ok":
        raise OsrmRejected(code)

    leg = body["routes"][0]
    # GeoJSON coordinates are [lon, lat]; the rest of the codebase uses (lat, lon).
    geometry = [(lat, lon) for lon, lat in leg["geometry"]["coordinates"]]
    total_miles = leg["distance"] / _METRES_PER_MILE
    return Route(geometry=geometry, total_miles=total_miles)
