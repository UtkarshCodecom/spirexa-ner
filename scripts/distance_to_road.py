"""Distance from every training point to the nearest road.

Proximity to a road is one of the strongest susceptibility covariates there
is, and not as a proxy for anything: cutting a bench into a hillside removes
the toe support that was holding the slope up. The GSI inventory says so
directly -- hundreds of its records name road cutting as the trigger.

Computed here rather than in Earth Engine because a KD-tree over the road
vertices answers 19,494 queries in seconds, where the same thing server-side
is 19,494 buffered reductions.

Distances are to the nearest road *vertex*. OSM geometry is dense enough in
this region that the error against true perpendicular distance is small
compared to the 30 m terrain grid everything else is sampled on.
"""

import json
import math
import os

import numpy as np
from scipy.spatial import cKDTree

ROADS = "data/geo/roads_topo.json"
POINTS = "data/susceptibility/points.json"
OUT = "data/susceptibility/road_distance.json"

LAT0 = 25.6              # mid-latitude of the region, for the local projection
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON = 111.320 * math.cos(math.radians(LAT0))


def to_km(lon, lat):
    return np.column_stack([np.asarray(lon) * KM_PER_DEG_LON,
                            np.asarray(lat) * KM_PER_DEG_LAT])


def main():
    print("loading road topology ...", flush=True)
    with open(ROADS) as f:
        data = json.load(f)
    ways = data["ways"]
    print(f"  {len(ways)} ways", flush=True)

    major_lon, major_lat, all_lon, all_lat = [], [], [], []
    for w in ways.values():
        lons = [c[0] for c in w["coords"]]
        lats = [c[1] for c in w["coords"]]
        all_lon.extend(lons); all_lat.extend(lats)
        if w["cls"] == "major":
            major_lon.extend(lons); major_lat.extend(lats)
    del data, ways
    print(f"  {len(all_lon)} vertices, {len(major_lon)} on major roads", flush=True)

    tree_all = cKDTree(to_km(all_lon, all_lat))
    tree_major = cKDTree(to_km(major_lon, major_lat))
    del all_lon, all_lat, major_lon, major_lat
    print("  trees built", flush=True)

    pts = json.load(open(POINTS))
    q = to_km([p["lon"] for p in pts], [p["lat"] for p in pts])
    d_all, _ = tree_all.query(q, k=1)
    d_major, _ = tree_major.query(q, k=1)

    out = {p["id"]: {"dist_road_m": round(float(a) * 1000, 1),
                     "dist_major_road_m": round(float(m) * 1000, 1)}
           for p, a, m in zip(pts, d_all, d_major)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"))

    lab = np.array([p["label"] for p in pts])
    print(f"\n-> {OUT}")
    for name, d in (("any road", d_all), ("major road", d_major)):
        pos = np.median(d[lab == 1]) * 1000
        neg = np.median(d[lab == 0]) * 1000
        print(f"   median distance to {name:<11} slides {pos:8.0f} m   "
              f"background {neg:8.0f} m")


if __name__ == "__main__":
    main()
