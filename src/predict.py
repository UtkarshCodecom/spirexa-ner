"""Landslide risk for any coordinate and date.

    python src/predict.py --lat 23.73 --lon 92.72 --date 2024-05-28
    python src/predict.py --lat 23.73 --lon 92.72               # today
    python src/predict.py --lat 23.73 --lon 92.72 --explain     # show drivers
"""

import argparse
import datetime

import joblib
import pandas as pd

from config import GEE_PROJECT, MODEL_PATH
from gee_features import get_features
from local_features import add_local_features

_bundle = None


def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def predict(lat, lon, date_str, with_features=False):
    bundle = _load()
    model, feature_cols, medians = (
        bundle["model"],
        bundle["feature_cols"],
        bundle["medians"],
    )

    feats = get_features(lat, lon, date_str, GEE_PROJECT)
    feats = add_local_features(feats, lat, lon)

    row = {
        c: feats.get(c) if feats.get(c) is not None else medians[c] for c in feature_cols
    }
    probability = float(model.predict_proba(pd.DataFrame([row], columns=feature_cols))[0][1])

    if with_features:
        return probability, {k: feats.get(k) for k in feature_cols}
    return probability


def band(risk):
    if risk >= 0.75:
        return "SEVERE"
    if risk >= 0.5:
        return "HIGH"
    if risk >= 0.25:
        return "MODERATE"
    return "LOW"


def main():
    parser = argparse.ArgumentParser(description="Predict landslide risk.")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument(
        "--date", type=str, default=datetime.date.today().isoformat(), help="YYYY-MM-DD"
    )
    parser.add_argument(
        "--explain", action="store_true", help="show the feature values behind the score"
    )
    args = parser.parse_args()

    probability, feats = predict(args.lat, args.lon, args.date, with_features=True)

    print()
    print(f"  Location   {args.lat}, {args.lon}")
    print(f"  Date       {args.date}")
    print(f"  Risk       {probability * 100:.1f}%   [{band(probability)}]")

    if args.explain:
        fos = feats.get("factor_of_safety")
        print()
        print("  Why:")
        print(f"    slope at point        {_fmt(feats.get('slope'))} deg")
        print(f"    steepest within 300m  {_fmt(feats.get('slope_max_nbhd'))} deg")
        print(f"    local relief          {_fmt(feats.get('relief_nbhd'))} m")
        print(f"    factor of safety      {_fmt(fos)}"
              f"{'   (< 1 = theoretically unstable)' if fos and fos < 1 else ''}")
        print(f"    rain last 24h         {_fmt(feats.get('rain_1d'))} mm")
        print(f"    rain last 7d          {_fmt(feats.get('rain_7d'))} mm")
        print(f"    rain last 30d         {_fmt(feats.get('rain_30d'))} mm")
        print(f"    surface soil moisture {_fmt(feats.get('soil_moisture_surface'))}")
        print(f"    distance to road      {_fmt(feats.get('dist_to_road_m'))} m")
    print()


def _fmt(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


if __name__ == "__main__":
    main()
