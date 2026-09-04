"""Builds the training table: real landslide events (label=1) plus sampled
non-landslide points/dates (label=0), each with satellite features from
Earth Engine.

Negatives are matched to their positive on distance-to-road. Without that,
the model learns reporting bias instead of physics: a slope failure that
blocks a highway gets catalogued, an identical one in remote forest does not,
so recorded landslides sit far closer to roads than random terrain does
(median 243 m vs 2542 m when sampled naively). A model trained on that
separates the classes on road proximity and then under-predicts risk for
exactly the remote settlements this system is meant to protect.
"""

import math
import random
from datetime import timedelta

import pandas as pd

from config import (
    EXCLUDE_WINDOW_DAYS,
    FEATURE_COLUMNS,
    GEE_PROJECT,
    NEGATIVE_RADIUS_DEG,
    NEGATIVES_PER_POSITIVE,
    POSITIVES_CSV,
    TRAINING_CSV,
)
from gee_features import get_features_batch
from local_features import add_local_features, distance_to_road_m

random.seed(42)

# A negative is accepted when its distance-to-road falls in the same log2
# bucket as its positive, i.e. within roughly a factor of two.
ROAD_MATCH_TOLERANCE = 1.0


def load_positives():
    df = pd.read_csv(POSITIVES_CSV)
    df["date"] = pd.to_datetime(df["date"])
    return df


def sample_negatives(positives):
    min_date, max_date = positives["date"].min(), positives["date"].max()
    total_days = (max_date - min_date).days
    event_dates = sorted(positives["date"].dt.date)

    def too_close_to_any_event(candidate_date):
        # event_dates is sorted, but a linear scan is still fast enough at this scale
        return any(abs((candidate_date - d).days) <= EXCLUDE_WINDOW_DAYS for d in event_dates)

    negatives = []
    unmatched = 0

    for _, pos in positives.iterrows():
        target_road_dist = distance_to_road_m(pos["lat"], pos["lon"])
        target_bucket = math.log2(max(target_road_dist, 1.0))

        made = 0
        attempts = 0
        # Widen the search radius if a matching negative proves hard to find.
        while made < NEGATIVES_PER_POSITIVE and attempts < 600:
            attempts += 1
            spread = NEGATIVE_RADIUS_DEG * (1 + attempts // 200)
            lat = round(pos["lat"] + random.uniform(-spread, spread), 5)
            lon = round(pos["lon"] + random.uniform(-spread, spread), 5)

            candidate_date = (min_date + timedelta(days=random.randint(0, total_days))).date()
            if too_close_to_any_event(candidate_date):
                continue

            cand_road_dist = distance_to_road_m(lat, lon)
            gap = abs(math.log2(max(cand_road_dist, 1.0)) - target_bucket)
            # Relax the match rather than give up entirely on stubborn sites.
            tolerance = ROAD_MATCH_TOLERANCE * (1 + attempts // 300)
            if gap > tolerance:
                continue

            negatives.append(
                {
                    "id": f"NEG{len(negatives) + 1}",
                    "date": pd.Timestamp(candidate_date),
                    "location": f"near_{pos['id']}",
                    "lat": lat,
                    "lon": lon,
                    "label": 0,
                }
            )
            made += 1

        unmatched += NEGATIVES_PER_POSITIVE - made

    if unmatched:
        print(f"  note: {unmatched} negative slot(s) unfilled after road-distance matching")
    return pd.DataFrame(negatives)


def fetch_all_features(df):
    points = [
        {
            "id": row["id"],
            "lat": row["lat"],
            "lon": row["lon"],
            "date": row["date"].strftime("%Y-%m-%d"),
        }
        for _, row in df.iterrows()
    ]

    print(f"Fetching satellite features for {len(points)} points...")
    by_id = get_features_batch(points, GEE_PROJECT)

    rows = []
    for _, row in df.iterrows():
        feats = dict(by_id.get(str(row["id"]), {}))
        if feats:
            feats = add_local_features(feats, row["lat"], row["lon"])
        rows.append({**row.to_dict(), **{c: feats.get(c) for c in FEATURE_COLUMNS}})
    return pd.DataFrame(rows)


def main():
    positives = load_positives()
    positives["label"] = 1
    negatives = sample_negatives(positives)

    all_points = pd.concat([positives, negatives], ignore_index=True, sort=False)
    result = fetch_all_features(all_points)

    missing = result[FEATURE_COLUMNS].isna().any(axis=1).sum()
    print(f"\n{len(result)} rows total, {missing} rows have at least one missing feature (will be median-imputed at training time)")

    result.to_csv(TRAINING_CSV, index=False)
    print(f"Saved training table to {TRAINING_CSV}")


if __name__ == "__main__":
    main()
