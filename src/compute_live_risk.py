"""Scores every monitored hotspot against today's conditions.

Writes data/processed/live_risk.csv, which the dashboard and the alert
system both read.
"""

import datetime

import joblib
import pandas as pd

from config import FEATURE_COLUMNS, GEE_PROJECT, MODEL_PATH
from gee_features import get_features_batch
from local_features import add_local_features

LOCATIONS_CSV = "data/processed/unique_locations.csv"
POSITIVES_CSV = "data/raw/combined_ner_landslides.csv"
OUTPUT_CSV = "data/processed/live_risk.csv"


def load_locations():
    try:
        return pd.read_csv(LOCATIONS_CSV)
    except FileNotFoundError:
        df = pd.read_csv(POSITIVES_CSV)
        unique = df.drop_duplicates(subset=["lat", "lon"])[
            ["id", "location", "lat", "lon", "state"]
        ]
        unique.to_csv(LOCATIONS_CSV, index=False)
        return unique


def main():
    today = datetime.date.today().isoformat()
    locations = load_locations()
    bundle = joblib.load(MODEL_PATH)
    model, feature_cols, medians = (
        bundle["model"],
        bundle["feature_cols"],
        bundle["medians"],
    )

    points = [
        {"id": r["id"], "lat": r["lat"], "lon": r["lon"], "date": today}
        for _, r in locations.iterrows()
    ]
    print(f"Scoring {len(points)} hotspots for {today}...")
    by_id = get_features_batch(points, GEE_PROJECT)

    rows = []
    for _, r in locations.iterrows():
        feats = dict(by_id.get(str(r["id"]), {}))
        if feats:
            feats = add_local_features(feats, r["lat"], r["lon"])
        row = {
            c: feats.get(c) if feats.get(c) is not None else medians[c]
            for c in feature_cols
        }
        prob = float(model.predict_proba(pd.DataFrame([row], columns=feature_cols))[0][1])
        rows.append({**r.to_dict(), "live_risk": prob, "as_of_date": today})

    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT_CSV, index=False)

    high = (out["live_risk"] >= 0.5).sum()
    print(f"\nSnapshot for {today} -> {OUTPUT_CSV}")
    print(f"  {len(out)} hotspots, {high} at high or severe risk")
    print(f"  mean risk {out['live_risk'].mean() * 100:.1f}%")


if __name__ == "__main__":
    main()
