"""Re-running a real landslide day by day, to see when the alert would have fired.

The hindcast answers a yes/no question: would the model have flagged this
event on the day it happened. That is the wrong question for anybody who has
to act on it. An alert that fires as the hillside moves is not a warning; the
number that matters is how many hours of notice there would have been.

So this walks the thirty days before a recorded failure and scores each one,
using only what would have been known that morning. The daily rainfall series
is reconstructed from the five totals the training set already carries --
1, 3, 7, 15 and 30 day -- by filling each shell evenly:

    day 30 (the failure)        rain_1d
    days 28-29                  (rain_3d  - rain_1d)  / 2
    days 24-27                  (rain_7d  - rain_3d)  / 4
    days 16-23                  (rain_15d - rain_7d)  / 8
    days 1-15                   (rain_30d - rain_15d) / 15

which reproduces all five recorded totals exactly. It is not the true daily
sequence -- nobody recorded that -- and where the real rain fell in one night
rather than evenly across a shell, the model would have crossed later and
sharper than this shows. That is stated rather than smoothed over, and it is
the reason the lead time here is an upper bound on what the model would have
managed, not a claim about what it did.

Everything else about the point -- slope, vegetation, road distance, soil --
is held at its recorded value, because none of it changed over those weeks.
"""

import os

import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAINING = os.path.join(_ROOT, "data/processed/training_data.csv")

SHELLS = [(1, "rain_1d", None), (3, "rain_3d", "rain_1d"),
          (7, "rain_7d", "rain_3d"), (15, "rain_15d", "rain_7d"),
          (30, "rain_30d", "rain_15d")]
DAYS = 30
ALERT = 0.5

_df = None
_bundle = None


def _data():
    global _df
    if _df is None:
        _df = pd.read_csv(TRAINING)
    return _df


def _model():
    global _bundle
    if _bundle is None:
        import joblib
        from config import MODEL_PATH
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def events(limit=60):
    """Recorded failures worth replaying: fatal first, then most recent."""
    df = _data()
    ev = df[df.label == 1].copy()
    ev["fatalities"] = ev["fatalities"].fillna(0)
    ev = ev.sort_values(["fatalities", "date"], ascending=[False, False])
    return [{"id": r["id"], "date": str(r["date"])[:10],
             "location": r["location"], "state": r["state"],
             "lat": round(float(r["lat"]), 4), "lon": round(float(r["lon"]), 4),
             "fatalities": int(r["fatalities"]),
             "trigger": r.get("trigger", ""),
             "rain_7d": round(float(r["rain_7d"]), 1),
             "slope_max_nbhd": (None if pd.isna(r["slope_max_nbhd"])
                                else int(r["slope_max_nbhd"]))}
            for _, r in ev.head(limit).iterrows()]


def daily_series(row):
    """Thirty days of rain that reproduce every recorded window total."""
    series = [0.0] * DAYS
    prev_days = 0
    prev_val = 0.0
    for days, col, _prev in SHELLS:
        total = float(row.get(col) or 0.0)
        shell_days = days - prev_days
        shell_total = max(total - prev_val, 0.0)
        per_day = shell_total / shell_days if shell_days else 0.0
        for k in range(prev_days, days):
            series[DAYS - 1 - k] = per_day
        prev_days, prev_val = days, total
    return series


def _windows(series, upto):
    """Trailing totals as they would have read on day `upto` (0-based)."""
    def tail(n):
        lo = max(0, upto - n + 1)
        return float(sum(series[lo:upto + 1]))
    return {"rain_1d": tail(1), "rain_3d": tail(3), "rain_7d": tail(7),
            "rain_15d": tail(15), "rain_30d": tail(30)}


def replay(event_id):
    """Score every one of the thirty days before a recorded failure."""
    df = _data()
    hit = df[df.id == event_id]
    if not len(hit):
        return {"error": f"no event {event_id}"}
    row = hit.iloc[0].to_dict()

    b = _model()
    model, cols, med = b["model"], b["feature_cols"], b["medians"]
    series = daily_series(row)

    frames = []
    for k in range(DAYS):
        w = _windows(series, k)
        feats = {}
        for c in cols:
            if c in w:
                feats[c] = w[c]
            else:
                v = row.get(c)
                feats[c] = med[c] if v is None or pd.isna(v) else v
        # Soil moisture is the one non-rain feature that genuinely tracked the
        # storm. Held at its recorded value it would make day 1 look as
        # saturated as day 30, so it is scaled with the 15-day total instead.
        if "soil_moisture_surface" in feats and row.get("rain_15d"):
            frac = min(1.0, w["rain_15d"] / max(float(row["rain_15d"]), 1e-6))
            base = med["soil_moisture_surface"]
            end = row.get("soil_moisture_surface")
            end = base if end is None or pd.isna(end) else float(end)
            feats["soil_moisture_surface"] = base + (end - base) * frac
            if "soil_moisture_subsurface" in feats:
                b2 = med["soil_moisture_subsurface"]
                e2 = row.get("soil_moisture_subsurface")
                e2 = b2 if e2 is None or pd.isna(e2) else float(e2)
                feats["soil_moisture_subsurface"] = b2 + (e2 - b2) * frac

        p = float(model.predict_proba(
            pd.DataFrame([[feats[c] for c in cols]], columns=cols))[0][1])
        frames.append({
            "day": k - (DAYS - 1),                 # 0 is the failure day
            "rain_today": round(series[k], 2),
            "rain_7d": round(w["rain_7d"], 1),
            "rain_15d": round(w["rain_15d"], 1),
            "risk": round(p, 4),
        })

    crossed = next((f for f in frames if f["risk"] >= ALERT), None)
    lead_days = -crossed["day"] if crossed else None
    return {
        "event": {"id": row["id"], "date": str(row["date"])[:10],
                  "location": row["location"], "state": row["state"],
                  "lat": round(float(row["lat"]), 4),
                  "lon": round(float(row["lon"]), 4),
                  "fatalities": int(row.get("fatalities") or 0),
                  "trigger": row.get("trigger", ""),
                  "slope_max_nbhd": (None if pd.isna(row.get("slope_max_nbhd"))
                                     else int(row["slope_max_nbhd"])),
                  "ndvi": (None if pd.isna(row.get("ndvi"))
                           else float(row["ndvi"]))},
        "alert_threshold": ALERT,
        "frames": frames,
        "crossed_on_day": crossed["day"] if crossed else None,
        "lead_days": lead_days,
        "peak_risk": max(f["risk"] for f in frames),
        "caught": bool(crossed),
        "caveat": ("Daily rain is reconstructed from the recorded 1, 3, 7, 15 "
                   "and 30 day totals by filling each shell evenly, so it "
                   "reproduces every recorded total but not the true daily "
                   "sequence. Where the rain actually fell in one night the "
                   "crossing would be later and sharper than this. Read the "
                   "lead time as an upper bound."),
    }
