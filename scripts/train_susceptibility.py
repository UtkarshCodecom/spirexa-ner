"""Trains and honestly evaluates the landslide susceptibility model.

Trained on the GSI inventory: 7,498 field-mapped landslides across seven
surveyed NER states, against background points drawn only where GSI actually
looked. This model answers where a slope is prone to fail. It carries no
dates and cannot answer when -- that is the existing trigger model's job, and
this one does not replace it.

Three things here are done because leaving them out is how susceptibility
papers end up reporting 0.97 and meaning very little:

SPATIAL SPLIT. Landslides cluster. A random 80/20 split puts a slide and its
neighbour 40 m away on opposite sides of the partition, so the test set is
half memorised before training starts. The headline number here is a spatially
blocked split; the random one is reported beside it, and the gap between them
is the size of the illusion.

ROAD PROXIMITY. Half the mapped slides sit within 21 m of a road, against
1,171 m for background. Some of that is real -- a road cut removes the toe
support holding a slope up -- and some of it is that GSI surveyors walk roads
and cannot map what they cannot reach. Left in, the feature dominates and the
model partly learns where GSI surveyed. So it is trained with roads, without
roads, and with background matched to the slides' own road distances.

SLOPE MATCHING. Background drawn uniformly lands in the Brahmaputra
floodplain, where the model learns that flat ground does not slide: true,
useless, and worth several points of AUC it has not earned.
"""

import json
import math
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, confusion_matrix,
                             precision_recall_fscore_support, roc_auc_score)
from sklearn.model_selection import train_test_split

POINTS = "data/susceptibility/points.json"
FEATURES = "data/susceptibility/features.jsonl"
FEATURES2 = "data/susceptibility/features2.jsonl"
ROADS = "data/susceptibility/road_distance.json"

# Two independently published inventories, mapped from satellite imagery
# rather than walked to. They matter for one reason above all others: their
# slides sit a median 1,796 m from the nearest road, against 21 m for GSI's.
# Same hazard, same mountains, utterly different distance distribution --
# which is the survey bias measured directly instead of argued about. They
# also carry 108 positives in Arunachal Pradesh, a state GSI has not
# inventoried at all and which the model has so far had to extrapolate into.
EXT_POINTS = "data/susceptibility/points_external_all.json"
EXT_FEATURES = "data/susceptibility/features_external.jsonl"
EXT_FEATURES2 = "data/susceptibility/features2_external.jsonl"
EXT_ROADS = "data/susceptibility/road_distance_external.json"
OUT_DIR = "data/processed"
MODEL_PATH = f"{OUT_DIR}/susceptibility_model.pkl"
REPORT_PATH = f"{OUT_DIR}/susceptibility_report.json"

BLOCK_DEG = 0.25          # ~25 km spatial blocks
TEST_FRAC = 0.20
SEED = 42

BASE_FEATURES = [
    # pass one: SRTM terrain, hydrology, vegetation, climate, land cover
    "elevation", "slope", "aspect", "hnd", "upa", "ndvi", "rain_annual_mm",
    "slope_mean", "slope_max", "elevation_max", "elevation_min",
    "frac_tree", "frac_built", "frac_bare_crop",
    "relief", "tpi", "twi",
    # pass two: Copernicus terrain, curvature, landform, soil, forest loss
    "cop_elevation", "cop_slope", "cop_aspect", "curvature", "curvature_mean",
    "cop_slope_mean", "tri", "landform", "mtpi",
    "soil_clay", "soil_sand", "soil_bulkdens", "soil_carbon", "soil_texture",
    "forest_loss_frac_mean", "forest_loss_year_max",
]
ROAD_FEATURES = ["dist_road_m", "dist_major_road_m"]


def load():
    pts = {p["id"]: p for p in json.load(open(POINTS))}
    roads = json.load(open(ROADS))
    n_gsi = len(pts)
    if os.path.exists(EXT_POINTS):
        pts.update({p["id"]: p for p in json.load(open(EXT_POINTS))})
    if os.path.exists(EXT_ROADS):
        roads.update(json.load(open(EXT_ROADS)))

    def read(path):
        out = {}
        if not os.path.exists(path):
            return out
        with open(path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out[r["id"]] = r          # later rows win, so a re-run repairs
        return out

    p1, p2 = read(FEATURES), read(FEATURES2)
    p1.update(read(EXT_FEATURES))
    p2.update(read(EXT_FEATURES2))
    print(f"  pass one {len(p1)} rows, pass two {len(p2)} rows, "
          f"both {len(set(p1) & set(p2))}")
    print(f"  GSI inventory {n_gsi} points, external inventories "
          f"{len(pts) - n_gsi}")
    rows = []
    for pid, r in p1.items():
        p = pts.get(pid)
        if not p:
            continue
        r = dict(r)
        r.update(p2.get(pid, {}))
        r.update({"label": p["label"], "lat": p["lat"], "lon": p["lon"],
                  "state": p.get("state", ""),
                  "source": p.get("source", "gsi")})
        r.update(roads.get(pid, {}))
        rows.append(r)
    df = pd.DataFrame(rows).drop_duplicates(subset="id")

    # The extraction was sped up partway through by splitting the land-cover
    # reduction off the terrain one, which renamed frac_x_mean to frac_x. The
    # first 360 rows carry the old names; coalesce rather than re-fetch them.
    for c in ("frac_tree", "frac_built", "frac_bare_crop"):
        if f"{c}_mean" in df.columns:
            df[c] = df[c] if c in df.columns else np.nan
            df[c] = df[c].fillna(df[f"{c}_mean"])
        elif c not in df.columns:
            df[c] = np.nan

    # derived terrain indices
    df["relief"] = df["elevation_max"] - df["elevation_min"]
    df["tpi"] = df["elevation"] - df["elevation_mean"]
    slope_rad = np.radians(df["slope"].clip(lower=0.5))
    df["twi"] = np.log((df["upa"].clip(lower=0.001) * 1e6) / np.tan(slope_rad))
    return df


def spatial_split(df, test_frac=TEST_FRAC, seed=SEED):
    """Whole blocks go to train or test, never split down the middle."""
    rng = np.random.default_rng(seed)
    key = (np.floor(df["lat"] / BLOCK_DEG).astype(int).astype(str) + "_"
           + np.floor(df["lon"] / BLOCK_DEG).astype(int).astype(str))
    blocks = np.asarray(key.unique(), dtype=object)
    rng.shuffle(blocks)
    # take blocks until the test share is met, so the split is by area not row
    n_target = int(len(df) * test_frac)
    test_blocks, n = set(), 0
    for b in blocks:
        if n >= n_target:
            break
        test_blocks.add(b)
        n += int((key == b).sum())
    return ~key.isin(test_blocks), key.isin(test_blocks), len(blocks), len(test_blocks)


def evaluate(model, Xtr, ytr, Xte, yte, label):
    if len(set(ytr)) < 2 or len(set(yte)) < 2:
        print(f"  {label:<34} skipped -- only one class present "
              f"(train {sorted(set(ytr))}, test {sorted(set(yte))})")
        return None
    model.fit(Xtr, ytr)
    p = model.predict_proba(Xte)[:, 1]
    pred = (p >= 0.5).astype(int)
    auc = roc_auc_score(yte, p)
    pr, rc, f1, _ = precision_recall_fscore_support(yte, pred, average="binary",
                                                    zero_division=0)
    tn, fp, fn, tp = confusion_matrix(yte, pred).ravel()
    print(f"  {label:<34} AUC {auc:.4f}   acc {(tp+tn)/len(yte)*100:5.2f}%   "
          f"P {pr*100:5.2f}%  R {rc*100:5.2f}%  F1 {f1:.3f}")
    return {"label": label, "auc": round(float(auc), 4),
            "accuracy": round(float((tp + tn) / len(yte)), 4),
            "precision": round(float(pr), 4), "recall": round(float(rc), 4),
            "f1": round(float(f1), 4),
            "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
            "n_train": int(len(ytr)), "n_test": int(len(yte))}


def match_controls(df, on, bins=20, seed=SEED):
    """Keeps background points whose distribution of `on` matches the slides.

    Case-control matching. If the background sits at the same slopes, or the
    same road distances, as the slides, then the model cannot win by noticing
    that slides are steep or roadside -- it has to find something else.
    """
    rng = np.random.default_rng(seed)
    pos = df[df.label == 1]
    neg = df[df.label == 0]
    edges = np.quantile(pos[on].dropna(), np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    keep = []
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        want = int(((pos[on] >= lo) & (pos[on] < hi)).sum())
        pool = neg.index[(neg[on] >= lo) & (neg[on] < hi)].to_numpy()
        if len(pool) and want:
            keep.extend(rng.choice(pool, size=min(want, len(pool)), replace=False))
    return df.loc[list(pos.index) + list(keep)]


def main():
    df = load()
    n_pos = int((df.label == 1).sum())
    print(f"loaded {len(df)} points  ({n_pos} slides, {len(df)-n_pos} background)")
    feats_all = [c for c in BASE_FEATURES + ROAD_FEATURES if c in df.columns]
    df = df.dropna(subset=["slope", "elevation"])
    med = df[feats_all].median()
    df[feats_all] = df[feats_all].fillna(med)
    print(f"usable after dropping points with no terrain: {len(df)}\n")

    rf = lambda: RandomForestClassifier(
        n_estimators=500, max_depth=None, min_samples_leaf=3,
        class_weight="balanced", n_jobs=-1, random_state=SEED)

    results = {}
    tr_s, te_s, n_blocks, n_test_blocks = spatial_split(df)
    print(f"spatial blocks: {n_blocks} total, {n_test_blocks} held out "
          f"({te_s.sum()} points)\n")

    no_road = [c for c in feats_all if c not in ROAD_FEATURES]

    print("RANDOM 80/20 SPLIT  (optimistic: neighbouring slides land on both sides)")
    itr, ite = train_test_split(df.index, test_size=TEST_FRAC, random_state=SEED,
                                stratify=df.label)
    def keep(name, r):
        if r is not None:
            results[name] = r

    keep("random_all", evaluate(
        rf(), df.loc[itr, feats_all], df.loc[itr, "label"],
        df.loc[ite, feats_all], df.loc[ite, "label"], "all features"))
    keep("random_no_road", evaluate(
        rf(), df.loc[itr, no_road], df.loc[itr, "label"],
        df.loc[ite, no_road], df.loc[ite, "label"], "without road distance"))

    print("\nSPATIAL BLOCK SPLIT  (the honest number)")
    keep("spatial_all", evaluate(
        rf(), df.loc[tr_s, feats_all], df.loc[tr_s, "label"],
        df.loc[te_s, feats_all], df.loc[te_s, "label"], "all features"))
    keep("spatial_no_road", evaluate(
        rf(), df.loc[tr_s, no_road], df.loc[tr_s, "label"],
        df.loc[te_s, no_road], df.loc[te_s, "label"], "without road distance"))

    print("\nSPATIAL SPLIT, BACKGROUND MATCHED ON SLOPE")
    dm = match_controls(df, "slope")
    tr_m, te_m, _, _ = spatial_split(dm)
    print(f"  matched set: {len(dm)} points "
          f"({int((dm.label==1).sum())} slides, {int((dm.label==0).sum())} background)")
    keep("matched_slope", evaluate(
        rf(), dm.loc[tr_m, no_road], dm.loc[tr_m, "label"],
        dm.loc[te_m, no_road], dm.loc[te_m, "label"], "slope-matched, no road"))

    print("\nSPATIAL SPLIT, BACKGROUND MATCHED ON ROAD DISTANCE")
    if "dist_road_m" in df.columns:
        dr = match_controls(df, "dist_road_m")
        tr_r, te_r, _, _ = spatial_split(dr)
        print(f"  matched set: {len(dr)} points")
        results["matched_road"] = evaluate(
            rf(), dr.loc[tr_r, feats_all], dr.loc[tr_r, "label"],
            dr.loc[te_r, feats_all], dr.loc[te_r, "label"], "road-matched, all features")

    # Two shipped models, not one. The all-features model scores higher, but
    # 46% of that score is road proximity, and road proximity is partly a map
    # of where GSI walked. The terrain-only model is weaker and honest: it is
    # the one that can be believed in Arunachal, where nobody has surveyed and
    # every road-distance feature would be answering a question about roads.
    # Both are saved. The web app shows both and says when they disagree.
    final = rf()
    final.fit(df.loc[tr_s, feats_all], df.loc[tr_s, "label"])
    imp = sorted(zip(feats_all, final.feature_importances_), key=lambda t: -t[1])
    print("\nfeature importance (all-features model):")
    for f, v in imp:
        print(f"   {f:<20} {v*100:5.2f}%  {'#' * int(v * 160)}")

    final_nr = rf()
    final_nr.fit(df.loc[tr_s, no_road], df.loc[tr_s, "label"])

    os.makedirs(OUT_DIR, exist_ok=True)
    joblib.dump({"model": final, "feature_cols": feats_all,
                 "model_no_road": final_nr, "feature_cols_no_road": no_road,
                 "medians": med.to_dict(), "results": results,
                 "n_slides": n_pos, "source": "GSI landslide inventory"},
                MODEL_PATH)
    json.dump({"results": results,
               "importance": [{"feature": f, "importance": round(float(v), 5)}
                              for f, v in imp],
               "n_points": len(df), "n_slides": n_pos,
               "block_deg": BLOCK_DEG},
              open(REPORT_PATH, "w"), indent=1)
    print(f"\n-> {MODEL_PATH}\n-> {REPORT_PATH}")


if __name__ == "__main__":
    main()
