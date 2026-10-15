"""Glacial lake area, year by year, from Sentinel-2.

This is the monitoring half of the GLOF system. A breach model is worth
nothing without a number to feed it, and the number that matters -- volume --
cannot be measured from orbit. Area can, every five days, for free, and the
Huggel relation turns it into volume.

NDWI separates water from rock and ice: (green - nir) / (green + nir). Ice
and snow are bright in green and dark in NIR too, so the melt season is used
rather than the annual median -- September to November, when these lakes are
at their fullest and their surroundings least snow-covered.

South Lhonak is the calibration case. It is documented as having grown from
roughly 0.4 km2 in the 1990s to about 1.6-1.7 km2 before it burst in October
2023, and it should be visibly smaller afterwards.

Thresholding NDWI over a flat 2.5 km box is not enough. These basins are full
of meltwater ponds and wet outwash, and counting every water pixel within
2.5 km put South Lhonak at 2.3 km2 against a published 1.68 -- about 37% high,
and noisy enough year to year to hide the very trend the system exists to
watch.

Connected components would be the principled fix and Earth Engine will not do
it here: maxSize caps at 1024 pixels and South Lhonak is roughly 16,800. So
each lake instead carries its own extent, sized to it and written down in
glof.LAKES, which is cruder but honest and reproducible.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ee

from config import GEE_PROJECT
from glof import LAKES

OUT = "data/processed/lake_areas.json"
YEARS = list(range(2016, 2026))
NDWI_THRESHOLD = 0.15
DEFAULT_RADIUS_M = 1200  # used only if a lake has no extent of its own


def main():
    ee.Initialize(project=GEE_PROJECT)
    out = {}

    for lake in LAKES:
        pt = ee.Geometry.Point([lake["lon"], lake["lat"]])
        area = pt.buffer(lake.get("radius_m", DEFAULT_RADIUS_M))
        series = []
        for yr in YEARS:
            col = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                   .filterBounds(area)
                   .filterDate(f"{yr}-09-01", f"{yr}-11-30")
                   .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 40)))
            n = col.size().getInfo()
            if not n:
                series.append({"year": yr, "scenes": 0, "area_km2": None})
                continue
            ndwi = col.median().normalizedDifference(["B3", "B8"]).rename("ndwi")
            water = ndwi.gt(NDWI_THRESHOLD)
            km2 = (water.multiply(ee.Image.pixelArea())
                   .reduceRegion(ee.Reducer.sum(), area, 10, maxPixels=1e10)
                   .values().get(0))
            val = ee.Number(km2).divide(1e6).getInfo()
            series.append({"year": yr, "scenes": n,
                           "area_km2": None if val is None else round(val, 4)})
            print(f"  {lake['name']:<20} {yr}  {n:>3} scenes  "
                  f"{'--' if val is None else f'{val:.3f}'} km2", flush=True)
        out[lake["id"]] = {"name": lake["name"], "lat": lake["lat"],
                           "lon": lake["lon"], "series": series}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
