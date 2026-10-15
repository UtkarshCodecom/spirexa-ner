"""The learned peak-discharge model, and what it replaced.

`glof.breach()` estimates peak outflow with Froehlich's 1995 regression,
scaled by a moraine coefficient of 0.45 that was calibrated against exactly
one event. Scored against 126 held-out real outbursts, that combination has an
R-squared of -1.128 in log space: worse than predicting the average discharge
for every lake on earth. It got South Lhonak right because it was tuned to.

Lutzow and Veh (2023) published the global GLOF inventory under CC-BY-4.0:
3,167 recorded outbursts, 502 of which report both the volume that left the
lake and the peak discharge it produced. scripts/train_glof_ml.py fits
gradient boosting to those, on features an operator has before the lake bursts
-- released volume, lake type, region, glacier area, latitude -- and holds a
quarter back to score it.

    model                     median factor error    within 2x    R2 (log)
    Froehlich, as shipped            9.58              10.3%       -1.128
    power law on volume              2.17              46.8%        0.461
    learned                          1.52              65.1%        0.720

    High Mountain Asia only (29 held-out events)
    Froehlich                        3.75              17.2%
    learned                          1.27              86.2%

Both are kept. Froehlich is the transparent one an engineer can check by hand
and it remains the default; the learned model is reported beside it, and where
they disagree by more than a factor of two the API says so. On South Lhonak
itself Froehlich is the closer of the two -- 5,028 against a published
5,000-7,000, where the learned model says 7,676 -- which is what tuning to a
single event buys you, and exactly why one event is not an evaluation.
"""

import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
MODEL_PATH = os.path.join(_ROOT, "data/processed/glof_qp_model.pkl")
REPORT_PATH = os.path.join(_ROOT, "data/processed/glof_qp_report.json")

# Measured, not assumed. Across 147 outbursts that report both the lake volume
# and the volume that left it, the drained fraction has a median of 1.00 --
# 0.94 for moraine-dammed lakes specifically. The project shipped 0.70, which
# is roughly the 25th percentile: conservative in the wrong direction, since
# under-draining a lake under-states the flood.
DRAINED_MEDIAN = {"moraine": 0.94, "ice": 1.00, "default": 0.95}
DRAINED_P25 = 0.70
DRAINED_N = 147

_bundle = None
_report = None


def available():
    return os.path.exists(MODEL_PATH)


def bundle():
    global _bundle
    if _bundle is None:
        import joblib
        _bundle = joblib.load(MODEL_PATH)
    return _bundle


def report():
    global _report
    if _report is None:
        import json
        with open(REPORT_PATH) as f:
            _report = json.load(f)
    return _report


def drained_fraction(lake_type="moraine", percentile="median"):
    """How much of a lake actually leaves, from 147 recorded outbursts."""
    if percentile == "p25":
        return DRAINED_P25
    return DRAINED_MEDIAN.get(lake_type, DRAINED_MEDIAN["default"])


def peak_discharge(volume_m3, lake_type="moraine", region="High Mountain Asia",
                   glacier_area_km2=5.0, lat=27.9):
    """Learned peak outflow for a volume of water leaving a lake."""
    if not available():
        return None
    import pandas as pd

    b = bundle()
    cols = b["feature_cols"]
    row = {c: 0 for c in cols}
    row["log_v0"] = math.log10(max(volume_m3, 1.0))
    if "glacier_area" in row:
        row["glacier_area"] = glacier_area_km2
    if "lat_abs" in row:
        row["lat_abs"] = abs(lat)
    for c in cols:
        if c.startswith("lt_") and c[3:].lower() in str(lake_type).lower():
            row[c] = 1
        if c.startswith("reg_") and str(region).replace(" ", "_")[:16] in c:
            row[c] = 1
    X = pd.DataFrame([row], columns=cols)
    return float(10 ** b["model"].predict(X)[0])


def power_law_discharge(volume_m3):
    """The field's standard empirical baseline, fitted on the same training split."""
    if not available():
        return None
    p = bundle()["power_law"]
    return float(10 ** (p["a"] + p["b"] * math.log10(max(volume_m3, 1.0))))


def compare(volume_m3, froehlich_peak, lake_type="moraine", **kw):
    """Both estimates side by side, and whether they disagree enough to matter."""
    learned = peak_discharge(volume_m3, lake_type=lake_type, **kw)
    if learned is None:
        return {"available": False}
    power = power_law_discharge(volume_m3)
    ratio = learned / max(froehlich_peak, 1e-6)
    return {
        "available": True,
        "froehlich_cumec": round(froehlich_peak),
        "learned_cumec": round(learned),
        "power_law_cumec": round(power),
        "ratio_learned_over_froehlich": round(ratio, 2),
        "disagree": bool(ratio > 2.0 or ratio < 0.5),
        "note": ("The two estimates differ by more than a factor of two. "
                 "Froehlich is the auditable one and stays the default; the "
                 "learned model is the one scored against 126 real outbursts. "
                 "Plan for the larger of the two."
                 if (ratio > 2.0 or ratio < 0.5) else
                 "Both estimates agree within a factor of two."),
    }


def scorecard():
    """What the learned model is worth, for the page that shows its number."""
    if not available():
        return {"available": False}
    r = report()
    return {
        "available": True,
        "source": r["source"],
        "n_events": r["n_events"], "n_train": r["n_train"], "n_test": r["n_test"],
        "models": r["results"],
        "high_mountain_asia": r.get("hma", {}),
        "south_lhonak": r.get("south_lhonak", {}),
        "drained_fraction": {
            "measured_median_moraine": DRAINED_MEDIAN["moraine"],
            "previously_assumed": DRAINED_P25,
            "n_outbursts": DRAINED_N,
        },
    }
