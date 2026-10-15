"""Builds the training points for the landslide susceptibility model.

Positives are the GSI inventory: 7,498 field-mapped landslides across the
eight NER states. That is two orders of magnitude more ground truth than the
318 dated events the trigger model is trained on -- but it carries no dates,
only the GSI field-season year, so it can say where a slope is prone to fail
and not when. Those are different models and this one is the first.

Negatives are the hard part of susceptibility modelling and the usual place
the numbers get quietly inflated. Sample them anywhere in the region and most
land in the Brahmaputra floodplain, where the model learns "flat ground does
not slide" -- true, useless, and worth about ten points of AUC it has not
earned. So a generous pool is drawn here and the matching is done later,
after the terrain is known, against the positives' own slope distribution.

    positives   every GSI point
    negatives   uniform over NER land, >= EXCLUSION_M from any positive
"""

import json
import math
import os
import random
import re

OUT = "data/susceptibility/points.json"
GEOJSON = "gsi_landslide_inventory.geojson"
RINGS = "data/geo/ner_state_rings.json"

EXCLUSION_M = 750          # no negative this close to a mapped slide
NEG_PER_POS = 1.6          # generous; matched down further at training time
SEED = 42

# An absence of mapped slides is not an absence of slides. Arunachal Pradesh
# has zero points in this inventory and is emphatically not landslide-free --
# GSI has not surveyed it at this scale. Drawing 3,631 background points there
# and none positive would teach the model that the state is safe, which is the
# same survey-intensity bias that inflated this project's first model.
# Negatives are drawn only where GSI actually looked, and in proportion to
# what they found, so the model learns to tell slopes apart within a surveyed
# state rather than to tell surveyed states from unsurveyed ones.
UNSURVEYED = {"Arunachal Pradesh"}


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat):
            x = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x:
                inside = not inside
        j = i
    return inside


def main():
    random.seed(SEED)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    gj = json.load(open(GEOJSON))
    pos = []
    for f in gj["features"]:
        p = f.get("properties") or {}
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        m = re.search(r"/((?:19|20)\d{2})/", str(p.get("SLIDE_NO", "")))
        pos.append({
            "id": f"GSI{p.get('OBJECTID')}",
            "lat": round(float(lat), 6), "lon": round(float(lon), 6),
            "label": 1,
            "state": (p.get("STATE") or "").strip(),
            "district": (p.get("DISTRICT") or "").strip(),
            "survey_year": int(m.group(1)) if m else None,
            "trigger": (p.get("TRIGGERING") or "").strip(),
            "activity": (p.get("ACTIVITY") or "").strip(),
            "material": (p.get("MATERIAL_TYPE") or "").strip(),
            "movement": (p.get("MOVEMENT_TYPE") or "").strip(),
            "ls_area_m2": p.get("LS_AREA"),
            "deaths": p.get("PERSONS_DEATH"),
        })
    print(f"positives: {len(pos)}")

    rings = json.load(open(RINGS))
    polys = []
    for name, rs in rings.items():
        for r in rs:
            xs = [c[0] for c in r]; ys = [c[1] for c in r]
            polys.append((name, r, min(xs), max(xs), min(ys), max(ys)))
    print(f"state rings: {len(polys)}")

    # coarse spatial index over the positives so the exclusion test is cheap
    CELL = 0.02                      # ~2 km
    grid = {}
    for p in pos:
        grid.setdefault((int(p["lat"] / CELL), int(p["lon"] / CELL)), []).append(p)

    def too_close(lat, lon):
        gy, gx = int(lat / CELL), int(lon / CELL)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for q in grid.get((gy + dy, gx + dx), ()):
                    if _haversine(lat, lon, q["lat"], q["lon"]) < EXCLUSION_M:
                        return True
        return False

    from collections import Counter
    per_state = Counter(p["state"] for p in pos)
    quota = {s: int(round(n * NEG_PER_POS)) for s, n in per_state.items()
             if s and s not in UNSURVEYED}
    print("negative quota by state:", dict(sorted(quota.items())))

    lon_min = min(p[2] for p in polys); lon_max = max(p[3] for p in polys)
    lat_min = min(p[4] for p in polys); lat_max = max(p[5] for p in polys)

    want = sum(quota.values())
    got = Counter()
    neg, tries = [], 0
    while len(neg) < want and tries < want * 1500:
        tries += 1
        lon = random.uniform(lon_min, lon_max)
        lat = random.uniform(lat_min, lat_max)
        state = None
        for name, ring, x0, x1, y0, y1 in polys:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and _point_in_ring(lon, lat, ring):
                state = name
                break
        if state is None or got[state] >= quota.get(state, 0):
            continue
        if too_close(lat, lon):
            continue
        got[state] += 1
        neg.append({"id": f"NEG{len(neg):06d}", "lat": round(lat, 6),
                    "lon": round(lon, 6), "label": 0, "state": state})
        if len(neg) % 2000 == 0:
            print(f"  negatives {len(neg)}/{want} ({tries} tries)", flush=True)

    print(f"negatives: {len(neg)} from {tries} tries")
    pts = pos + neg
    json.dump(pts, open(OUT, "w"))
    print(f"-> {OUT}  ({len(pts)} points, {os.path.getsize(OUT)/1024/1024:.1f} MB)")

    print("\nby state:")
    cp, cn = Counter(p["state"] for p in pos), Counter(n["state"] for n in neg)
    for s in sorted(set(cp) | set(cn)):
        print(f"   {s:<20} {cp.get(s,0):>5} slides   {cn.get(s,0):>5} background")


if __name__ == "__main__":
    main()
