"""Exports the HAND terrain grid for the NER frame, once.

HAND -- Height Above Nearest Drainage -- is the terrain index NOAA's National
Water Model uses to turn a river stage into a flood map: for every pixel, how
far it sits above the channel it drains into. Flooding to a stage of h metres
is then just "every pixel whose HAND is below h".

MERIT Hydro publishes HAND globally at 3 arc-seconds, and it is in the Earth
Engine catalogue, so none of it has to be computed here.

The grid is written as a greyscale PNG on the dashboard's own map frame, so
the browser can threshold it against a slider with no server call and no
internet -- the same reason three.js is vendored for the simulator.

    pixel value 0..250  ->  HAND 0..50 m   (value = HAND * 5)
    pixel value 255     ->  never floods (drains to a trivial catchment)
"""

import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ee
from config import GEE_PROJECT

# identical to build_dashboard / mobile_geo
LON_MIN, LON_MAX = 87.5, 97.8
LAT_MIN, LAT_MAX = 21.5, 29.8
WIDTH, HEIGHT = 1800, 1609          # 2x the dashboard frame, for zooming in

HAND_MAX_M = 50.0                   # above this nothing we care about floods

OUT = "static/hand_ner.png"


def main():
    ee.Initialize(project=GEE_PROJECT)
    region = ee.Geometry.Rectangle([LON_MIN, LAT_MIN, LON_MAX, LAT_MAX], None, False)

    merit = ee.Image("MERIT/Hydro/v1_0_1")
    hnd = merit.select("hnd")

    # No catchment mask here. The obvious-looking filter -- drop pixels whose
    # own upstream area is small -- is wrong: a floodplain pixel beside the
    # Brahmaputra has a tiny catchment of its own and still drains into it.
    # MERIT already computes hnd against a thresholded channel network, so
    # the gully problem is handled upstream of us.
    scaled = (
        hnd.clamp(0, HAND_MAX_M)
        .multiply(250.0 / HAND_MAX_M)
        .unmask(255)
        .toByte()
        .rename("hand")
    )

    url = scaled.getThumbURL({
        "region": region,
        "dimensions": f"{WIDTH}x{HEIGHT}",
        "format": "png",
        "min": 0,
        "max": 255,
    })
    print("requesting grid from Earth Engine ...", flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as r, open(OUT, "wb") as f:
        f.write(r.read())

    print(f"-> {OUT}  ({os.path.getsize(OUT)/1024:.0f} KB, {WIDTH}x{HEIGHT})")
    print(f"   HAND 0-{HAND_MAX_M:.0f} m encoded as 0-250; 255 = no data")


if __name__ == "__main__":
    sys.exit(main())
