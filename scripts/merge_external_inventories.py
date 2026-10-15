"""Folds two published landslide inventories into the susceptibility points.

The GSI inventory is the backbone -- 7,498 field-mapped slides -- but it has
a hole: Arunachal Pradesh has zero records in it. Not because the state is
stable, which it emphatically is not, but because GSI has not surveyed it at
this scale. That forced the first model to exclude Arunachal entirely rather
than learn that the state is safe.

Two CC-BY-4.0 datasets from Zenodo fill it:

  Large Landslide Inventory of the Eastern Himalaya (10.5281/zenodo.18931430)
      420 large landslides mapped from remote sensing, 284 of them inside the
      Arunachal box. No dates -- this is a susceptibility source, not a
      trigger one.

  Multi-temporal landslide inventory for southern Sikkim (zenodo.8169506)
      Google Earth and Cartosat-1 mapping, year-level attribution on the
      polygons. Again no day, so again susceptibility only.

Neither carries the day-level dates the rainfall trigger model needs. That
data does not appear to exist publicly for this region, which is itself the
finding: the trigger model's 2017-2023 gap cannot be closed from open sources.
"""

import json
import math
import os
import re

import shapefile

GSI_POINTS = "data/susceptibility/points.json"
EH_KML = "data/external/eastern_himalaya.kml"
SIKKIM_DIR = "data/external/sikkim_multitemporal"
OUT = "data/susceptibility/points_external.json"

NER = (87.5, 97.8, 21.5, 29.8)
DEDUP_M = 250          # a slide already in GSI should not be counted twice


def _km(lat1, lon1, lat2, lon2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.asin(math.sqrt(a))


def eastern_himalaya():
    txt = open(EH_KML, encoding="utf-8", errors="replace").read()
    out = []
    for lon, lat in re.findall(r"<coordinates>\s*([-\d.]+),([-\d.]+)", txt):
        lon, lat = float(lon), float(lat)
        if NER[0] <= lon <= NER[1] and NER[2] <= lat <= NER[3]:
            out.append((lat, lon, "eastern_himalaya_zenodo18931430"))
    return out


def sikkim():
    out = []
    for name in ("Google_Earth_landslides_point_21Dec2021",
                 "Cartosat_landslides_21Dec2021"):
        path = os.path.join(SIKKIM_DIR, name)
        if not os.path.exists(path + ".shp"):
            continue
        try:
            sf = shapefile.Reader(path)
        except Exception as e:
            print(f"  cannot read {name}: {e}")
            continue
        for shp in sf.shapes():
            if not shp.points:
                continue
            xs = [p[0] for p in shp.points]
            ys = [p[1] for p in shp.points]
            lon, lat = sum(xs) / len(xs), sum(ys) / len(ys)
            if NER[0] <= lon <= NER[1] and NER[2] <= lat <= NER[3]:
                out.append((lat, lon, f"sikkim_zenodo8169506:{name}"))
    return out


def main():
    gsi = json.load(open(GSI_POINTS))
    pos = [p for p in gsi if p["label"] == 1]
    print(f"GSI positives: {len(pos)}")

    CELL = 0.01
    grid = {}
    for p in pos:
        grid.setdefault((int(p["lat"]/CELL), int(p["lon"]/CELL)), []).append(p)

    def duplicate(lat, lon):
        gy, gx = int(lat/CELL), int(lon/CELL)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for q in grid.get((gy+dy, gx+dx), ()):
                    if _km(lat, lon, q["lat"], q["lon"]) < DEDUP_M:
                        return True
        return False

    added, skipped = [], 0
    for src_name, rows in (("eastern himalaya", eastern_himalaya()),
                           ("sikkim multi-temporal", sikkim())):
        keep = 0
        for lat, lon, src in rows:
            if duplicate(lat, lon):
                skipped += 1
                continue
            rec = {"id": f"EXT{len(added):05d}", "lat": round(lat, 6),
                   "lon": round(lon, 6), "label": 1, "state": "",
                   "source": src}
            added.append(rec)
            grid.setdefault((int(lat/CELL), int(lon/CELL)), []).append(rec)
            keep += 1
        print(f"  {src_name:<24} {len(rows):>5} found, {keep:>5} new")

    print(f"\n{len(added)} new positives, {skipped} were already in GSI")
    aru = sum(1 for p in added if 91.5 <= p["lon"] <= 97.5 and 26.6 <= p["lat"] <= 29.5)
    print(f"  of which {aru} fall in the Arunachal box, where GSI had none")

    json.dump(added, open(OUT, "w"))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------
def add_background():
    """Background for the newly covered ground, chiefly Arunachal.

    The original sampler skipped Arunachal on purpose: positives there were
    zero, so any background drawn would have taught the model the state was
    safe. Now that 284 real slides are on the books there, background can be
    drawn -- and must be, or the state swings the other way and everything in
    it scores high.
    """
    import random
    from collections import Counter

    random.seed(11)
    new_pos = json.load(open(OUT))
    rings = json.load(open("data/geo/ner_state_rings.json"))
    polys = []
    for name, rs in rings.items():
        for r in rs:
            xs = [c[0] for c in r]; ys = [c[1] for c in r]
            polys.append((name, r, min(xs), max(xs), min(ys), max(ys)))

    def _inside(lon, lat, ring):
        ins = False; n = len(ring); j = n - 1
        for i in range(n):
            xi, yi = ring[i]; xj, yj = ring[j]
            if (yi > lat) != (yj > lat):
                if lon < (xj-xi)*(lat-yi)/(yj-yi)+xi:
                    ins = not ins
            j = i
        return ins

    def state_of(lon, lat):
        for name, ring, x0, x1, y0, y1 in polys:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and _inside(lon, lat, ring):
                return name
        return None

    for p in new_pos:
        if not p.get("state"):
            p["state"] = state_of(p["lon"], p["lat"]) or ""
    json.dump(new_pos, open(OUT, "w"))
    per = Counter(p["state"] for p in new_pos if p["state"])
    print("\nnew positives by state:", dict(per))

    quota = {s: int(round(n * 1.6)) for s, n in per.items()}
    all_pos = [p for p in json.load(open(GSI_POINTS)) if p["label"] == 1] + new_pos
    CELL = 0.02
    grid = {}
    for p in all_pos:
        grid.setdefault((int(p["lat"]/CELL), int(p["lon"]/CELL)), []).append(p)

    def near(lat, lon):
        gy, gx = int(lat/CELL), int(lon/CELL)
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                for q in grid.get((gy+dy, gx+dx), ()):
                    if _km(lat, lon, q["lat"], q["lon"]) < 750:
                        return True
        return False

    lon0 = min(p[2] for p in polys); lon1 = max(p[3] for p in polys)
    lat0 = min(p[4] for p in polys); lat1 = max(p[5] for p in polys)
    want = sum(quota.values()); got = Counter(); neg = []
    tries = 0
    while len(neg) < want and tries < want * 3000:
        tries += 1
        lon = random.uniform(lon0, lon1); lat = random.uniform(lat0, lat1)
        st = state_of(lon, lat)
        if st is None or got[st] >= quota.get(st, 0) or near(lat, lon):
            continue
        got[st] += 1
        neg.append({"id": f"EXTNEG{len(neg):05d}", "lat": round(lat,6),
                    "lon": round(lon,6), "label": 0, "state": st,
                    "source": "background_for_external"})
    print(f"background drawn: {len(neg)} ({dict(got)})")

    combined = new_pos + neg
    path = "data/susceptibility/points_external_all.json"
    json.dump(combined, open(path, "w"))
    print(f"-> {path}  ({len(combined)} points to extract)")


if __name__ == "__main__" and os.environ.get("ADD_BG"):
    add_background()
