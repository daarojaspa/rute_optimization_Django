from dataclasses import dataclass
from bisect import bisect_right

TANK_GAL = 50
MPG = 10
RANGE_MI = TANK_GAL * MPG - 10  # 490 usable, 10 mi reserve


class NoStationInRangeError(Exception):
    """A gap longer than the vehicle's usable range."""


@dataclass(frozen=True)
class Station:
    name: str
    offset: float  # distance along the route from origin
    price: float  # USD per gallon
    dtour: float # perpendicular distance from the route

@dataclass(frozen=True)
class Purchase:
    station: Station
    gallons: float

    @property
    def cost(self) -> float:
        return self.gallons * self.station.price




def reachable_from(position: float, stations: list[Station]) -> list[Station]:
    """Stations strictly ahead and within usable range. Assumes sorted by offset."""
    lo = bisect_right(stations, position, key=lambda s: s.offset)
    hi = bisect_right(stations, position + RANGE_MI, key=lambda s: s.offset)
    return stations[lo:hi]

def next_stop(current_price: float, reachable: list[Station]) -> tuple[Station, str]:
    """Nearest cheaper station -> buy just enough. Otherwise fill up and go
    to the cheapest in range."""
    if not reachable:
        raise NoStationInRangeError("no station within range")

    for station in reachable:  # nearest-first
        if station.price < current_price:
            return station, "JUST_ENOUGH"

    return min(reachable, key=lambda s: s.price), "FULL_TANK"


def miles_to_buy(strategy: str, gap_mi: float, tank_mi: float) -> float:
    if strategy == "JUST_ENOUGH":
        return max(0.0, gap_mi - tank_mi)
    return RANGE_MI - tank_mi  # FULL_TANK


def plan_route(goal_mile: float, stations: list[Station]) -> list[Purchase]:
    destination = Station(name="DESTINATION", offset=goal_mile, price=0.0,dtour=0.0)
    stops = sorted(stations + [destination], key=lambda s: s.offset)

    position, tank = 0.0, float(RANGE_MI)  # full tank at origin
    here = Station(name="ORIGIN", offset=0.0, price=0.0,dtour=0.0)
    purchases: list[Purchase] = []

    while position < goal_mile:
        reachable = reachable_from(position, stops)
        if not reachable:
            raise NoStationInRangeError(
                f"gap over {RANGE_MI} mi after mile {position:.0f}"
            )

        pick, strategy = next_stop(here.price, reachable)
        gap = pick.offset- position + 2*pick.dtour
        buy_mi = miles_to_buy(strategy, gap, tank)

        if buy_mi > 0:
            purchases.append(Purchase(here, buy_mi / MPG))

        tank = tank + buy_mi - gap 
        position, here = pick.offset, pick

    return purchases
