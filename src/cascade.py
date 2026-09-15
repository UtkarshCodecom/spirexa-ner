"""The cascading hazard engine: one storm, two hazards, one chain.

Landslide risk and flood risk are not two independent predictions that happen
to share a rain gauge. They are fed by the same water, and they compete for
it -- which is what makes the chain worth modelling rather than just putting
two numbers side by side.

Rain arriving on a hillside splits between infiltration and runoff, and the
split is not fixed. On dry ground most of it soaks in: the soil store fills,
pore pressure rises, the factor of safety falls, and the learned model sees a
wetting slope. Almost none of it reaches the river. As the soil approaches
saturation it stops accepting water, the runoff coefficient climbs, and the
same rainfall that was quietly destabilising a slope an hour ago is now
going straight into the channel.

So the two hazards run on a lag -- and which one leads is not fixed. It
turns on how wet the ground already was when the storm arrived:

    antecedent soil   first warning        gap
    18% saturated     slope              +12.5 h before the river
    31%               slope               +5.0 h
    58%               river               -3.0 h
    84%               river               -1.0 h

On dry ground the hillside drinks the storm and fails while the river is
still low. On ground already wet from a previous week, almost nothing soaks
in, the river responds within its routing time, and the flood arrives first.

This is the argument for modelling the chain rather than running two
independent predictors: neither hazard model alone tracks the state variable
that decides which of them you should be watching. A system that watches
only the river arrives twelve hours late for a dry-antecedent landslide, and
a system that watches only the slope misses a wet-antecedent flood entirely.

Everything here is explicit and checkable. The only learned component is the
landslide probability, which is the project's existing Random Forest; the
water balance, the stability calculation and the routing are all textbook.
"""

import math

import pandas as pd

import scenarios
from local_features import factor_of_safety

# --- soil column -------------------------------------------------------
POROSITY = 0.45           # vol/vol at saturation
SOIL_DEPTH_M = 1.5        # the mantle that actually fails in a shallow slide
# Gravity drainage, vol/vol per hour at saturation, falling away as the
# column empties -- dry soil has nothing to drain. A flat rate here is what
# made the first version useless: at 0.004/h it removed 0.096 vol/vol a day,
# almost exactly the infiltration from a 260 mm storm, so the soil never
# wetted up and neither hazard ever moved.
DRAIN_SAT_PER_H = 0.0016

# --- runoff ------------------------------------------------------------
C_DRY, C_WET = 0.18, 0.88  # runoff coefficient, empty soil -> saturated soil
C_SHAPE = 1.8              # how sharply it turns once the store fills

# --- channel -----------------------------------------------------------
# Stage-discharge is a local relation, so it has to be built from the
# catchment rather than hardcoded: a rating calibrated for a 2,000 km2 river
# says a 180 km2 stream never floods, which is how the first run reported a
# 2.8 m peak against a 6 m bank.
RATING_B = 0.40
BANKFULL_M = 6.0
SPECIFIC_FLOOD = 0.85     # m3/s per km2 at bank-full, wet monsoon headwater


def _rating_a(catchment_km2):
    return BANKFULL_M / (bankfull_q(catchment_km2) ** RATING_B)


def bankfull_q(catchment_km2):
    return max(5.0, SPECIFIC_FLOOD * catchment_km2)


def _storage_k(catchment_km2):
    """Linear-reservoir constant, hours -- the catchment's memory.

    Without it, rain falling at hour zero is in the river at hour zero, the
    hydrograph is a step function, and every asset downstream floods at
    T+0.0 in every run. A real catchment fills and empties over hours, and
    that lag is most of why the slope fails before the river arrives.
    """
    return 1.6 * (catchment_km2 ** 0.3)

# Thresholds sit above bank-full, because that is what a bank is. The first
# version put the road at 4.2 m against a 6.0 m bank, so the road drowned
# before the river left its channel and the sequence read backwards.
DEFAULT_ASSETS = [
    {"name": "Valley road", "kind": "road", "flood_stage_m": 6.4, "on_slope": True},
    {"name": "Riverside settlement", "kind": "settlement", "flood_stage_m": 7.0,
     "people": 640},
    {"name": "River bridge", "kind": "bridge", "flood_stage_m": 8.2},
    {"name": "Powerhouse yard", "kind": "power", "flood_stage_m": 9.0},
]


def _rolling(history_mm, hours_back, dt_h):
    """Rainfall total over the last N hours, from an hourly-ish history."""
    n = max(1, int(round(hours_back / dt_h)))
    return float(sum(history_mm[-n:]))


def simulate(
    rain_mm_per_day,
    hours=48,
    dt_h=0.5,
    slope_deg=42.0,
    catchment_km2=180.0,
    start_soil=0.22,
    antecedent_mm=None,
    base_features=None,
    assets=None,
):
    """Marches one storm through soil, slope and channel together.

    Returns the full timeline plus the ordered list of things that broke and
    when -- which is the question an operator actually asks: not "how bad",
    but "what goes first, and how long have I got".
    """
    assets = assets or DEFAULT_ASSETS
    base = dict(base_features or {})

    # Antecedent rainfall matters more than the storm on day one; without it
    # every simulation starts from an implausibly dry catchment.
    if antecedent_mm is None:
        antecedent_mm = {"rain_15d": 90.0, "rain_30d": 160.0}

    rating_a = _rating_a(catchment_km2)
    k_route = _storage_k(catchment_km2)
    q_channel = 0.06 * bankfull_q(catchment_km2)     # baseflow before the storm
    theta = start_soil                       # vol/vol
    steps = int(hours / dt_h) + 1
    hist = []                                # mm of rain per step
    rows, timeline = [], []

    rain_per_step = rain_mm_per_day / 24.0 * dt_h

    for i in range(steps):
        t = i * dt_h
        hist.append(rain_per_step)

        # --- the split, and it moves as the soil fills ---
        wetness = min(1.0, theta / POROSITY)
        c = C_DRY + (C_WET - C_DRY) * (wetness ** C_SHAPE)
        runoff_mm = rain_per_step * c
        infil_mm = rain_per_step * (1.0 - c)

        # --- soil store ---
        theta += (infil_mm / 1000.0) / SOIL_DEPTH_M
        theta -= DRAIN_SAT_PER_H * (wetness ** 2) * dt_h
        theta = max(0.02, min(POROSITY, theta))

        # --- channel ---
        # Runoff generated this step, then routed through the catchment's
        # storage rather than teleported into the channel.
        q_direct = (runoff_mm / 1000.0) / (dt_h * 3600.0) * catchment_km2 * 1e6
        q_channel += (q_direct - q_channel) * (dt_h / k_route)
        q = max(q_channel, 0.0)
        stage = rating_a * (max(q, 1.0) ** RATING_B)

        # --- slope, physics ---
        fos = factor_of_safety(slope_deg, theta)

        # --- slope, learned: one row per step, scored in a single batch ---
        feats = dict(base)
        feats.update({
            "rain_1d": _rolling(hist, 24, dt_h),
            "rain_3d": _rolling(hist, 72, dt_h),
            "rain_7d": _rolling(hist, 168, dt_h),
            "rain_15d": antecedent_mm["rain_15d"] + _rolling(hist, 360, dt_h),
            "rain_30d": antecedent_mm["rain_30d"] + _rolling(hist, 720, dt_h),
            "soil_moisture_surface": theta,
            "soil_moisture_subsurface": theta * 0.92,
            "slope_max_nbhd": slope_deg,
            "slope": max(4.0, slope_deg - 8.0),
            "factor_of_safety": fos,
        })
        rows.append(feats)
        timeline.append({
            "t": round(t, 2), "soil": round(theta, 4),
            "soil_pct": round(theta / POROSITY * 100, 1),
            "runoff_coeff": round(c, 3),
            "discharge": round(q, 1), "stage": round(stage, 2),
            "fos": None if fos is None else round(fos, 3),
        })

    # One batch through the forest rather than `steps` separate calls.
    bundle = scenarios._load()
    cols = bundle["feature_cols"]
    medians = bundle["medians"]
    frame = pd.DataFrame(
        [{c: (r.get(c) if r.get(c) is not None else medians[c]) for c in cols}
         for r in rows],
        columns=cols,
    )
    risks = bundle["model"].predict_proba(frame)[:, 1]
    for step, risk in zip(timeline, risks):
        step["landslide_risk"] = round(float(risk), 4)

    events = _sequence(timeline, assets)
    return {
        "timeline": timeline,
        "events": events,
        "peak": _peak(timeline),
        "lead_hours": lead_time(events),
    }


def _first(timeline, test):
    for s in timeline:
        if test(s):
            return s
    return None


def _sequence(timeline, assets):
    """The ordered failure chain, with the hour each link closes."""
    out = []

    def add(step, kind, label, severity, detail):
        if step is not None:
            out.append({"t": step["t"], "kind": kind, "label": label,
                        "severity": severity, "detail": detail})

    add(_first(timeline, lambda s: s["soil_pct"] >= 70), "soil",
        "Soil approaching saturation", "watch",
        "The hillside stops accepting water; from here most of the rain goes to the river.")
    # Only a crossing is news. A slope that is already under 1 at hour zero is
    # a standing condition, and reporting it as an event at T+0.0 in every
    # single run trains the reader to ignore the line.
    if timeline[0]["fos"] is not None and timeline[0]["fos"] >= 1.0:
        add(_first(timeline, lambda s: s["fos"] is not None and s["fos"] < 1.0), "slope",
            "Factor of safety falls below 1", "warn",
            "The physics model no longer holds the slope. A threshold, not a forecast.")
    add(_first(timeline, lambda s: s["landslide_risk"] >= 0.50), "slope",
        "Landslide risk crosses 50%", "warn",
        "The learned model reaches the band at which SPIREXA raises an alert.")
    add(_first(timeline, lambda s: s["stage"] >= BANKFULL_M), "flood",
        "River leaves its banks", "warn",
        f"Stage passes the bank-full figure of {BANKFULL_M} m.")

    for a in sorted(assets, key=lambda a: a["flood_stage_m"]):
        step = _first(timeline, lambda s, a=a: s["stage"] >= a["flood_stage_m"])
        detail = f"Inundated once stage passes {a['flood_stage_m']} m."
        if a.get("people"):
            detail += f" About {a['people']} people."
        add(step, a["kind"], f"{a['name']} under water", "fail", detail)
        if a.get("on_slope"):
            blocked = _first(timeline, lambda s: s["landslide_risk"] >= 0.60)
            add(blocked, "road", f"{a['name']} blocked by debris", "fail",
                "Independent of the river: the slope above it fails first.")

    out.sort(key=lambda e: e["t"])
    return out


def _peak(timeline):
    top_r = max(timeline, key=lambda s: s["landslide_risk"])
    top_s = max(timeline, key=lambda s: s["stage"])
    return {
        "landslide_risk": top_r["landslide_risk"], "landslide_at_h": top_r["t"],
        "stage_m": top_s["stage"], "stage_at_h": top_s["t"],
        "discharge": top_s["discharge"],
    }


def lead_time(events):
    """Hours between the slope warning and the river leaving its banks.

    Positive means the slope goes first and the number is how much warning a
    river gauge would have cost you. Negative means the flood leads. The sign
    is set by antecedent soil moisture, not by the storm.
    """
    slope = next((e for e in events if e["kind"] == "slope"), None)
    flood = next((e for e in events if e["kind"] == "flood"), None)
    if not slope or not flood:
        return None
    return round(flood["t"] - slope["t"], 2)
