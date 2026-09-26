"""Turns raw fuel-price and US-cities rows into clean, located stations.

Interface: ``build(fuel_rows, city_rows, fail_under)`` takes rows as dicts (as produced by
``csv.DictReader``) and returns a ``BuildResult``. It is pure: no files, no database, no
network, no clock, so identical input always gives identical output.

Processing order (spec FR-003..FR-011): normalize, drop bad prices, drop non-US states,
deduplicate stations by OPIS ID, collapse cities, join on (city key, state), spread stations
that share a city, then enforce the match-rate gate.
"""

import hashlib
import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 50 states plus DC. Canadian provinces and US territories present in the fuel file are dropped.
US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
MAX_PRICE = 10.00  # USD per gallon; anything above is treated as bad data
# Closed list of token expansions for the matching key (spec FR-004). Bare "MT" is NOT expanded.
_TOKEN_EXPANSIONS = {"ST.": "SAINT", "ST": "SAINT", "FT.": "FORT", "FT": "FORT", "MT.": "MOUNT"}
# Spread same-city stations by at most 5 miles; 4.9 leaves margin for the flat-earth conversion.
_MAX_SHIFT_MILES = 4.9
_MILES_PER_DEGREE_LAT = 69.0
_MILES_PER_DEGREE_LON_AT_EQUATOR = 69.17
_SPREAD_WARN_MILES = 50.0

_FUEL_COLUMNS = ("OPIS Truckstop ID", "Truckstop Name", "Address", "City", "State", "Retail Price")
_CITY_COLUMNS = ("CITY", "STATE_CODE", "LATITUDE", "LONGITUDE")


class DataBuildError(Exception):
    """Input data cannot produce a station table (bad columns, no surviving stations, ...)."""


class MatchRateTooLow(DataBuildError):
    """The share of stations matched to a city is below the requested threshold."""

    def __init__(self, result: "BuildResult", fail_under: float) -> None:
        super().__init__(
            f"match rate {result.stats.match_rate:.4f} is below --fail-under {fail_under}"
        )
        self.result = result


@dataclass(frozen=True)
class StationRecord:
    """A deduplicated, located station. Prices are USD per gallon; coordinates are degrees."""

    opis_id: int
    name: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    retail_price: float


@dataclass(frozen=True)
class CityRecord:
    city: str
    city_key: str
    state: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class UnmatchedStation:
    name: str
    city: str
    state: str


@dataclass(frozen=True)
class BuildStats:
    rows_read: int = 0
    dropped_bad_price: int = 0
    dropped_state: dict[str, int] = field(default_factory=dict)
    stations: int = 0  # distinct stations after cleaning and deduplication
    rows_collapsed: int = 0  # duplicate rows removed by deduplication
    groups_collapsed: int = 0  # OPIS IDs that had more than one row
    city_rows_read: int = 0
    city_rows_collapsed: int = 0
    matched: int = 0
    unmatched: int = 0
    match_rate: float = 0.0


@dataclass(frozen=True)
class BuildResult:
    stations: list[StationRecord]  # matched stations only, ascending opis_id
    cities: list[CityRecord]  # one per (city_key, state), sorted
    unmatched: list[UnmatchedStation]
    stats: BuildStats


@dataclass(frozen=True)
class _Row:
    opis_id: int
    name: str
    address: str
    city: str
    key: str
    state: str
    price: float


def build(
    fuel_rows: list[dict[str, str]], city_rows: list[dict[str, str]], fail_under: float = 0.95
) -> BuildResult:
    """Clean, deduplicate, locate and spread stations; raise MatchRateTooLow below the gate.

    ``MatchRateTooLow.result`` carries the full result so callers can still report unmatched
    stations. Raises DataBuildError for missing columns or when no station survives cleaning.
    """
    _require_columns(fuel_rows, _FUEL_COLUMNS, "fuel")
    _require_columns(city_rows, _CITY_COLUMNS, "cities")

    kept, dropped_price, dropped_state = _clean_stations(fuel_rows)
    stations, groups_collapsed = _dedupe_stations(kept)
    if not stations:
        raise DataBuildError("no stations survived cleaning")

    cities = _collapse_cities(city_rows)
    located, unmatched = _join_and_spread(stations, cities)

    stats = BuildStats(
        rows_read=len(fuel_rows),
        dropped_bad_price=dropped_price,
        dropped_state=dict(sorted(dropped_state.items())),
        stations=len(stations),
        rows_collapsed=len(kept) - len(stations),
        groups_collapsed=groups_collapsed,
        city_rows_read=len(city_rows),
        city_rows_collapsed=len(city_rows) - len(cities),
        matched=len(located),
        unmatched=len(unmatched),
        match_rate=len(located) / len(stations),
    )
    result = BuildResult(
        stations=located,
        cities=sorted(cities.values(), key=lambda c: (c.state, c.city_key)),
        unmatched=unmatched,
        stats=stats,
    )
    if stats.match_rate < fail_under:
        raise MatchRateTooLow(result, fail_under)
    return result


# --- normalization ---------------------------------------------------------------------------


def _collapse_ws(text: str) -> str:
    return " ".join(text.split())


def _display_city(text: str) -> str:
    return _collapse_ws(text).title()


def _city_key(display: str) -> str:
    return " ".join(_TOKEN_EXPANSIONS.get(t, t) for t in display.upper().split())


def _require_columns(rows: list[dict[str, str]], columns: tuple[str, ...], label: str) -> None:
    if not rows:
        return
    missing = [c for c in columns if c not in rows[0]]
    if missing:
        raise DataBuildError(f"{label} data is missing required column(s): {', '.join(missing)}")


def _parse_price(text: str | None) -> float | None:
    """Price as float, or None when it is empty, non-numeric, non-positive or above MAX_PRICE."""
    try:
        value = float((text or "").strip())
    except ValueError:
        return None
    if math.isnan(value) or not 0 < value <= MAX_PRICE:
        return None
    return value


# --- stations --------------------------------------------------------------------------------


def _clean_stations(rows: list[dict[str, str]]) -> tuple[list[_Row], int, dict[str, int]]:
    kept: list[_Row] = []
    dropped_price = 0
    dropped_state: dict[str, int] = defaultdict(int)
    for raw in rows:
        price = _parse_price(raw["Retail Price"])
        if price is None:
            dropped_price += 1
            continue
        state = raw["State"].strip().upper()
        if state not in US_STATES:
            dropped_state[state] += 1
            continue
        try:
            opis_id = int(raw["OPIS Truckstop ID"].strip())
        except ValueError as err:
            raise DataBuildError(
                f"invalid OPIS Truckstop ID: {raw['OPIS Truckstop ID']!r}"
            ) from err
        display = _display_city(raw["City"])
        kept.append(
            _Row(
                opis_id=opis_id,
                name=_collapse_ws(raw["Truckstop Name"]),
                address=_collapse_ws(raw["Address"]),
                city=display,
                key=_city_key(display),
                state=state,
                price=price,
            )
        )
    return kept, dropped_price, dropped_state


def _dedupe_stations(rows: list[_Row]) -> tuple[list[_Row], int]:
    """One row per OPIS ID: the lowest-priced row, first in file order on ties."""
    best: dict[int, _Row] = {}
    counts: dict[int, int] = defaultdict(int)
    for row in rows:
        counts[row.opis_id] += 1
        current = best.get(row.opis_id)
        if current is None or row.price < current.price:
            best[row.opis_id] = row
    groups_collapsed = sum(1 for n in counts.values() if n > 1)
    return [best[i] for i in sorted(best)], groups_collapsed


# --- cities ----------------------------------------------------------------------------------


def _collapse_cities(rows: list[dict[str, str]]) -> dict[tuple[str, str], CityRecord]:
    """One city per (key, state): the largest-population row if the file has one, else the first."""
    groups: dict[tuple[str, str], list[tuple[float, CityRecord]]] = defaultdict(list)
    for raw in rows:
        display = _display_city(raw["CITY"])
        state = raw["STATE_CODE"].strip().upper()
        try:
            lat, lon = float(raw["LATITUDE"]), float(raw["LONGITUDE"])
        except ValueError as err:
            raise DataBuildError(f"invalid coordinates for city {display!r}, {state}") from err
        population = _parse_population(raw.get("POPULATION"))
        record = CityRecord(display, _city_key(display), state, round(lat, 6), round(lon, 6))
        groups[(record.city_key, state)].append((population, record))

    cities: dict[tuple[str, str], CityRecord] = {}
    for key, members in groups.items():
        chosen = max(members, key=lambda m: m[0])[1]  # max() keeps the first on ties
        cities[key] = chosen
        _warn_if_spread(key, [m[1] for m in members])
    return cities


def _parse_population(text: str | None) -> float:
    try:
        return float((text or "").strip())
    except ValueError:
        return -1.0


def _warn_if_spread(key: tuple[str, str], members: list[CityRecord]) -> None:
    widest = max((_miles_between(a, b) for a in members for b in members), default=0.0)
    if widest > _SPREAD_WARN_MILES:
        logger.warning("city %s, %s has rows %.0f miles apart; using the chosen row", *key, widest)


def _miles_between(a: CityRecord, b: CityRecord) -> float:
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat, dlon = lat2 - lat1, math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3959 * 2 * math.asin(math.sqrt(h))


# --- join and spread -------------------------------------------------------------------------


def _join_and_spread(
    stations: list[_Row], cities: dict[tuple[str, str], CityRecord]
) -> tuple[list[StationRecord], list[UnmatchedStation]]:
    located: list[StationRecord] = []
    unmatched: list[UnmatchedStation] = []
    seen_city: set[tuple[str, str]] = set()
    for row in stations:  # ascending opis_id, so the first station seen per city is its lowest
        key = (row.key, row.state)
        found = cities.get(key)
        if found is None:
            unmatched.append(UnmatchedStation(row.name, row.city, row.state))
            continue
        lat, lon = found.latitude, found.longitude
        if key in seen_city:
            lat, lon = _shifted(row.opis_id, lat, lon)
        seen_city.add(key)
        located.append(
            StationRecord(
                row.opis_id, row.name, row.address, row.city, row.state, lat, lon, row.price
            )
        )
    return located, unmatched


def _shifted(opis_id: int, lat: float, lon: float) -> tuple[float, float]:
    """Deterministically move a point up to _MAX_SHIFT_MILES, derived only from opis_id."""
    digest = hashlib.sha256(str(opis_id).encode()).digest()
    angle = 2 * math.pi * int.from_bytes(digest[:4], "big") / 2**32
    distance = _MAX_SHIFT_MILES * int.from_bytes(digest[4:8], "big") / 2**32
    dlat = distance * math.sin(angle) / _MILES_PER_DEGREE_LAT
    dlon = (
        distance
        * math.cos(angle)
        / (_MILES_PER_DEGREE_LON_AT_EQUATOR * math.cos(math.radians(lat)))
    )
    return round(lat + dlat, 6), round(lon + dlon, 6)
