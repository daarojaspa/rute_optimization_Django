"""One OSRM call per uncached request: route geometry and distance (spec FR-010..FR-014;
research.md D4, D5).

Interface: ``fetch_route(start_coord, finish_coord, client) -> Route``. ``client`` is an
injected ``httpx.Client`` so tests assert the call count with respx; this module never builds
its own client or retries. ``decode_polyline`` is a small, hand-written decoder (no dependency;
research.md D5) with a golden test against OSRM's published encoding example.
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


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode an OSRM polyline string into (lat, lon) pairs in route order."""
    factor = 10**precision
    coordinates: list[tuple[float, float]] = []
    index = 0
    lat = lon = 0
    while index < len(encoded):
        delta_lat, index = _decode_signed_number(encoded, index)
        delta_lon, index = _decode_signed_number(encoded, index)
        lat += delta_lat
        lon += delta_lon
        coordinates.append((lat / factor, lon / factor))
    return coordinates


def _decode_signed_number(encoded: str, index: int) -> tuple[int, int]:
    """One signed, zigzag-encoded, base-32 varint, starting at `index`. Returns (value, next)."""
    result = 0
    shift = 0
    while True:
        byte = ord(encoded[index]) - 63
        index += 1
        result |= (byte & 0x1F) << shift
        shift += 5
        if byte < 0x20:
            break
    value = ~(result >> 1) if result & 1 else result >> 1
    return value, index


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
        "overview": "full",
        "geometries": "polyline",
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
    geometry = decode_polyline(leg["geometry"])
    total_miles = leg["distance"] / _METRES_PER_MILE
    return Route(geometry=geometry, total_miles=total_miles)
