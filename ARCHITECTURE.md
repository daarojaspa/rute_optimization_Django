### Core data flow

The API is called with a start and an end location. Both parameters are strings
drawn from the list of cities and states predefined in the `us_cities.csv`
dataset.

The orchestrator fires the process:

1. Cross-reference each string with the coordinates established in the dataset —
   not against the database directly, but against a cached view of the data, for
   performance.
2. With those coordinates, two jobs are performed:
   - Call the OSRM API with the coordinates to obtain the shortest route.
   - Prefilter every stop that is, at first glance, obviously off the route (a
     New York → New Hampshire trip does not need a stop in Texas).
3. A cached database of stops — built beforehand from a list of stops with city
   and state, cleaned and normalized, then joined with the `us_cities` dataset to
   add coordinates, and filtered in the previous step — is the input to a module
   that returns, for each station, the route mile it is nearest to, its offset,
   and how long the detour is. This module identifies the stations that are on
   the way and cherry-picks them by offset.

note : cached view means
for cities it's a coordinate lookup
CityIndex (dict keyed by (city, state));
 for stations it's a numpy array plus a spatial index:  StationIndex (arrays + KD-tree), 
 both built once per process from the DB. 


4. That list, carrying price, mile and distance-to-route attributes, is the input
   to the route-calculation module: the algorithm that selects the best prices
   along the route. It returns an array of the stops that must be made and their
   prices.
5. A final module serializes that array into the output, adding the map data and,
   for each stop, the state, city, mile and any other meaningful information,
   plus the price and the fuel added.

Proposed folder structure:

    config/            settings, urls
    stations/          Django app — data only
      models.py        Station, City
      management/commands/load_stations.py   ← module 1, runs offline
    routing/           plain Python, zero Django imports
      osrm.py          ← module 2 (HTTP client only)
      corridor.py      ← modules 3 + 4
      planner.py       ← module 5
      pricing.py       ← module 6
      pipeline.py      ← orchestrator: calls 2→3→4→5→6, returns a dataclass
    api/
      views.py         ← module 7, thin: parse → call pipeline → serialize
      serializers.py

