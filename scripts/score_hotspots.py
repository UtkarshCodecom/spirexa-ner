"""Scores every monitored hotspot for susceptibility, once, offline.

The dashboard watches 311 locations. Their trigger risk is recomputed daily
from rainfall; their susceptibility does not change from one day to the next,
so it is computed here and cached. The web app then crosses the two without
an Earth Engine call in the request path.

Run after retraining, or after the hotspot list changes. Takes a few minutes:
most of it is building the road KD-tree.
"""

import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import susceptibility as susc

LIVE = "data/processed/live_risk.csv"
OUT = "data/processed/hotspot_susceptibility.json"


def main():
    rows = list(csv.DictReader(open(LIVE)))
    points = [{"id": r["id"], "lat": float(r["lat"]), "lon": float(r["lon"]),
               "location": r["location"], "state": r["state"],
               "trigger": float(r["live_risk"])} for r in rows]
    print(f"{len(points)} hotspots", flush=True)

    scored = susc.score_points(points)

    out = []
    for p, s in zip(points, scored):
        f = s.pop("features", {})
        d = susc.decision(p["trigger"], s["with_roads"], s["terrain_only"])
        out.append({
            "id": p["id"], "location": p["location"], "state": p["state"],
            "lat": p["lat"], "lon": p["lon"],
            "with_roads": s["with_roads"], "terrain_only": s["terrain_only"],
            "band": susc.band(s["terrain_only"]),
            "band_with_roads": susc.band(s["with_roads"]),
            "ground": d["ground"]["kind"],
            "ground_label": d["ground"]["label"],
            "dist_road_m": round(f.get("dist_road_m", 0.0)),
            "slope": round(f.get("cop_slope") or f.get("slope") or 0.0, 1),
            "relief_m": round(susc.derive(f).get("relief") or 0.0),
            "ndvi": round((f.get("ndvi") or 0.0) / 1e4, 3),
        })

    kinds = {}
    for r in out:
        kinds[r["ground"]] = kinds.get(r["ground"], 0) + 1
    payload = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "model": susc.model_card(),
        "counts": kinds,
        "hotspots": out,
    }
    json.dump(payload, open(OUT, "w"), indent=1)

    print(f"\n-> {OUT}")
    print("  ground type:")
    for k, v in sorted(kinds.items(), key=lambda t: -t[1]):
        print(f"    {k:<12} {v}")
    hi = sorted(out, key=lambda r: -r["terrain_only"])[:8]
    print("\n  most susceptible on terrain alone:")
    for r in hi:
        print(f"    {r['terrain_only']:.2f} / {r['with_roads']:.2f}  "
              f"{r['location'][:46]:<46} {r['ground']}")


if __name__ == "__main__":
    main()
