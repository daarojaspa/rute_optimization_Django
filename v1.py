def cheapest(in_range: list):
    """Return the station with the lowest retail price, or None if empty."""
    if not in_range:
        return None
    return min(in_range, key=lambda s: s["retail_price"])      
def routing(goal_mile,stations):
    position = 0, tank = 50, chosen = [], 
    RANGE_MI=490
    DONE=False
    total_cost=0
    while not DONE :
        # 1. ARRIVAL CHECK FIRST
        if goal_mile - position <= RANGE_MI:
            DONE=True
            return chosen,total_cost


        # 2. who can I still reach ahead of me?
        reachable = [s for s in stations if position < s.mile <= position + RANGE_MI]

        # 3. INFEASIBLE: nothing reachable AND goal too far
        if len(reachable) ==0:
            return f"trip can't be made bigger gap than 490 miles in mile {chosen.last().mile}"

        # 4. greedy pick + fill full
        pick = cheapest(reachable)
        fillTamk(position,pick,goal_mile)
        chosen.append(pick)
        position = pick.mile
    return chosen
def fill_the_tank (chosen):
    position=0
    fill_up=[]
    for i in chosen.itemize():
        if i+1 !=None: #if the next item exists
            if i.price<= (i+1).price :
                galons=(i.mile-position)/10
                price=i.price
                fill_up.append({galons:galons;price:price})
            else:
                galons=(i+1.mile-i.mile)/10 #what ever need it to get to chepest
                price=i.price
                fill_up.append({galons:galons;price:price})    
        else: # only one stop in route 
                galons=(i.mile-position)/10
                            price=i.price
                            fill_up.append({galons:galons;price:price})
        position=i.mile
    return fill_up
                            

            
    pass
def calculate_cost (fill_ups):
    #calculates  costs multiplieng galons per price summing them up and doing and printing a recibe 

__name__ == '__ main __'

goal_mile=1005
stations=[{id:1,mile:130,price:3},{id:2,mile:330,price:3.4},{id:3,mile:630,price:2},{id:4,mile:1003,price:4.1}]
route=routing=(goal_mile,stations)
fill_ups = fill_the_tank(route)
recipe=calculate_cost (fill_ups)
