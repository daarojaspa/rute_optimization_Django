### Phase 0 — cumulative distance calculator

A module that receives an ordered list of `(lat, lon)` tuples (the route geometry
returned by OSRM with `overview=simplified`, on the order of hundreds of points)
and produces the cumulative distance in miles from the origin to each point.

Distance between two consecutive points uses the **haversine formula**, which
measures great-circle distance on a sphere and is correct at any latitude:

    R_MI = 3958.8                      # mean Earth radius in miles
    φ1, φ2 = radians(lat1), radians(lat2)
    Δφ     = φ2 - φ1
    Δλ     = radians(lon2 - lon1)

    a = sin²(Δφ / 2) + cos(φ1) * cos(φ2) * sin²(Δλ / 2)
    d = 2 * R_MI * asin(sqrt(a))

Planar distance on raw lat/lon is not acceptable here: a degree of longitude is
only ~0.77 of a degree of latitude at 40°N, so an unscaled planar formula is off
by roughly 25% on east-west legs. Haversine is used rather than a cosine-scaled
planar approximation because the point count is in the hundreds, not thousands,
so the extra trig cost is irrelevant and no approximation needs defending.

The module exposes:

- `cumulative[i]` — miles from origin to geometry point `i`, with `cumulative[0] = 0`
- `total_miles`   — equal to `cumulative[-1]`

This object is consumed by phase 1 (box placement and station offsets) and
phase 3 (route planning).

**Note on accuracy:** because the geometry is simplified, summed haversine
distance slightly underestimates true road distance (simplification cuts
corners). OSRM returns an authoritative `routes[0].distance` in the same
response; the module compares its own total against that value after transforming it from meters (default unit) to miles and scales the
cumulative array by the ratio so that offsets line up with real road miles.

### phase 1 bounding boxes around the route,
because the number of boxes  impluves the acuracy of the filtering of the  stations in route, we will start with a resolution of 50 miles so total cumulative distance  devided between 50 will be the least amount of boxes needed, this boxes will be place  along the route every resolution miles, and the array of stations will be filter to see wichones  are inside at least one of the boxes.

n_boxes = clamp(ceil(total_miles / 50), 1, 200)
box_length= resolution *1.1
box_with = box_length*0.25

with the stations that are inside of the boxes  2 distances will be calculated:  offset, how far along the route is the station  and  a dtour distance that will be the distance that is perpendicular to the route, this will be new atributes to the  stations , and an array of stations will be created and sorted by offset distance, then if any 2 stations have the same offset, dtour and price it will be asume that they are duplicates and one of them will be delete it, the output of this phase . the out put will be list[station,offset,dtour,price]
for float comparations  sabe in data base only 2 decimals after the point for all floats. and math.isclose for comparations with absolute tolerance of 0.001

### phase 3  planning the route 
the output of the phase 2  should be input for this phase wich is mainly stated in main branch  v2.py  that is the second draft of the algorithm ther eyou could find
there the starting conditions of the trip are set , then  a custumm exeption for when  the trip cant be made,
then the data models of station and purchase are defined,then a function that helps deciding if an station is reachable and a function that, then next stop  helps deciding the strategy that will be use to fill up the tank using a strategy pattern
and a function that decides  how much to fill the tank with acording to the strategy. then the plan route function as you can see this second draft sorted the stations by  offset, but becouse  this was already done in previus phases this could be skiped in your implementation, 

### phase 4 calculate cost function 
this function will calculate the cost of the  
fill ups  an write a detail recipe  in a json format and handle it to the api  to send it back to the client that gave the request, not only stating price but  start and end  of the trip, stops  amount of fuel recharged,  and number of stops taking as input the purchases list of the previus phases. money will be  converted to decimals to do the money calculations 