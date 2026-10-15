"""How much of the answer to believe, and what to do when two sources disagree.

Every number on the dashboard is a probability, and every probability is
computed from inputs that are sometimes late, sometimes missing and sometimes
wrong. A risk figure on its own hides all of that. An operator who is asked to
close a highway on the strength of 74% is entitled to know whether the model
had soil moisture that morning, whether the radar pass happened, and whether
the node standing on that hillside agrees with the satellite looking at it.

Two things here, and they are the same idea at two scales.

CONFIDENCE AND FRESHNESS
    Confidence is how much of the feature vector was real rather than filled
    in with the training median, tempered by how decisive the model itself
    was. A model that had every input and answered 0.92 is in a different
    position from one that had eleven of seventeen and answered 0.51, and
    reporting both as "HIGH" is how a warning system loses its audience.

    Freshness is the age of what it was answering with. The satellite feeds
    have honest, published latencies -- IMERG is roughly four hours behind,
    SMAP two to three days, Sentinel-1 six -- and a system that pretends they
    are live is lying by omission.

LOCAL ANOMALY
    When a ground node reads much wetter than the satellite says the region
    is, that is not necessarily an error in either. It is usually a cell that
    the 11 km grid averaged away, which is exactly the storm that takes a
    hillside down. The useful response is not to pick a winner but to say
    plainly that the two disagree, by how much, and in which direction --
    because "regional data says moderate, the node on the slope says severe"
    is a dispatch decision, and picking one silently is not.
"""

import datetime

# What each satellite input is actually worth in hours, as published. These
# are latencies, not refresh rates: IMERG Late runs every half hour but the
# half hour you get is four hours old.
LATENCY_H = {
    "rain_1d": 4, "rain_3d": 4, "rain_7d": 4, "rain_15d": 4, "rain_30d": 4,
    "soil_moisture_surface": 60, "soil_moisture_subsurface": 60,
    "vv_anomaly": 144,
    "elevation": None, "slope": None, "aspect": None,   # terrain does not age
    "slope_max_nbhd": None, "slope_mean_nbhd": None, "relief_nbhd": None,
    "dist_to_road_m": None, "ndvi": 384, "factor_of_safety": 4,
}

SOURCE_OF = {
    "rain_1d": "GPM IMERG", "rain_3d": "GPM IMERG", "rain_7d": "GPM IMERG",
    "rain_15d": "GPM IMERG", "rain_30d": "GPM IMERG",
    "soil_moisture_surface": "SMAP", "soil_moisture_subsurface": "SMAP",
    "vv_anomaly": "Sentinel-1", "ndvi": "MODIS",
}

# Features that carry most of the decision. Losing one of these costs more
# than losing a terrain column that barely moves between neighbouring pixels.
HEAVY = {"rain_7d", "rain_15d", "rain_30d", "factor_of_safety",
         "soil_moisture_surface", "slope"}


def confidence(features, risk):
    """0-1, with the reasons it is not 1."""
    if not features:
        return {"score": None, "reasons": ["no feature vector"]}
    total = weight = 0.0
    missing, missing_heavy = [], []
    for k, v in features.items():
        w = 2.5 if k in HEAVY else 1.0
        total += w
        if v is None:
            missing.append(k)
            if k in HEAVY:
                missing_heavy.append(k)
        else:
            weight += w
    coverage = weight / total if total else 0.0

    # A probability sitting on the decision boundary is a weaker statement
    # than the same model answering 0.95, whatever its inputs were.
    decisiveness = min(1.0, abs(risk - 0.5) / 0.35) if risk is not None else 0.5
    score = 0.72 * coverage + 0.28 * decisiveness

    reasons = []
    if missing_heavy:
        srcs = sorted({SOURCE_OF.get(k, k) for k in missing_heavy})
        reasons.append(f"{', '.join(srcs)} unavailable for this point")
    elif missing:
        reasons.append(f"{len(missing)} minor inputs median-filled")
    if decisiveness < 0.5:
        reasons.append("model is near its decision boundary")
    if not reasons:
        reasons.append("every input present, model decisive")
    return {"score": round(score, 3), "coverage": round(coverage, 3),
            "decisiveness": round(decisiveness, 3),
            "missing": missing, "reasons": reasons,
            "band": "HIGH" if score >= 0.75 else
                    "MODERATE" if score >= 0.5 else "LOW"}


# Freshness is scored on the feeds that decide today's answer, not on every
# feed. MODIS NDVI is a 16-day composite and always "384 hours old", which is
# fine: vegetation cover does not change between Tuesday and Wednesday, and
# scoring it as stale marks every point in the region stale forever. Terrain
# never ages at all, and factor of safety is derived from rain rather than
# fetched. What matters is whether the rain, the soil moisture and the radar
# are current.
# Sentinel-1 sits with NDVI rather than with the rain. Its six-day revisit is
# not a delay in a fast signal; backscatter anomaly is a slow variable, like
# vegetation cover, and scoring it as stale marked every point in the region
# stale forever for a reason that would never change an operator's decision
# today. Rain and soil moisture are what move the answer between this morning
# and this evening, so they are what freshness is about.
FAST = {"rain_1d", "rain_3d", "rain_7d", "rain_15d", "rain_30d",
        "soil_moisture_surface", "soil_moisture_subsurface"}
SLOW = {"ndvi", "vv_anomaly"}


def freshness(features, as_of=None, station_age_s=None):
    """0-1 over the feeds that move, plus the age of each in plain hours."""
    feeds, slow, absent = {}, {}, set()
    worst = 0
    for k, v in (features or {}).items():
        h = LATENCY_H.get(k)
        if h is None:
            continue
        src = SOURCE_OF.get(k, k)
        if v is None:
            # A feed that did not arrive is not fresh, it is missing, and the
            # first version of this scored it as fresh because there was
            # nothing old to count. Absent beats old, every time.
            if k in FAST:
                absent.add(src)
            continue
        if k in SLOW:
            slow[src] = max(slow.get(src, 0), h)
            continue
        if k not in FAST:
            continue
        feeds[src] = max(feeds.get(src, 0), h)
        worst = max(worst, h)

    snapshot_h = None
    if as_of:
        try:
            d = datetime.date.fromisoformat(str(as_of)[:10])
            snapshot_h = (datetime.date.today() - d).days * 24
        except Exception:                                 # noqa: BLE001
            snapshot_h = None

    # 24 h is fresh, a week is not. Terrain is excluded: it does not age.
    age_h = max(worst, snapshot_h or 0)
    score = max(0.0, min(1.0, 1.0 - (age_h - 12) / (168 - 12)))
    if absent:
        score = min(score, 0.45)
    out = {"score": round(score, 3), "worst_feed_h": worst,
           "snapshot_age_h": snapshot_h,
           "feeds": [{"source": k, "latency_h": v} for k, v in
                     sorted(feeds.items(), key=lambda t: -t[1])],
           "absent": sorted(absent),
           "slow_layers": [{"source": k, "latency_h": v,
                            "note": "slow layer; revisit, not delay"}
                           for k, v in slow.items()],
           "band": "FRESH" if score >= 0.7 else
                   "AGEING" if score >= 0.4 else "STALE"}
    if station_age_s is not None:
        out["station_age_min"] = round(station_age_s / 60, 1)
    return out


# --------------------------------------------------------------------------
# satellite against ground

def _pct(v, lo, hi):
    if v is None:
        return None
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def conflict(station_readings, features):
    """Where the node on the slope and the satellite over it disagree."""
    if not station_readings or not features:
        return None

    pairs = []

    # wetness: the node's soil probe against SMAP's surface estimate
    g = station_readings.get("soil_moisture_pct")
    s = features.get("soil_moisture_surface")
    if g is not None and s is not None:
        pairs.append(("Soil wetness", _pct(g, 0, 100), _pct(s, 0.05, 0.45),
                      "node soil probe", "SMAP surface"))

    # rain now: the tipping bucket against the last day of IMERG
    g = station_readings.get("rain_pct")
    s = features.get("rain_1d")
    if g is not None and s is not None:
        pairs.append(("Rain now", _pct(g, 0, 100), _pct(s, 0, 40),
                      "node rain sensor", "IMERG last 24 h"))

    # the node's own surface wetness against the same SMAP figure
    g = station_readings.get("wetness_pct")
    s = features.get("soil_moisture_surface")
    if g is not None and s is not None:
        pairs.append(("Surface wetness", _pct(g, 0, 100), _pct(s, 0.05, 0.45),
                      "node wetness plate", "SMAP surface"))

    rows, worst = [], 0.0
    for label, gv, sv, gsrc, ssrc in pairs:
        if gv is None or sv is None:
            continue
        d = gv - sv
        rows.append({"what": label, "ground": round(gv, 3),
                     "satellite": round(sv, 3), "delta": round(d, 3),
                     "ground_source": gsrc, "satellite_source": ssrc,
                     "direction": "ground wetter" if d > 0 else "satellite wetter"})
        worst = max(worst, abs(d))

    if not rows:
        return None

    if worst >= 0.35:
        level, text = "ANOMALY", (
            "The node on this slope and the satellite over it are telling "
            "different stories. An 11 km grid cell averages away the "
            "convective cell that actually sits on one hillside, which is "
            "usually the one that fails. Treat the higher of the two as the "
            "working assumption and send somebody to look.")
    elif worst >= 0.2:
        level, text = "DIVERGING", (
            "Ground and satellite are drifting apart but not yet far enough "
            "to act on. Worth watching over the next few hours.")
    else:
        level, text = "AGREED", (
            "Ground node and satellite agree within normal instrument "
            "spread, which is the case in which a single risk number means "
            "what it says.")

    return {"level": level, "max_delta": round(worst, 3),
            "rows": sorted(rows, key=lambda r: -abs(r["delta"])),
            "text": text}


def assess(features, risk, as_of=None, station=None):
    """The three numbers together, which is how they should be read."""
    readings = (station or {}).get("readings") or {}
    age = (station or {}).get("age_seconds")
    c = confidence(features, risk)
    f = freshness(features, as_of, age)
    x = conflict(readings, features) if (station or {}).get("connected") else None
    return {"risk": risk, "confidence": c, "freshness": f, "conflict": x,
            "headline": _headline(risk, c, f, x)}


def _headline(risk, c, f, x):
    if x and x["level"] == "ANOMALY":
        return ("The ground node disagrees with the satellite. Act on the "
                "higher reading until somebody has looked.")
    if c["score"] is not None and c["score"] < 0.5:
        return ("Treat this number as weak: " + c["reasons"][0] + ".")
    if f.get("absent"):
        return (", ".join(f["absent"]) + " did not arrive for this point. "
                "The model ran on training medians in its place.")
    if f["band"] == "STALE":
        return ("The inputs behind this are old. Oldest feed that matters is "
                f"{f['worst_feed_h']} h behind.")
    if risk is not None and risk >= 0.5:
        return "High risk, and the inputs behind it are present and current."
    return "Inputs present and current."
