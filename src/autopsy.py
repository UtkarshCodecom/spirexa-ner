"""Why the model missed what it missed.

Accuracy figures say how often a model is right. They say nothing about the
shape of its failures, and the shape is what tells you whether the next
thing to buy is a better model, a denser sensor network or a better
inventory.

So every recorded landslide the hindcast scored below the alert line gets an
autopsy. The evidence is already in the training table: which satellite
feeds returned a value for that place and day, how precisely the event was
located in the source catalogue, what triggered it, and how much rain the
satellite actually recorded.

The headline is uncomfortable and worth saying out loud: the median missed
event had 32.7 mm of satellite rainfall over the preceding week. The median
caught event had 128.0 mm. The model is not mostly failing to reason about
rain it can see -- it is mostly being handed events where the rain was never
in the data.
"""

import pandas as pd

from config import FEATURE_COLUMNS, TRAINING_CSV

HINDCAST_CSV = "data/processed/hindcast_results.csv"
ALERT_LINE = 0.50

# Wet-season rainfall a slide of this kind would normally sit on top of.
RAIN_EXPECTED_7D = 60.0
COARSE_KM = 25.0

RAIN_TRIGGERS = {"downpour", "rain", "continuous_rain", "monsoon", "cyclone remal"}

MODES = {
    "rain_unseen": (
        "Rainfall never reached the data",
        "Catalogued as rain-triggered, but the satellite recorded little rain "
        "for that week. IMERG resolves about 10 km; a convective downpour on "
        "one ridge is smaller than one pixel.",
    ),
    "location": (
        "Location too coarse to sample",
        "The catalogue places this event to within tens of kilometres, so the "
        "terrain and rainfall behind the prediction may belong to a different "
        "hillside entirely.",
    ),
    "coverage": (
        "Ground-state feeds missing",
        "Soil moisture or radar returned nothing for that place and day, so "
        "the model fell back to the training median and effectively guessed "
        "the state of the ground.",
    ),
    "out_of_scope": (
        "Not a rainfall event",
        "Triggered by something the model does not represent. Missing it is "
        "correct behaviour, not error.",
    ),
    "genuine": (
        "Genuine model miss",
        "Rain was present in the data, the location was precise and the feeds "
        "were complete. The model simply got it wrong. This is the only "
        "bucket a better model would fix.",
    ),
}

# Most-specific explanation first: an event triggered by mining is out of
# scope whatever else is wrong with it.
PRIORITY = ["out_of_scope", "rain_unseen", "location", "coverage", "genuine"]

_cache = None


def _km(accuracy):
    if not isinstance(accuracy, str):
        return None
    a = accuracy.strip().lower()
    if a == "exact":
        return 0.0
    if a.endswith("km"):
        try:
            return float(a[:-2])
        except ValueError:
            return None
    return None


def _autopsy_row(row):
    factors = []
    trigger = str(row.get("trigger", "")).strip().lower()
    if trigger and trigger not in RAIN_TRIGGERS and trigger != "unknown":
        factors.append("out_of_scope")

    rain7 = row.get("rain_7d")
    if pd.notna(rain7) and rain7 < RAIN_EXPECTED_7D and trigger in RAIN_TRIGGERS:
        factors.append("rain_unseen")

    km = _km(row.get("location_accuracy"))
    if km is None or km >= COARSE_KM:
        factors.append("location")

    missing = [c for c in ("soil_moisture_surface", "soil_moisture_subsurface",
                           "vv_anomaly") if pd.isna(row.get(c))]
    if missing:
        factors.append("coverage")

    if not factors:
        factors.append("genuine")

    primary = next(m for m in PRIORITY if m in factors)
    return primary, factors, missing, rain7, km


def report():
    """Per-event autopsies plus the distribution of failure modes."""
    global _cache
    if _cache is not None:
        return _cache

    train = pd.read_csv(TRAINING_CSV)
    hind = pd.read_csv(HINDCAST_CSV)
    keep = ["id", "trigger", "location_accuracy"] + FEATURE_COLUMNS
    joined = hind.merge(
        train[[c for c in keep if c in train.columns]],
        on="id", how="left", suffixes=("", "_t"),
    )

    missed = joined[joined["predicted_probability"] < ALERT_LINE]
    events, counts = [], {k: 0 for k in MODES}

    for _, r in missed.iterrows():
        primary, factors, missing, rain7, km = _autopsy_row(r)
        counts[primary] += 1
        events.append({
            "id": r["id"],
            "date": r.get("date"),
            "location": r.get("location"),
            "state": r.get("state"),
            "scored": round(float(r["predicted_probability"]), 3),
            "fatalities": (None if pd.isna(r.get("fatalities"))
                           else int(r.get("fatalities"))),
            "trigger": r.get("trigger"),
            "rain_7d": None if pd.isna(rain7) else round(float(rain7), 1),
            "location_km": km,
            "missing_feeds": missing,
            "primary": primary,
            "primary_label": MODES[primary][0],
            "why": MODES[primary][1],
            "factors": factors,
        })

    events.sort(key=lambda e: (-(e["fatalities"] or 0), e["scored"]))
    total_events = int((joined["predicted_probability"] >= 0).sum())

    _cache = {
        "alert_line": ALERT_LINE,
        "events_total": total_events,
        "missed_total": len(events),
        "caught_rate": round(1 - len(events) / max(total_events, 1), 3),
        "modes": [
            {"key": k, "label": MODES[k][0], "detail": MODES[k][1],
             "count": counts[k],
             "share": round(counts[k] / max(len(events), 1), 3)}
            for k in PRIORITY
        ],
        "median_rain_missed": round(float(missed["rain_7d"].median()), 1),
        "median_rain_caught": round(
            float(joined[joined["predicted_probability"] >= ALERT_LINE]["rain_7d"].median()), 1),
        "events": events,
    }
    return _cache
