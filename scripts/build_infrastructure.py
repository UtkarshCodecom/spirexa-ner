"""Settlements, hospitals, dams and power stations for the impact graph.

Built from the GeoNames India dump rather than Overpass. Overpass was the
first choice and is the better data for roads, but the public instances
answered this workload with a steady alternation of 504 and 429 -- a whole
state of villages, hospitals and power nodes is past what a shared volunteer
service should be asked for, however politely it is tiled. GeoNames is one
16 MB download, carries population figures OSM usually lacks, and is CC-BY.

What is lost by the swap: OSM's hospitals are more complete in towns, and
GeoNames has no bridges at all. What is gained: population on most
settlements, which is what turns "three villages cut off" into a number
somebody can act on.
"""

import csv
import io
import json
import os
import urllib.request
import zipfile

URL = "https://download.geonames.org/export/dump/IN.zip"
CACHE = "data/raw/geonames_IN.zip"
OUT = "data/geo/infrastructure.json"

# The eight North-Eastern states, generously bounded. Points are kept on the
# box; the state label is only a hint and nothing downstream routes on it.
FRAME = (21.8, 87.5, 29.6, 97.6)          # s, w, n, e

STATES = {
    "Sikkim": (27.05, 88.00, 28.15, 88.95),
    "Arunachal Pradesh": (26.60, 91.55, 29.45, 97.45),
    "Assam": (24.10, 89.65, 28.00, 96.05),
    "Meghalaya": (25.00, 89.80, 26.15, 92.85),
    "Nagaland": (25.15, 93.30, 27.05, 95.30),
    "Manipur": (23.80, 92.95, 25.70, 94.80),
    "Mizoram": (21.90, 92.20, 24.55, 93.45),
    "Tripura": (22.90, 91.00, 24.55, 92.40),
}

# GeoNames feature codes worth keeping, mapped to what this system calls them.
KIND = {
    "PPL": "settlement", "PPLA": "settlement", "PPLA2": "settlement",
    "PPLA3": "settlement", "PPLA4": "settlement", "PPLC": "settlement",
    "PPLL": "settlement", "PPLX": "settlement", "PPLS": "settlement",
    "HSP": "hospital", "HSPC": "hospital", "HSPD": "hospital",
    "DAM": "dam", "PS": "power", "PSH": "power", "PSTN": "power",
}
PLACE_RANK = {"PPLC": "city", "PPLA": "city", "PPLA2": "town",
              "PPLA3": "town", "PPLA4": "town", "PPL": "village",
              "PPLL": "village", "PPLX": "village", "PPLS": "village"}


def state_of(lat, lon):
    for name, (s, w, n, e) in STATES.items():
        if s <= lat <= n and w <= lon <= e:
            return name
    return ""


def main():
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    if not os.path.exists(CACHE):
        print(f"downloading {URL} ...", flush=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "SPIREXA/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            open(CACHE, "wb").write(r.read())
    print(f"  {os.path.getsize(CACHE)/1e6:.1f} MB", flush=True)

    s0, w0, n0, e0 = FRAME
    assets, seen = [], set()
    with zipfile.ZipFile(CACHE) as z:
        with z.open("IN.txt") as f:
            rd = csv.reader(io.TextIOWrapper(f, encoding="utf-8"),
                            delimiter="\t", quoting=csv.QUOTE_NONE)
            for row in rd:
                if len(row) < 15:
                    continue
                try:
                    lat, lon = float(row[4]), float(row[5])
                except ValueError:
                    continue
                if not (s0 <= lat <= n0 and w0 <= lon <= e0):
                    continue
                kind = KIND.get(row[7])
                if not kind:
                    continue
                gid = "g" + row[0]
                if gid in seen:
                    continue
                seen.add(gid)
                pop = int(row[14]) if row[14].isdigit() else 0
                assets.append({
                    "id": gid, "kind": kind, "name": row[1],
                    "state": state_of(lat, lon),
                    "lat": round(lat, 5), "lon": round(lon, 5),
                    "place": PLACE_RANK.get(row[7]),
                    "population": pop or None,
                    "source": "GeoNames",
                })

    json.dump({"assets": assets, "source": "GeoNames IN dump (CC-BY 4.0)"},
              open(OUT, "w"))
    kinds, states = {}, {}
    with_pop = 0
    for a in assets:
        kinds[a["kind"]] = kinds.get(a["kind"], 0) + 1
        states[a["state"] or "outside"] = states.get(a["state"] or "outside", 0) + 1
        with_pop += bool(a["population"])
    print(f"\n-> {OUT}  {len(assets)} assets")
    print("   by kind: ", kinds)
    print(f"   with population: {with_pop}")
    for k, v in sorted(states.items(), key=lambda t: -t[1]):
        print(f"     {k:<20} {v}")


if __name__ == "__main__":
    main()
