"""Pulls the NER river network and standing water from OpenStreetMap.

Writes data/geo/rivers_classified.json in the same shape as
roads_classified.json, so the dashboard, the mobile /api/geo payload and the
Android path renderer all consume it with no new code:

    {"major": [[[lon,lat], ...], ...],     # named rivers and canals
     "minor": [[[lon,lat], ...], ...],     # unnamed rivers, big streams
     "water": [[[lon,lat], ...], ...]}     # lakes, reservoirs, glacial lakes

Overpass times out on a query this size, so the region is fetched in tiles
with a pause between them. Run it once; the output is committed.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = "data/geo/rivers_classified.json"
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Same frame the dashboard projects.
LON_MIN, LON_MAX = 87.5, 97.8
LAT_MIN, LAT_MAX = 21.5, 29.8
TILE = 1.0          # degrees; 2 deg with polygons reliably 504s
PAUSE = 6           # seconds between tiles -- Overpass is a shared free service


def query(body, timeout=600):
    data = urllib.parse.urlencode({"data": body}).encode()
    last = None
    for attempt in range(4):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(
                url, data=data,
                headers={"User-Agent": "SPIREXA/1.0 (landslide+flood research; contact via github.com/UtkarshCodecom/spirexa-ner)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            wait = 20 * (attempt + 1)
            print(f"    retry in {wait}s ({type(e).__name__}: {e})", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Overpass failed after 4 attempts: {last}")


def tile_query(s, w, n, e, water=False):
    """Rivers and standing water go in separate passes: asking Overpass for
    both at once times out across most of this region."""
    bbox = f"{s},{w},{n},{e}"
    if water:
        body = (f'way["natural"="water"]["water"~"^(lake|reservoir|oxbow)$"]({bbox});'
                f'way["landuse"="reservoir"]({bbox});')
    else:
        body = f'way["waterway"~"^(river|canal)$"]({bbox});'
    return f"[out:json][timeout:300];({body});out geom;"


def main():
    os.makedirs("data/geo", exist_ok=True)
    major, minor, water = [], [], []
    seen = set()

    lat = LAT_MIN
    tiles = []
    while lat < LAT_MAX:
        lon = LON_MIN
        while lon < LON_MAX:
            tiles.append((lat, lon, min(lat + TILE, LAT_MAX), min(lon + TILE, LON_MAX)))
            lon += TILE
        lat += TILE

    print(f"{len(tiles)} tiles over {LON_MIN}-{LON_MAX}E {LAT_MIN}-{LAT_MAX}N", flush=True)
    failed = []
    for i, (s, w, n, e) in enumerate(tiles, 1):
        print(f"[{i}/{len(tiles)}] {s:.1f}-{n:.1f}N {w:.1f}-{e:.1f}E ...", end=" ", flush=True)
        try:
            res = query(tile_query(s, w, n, e))
        except RuntimeError as err:
            # one dead tile should not cost the other 82
            print(f"SKIPPED ({err})", flush=True)
            failed.append((s, w, n, e))
            continue
        got_m = got_n = got_w = 0
        for el in res.get("elements", []):
            if el.get("type") != "way" or "geometry" not in el:
                continue
            if el["id"] in seen:          # ways straddle tile borders
                continue
            seen.add(el["id"])
            coords = [[round(p["lon"], 5), round(p["lat"], 5)] for p in el["geometry"]]
            if len(coords) < 2:
                continue
            tags = el.get("tags", {})
            if tags.get("waterway") in ("river", "canal"):
                if tags.get("name"):
                    major.append(coords); got_m += 1
                else:
                    minor.append(coords); got_n += 1
            else:
                water.append(coords); got_w += 1
        print(f"{got_m} named, {got_n} unnamed, {got_w} water", flush=True)
        time.sleep(PAUSE)

    if failed:
        print(f"\n{len(failed)} tiles failed and were skipped:")
        for s, w, n, e in failed:
            print(f"   {s:.1f}-{n:.1f}N {w:.1f}-{e:.1f}E")

    out = {"major": major, "minor": minor, "water": water}
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    size = os.path.getsize(OUT) / 1024 / 1024
    print(f"\n-> {OUT}  ({size:.1f} MB)")
    print(f"   named rivers {len(major)}, unnamed {len(minor)}, water bodies {len(water)}")


if __name__ == "__main__":
    sys.exit(main())
