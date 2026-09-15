"""Exports the NER river network as a raster, from the same source as HAND.

OpenStreetMap has the names, but Overpass rate-limits this region down to
hours per pass. MERIT Hydro is already in the Earth Engine catalogue, is the
same dataset HAND comes from -- so the rivers line up with the flood layer
pixel for pixel, which OSM geometry would not -- and carries upstream
drainage area, which is what sizes a river.

    viswth  river width, widened for display
    upa     upstream drainage area, km2

Output is a PNG on the dashboard's map frame:
    R = river present, intensity by log(catchment)   0 = no river
"""

import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ee
from config import GEE_PROJECT

LON_MIN, LON_MAX = 87.5, 97.8
LAT_MIN, LAT_MAX = 21.5, 29.8
WIDTH, HEIGHT = 1800, 1609
MIN_CATCHMENT_KM2 = 100.0

OUT = "static/rivers_ner.png"


def main():
    ee.Initialize(project=GEE_PROJECT)
    region = ee.Geometry.Rectangle([LON_MIN, LAT_MIN, LON_MAX, LAT_MAX], None, False)

    merit = ee.Image("MERIT/Hydro/v1_0_1")
    upa = merit.select("upa")
    vis = merit.select("viswth")

    # A channel is anywhere MERIT gives a visualisation width. Brightness runs
    # with log10 of the catchment behind it, so the Brahmaputra reads heavier
    # than a hill stream instead of every river being one flat blue.
    # viswth > 0 covers 30% of the frame once downsampled to ~600 m pixels --
    # a blue wash, not a river network. Catchment size is the honest filter:
    # 100 km2 upstream is a river somebody would name.
    is_river = upa.gte(MIN_CATCHMENT_KM2)
    mag = (
        upa.max(1).log10()                 # 2 at 100 km2, ~5.6 at the Brahmaputra
        .unitScale(2.0, 5.6).clamp(0, 1)
        .multiply(185).add(70)             # 70..255, so tributaries stay visible
    )
    band = mag.where(is_river.Not(), 0).unmask(0).toByte().rename("river")

    url = band.getThumbURL({
        "region": region, "dimensions": f"{WIDTH}x{HEIGHT}",
        "format": "png", "min": 0, "max": 255,
    })
    print("requesting river grid from Earth Engine ...", flush=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as r, open(OUT, "wb") as f:
        f.write(r.read())
    print(f"-> {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB, {WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    sys.exit(main())
