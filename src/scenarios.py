"""Risk attribution, counterfactual simulation, and decision guidance.

Three things the plain risk number cannot answer on its own:

  what_changed()  why did risk move between two dates
  simulate()      what would risk be under different conditions
  decision_for()  what a responder should actually do about it

Kept separate from predict.py deliberately: that module is the single
scoring path used by the dashboard and the alert engine, and nothing here
should be able to disturb it.
"""

import datetime

import joblib
import pandas as pd

from config import MODEL_PATH
from local_features import factor_of_safety

_bundle = None

# Computed from other features rather than measured independently.
DERIVED_FEATURES = {"factor_of_safety"}


def _load():
    global _bundle
    if _bundle is None:
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


# Human-readable names and units, for anything shown to a person.
LABELS = {
    "rain_1d": ("Rainfall, last 24h", "mm"),
    "rain_3d": ("Rainfall, last 3 days", "mm"),
    "rain_7d": ("Rainfall, last 7 days", "mm"),
    "rain_15d": ("Rainfall, last 15 days", "mm"),
    "rain_30d": ("Rainfall, last 30 days", "mm"),
    "soil_moisture_surface": ("Soil moisture, surface", "vol/vol"),
    "soil_moisture_subsurface": ("Soil moisture, root zone", "vol/vol"),
    "vv_anomaly": ("Radar (SAR) anomaly", "dB"),
    "ndvi": ("Vegetation cover (NDVI)", ""),
    "factor_of_safety": ("Factor of safety", ""),
    "slope": ("Slope at point", "deg"),
    "slope_max_nbhd": ("Steepest slope within 300m", "deg"),
    "slope_mean_nbhd": ("Mean slope within 300m", "deg"),
    "relief_nbhd": ("Local relief", "m"),
    "elevation": ("Elevation", "m"),
    "aspect": ("Slope aspect", "deg"),
    "dist_to_road_m": ("Distance to nearest road", "m"),
}

# Only conditions that can actually change are worth a slider. Terrain is
# fixed; offering to "simulate" a different slope would be meaningless.
SIMULATABLE = [
    {"key": "rain_1d", "min": 0, "max": 300, "step": 1},
    {"key": "rain_3d", "min": 0, "max": 500, "step": 1},
    {"key": "rain_7d", "min": 0, "max": 800, "step": 5},
    {"key": "rain_15d", "min": 0, "max": 1200, "step": 10},
    {"key": "rain_30d", "min": 0, "max": 2000, "step": 10},
    {"key": "soil_moisture_surface", "min": 0.0, "max": 0.6, "step": 0.01},
    {"key": "soil_moisture_subsurface", "min": 0.0, "max": 0.6, "step": 0.01},
    {"key": "ndvi", "min": -0.2, "max": 1.0, "step": 0.01},
]


def band(risk):
    if risk >= 0.75:
        return "SEVERE"
    if risk >= 0.5:
        return "HIGH"
    if risk >= 0.25:
        return "MODERATE"
    return "LOW"


def _row(feats):
    """Model-ready row: missing values fall back to the training medians,
    exactly as predict.py does, so scores stay comparable."""
    bundle = _load()
    medians = bundle["medians"]
    return {
        c: (feats.get(c) if feats.get(c) is not None else medians[c])
        for c in bundle["feature_cols"]
    }


def score(feats):
    bundle = _load()
    cols = bundle["feature_cols"]
    frame = pd.DataFrame([_row(feats)], columns=cols)
    return float(bundle["model"].predict_proba(frame)[0][1])


def apply_overrides(feats, overrides):
    """Applies slider values, then rebuilds anything derived from them.

    factor_of_safety is computed from slope and soil moisture, so changing
    soil moisture without recomputing it would simulate a wetter slope that
    is somehow no less stable -- incoherent, and the first thing a
    geotechnical reviewer would notice.
    """
    out = dict(feats)
    for key, value in overrides.items():
        if key in out or key in {s["key"] for s in SIMULATABLE}:
            out[key] = float(value)

    slope = out.get("slope_max_nbhd")
    if slope is None:
        slope = out.get("slope")
    recomputed = factor_of_safety(slope, out.get("soil_moisture_surface"))
    if recomputed is not None:
        out["factor_of_safety"] = recomputed
    return out


def simulate(feats, overrides):
    """Baseline vs. counterfactual, plus what the change means."""
    baseline_risk = score(feats)
    modified = apply_overrides(feats, overrides)
    modified_risk = score(modified)

    changed = []
    for key, value in overrides.items():
        before = feats.get(key)
        after = modified.get(key)
        if before is None or after is None:
            continue
        if abs(float(after) - float(before)) < 1e-9:
            continue
        label, unit = LABELS.get(key, (key, ""))
        changed.append({
            "key": key, "label": label, "unit": unit,
            "before": round(float(before), 3),
            "after": round(float(after), 3),
        })

    # factor_of_safety moves on its own as a consequence; report it as such.
    fos_before, fos_after = feats.get("factor_of_safety"), modified.get("factor_of_safety")
    derived = None
    if fos_before is not None and fos_after is not None and abs(fos_after - fos_before) > 1e-6:
        derived = {
            "key": "factor_of_safety",
            "label": LABELS["factor_of_safety"][0],
            "before": round(float(fos_before), 3),
            "after": round(float(fos_after), 3),
            "note": "recomputed from the new soil moisture",
        }

    return {
        "baseline": {
            "risk": round(baseline_risk, 4),
            "risk_percent": round(baseline_risk * 100, 1),
            "severity": band(baseline_risk),
        },
        "simulated": {
            "risk": round(modified_risk, 4),
            "risk_percent": round(modified_risk * 100, 1),
            "severity": band(modified_risk),
        },
        "delta_percent": round((modified_risk - baseline_risk) * 100, 1),
        "crosses_threshold": band(modified_risk) != band(baseline_risk),
        "changed": changed,
        "derived": derived,
    }


def attribute(feats_then, feats_now):
    """Which feature movements actually drove the risk change.

    Done by ablation rather than by ranking feature importances: for each
    feature, score the present-day conditions with that one value put back
    to where it was, and see how much of the change disappears. That
    measures this feature's real contribution to THIS movement, instead of
    its average importance across the whole training set.
    """
    risk_then = score(feats_then)
    risk_now = score(feats_now)
    total = risk_now - risk_then

    contributions = []
    for key in _load()["feature_cols"]:
        before, after = feats_then.get(key), feats_now.get(key)
        if before is None or after is None:
            continue
        if abs(float(after) - float(before)) < 1e-9:
            continue

        reverted = dict(feats_now)
        reverted[key] = before
        effect = risk_now - score(reverted)     # risk lost by undoing this one move

        label, unit = LABELS.get(key, (key, ""))
        pct = None
        if abs(float(before)) > 1e-6:
            pct = round((float(after) - float(before)) / abs(float(before)) * 100, 1)

        contributions.append({
            "key": key, "label": label, "unit": unit,
            "before": round(float(before), 3),
            "after": round(float(after), 3),
            "change_percent": pct,
            "direction": "up" if after > before else "down",
            "effect_on_risk": round(effect * 100, 2),
            # factor_of_safety is computed FROM slope and soil moisture, so an
            # ablation credits it and soil moisture for the same underlying
            # movement. Its marginal effect can therefore come out with a
            # counter-intuitive sign. Flagged so it can be shown apart from
            # the independent measurements rather than ranked against them.
            "derived": key in DERIVED_FEATURES,
        })

    contributions.sort(key=lambda c: abs(c["effect_on_risk"]), reverse=True)

    # The headline driver must be something actually measured, not a quantity
    # computed from the others.
    driver = None
    for c in contributions:
        if c["derived"]:
            continue
        if c["effect_on_risk"] * (1 if total >= 0 else -1) > 0:
            driver = c
            break

    return {
        "risk_then": {"risk_percent": round(risk_then * 100, 1), "severity": band(risk_then)},
        "risk_now": {"risk_percent": round(risk_now * 100, 1), "severity": band(risk_now)},
        "delta_percent": round(total * 100, 1),
        "direction": "rose" if total > 0 else ("fell" if total < 0 else "unchanged"),
        "contributions": contributions,
        "primary_driver": driver,
    }


# ---------------------------------------------------------------- decision --
# The model produces a number. These turn it into something a person can act
# on -- deliberately phrased as recommendations, because the system advises
# and a human authority decides.
_ACTIONS = {
    "SEVERE": [
        "Inspect the slope on the ground before movement is reported",
        "Check road and culvert condition immediately below the slope",
        "Cross-check against any field reports from the area",
        "Prepare a local warning for settlements downslope",
    ],
    "HIGH": [
        "Schedule a slope inspection within 24 hours",
        "Identify which road segments sit below this slope",
        "Put local wardens on notice; do not issue a public warning yet",
    ],
    "MODERATE": [
        "Keep on the daily watch-list",
        "Review again if rainfall continues",
    ],
    "LOW": [
        "Routine monitoring only; no action required",
    ],
}

_POSTURE = {
    "SEVERE": "CRITICAL - act now",
    "HIGH": "ELEVATED - prepare",
    "MODERATE": "WATCH - keep under review",
    "LOW": "NORMAL - routine monitoring",
}


def decision_for(risk):
    label = band(risk)
    return {
        "risk_percent": round(float(risk) * 100, 1),
        "severity": label,
        "posture": _POSTURE[label],
        "actions": _ACTIONS[label],
        "note": "Recommendation only. The model advises; the responsible "
                "authority decides and is accountable for the decision.",
    }


def days_ago(date_str, days):
    d = datetime.date.fromisoformat(date_str)
    return (d - datetime.timedelta(days=days)).isoformat()
