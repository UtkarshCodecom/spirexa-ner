"""Collapses the OSM road dump into a routable graph small enough to keep.

data/geo/roads_topo.json is 428 MB and 12.4 million vertices, which is the
right shape for measuring distance to a road and the wrong shape for asking
whether a village can still be reached. Almost every one of those vertices is
a bend, not a decision: it has exactly two neighbours and nothing routes
through it differently than through its neighbour.

So this keeps only the nodes that matter -- junctions, where three or more
way-ends meet, and the ends of ways themselves -- and turns each run between
them into a single edge carrying its real length and its geometry. 12.4
million vertices become a few hundred thousand nodes, and the graph fits in
memory with room to answer questions.

Edges are indexed into a tenth-of-a-degree grid so a hazard 40 km wide can
pull the roads it touches without scanning the country.
"""

import collections
import json
import math
import os
import pickle
import sys

ROADS = "data/geo/roads_topo.json"
OUT = "data/processed/road_graph.pkl"
CELL = 0.1                       # degrees; about 11 km


def haversine_m(a, b):
    lon1, lat1 = a
    lon2, lat2 = b
    p = math.pi / 180
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    x = (math.sin(dlat / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dlon / 2) ** 2)
    return 6371000.0 * 2 * math.asin(math.sqrt(x))


def main():
    print("reading road topology ...", flush=True)
    with open(ROADS) as f:
        ways = json.load(f)["ways"]
    print(f"  {len(ways)} ways", flush=True)

    # how many ways touch each node: >1 means a junction
    deg = collections.Counter()
    for w in ways.values():
        for n in w["nodes"]:
            deg[n] += 1
    print(f"  {len(deg)} distinct vertices", flush=True)

    nodes = {}
    edges = []
    for wid, w in ways.items():
        ns, cs = w["nodes"], w["coords"]
        if len(ns) < 2:
            continue
        # split points: the two ends, plus anything shared with another way
        splits = [0] + [i for i in range(1, len(ns) - 1) if deg[ns[i]] > 1] \
                 + [len(ns) - 1]
        for k in range(len(splits) - 1):
            i, j = splits[k], splits[k + 1]
            if j <= i:
                continue
            geom = cs[i:j + 1]
            length = sum(haversine_m(geom[m], geom[m + 1])
                         for m in range(len(geom) - 1))
            if length <= 0:
                continue
            a, b = ns[i], ns[j]
            nodes.setdefault(a, tuple(cs[i]))
            nodes.setdefault(b, tuple(cs[j]))
            # thin the geometry: a bend every ~200 m is plenty for drawing
            keep = [geom[0]]
            acc = 0.0
            for m in range(1, len(geom)):
                acc += haversine_m(geom[m - 1], geom[m])
                if acc >= 200 or m == len(geom) - 1:
                    keep.append(geom[m]); acc = 0.0
            edges.append({"a": a, "b": b, "m": round(length, 1),
                          "cls": w["cls"], "geom": keep, "way": int(wid)})
    del ways, deg
    print(f"  {len(nodes)} junction nodes, {len(edges)} edges", flush=True)

    grid = collections.defaultdict(list)
    for idx, e in enumerate(edges):
        cells = {(int(math.floor(lon / CELL)), int(math.floor(lat / CELL)))
                 for lon, lat in e["geom"]}
        for c in cells:
            grid[c].append(idx)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        pickle.dump({"nodes": nodes, "edges": edges,
                     "grid": dict(grid), "cell": CELL}, f,
                    protocol=pickle.HIGHEST_PROTOCOL)
    mb = os.path.getsize(OUT) / 1e6
    print(f"-> {OUT}  ({mb:.0f} MB, {len(grid)} grid cells)")


if __name__ == "__main__":
    main()
