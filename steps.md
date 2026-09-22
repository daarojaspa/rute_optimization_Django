Let me grab the correct current tutorial link for you.Two quick things up front: I can't see the CSV — it was attached to their email, not shared with me here. So I'll tell you what to look for when you open it. And the tutorial link is below.

**DRF tutorial:** https://www.django-rest-framework.org/tutorial/quickstart/ for setup. But for *your* task, parts **2 (Requests & Responses)** and **3 (Class-based views)** at the same site matter more — you need one `APIView`, not the viewsets/routers the Quickstart pushes. Read those two, skip the rest.

**Problem context (so the requirements stop being scary):**
The whole thing is: given a start and end city, draw the driving route, and figure out the cheapest way to buy fuel along it given a 500-mile tank and 10 mpg. That's it. "Optimal" just means: don't fill up at expensive stations if a cheaper one is still within reach of your tank. The "≤3 API calls" rule is really telling you the *architecture* — do the expensive work once, offline, not per request.

**When you open the CSV, check in 30 seconds:** Does it have latitude/longitude columns, or just addresses/city/state? If it has coordinates → great, skip geocoding. If not → you geocode once offline and cache. That single fact changes ~2 hours of work, so look first.

---

## Steps reordered by how much they decide your Loom

**Tier 1 — Own these. This IS your Loom. (~5–6 hrs)**

1. **The fuel-stop selection algorithm.** Greedy: from where you are, look at all cheap-enough stations reachable within 500 mi that lie near the route, pick the best, "drive" there, repeat. This is the one thing they're actually testing. Write it by hand. On the Loom you'll walk through *why* greedy works here and where it could fail — that sentence is what separates you from every candidate who pasted AI output.
2. **Matching stations to the route.** Deciding which stations count as "on the way" (distance from each station to the route line). Simple version is fine, but you must be able to explain your choice.
3. **The response design.** What you return and why: route geometry, chosen stops, total cost. Being able to say "I return X because the client needs Y" is senior-signal.

**Tier 2 — Make it work, delegate heavily to AI. (~5 hrs)**

4. **Routing API integration** — one call to get route geometry + distance. Use **OSRM public demo** (no API key): `router.project-osrm.org`. Let AI write the `requests` call; you just verify it's *one* call.
5. **CSV loader + geocode cache** — management command to load stations into your DB, geocode once if needed. Pure boilerplate, delegate it.
6. **Cost calc** — `total_miles / 10 = gallons`, sum price × gallons per fill-up. Trivial.
7. **Scaffold** — venv, install, startproject/startapp, one URL, one APIView. Delegate, but understand each file (this is your 3 hrs of learning, done *while* building rather than separately).

**Tier 3 — Required to submit, low thinking. (~3 hrs)**

8. **Postman test** — confirm it returns correct results.
9. **Loom (≤5 min)** — Postman working, then narrate Tier 1. Budget an hour; expect 2–3 takes.
10. **README + GitHub push** — AI writes the README from your code.

**Do first, outside all tiers:** the timing email to ena@. Nothing else counts if the window's closed.

---

Rough budget: 3 hrs learning-while-scaffolding, 5–6 on Tier 1, ~4 on the rest of the build, 3 on test/Loom/README, ~2 buffer. Fits 18 with room.

The one place people from zero stall is Tier 1, step 1. Want me to walk through that algorithm in plain terms — no code yet, just the logic — so you can write it yourself?
