"""Re-samples rainfall as a neighbourhood maximum, and tests whether it helps.

The failure autopsy says 58% of the model's misses are events where the
satellite recorded little rain for a week the catalogue describes as a
downpour. IMERG resolves about 11 km. A convective cell that sits on one
ridge is smaller than one pixel, and the pixel containing the catalogued
coordinate is not necessarily the pixel the storm was in -- particularly
when the catalogue itself only places the event to within 5 to 50 km.

So: sample the same IMERG windows again, but take the maximum over a radius
instead of the value at a point, and add those as extra features rather than
replacing the point values. The model then has both and can decide.

Applied identically to landslides and non-events -- taking a maximum only
for the positive class would leak the label and manufacture a result.

Writes data/processed/storm_rain.csv (id, storm_rain_1d/3d/7d), which
build_dataset-style joins can pick up.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ee
import pandas as pd

from config import GEE_PROJECT, TRAINING_CSV
from gee_features import MISSING, _collections, _or_missing, init

OUT = "data/processed/storm_rain.csv"
STORM_WINDOWS = (1, 3, 7)
STORM_RADIUS_M = 15000      # ~1.5 IMERG pixels; matches the finer end of the
                            # catalogue's own location uncertainty
CHUNK = 25


def main():
    init(GEE_PROJECT)
    col = _collections()

    df = pd.read_csv(TRAINING_CSV)
    points = [
        {"id": str(r["id"]), "lat": float(r["lat"]), "lon": float(r["lon"]),
         "date": str(r["date"])[:10]}
        for _, r in df.iterrows()
    ]
    done = {}
    if os.path.exists(OUT):
        prev = pd.read_csv(OUT)
        done = {str(r["id"]): r for _, r in prev.iterrows()}
        print(f"resuming: {len(done)} already extracted", flush=True)
    todo = [p for p in points if p["id"] not in done]
    print(f"{len(points)} rows, {len(todo)} to extract", flush=True)

    def per_feature(feat):
        date = ee.Date(feat.get("d"))
        area = feat.geometry().buffer(STORM_RADIUS_M)
        bands = []
        for days in STORM_WINDOWS:
            window = col["gpm"].filterDate(date.advance(-days, "day"), date)
            # scale each 30-min snapshot before reducing, never after, or the
            # MISSING sentinel gets scaled too and slips past the cleaner
            half = window.map(lambda img: img.multiply(0.5))
            bands.append(_or_missing(half, ee.Reducer.sum(), ["r"])
                         .rename(f"storm_rain_{days}d"))
        img = ee.Image.cat(bands)
        stats = img.reduceRegion(
            reducer=ee.Reducer.max(), geometry=area, scale=5000, maxPixels=1e9)
        return ee.Feature(None, stats.set("pid", feat.get("pid")))

    rows = list(done.values())
    for start in range(0, len(todo), CHUNK):
        chunk = todo[start:start + CHUNK]
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]),
                       {"pid": p["id"], "d": p["date"]})
            for p in chunk
        ])
        for attempt in range(4):
            try:
                got = fc.map(per_feature).getInfo()["features"]
                break
            except Exception as e:                    # noqa: BLE001
                print(f"    retry ({type(e).__name__}: {e})", flush=True)
                time.sleep(20 * (attempt + 1))
        else:
            print("    chunk failed, skipping", flush=True)
            continue

        for g in got:
            pr = g["properties"]
            rec = {"id": pr.get("pid")}
            for days in STORM_WINDOWS:
                v = pr.get(f"storm_rain_{days}d")
                rec[f"storm_rain_{days}d"] = (
                    None if v is None or v <= MISSING + 1 else round(float(v), 2))
            rows.append(rec)

        pd.DataFrame(rows).to_csv(OUT, index=False)
        print(f"  {min(start + CHUNK, len(todo))}/{len(todo)}", flush=True)

    print(f"\n-> {OUT}  ({len(rows)} rows)")


if __name__ == "__main__":
    sys.exit(main())
