"""Re-fetches the NER road network with its topology intact.

data/geo/roads_classified.json is fine for drawing and useless for routing:
it was simplified, which moved and dropped vertices, so only 15% of way
endpoints still coincide. Built into a graph it falls into 7,922 components
with the largest holding 0.1% of nodes -- you cannot ask it which road still
reaches a village.

The fix is node identity rather than coordinate proximity. Overpass 'out body
geom' returns both the node ids of a way and its coordinates, so junctions
are exact by construction: two ways meet where they share a node id, however
the geometry is later simplified for display.

Overpass rate-limits this region hard, so this is built to be left running:
every tile is written to disk as it lands, and re-running skips whatever is
already there.

    data/geo/roads_topo.json
        {"ways": {id: {"cls": "major"|"minor",
                       "nodes": [node_id, ...],
                       "coords": [[lon, lat], ...]}},
         "done": ["lat,lon", ...]}
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

OUT = "data/geo/roads_topo.json"
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]

LON_MIN, LON_MAX = 87.5, 97.8
LAT_MIN, LAT_MAX = 21.5, 29.8
TILE = 1.0
PAUSE = 12            # be a good citizen; the run is expected to be long

MAJOR = "motorway|trunk|primary"
MINOR = "secondary|tertiary|unclassified"


def query(body, timeout=400):
    data = urllib.parse.urlencode({"data": body}).encode()
    last = None
    for attempt in range(6):
        url = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": "SPIREXA/1.0 (landslide+flood research; "
                              "github.com/UtkarshCodecom/spirexa-ner)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:                     # noqa: BLE001 - any failure retries
            last = e
            wait = min(240, 25 * (attempt + 1))
            print(f"      retry in {wait}s ({type(e).__name__}: {e})", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"failed after 6 attempts: {last}")


def load():
    if os.path.exists(OUT):
        with open(OUT) as f:
            d = json.load(f)
        return d.get("ways", {}), set(d.get("done", []))
    return {}, set()


def save(ways, done):
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"ways": ways, "done": sorted(done)}, f, separators=(",", ":"))
    os.replace(tmp, OUT)          # atomic, so a kill mid-write cannot corrupt it


def main():
    os.makedirs("data/geo", exist_ok=True)
    ways, done = load()
    if ways:
        print(f"resuming: {len(ways)} ways, {len(done)} tiles already fetched", flush=True)

    tiles = []
    lat = LAT_MIN
    while lat < LAT_MAX:
        lon = LON_MIN
        while lon < LON_MAX:
            tiles.append((round(lat, 1), round(lon, 1)))
            lon += TILE
        lat += TILE

    todo = [t for t in tiles if f"{t[0]},{t[1]}" not in done]
    print(f"{len(tiles)} tiles, {len(todo)} to go", flush=True)

    for i, (s, w) in enumerate(todo, 1):
        n, e = min(s + TILE, LAT_MAX), min(w + TILE, LON_MAX)
        bbox = f"{s},{w},{n},{e}"
        print(f"[{i}/{len(todo)}] {s}-{n}N {w}-{e}E ...", end=" ", flush=True)
        try:
            res = query(f'[out:json][timeout:300];'
                        f'way["highway"~"^({MAJOR}|{MINOR})$"]({bbox});'
                        f'out body geom;')
        except RuntimeError as err:
            print(f"SKIPPED ({err})", flush=True)
            continue

        added = 0
        for el in res.get("elements", []):
            if el.get("type") != "way":
                continue
            wid = str(el["id"])
            if wid in ways:
                continue
            nodes = el.get("nodes") or []
            geom = el.get("geometry") or []
            if len(nodes) < 2 or len(nodes) != len(geom):
                continue                      # clipped at the tile edge
            hw = (el.get("tags") or {}).get("highway", "")
            ways[wid] = {
                "cls": "major" if hw in MAJOR.split("|") else "minor",
                "nodes": nodes,
                "coords": [[round(p["lon"], 6), round(p["lat"], 6)] for p in geom],
            }
            added += 1

        done.add(f"{s},{w}")
        save(ways, done)
        print(f"+{added} ways (total {len(ways)})", flush=True)
        time.sleep(PAUSE)

    print(f"\n-> {OUT}  ({os.path.getsize(OUT)/1024/1024:.1f} MB, {len(ways)} ways)")


if __name__ == "__main__":
    sys.exit(main())
