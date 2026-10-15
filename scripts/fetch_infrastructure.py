"""What is actually inside a red zone: settlements, hospitals, power, bridges.

A hazard map that stops at "this area is dangerous" leaves the hardest part
to the person reading it. What they need is the next line -- how many people,
which road, whether the hospital is on the far side of the break.

Pulled from OpenStreetMap through Overpass, once, and cached. Queried state by
state because a single request for the whole North-East times out, and slowly
because Overpass is a shared volunteer service and hammering it is how the
next person gets blocked.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

OUT = "data/geo/infrastructure.json"
# kumi.systems is in the list everywhere but times out from here every time;
# osm.ch answers fast and is the useful fallback.
ENDPOINTS = ["https://overpass-api.de/api/interpreter",
             "https://overpass.osm.ch/api/interpreter"]

# One box per state keeps each response small enough to come back.
BOXES = {
    "Sikkim": (27.05, 88.00, 28.15, 88.95),
    "Arunachal Pradesh": (26.60, 91.55, 29.45, 97.45),
    "Assam": (24.10, 89.65, 28.00, 96.05),
    "Meghalaya": (25.00, 89.80, 26.15, 92.85),
    "Nagaland": (25.15, 93.30, 27.05, 95.30),
    "Manipur": (23.80, 92.95, 25.70, 94.80),
    "Mizoram": (21.90, 92.20, 24.55, 93.45),
    "Tripura": (22.90, 91.00, 24.55, 92.40),
}

# One feature class per request over a one-degree tile. The obvious query --
# all four classes over a whole state -- returns 504 every time: Overpass
# budgets by area x tags, and a 6-degree box of Arunachal with four regexes is
# far past it. Small and boring gets answers; clever and large does not.
TILE_DEG = 1.0
SELECTORS = [
    ('node["place"~"^(city|town|village)$"]', "places"),
    ('node["amenity"~"^(hospital|clinic)$"]', "health"),
    ('node["power"~"^(plant|substation)$"]', "power"),
]
QUERY = """[out:json][timeout:90];
{sel}({s},{w},{n},{e});
out tags;"""


def fetch(q, tries=4):
    for i in range(tries):
        url = ENDPOINTS[i % len(ENDPOINTS)]
        try:
            data = urllib.parse.urlencode({"data": q}).encode()
            req = urllib.request.Request(url, data=data,
                                         headers={"User-Agent": "SPIREXA/1.0"})
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read().decode())
        except Exception as exc:                          # noqa: BLE001
            print(f"    {type(exc).__name__}: {str(exc)[:80]}", flush=True)
            time.sleep(8 * (i + 1))
    return None


def classify(tags):
    if tags.get("place") in ("city", "town", "village"):
        return "settlement"
    if tags.get("amenity") in ("hospital", "clinic"):
        return "hospital"
    if tags.get("power") in ("plant", "substation"):
        return "power"
    return None


def main():
    have = {}
    if os.path.exists(OUT):
        have = {a["id"]: a for a in json.load(open(OUT))["assets"]}
        print(f"resuming with {len(have)} assets")

    done = set()
    donefile = OUT + ".done"
    if os.path.exists(donefile):
        done = set(json.load(open(donefile)))

    jobs = []
    for state, (s0, w0, n0, e0) in BOXES.items():
        y = s0
        while y < n0:
            x = w0
            while x < e0:
                for sel, label in SELECTORS:
                    jobs.append((state, label, sel,
                                 round(y, 2), round(x, 2),
                                 round(min(y + TILE_DEG, n0), 2),
                                 round(min(x + TILE_DEG, e0), 2)))
                x += TILE_DEG
            y += TILE_DEG
    print(f"{len(jobs)} tile-queries", flush=True)

    for k, (state, label, sel, s, w, n, e) in enumerate(jobs, 1):
        key = f"{state}|{label}|{s}|{w}"
        if key in done:
            continue
        d = fetch(QUERY.format(sel=sel, s=s, w=w, n=n, e=e))
        if not d:
            print(f"  [{k}/{len(jobs)}] {key}: failed", flush=True)
            continue
        added = 0
        for el in d.get("elements", []):
            tags = el.get("tags", {})
            kind = classify(tags)
            if not kind:
                continue
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            if lat is None or lon is None:
                continue
            aid = f"{el['type'][0]}{el['id']}"
            pop = tags.get("population")
            have[aid] = {
                "id": aid, "kind": kind, "state": state,
                "name": tags.get("name") or tags.get("name:en") or "",
                "lat": round(lat, 5), "lon": round(lon, 5),
                "place": tags.get("place"),
                "population": int(pop) if pop and pop.isdigit() else None,
            }
            added += 1
        done.add(key)
        if k % 5 == 0 or added:
            print(f"  [{k}/{len(jobs)}] {key}: +{added}  (total {len(have)})",
                  flush=True)
            json.dump({"assets": list(have.values())}, open(OUT, "w"))
            json.dump(sorted(done), open(donefile, "w"))
        time.sleep(9)   # Overpass meters by IP; 3 s earns 429s, 9 s does not

    json.dump({"assets": list(have.values())}, open(OUT, "w"))
    json.dump(sorted(done), open(donefile, "w"))

    kinds = {}
    for a in have.values():
        kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
    print(f"\n-> {OUT}  {len(have)} assets  {kinds}")


if __name__ == "__main__":
    main()
