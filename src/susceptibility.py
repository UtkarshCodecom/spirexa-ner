"""Where the ground is prone to failing -- and what to do about it.

The trigger model answers *when*: it reads the last fortnight of rain and
says whether today is dangerous. It knows nothing about the hillside. The
susceptibility model answers *where*: trained on 7,498 GSI field-mapped
landslides against 11,996 background points, on terrain, soil, vegetation,
hydrology and road proximity, it says whether a slope is the kind that fails.
Neither is useful alone. Rain on stable ground is weather; a bad slope in dry
weather is a maintenance ticket. Both together is an evacuation.

TWO MODELS, NOT ONE
    with_roads     spatial-block AUC 0.9467
    terrain_only   spatial-block AUC 0.8682

The first is stronger, and 46% of its strength is distance to the nearest
road. Part of that is physics -- a road cut removes the toe support holding a
slope up, and hundreds of GSI records name road cutting as the trigger. Part
of it is that GSI surveyors walk roads, so a roadside slide gets mapped and
an identical slide two ridges back does not. The second model has both road
features removed. It is weaker and it is the one that can be believed where
nobody has surveyed.

Shipping both turns a caveat into a diagnosis. The gap between them is not
noise -- it says which kind of problem this is:

    both high             the hillside itself is unstable
    roads high only       the road cut is the hazard, not the slope
    terrain high only     steep ground away from any road, likely unmapped

and each of those has a different fix, a different budget, and a different
department.
"""

import datetime
import json
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_SCRIPTS = os.path.join(_ROOT, "scripts")

MODEL_PATH = os.path.join(_ROOT, "data/processed/susceptibility_model.pkl")
REPORT_PATH = os.path.join(_ROOT, "data/processed/susceptibility_report.json")
HOTSPOT_PATH = os.path.join(_ROOT, "data/processed/hotspot_susceptibility.json")
ROADS_TOPO = os.path.join(_ROOT, "data/geo/roads_topo.json")
ROAD_CACHE = os.path.join(_ROOT, "data/processed/road_vertices.npz")

NBHD_M = 300
LC_SCALE = 100
SOIL_SCALE = 250

LAT0 = 25.6
KM_PER_DEG_LAT = 110.574
KM_PER_DEG_LON = 111.320 * math.cos(math.radians(LAT0))

_bundle = None
_trees = None
_report = None


# --------------------------------------------------------------------------
# model

def bundle():
    """The trained pair. Loaded once; the two forests are ~180 MB together."""
    global _bundle
    if _bundle is None:
        import joblib
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def report():
    global _report
    if _report is None:
        with open(REPORT_PATH) as f:
            _report = json.load(f)
    return _report


def available():
    return os.path.exists(MODEL_PATH)


# --------------------------------------------------------------------------
# road distance

def _road_trees():
    """KD-trees over every OSM road vertex in the region.

    Built from a 428 MB topology dump, so the vertices are cached to a 100 MB
    array the first time and the dump is never read again. The trees take
    about twenty seconds to build and are then reused for the life of the
    process, which is why nothing here is done per-request from cold.
    """
    global _trees
    if _trees is not None:
        return _trees
    from scipy.spatial import cKDTree

    if not os.path.exists(ROAD_CACHE):
        cache_road_vertices()
    z = np.load(ROAD_CACHE)
    _trees = (cKDTree(z["all"]), cKDTree(z["major"]))
    return _trees


def cache_road_vertices():
    """One-off: flatten the OSM topology to two projected vertex arrays."""
    print("caching road vertices from topology dump ...", flush=True)
    with open(ROADS_TOPO) as f:
        ways = json.load(f)["ways"]
    all_pts, major_pts = [], []
    for w in ways.values():
        major = w["cls"] == "major"
        for lon, lat in w["coords"]:
            all_pts.append((lon * KM_PER_DEG_LON, lat * KM_PER_DEG_LAT))
            if major:
                major_pts.append((lon * KM_PER_DEG_LON, lat * KM_PER_DEG_LAT))
    del ways
    np.savez(ROAD_CACHE,
             all=np.asarray(all_pts, dtype=np.float32),
             major=np.asarray(major_pts, dtype=np.float32))
    print(f"  {len(all_pts)} vertices, {len(major_pts)} major -> {ROAD_CACHE}",
          flush=True)


def road_distance(points):
    """Metres to the nearest road vertex, and to the nearest major one."""
    tree_all, tree_major = _road_trees()
    q = np.column_stack([
        np.asarray([p["lon"] for p in points], dtype=np.float64) * KM_PER_DEG_LON,
        np.asarray([p["lat"] for p in points], dtype=np.float64) * KM_PER_DEG_LAT,
    ])
    d_all, _ = tree_all.query(q, k=1)
    d_maj, _ = tree_major.query(q, k=1)
    return [{"dist_road_m": float(a * 1000.0), "dist_major_road_m": float(m * 1000.0)}
            for a, m in zip(d_all, d_maj)]


# --------------------------------------------------------------------------
# terrain features
#
# The two image definitions are imported from the extraction scripts rather
# than copied, so a point scored live and a point in the training set are
# guaranteed to be measuring the same thing. A copy here would drift the
# first time either is touched, and the drift would be silent.

def _images():
    if _SCRIPTS not in sys.path:
        sys.path.insert(0, _SCRIPTS)
    import extract_susceptibility_features as p1
    import extract_susceptibility_features2 as p2
    return p1.build_image(), p2.build_image()


def terrain_features(points, chunk=100):
    """Every static covariate the model was trained on, for a list of points.

    points: [{"id":, "lat":, "lon":}, ...]
    """
    import ee
    from config import GEE_PROJECT

    try:
        ee.Initialize(project=GEE_PROJECT)
    except Exception:                                     # noqa: BLE001
        pass
    img1, img2 = _images()

    point_bands = img1.select(["elevation", "slope", "aspect", "hnd", "upa",
                               "ndvi", "rain_annual_mm"])
    terrain_nbhd = img1.select(["elevation", "slope"])
    lc_nbhd = img1.select(["frac_tree", "frac_built", "frac_bare_crop"])
    nbhd_red = (ee.Reducer.mean()
                .combine(ee.Reducer.max(), sharedInputs=True)
                .combine(ee.Reducer.min(), sharedInputs=True))
    point_img, soil_img, loss_img = img2["point"], img2["soil"], img2["loss"]
    curv_nbhd = point_img.select(["curvature", "cop_slope"])

    def per_feature(feat):
        g = feat.geometry()
        ring = g.buffer(NBHD_M)
        at = point_bands.reduceRegion(ee.Reducer.first(), g, 30, maxPixels=1e9)
        terr = terrain_nbhd.reduceRegion(nbhd_red, ring, 30, maxPixels=1e9)
        lc = lc_nbhd.reduceRegion(ee.Reducer.mean(), ring, LC_SCALE, maxPixels=1e9)
        at2 = point_img.reduceRegion(ee.Reducer.first(), g, 30, maxPixels=1e9)
        curv = curv_nbhd.reduceRegion(ee.Reducer.mean(), ring, 30, maxPixels=1e9) \
            .rename(["curvature", "cop_slope"], ["curvature_mean", "cop_slope_mean"])
        soil = soil_img.reduceRegion(ee.Reducer.first(), g, SOIL_SCALE, maxPixels=1e9)
        loss = loss_img.reduceRegion(
            ee.Reducer.mean().combine(ee.Reducer.max(), sharedInputs=True),
            ring, 30, maxPixels=1e9)
        return ee.Feature(None, at.combine(terr).combine(lc).combine(at2)
                          .combine(curv).combine(soil).combine(loss)
                          .set("pid", feat.get("pid")))

    out = {}
    for start in range(0, len(points), chunk):
        part = points[start:start + chunk]
        fc = ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point([p["lon"], p["lat"]]), {"pid": p["id"]})
            for p in part
        ])
        rows = fc.map(per_feature).getInfo()["features"]
        for r in rows:
            pr = dict(r["properties"])
            pid = pr.pop("pid")
            out[pid] = {k: (None if v is None else float(v)) for k, v in pr.items()}
        print(f"  features {min(start + chunk, len(points))}/{len(points)}",
              flush=True)
    return out


def derive(r):
    """The three indices the training loader computes rather than fetches."""
    r = dict(r)
    for c in ("frac_tree", "frac_built", "frac_bare_crop"):
        if r.get(c) is None and r.get(f"{c}_mean") is not None:
            r[c] = r[f"{c}_mean"]
    if r.get("elevation_max") is not None and r.get("elevation_min") is not None:
        r["relief"] = r["elevation_max"] - r["elevation_min"]
    if r.get("elevation") is not None and r.get("elevation_mean") is not None:
        r["tpi"] = r["elevation"] - r["elevation_mean"]
    if r.get("upa") is not None and r.get("slope") is not None:
        slope_rad = math.radians(max(r["slope"], 0.5))
        r["twi"] = math.log(max(r["upa"], 0.001) * 1e6 / math.tan(slope_rad))
    return r


# --------------------------------------------------------------------------
# scoring

def score_rows(rows):
    """Both probabilities for a list of already-featured points."""
    import pandas as pd

    b = bundle()
    med = b["medians"]
    cols_all = b["feature_cols"]
    cols_nr = b.get("feature_cols_no_road") or [
        c for c in cols_all if not c.startswith("dist_")]

    frame = []
    for r in rows:
        r = derive(r)
        frame.append({c: (r.get(c) if r.get(c) is not None else med.get(c))
                      for c in cols_all})
    X = pd.DataFrame(frame, columns=cols_all)
    p_all = b["model"].predict_proba(X)[:, 1]
    nr = b.get("model_no_road")
    p_nr = nr.predict_proba(X[cols_nr])[:, 1] if nr is not None else p_all
    return [{"with_roads": round(float(a), 4), "terrain_only": round(float(t), 4)}
            for a, t in zip(p_all, p_nr)]


def score_points(points):
    """Full path from coordinates to both scores. One EE round trip per 100."""
    feats = terrain_features(points)
    roads = road_distance(points)
    rows = []
    for p, rd in zip(points, roads):
        r = dict(feats.get(p["id"], {}))
        r.update(rd)
        rows.append(r)
    scored = score_rows(rows)
    for p, s, r in zip(points, scored, rows):
        s["features"] = r
    return scored


# --------------------------------------------------------------------------
# what an operator is supposed to do with two numbers

def band(p):
    if p >= 0.75:
        return "SEVERE"
    if p >= 0.5:
        return "HIGH"
    if p >= 0.25:
        return "MODERATE"
    return "LOW"


def ground_type(with_roads, terrain_only):
    """Which of the three the disagreement between the models means."""
    gap = with_roads - terrain_only
    if terrain_only >= 0.5 and with_roads >= 0.5:
        return {"kind": "slope",
                "label": "Unstable hillside",
                "detail": "Both models agree without needing road proximity. "
                          "The slope itself is the problem: drainage, "
                          "vegetation and toe support work, not a road fix."}
    if gap >= 0.25 and with_roads >= 0.5:
        return {"kind": "road_cut",
                "label": "Road-cut hazard",
                "detail": "The score is carried by proximity to a cut. "
                          "Treat as an engineering asset -- retaining wall, "
                          "cut-slope drainage, benching -- and note that GSI "
                          "maps roadsides far more thoroughly than backslopes."}
    if terrain_only - with_roads >= 0.15 and terrain_only >= 0.5:
        return {"kind": "unmapped",
                "label": "Steep ground, no road",
                "detail": "Terrain says prone, road distance says nobody has "
                          "been there. This is the case the inventory is "
                          "blind to -- most of Arunachal looks like this."}
    return {"kind": "stable",
            "label": "Not a susceptible slope",
            "detail": "Neither model finds this ground prone to failing."}


def decision(trigger, with_roads, terrain_only):
    """The one output a district officer actually reads.

    Susceptibility is static and trigger is today's rain. Crossing them is
    the whole point: the same 70% rainfall score means evacuate on one
    hillside and means nothing on another.
    """
    susc = terrain_only          # the conservative one drives the decision
    hot = trigger >= 0.5
    prone = susc >= 0.5 or with_roads >= 0.6

    if hot and prone:
        action, why = "ACT", ("Rain is at a triggering level and the ground "
                              "is the kind that fails. Close the road, move "
                              "people off the toe, send a patrol.")
    elif hot and not prone:
        action, why = "WATCH", ("The rain is real but this ground has no "
                                "history or terrain signature of failing. "
                                "Keep it on the board; do not spend the "
                                "response budget here first.")
    elif not hot and prone:
        action, why = "PREPARE", ("Dry today, but this is a slope that fails "
                                  "when it is not. This is where a sensor "
                                  "goes, and where pre-monsoon drainage work "
                                  "pays for itself.")
    else:
        action, why = "CLEAR", "Neither the sky nor the ground is a problem."

    return {"action": action, "why": why,
            "trigger": round(float(trigger), 4),
            "susceptibility": round(float(with_roads), 4),
            "susceptibility_terrain_only": round(float(terrain_only), 4),
            "disagreement": round(float(with_roads - terrain_only), 4),
            "ground": ground_type(with_roads, terrain_only)}


# --------------------------------------------------------------------------
# precomputed hotspot table

def hotspots():
    if not os.path.exists(HOTSPOT_PATH):
        return None
    with open(HOTSPOT_PATH) as f:
        return json.load(f)


def hotspot_map():
    h = hotspots()
    return {r["id"]: r for r in h["hotspots"]} if h else {}


def model_card():
    """What the numbers mean, for the page that shows them."""
    r = report()["results"]
    return {
        "source": "GSI landslide inventory, 7,498 field-mapped slides",
        "n_points": report().get("n_points"),
        "n_slides": report().get("n_slides"),
        "with_roads": {"auc": r["spatial_all"]["auc"],
                       "accuracy": r["spatial_all"]["accuracy"]},
        "terrain_only": {"auc": r["spatial_no_road"]["auc"],
                         "accuracy": r["spatial_no_road"]["accuracy"]},
        "random_split_auc": r["random_all"]["auc"],
        "road_share": round(sum(f["importance"] for f in report()["importance"]
                                if f["feature"].startswith("dist_")), 4),
        "split": f"spatially blocked, {report().get('block_deg')} degree blocks",
        "generated": datetime.datetime.fromtimestamp(
            os.path.getmtime(MODEL_PATH)).isoformat(timespec="seconds"),
    }
