"""Static terrain and land-cover covariates for the susceptibility model.

Every feature here is time-invariant on the scale that matters: what makes a
hillside prone to failing, not what makes it fail on a given Tuesday. The
trigger model already handles the Tuesday.

    SRTM              elevation, slope, aspect, local relief, TPI
    MERIT Hydro       height above nearest drainage, upstream area -> TWI
    MODIS             NDVI, a decade's median
    CHIRPS            mean annual rainfall, the climatological soaking
    ESA WorldCover    tree / built / bare fractions around the point

Distance to road is computed locally from the OSM topology dump rather than
here: 340,068 ways through a KD-tree beats 19,494 server-side buffers.

Resumable -- it writes after every chunk, and re-running skips what is done.
"""

import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ee

from config import GEE_PROJECT

POINTS = "data/susceptibility/points_external_all.json"
OUT = "data/susceptibility/features_external.jsonl"

NBHD_M = 300
# Bigger chunks amortise the round trip; the server-side work per point is
# unchanged but there are a quarter as many requests.
CHUNK = 150
# Land-cover fractions are sampled coarser than the terrain. WorldCover is a
# 10 m categorical product and averaging it at 30 m over a 300 m buffer was
# the single most expensive thing in the request; at 100 m the fraction is
# statistically the same and the call is far cheaper.
LC_SCALE = 100
MISSING = -9999


def build_image():
    srtm = ee.Image("USGS/SRTMGL1_003")
    terr = ee.Terrain.products(srtm)
    merit = ee.Image("MERIT/Hydro/v1_0_1")

    ndvi = (ee.ImageCollection("MODIS/061/MOD13Q1")
            .filterDate("2015-01-01", "2025-01-01").select("NDVI").median())

    chirps = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
              .filterDate("2015-01-01", "2025-01-01").select("precipitation").mean()
              .multiply(365).rename("rain_annual_mm"))

    wc = ee.Image("ESA/WorldCover/v200/2021").select("Map")
    tree = wc.eq(10).rename("frac_tree")
    built = wc.eq(50).rename("frac_built")
    bare = wc.eq(60).Or(wc.eq(40)).rename("frac_bare_crop")

    return (terr.select(["elevation", "slope", "aspect"])
            .addBands(merit.select(["hnd", "upa"]))
            .addBands(ndvi.rename("ndvi"))
            .addBands(chirps)
            .addBands(tree).addBands(built).addBands(bare))


def main():
    ee.Initialize(project=GEE_PROJECT)
    img = build_image()
    point_bands = img.select(["elevation", "slope", "aspect", "hnd", "upa",
                              "ndvi", "rain_annual_mm"])
    terrain_nbhd = img.select(["elevation", "slope"])
    lc_nbhd = img.select(["frac_tree", "frac_built", "frac_bare_crop"])
    nbhd_red = (ee.Reducer.mean()
                .combine(ee.Reducer.max(), sharedInputs=True)
                .combine(ee.Reducer.min(), sharedInputs=True))

    pts = json.load(open(POINTS))
    done = set()
    if os.path.exists(OUT):
        with open(OUT) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
        print(f"resuming: {len(done)} already extracted", flush=True)
    todo = [p for p in pts if p["id"] not in done]
    # Shuffled, because the point file is every landslide followed by every
    # background point. Extracted in that order, a run interrupted at 40% has
    # 7,498 positives and no negatives, and nothing can be trained on it.
    # Shuffled, any prefix is a usable sample of both classes.
    random.Random(42).shuffle(todo)
    print(f"{len(pts)} points, {len(todo)} to extract (shuffled)", flush=True)

    def per_feature(feat):
        g = feat.geometry()
        ring = g.buffer(NBHD_M)
        at = point_bands.reduceRegion(ee.Reducer.first(), g, 30, maxPixels=1e9)
        terr = terrain_nbhd.reduceRegion(nbhd_red, ring, 30, maxPixels=1e9)
        lc = lc_nbhd.reduceRegion(ee.Reducer.mean(), ring, LC_SCALE, maxPixels=1e9)
        return ee.Feature(
            None, at.combine(terr).combine(lc).set("pid", feat.get("pid")))

    t0 = time.time()
    with open(OUT, "a") as out:
        for start in range(0, len(todo), CHUNK):
            chunk = todo[start:start + CHUNK]
            fc = ee.FeatureCollection([
                ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"pid": p["id"]})
                for p in chunk
            ])
            rows = None
            for attempt in range(4):
                try:
                    rows = fc.map(per_feature).getInfo()["features"]
                    break
                except Exception as e:                       # noqa: BLE001
                    print(f"    retry ({type(e).__name__}: {str(e)[:90]})", flush=True)
                    time.sleep(15 * (attempt + 1))
            if rows is None:
                print("    chunk failed, skipping", flush=True)
                continue

            for r in rows:
                pr = r["properties"]
                rec = {"id": pr.pop("pid")}
                for k, v in pr.items():
                    rec[k] = None if v is None else float(v)
                out.write(json.dumps(rec) + "\n")
            out.flush()

            n = min(start + CHUNK, len(todo))
            rate = n / max(time.time() - t0, 1e-6)
            eta = (len(todo) - n) / max(rate, 1e-6) / 60
            print(f"  {n}/{len(todo)}   {rate:.1f} pts/s   eta {eta:.0f} min", flush=True)

    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
