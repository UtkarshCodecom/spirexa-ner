"""Second feature pass: better terrain, curvature, soil, and forest loss.

The first pass used SRTM and land cover, which is the standard minimum. This
adds the covariates that susceptibility literature consistently finds matter
and that the first pass had no way to express:

    Copernicus GLO-30   a better DEM than SRTM in steep terrain, where SRTM's
                        C-band radar struggles with layover and voids -- and
                        steep terrain is the entire study area
    curvature           whether a slope is concave (water and debris converge)
                        or convex (they diverge). One of the strongest single
                        predictors there is, and absent from pass one.
    ruggedness          local relief at the scale a failure actually happens
    landform class      ERGo's terrain classification: valley, ridge, slope
    mTPI                position in the landscape at multiple scales
    soil                clay, sand, bulk density, organic carbon. What is on
                        the slope decides whether water raises pore pressure
                        or drains away, and nothing in pass one knew anything
                        about the material at all.
    forest loss         Hansen year of loss nearby. Cutting a hillside down is
                        a landslide driver on a timescale of a few years.

Keyed by the same point ids as pass one and joined at training time, so the
first pass does not have to be thrown away and re-run.
"""

import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import ee

from config import GEE_PROJECT

POINTS = "data/susceptibility/points.json"
OUT = "data/susceptibility/features2.jsonl"

NBHD_M = 300
CHUNK = 150
SOIL_SCALE = 250


def build_image():
    # mosaic() returns an image with no meaningful projection -- it defaults to
    # WGS84 at one degree per pixel. ee.Terrain then computes slope across
    # 111 km cells and reports 1 degree on a hillside SRTM calls 38. The same
    # silence affects convolve and reduceNeighborhood. Pin the projection back
    # to the collection's own before doing anything spatial with it.
    col = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM")
    proj = col.first().projection()
    cop = col.mosaic().setDefaultProjection(proj)
    terr = ee.Terrain.products(cop.rename("elevation"))

    # Laplacian of elevation approximates total curvature: negative is
    # concave (convergent, wet, where debris collects), positive convex.
    curv = cop.convolve(ee.Kernel.laplacian8()).rename("curvature")
    # Ruggedness: how much the surface varies in the immediate neighbourhood.
    tri = cop.reduceNeighborhood(
        ee.Reducer.stdDev(), ee.Kernel.square(3)).rename("tri")

    landform = ee.Image("CSP/ERGo/1_0/Global/SRTM_landforms").rename("landform")
    mtpi = ee.Image("CSP/ERGo/1_0/Global/SRTM_mTPI").rename("mtpi")

    soil = (ee.Image("OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02")
            .select("b10").rename("soil_clay")
            .addBands(ee.Image("OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02")
                      .select("b10").rename("soil_sand"))
            .addBands(ee.Image("OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02")
                      .select("b10").rename("soil_bulkdens"))
            .addBands(ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02")
                      .select("b10").rename("soil_carbon"))
            .addBands(ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02")
                      .select("b10").rename("soil_texture")))

    # Two different questions: how much of the neighbourhood was cleared, and
    # how recently. Max year alone is near-constant because almost every ring
    # in this region contains at least one lost pixel.
    hansen = ee.Image("UMD/hansen/global_forest_change_2025_v1_13").select("lossyear")
    loss = (hansen.gt(0).unmask(0).rename("forest_loss_frac")
            .addBands(hansen.unmask(0).rename("forest_loss_year")))

    return {
        "point": terr.select(["elevation", "slope", "aspect"])
                 .rename(["cop_elevation", "cop_slope", "cop_aspect"])
                 .addBands(curv).addBands(tri)
                 .addBands(landform).addBands(mtpi),
        "soil": soil,
        "loss": loss,
    }


def main():
    ee.Initialize(project=GEE_PROJECT)
    img = build_image()
    point_img, soil_img, loss_img = img["point"], img["soil"], img["loss"]
    curv_nbhd = point_img.select(["curvature", "cop_slope"])

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
    random.Random(42).shuffle(todo)
    print(f"{len(pts)} points, {len(todo)} to extract (shuffled)", flush=True)

    def per_feature(feat):
        g = feat.geometry()
        ring = g.buffer(NBHD_M)
        at = point_img.reduceRegion(ee.Reducer.first(), g, 30, maxPixels=1e9)
        curv = curv_nbhd.reduceRegion(ee.Reducer.mean(), ring, 30, maxPixels=1e9) \
            .rename(["curvature", "cop_slope"], ["curvature_mean", "cop_slope_mean"])
        soil = soil_img.reduceRegion(ee.Reducer.first(), g, SOIL_SCALE, maxPixels=1e9)
        # any forest clearing within the ring, and how recent
        loss = loss_img.reduceRegion(
            ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True),
            ring, 30, maxPixels=1e9)
        return ee.Feature(None, at.combine(curv).combine(soil).combine(loss)
                          .set("pid", feat.get("pid")))

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
            print(f"  {n}/{len(todo)}   {rate:.1f} pts/s   "
                  f"eta {(len(todo)-n)/max(rate,1e-6)/60:.0f} min", flush=True)
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
