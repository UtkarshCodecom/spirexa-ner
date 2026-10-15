"""Finds the glacial lakes, instead of me typing in where I think they are.

The first version of glof.LAKES carried five lakes. One of them, South
Lhonak, was right. The other four were coordinates I had written down from
memory, and Sentinel-2 found essentially no water at any of them -- 0.001 km2
where a lake was supposed to be. Publishing those as monitored sites would
have been fabrication dressed as a system.

So the inventory is built from the imagery instead: melt-season water, above
the elevation where these lakes sit, larger than a pond, inside the Teesta
headwaters. What comes out is checkable against the imagery by anyone.

    NDWI      (green - nir) / (green + nir), melt season median
    elevation SRTM, above MIN_ELEV_M
    size      at least MIN_AREA_KM2, which drops meltwater puddles
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ee

from config import GEE_PROJECT

OUT = "data/processed/glacial_lakes.json"

# Teesta headwaters: north Sikkim and the Tibetan border ridge that drains
# into it. Everything downstream of here is somebody's dam.
REGION = [88.0, 27.55, 89.0, 28.25]

# Which melt season to map.
#
# 2022 is the validation reference: the last full season before the October
# 2023 breach, so the chain can be run against an outcome that is published.
# It is the wrong year to operate on, and the first version shipped it as
# though it were current. The operational inventory is the most recent
# COMPLETE melt season -- complete because these lakes are only visible for
# about three months a year and a single pass is usually cloud or ice.
#
#     python scripts/detect_glacial_lakes.py            # latest complete season
#     python scripts/detect_glacial_lakes.py 2022       # the validation baseline
#
# Running a year writes glacial_lakes_<year>.json, and the latest complete
# season is also written to glacial_lakes.json, which is what glof.py reads.
DEFAULT_YEAR = 2025
REF_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_YEAR
MIN_ELEV_M = 4200
MIN_AREA_KM2 = 0.05
NDWI_THRESHOLD = 0.15
SCALE = 20


def main():
    ee.Initialize(project=GEE_PROJECT)
    region = ee.Geometry.Rectangle(REGION, None, False)

    col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
           .filterBounds(region)
           .filterDate(f"{REF_YEAR}-09-01", f"{REF_YEAR}-11-30")
           .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40)))
    print(f"scenes in {REF_YEAR} melt season: {col.size().getInfo()}", flush=True)

    ndwi = col.median().normalizedDifference(["B3", "B8"]).rename("ndwi")
    srtm = ee.Image("USGS/SRTMGL1_003")
    water = ndwi.gt(NDWI_THRESHOLD).And(srtm.gt(MIN_ELEV_M)).selfMask().rename("w")

    vectors = water.reduceToVectors(
        geometry=region, scale=SCALE, geometryType="polygon",
        eightConnected=True, maxPixels=1e10, bestEffort=True,
    )
    with_area = vectors.map(lambda f: f.set({
        "area_km2": f.geometry().area(maxError=30).divide(1e6),
    }))
    big = with_area.filter(ee.Filter.gte("area_km2", MIN_AREA_KM2))

    print("fetching lake polygons ...", flush=True)
    feats = big.getInfo()["features"]
    print(f"  {len(feats)} water bodies above {MIN_AREA_KM2} km2 and {MIN_ELEV_M} m",
          flush=True)

    lakes = []
    for f in feats:
        geom = ee.Geometry(f["geometry"])
        c = geom.centroid(maxError=30).coordinates().getInfo()
        elev = srtm.reduceRegion(
            ee.Reducer.median(), geom, 30, maxPixels=1e9).get("elevation").getInfo()
        lakes.append({
            "lon": round(c[0], 5), "lat": round(c[1], 5),
            "area_km2": round(f["properties"]["area_km2"], 4),
            "elev_m": None if elev is None else round(elev),
        })

    lakes.sort(key=lambda l: -l["area_km2"])
    for i, l in enumerate(lakes, 1):
        l["id"] = f"GL{i:02d}"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    year_path = f"data/processed/glacial_lakes_{REF_YEAR}.json"
    payload = {"reference_year": REF_YEAR, "region": REGION,
               "min_area_km2": MIN_AREA_KM2, "min_elev_m": MIN_ELEV_M,
               "lakes": lakes}
    # Always keep the year's own file, so 2022 stays available as the
    # validation baseline after a newer season overwrites the operational one.
    json.dump(payload, open(year_path, "w"), indent=1)
    if REF_YEAR >= DEFAULT_YEAR:
        json.dump(payload, open(OUT, "w"), indent=1)

    print(f"\n-> {year_path}" + (f"\n-> {OUT}" if REF_YEAR >= DEFAULT_YEAR else ""))
    print(f"{'id':>5} {'area km2':>9} {'elev m':>7}  centroid")
    for l in lakes[:20]:
        print(f"{l['id']:>5} {l['area_km2']:>9.3f} {str(l['elev_m']):>7}  "
              f"{l['lat']:.4f}, {l['lon']:.4f}")


if __name__ == "__main__":
    main()
