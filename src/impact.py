"""What is actually inside the red zone, and what stops working when it goes.

A hazard map says a place is dangerous. That is the easy half. The half that
decides whether anyone acts is the next line: how many people are behind the
break, which road was the only road, and whether the hospital is now on the
far side of it.

This module answers that from real geometry rather than from a diagram. The
road network is OpenStreetMap's, collapsed to a routable graph of 492,257
junctions and 560,385 edges; the settlements, hospitals and power assets are
OSM's too. A hazard is a point and a radius. Everything follows:

    1. every road edge whose geometry passes through the zone is cut
    2. every asset inside the zone is directly exposed
    3. for every settlement within reach, the shortest path to its nearest
       hospital is computed twice -- with the network intact and with those
       edges removed

and the difference between those two numbers is the thing worth reporting.
A village that gains four kilometres of detour is an inconvenience. A village
whose path does not exist any more is a helicopter.

This is also the dependency engine: the chain is road -> settlement ->
hospital, and it is evaluated rather than drawn, so when a single edge carries
three villages' only access, that falls out of the shortest-path result
instead of having to be asserted.
"""

import heapq
import json
import math
import os
import pickle

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

GRAPH_PATH = os.path.join(_ROOT, "data/processed/road_graph.pkl")
ASSET_PATH = os.path.join(_ROOT, "data/geo/infrastructure.json")

# A landslide closes a road over tens of metres, not kilometres. 500 m covers
# a normal scarp-to-toe run-out plus the stretch either side that gets buried
# or undercut. It was 1.5 km first, which in Gangtok's switchbacks cut 41 km
# of road from one slide -- arithmetically true and operationally absurd.
DEFAULT_RADIUS_KM = 0.5
SEARCH_KM = 45.0          # how far around the hazard to bother routing
# Most settlements are not on a junction. This is how far a settlement may sit
# from the nearest graph node before it is treated as off-network.
SNAP_KM = 6.0

_graph = None
_assets = None


def available():
    return os.path.exists(GRAPH_PATH)


def graph():
    global _graph
    if _graph is None:
        with open(GRAPH_PATH, "rb") as f:
            _graph = pickle.load(f)
    return _graph


def assets():
    global _assets
    if _assets is None:
        if os.path.exists(ASSET_PATH):
            _assets = json.load(open(ASSET_PATH))["assets"]
        else:
            _assets = []
    return _assets


# --------------------------------------------------------------------------
# geometry

def _km(lon1, lat1, lon2, lat2):
    p = math.pi / 180
    x = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p)
         * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(max(x, 0.0)))


def _cells(lat, lon, km, cell):
    """Grid cells covering a circle, in the graph's own cell size."""
    dlat = km / 110.574
    dlon = km / (111.320 * math.cos(math.radians(lat)) or 1e-6)
    out = []
    y0 = int(math.floor((lat - dlat) / cell))
    y1 = int(math.floor((lat + dlat) / cell))
    x0 = int(math.floor((lon - dlon) / cell))
    x1 = int(math.floor((lon + dlon) / cell))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            out.append((x, y))
    return out


def _edges_near(lat, lon, km):
    g = graph()
    idxs = set()
    for c in _cells(lat, lon, km, g["cell"]):
        idxs.update(g["grid"].get(c, ()))
    return idxs


def _edge_min_km(edge, lat, lon):
    """Closest approach of an edge's polyline to a point."""
    return min(_km(lon, lat, p[0], p[1]) for p in edge["geom"])


# --------------------------------------------------------------------------
# routing

def _subgraph(lat, lon, km):
    """Adjacency for everything within km of the hazard, built per query.

    Built fresh rather than cached because a country-wide adjacency is 560,385
    edges of dictionary and the question is always local.
    """
    g = graph()
    adj = {}
    keep = {}
    for i in _edges_near(lat, lon, km):
        e = g["edges"][i]
        keep[i] = e
        adj.setdefault(e["a"], []).append((e["b"], e["m"], i))
        adj.setdefault(e["b"], []).append((e["a"], e["m"], i))
    return adj, keep


def _nearest_node(adj, lat, lon, limit_km=SNAP_KM):
    g = graph()
    best, bestd = None, limit_km
    for nid in adj:
        p = g["nodes"].get(nid)
        if not p:
            continue
        d = _km(lon, lat, p[0], p[1])
        if d < bestd:
            best, bestd = nid, d
    return best, bestd


def _dijkstra(adj, src, blocked=frozenset(), targets=None, cap_m=250000):
    """Shortest road distance from src, optionally with edges removed."""
    dist = {src: 0.0}
    seen = set()
    pq = [(0.0, src)]
    found = {}
    want = set(targets or ())
    while pq:
        d, u = heapq.heappop(pq)
        if u in seen:
            continue
        seen.add(u)
        if u in want:
            found[u] = d
            want.discard(u)
            if not want and targets is not None:
                break
        if d > cap_m:
            continue
        for v, w, ei in adj.get(u, ()):
            if ei in blocked or v in seen:
                continue
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return found if targets is not None else dist


# --------------------------------------------------------------------------
# the question

def impact(lat, lon, radius_km=DEFAULT_RADIUS_KM, search_km=SEARCH_KM,
           max_settlements=40):
    """Everything the red zone contains, and everything it disconnects."""
    if not available():
        return {"error": "road graph not built",
                "fix": "python scripts/build_road_graph.py"}

    g = graph()
    adj, local = _subgraph(lat, lon, search_km)

    # --- 1. roads cut -------------------------------------------------
    cut, cut_m, by_cls = set(), 0.0, {}
    for i, e in local.items():
        if _edge_min_km(e, lat, lon) <= radius_km:
            cut.add(i)
            cut_m += e["m"]
            by_cls[e["cls"]] = by_cls.get(e["cls"], 0) + 1

    # --- 2. what is inside the zone ----------------------------------
    inside, nearby = [], []
    for a in assets():
        d = _km(lon, lat, a["lon"], a["lat"])
        if d <= radius_km:
            inside.append(dict(a, km=round(d, 2)))
        elif d <= search_km:
            nearby.append((d, a))
    nearby.sort(key=lambda t: t[0])

    # Villages first: a town is its own service centre and routing it to
    # itself answers nothing.
    villages = [a for d, a in nearby if a["kind"] == "settlement"
                and a.get("place") not in ("town", "city")]
    settlements = villages[:max_settlements]
    hospitals = [a for d, a in nearby if a["kind"] == "hospital"][:25]
    power = [a for d, a in nearby if a["kind"] == "power"][:10]

    # --- 3. who loses their road -------------------------------------
    #
    # Routing to hospitals alone was the first design and it does not survive
    # contact with the data: GeoNames lists two hospitals in the whole
    # North-East, and Overpass, which has hundreds, answers this workload with
    # 429s. So the target is a service centre -- a hospital where one is
    # recorded, otherwise a town or city, otherwise any settlement of five
    # thousand or more. That is where the hospital, the market, the block
    # office and the fuel are, and it is what a village loses when the road
    # goes. Which kind of centre was actually used is reported, because
    # "cut off from a town" and "cut off from a hospital" are different
    # claims and the reader is entitled to know which one is being made.
    centres = list(hospitals)
    seen_ids = {h["id"] for h in centres}
    for d, a in nearby:
        if a["id"] in seen_ids or a["kind"] != "settlement":
            continue
        if a.get("place") in ("town", "city") or (a.get("population") or 0) >= 5000:
            centres.append(a)
            seen_ids.add(a["id"])
        if len(centres) >= 30:
            break
    centre_kind = ("hospital" if hospitals and len(hospitals) >= len(centres) / 2
                   else "town or large settlement")

    hosp_nodes = {}
    for h in centres:
        n, _ = _nearest_node(adj, h["lat"], h["lon"])
        if n is not None:
            hosp_nodes.setdefault(n, h)

    isolated, detoured, fine = [], [], 0
    if hosp_nodes:
        for s in settlements:
            n, snap = _nearest_node(adj, s["lat"], s["lon"])
            if n is None:
                continue
            before = _dijkstra(adj, n, targets=set(hosp_nodes))
            if not before:
                continue
            b_node = min(before, key=before.get)
            b_km = before[b_node] / 1000.0
            after = _dijkstra(adj, n, blocked=cut, targets=set(hosp_nodes))
            row = {"name": s["name"] or s["id"], "place": s["place"],
                   "lat": s["lat"], "lon": s["lon"],
                   "population": s["population"],
                   "centre": hosp_nodes[b_node]["name"] or "nearest centre",
                   "centre_kind": hosp_nodes[b_node]["kind"],
                   "before_km": round(b_km, 1)}
            if not after:
                row["after_km"] = None
                isolated.append(row)
            else:
                a_km = min(after.values()) / 1000.0
                row["after_km"] = round(a_km, 1)
                row["extra_km"] = round(a_km - b_km, 1)
                if row["extra_km"] > 0.5:
                    detoured.append(row)
                else:
                    fine += 1
        isolated.sort(key=lambda r: -(r["population"] or 0))
        detoured.sort(key=lambda r: -r["extra_km"])

    people_isolated = sum(r["population"] or 0 for r in isolated)
    return {
        "at": {"lat": lat, "lon": lon, "radius_km": radius_km},
        "roads": {"segments_cut": len(cut), "km_cut": round(cut_m / 1000.0, 2),
                  "by_class": by_cls},
        "inside": inside,
        "counts": {"settlements_checked": len(settlements),
                   "centres_in_range": len(centres),
                   "hospitals_in_range": len(hospitals),
                   "power_assets": len(power),
                   "isolated": len(isolated), "detoured": len(detoured),
                   "unaffected": fine},
        "isolated": isolated[:12],
        "detoured": detoured[:12],
        "people_isolated": people_isolated,
        "power": [dict(a, km=round(_km(lon, lat, a["lon"], a["lat"]), 1))
                  for a in power[:5]],
        "centre_kind": centre_kind,
        # No centre inside the window is not an empty result, it is the
        # result: this is somewhere whose nearest town is further away than
        # the whole search, and a road closure there is a different kind of
        # problem from one outside Kohima.
        "no_centre_in_range": not centres,
        "note": (f"Villages are routed to the nearest service centre ("
                 f"{centre_kind}). 'Isolated' means no road path to any of "
                 f"them exists once the cut segments are removed, within the "
                 f"{search_km:.0f} km window searched rather than globally. "
                 f"Population is GeoNames' where it has one, which is about "
                 f"one settlement in twenty."),
    }


def cut_geometry(lat, lon, radius_km=DEFAULT_RADIUS_KM, search_km=12.0):
    """The cut segments themselves, for drawing on a map."""
    if not available():
        return []
    g = graph()
    out = []
    for i in _edges_near(lat, lon, search_km):
        e = g["edges"][i]
        if _edge_min_km(e, lat, lon) <= radius_km:
            out.append({"cls": e["cls"], "m": e["m"], "geom": e["geom"]})
    return out
