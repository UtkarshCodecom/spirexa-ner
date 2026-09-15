"""Where the next ground sensor should go.

A hazard model tells you where risk is high. It does not tell you where the
model itself is weakest, and those are not the same map -- which matters,
because hardware budgets are spent on the second one.

The failure autopsy already says why each historical miss was missed. That
turns sensor siting from a guess into an argument: a ground node fixes some
failure modes and not others.

    rainfall never reached the data   a rain gauge on the slope fixes this
    ground-state feeds missing        a soil probe fixes this
    location too coarse to sample     a sensor does not fix a bad catalogue
    not a rainfall event              nor does it fix an out-of-scope trigger

So a site scores highly when live risk is high, when the events history
records near it were missed for reasons a sensor addresses, when the
satellite feeds are chronically absent there, when nothing is already
deployed nearby, and when people have died there before.

Every number below comes from data already in the repository. Nothing is
estimated by eye.
"""

import math

import pandas as pd

import autopsy
from config import TRAINING_CSV

LIVE_CSV = "data/processed/live_risk.csv"

NEAR_KM = 40.0            # what counts as "near" this site
# One node cannot watch two valleys, and two nodes 10 km apart in the same
# one are a wasted budget line. A plan respects a spacing floor.
MIN_SEPARATION_KM = 25.0
SENSOR_USEFUL = {"rain_unseen", "coverage"}    # modes a ground node addresses

# Nodes already in the field. One prototype, at the Aizawl test site.
DEPLOYED = [
    {"id": "NODE-01", "lat": 23.7348, "lon": 92.7187, "note": "Arduino prototype"},
]

WEIGHTS = {"risk": 0.30, "blind": 0.28, "gaps": 0.18, "coverage": 0.14, "harm": 0.10}

_cache = None


def _km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * r * math.asin(math.sqrt(a))


def _norm(vals):
    lo, hi = min(vals), max(vals)
    span = hi - lo
    return [0.0 if span == 0 else (v - lo) / span for v in vals]


def rank(limit=8):
    global _cache
    if _cache is not None:
        return _cache[:limit] if limit else _cache

    live = pd.read_csv(LIVE_CSV)
    train = pd.read_csv(TRAINING_CSV)
    events = train[train["label"] == 1]

    rep = autopsy.report()
    miss_mode = {str(e["id"]): e["primary"] for e in rep["events"]}

    rows = []
    for _, h in live.iterrows():
        lat, lon = float(h["lat"]), float(h["lon"])

        near = events[
            (events["lat"].sub(lat).abs() < 0.6) & (events["lon"].sub(lon).abs() < 0.6)
        ]
        near = near[[_km(lat, lon, float(r["lat"]), float(r["lon"])) <= NEAR_KM
                     for _, r in near.iterrows()]]

        n_near = len(near)
        fixable = sum(1 for i in near["id"].astype(str)
                      if miss_mode.get(i) in SENSOR_USEFUL)
        gaps = 0.0
        if n_near:
            gaps = float(
                near[["soil_moisture_surface", "vv_anomaly"]].isna().mean().mean())
        harm = float(near["fatalities"].fillna(0).sum()) if n_near else 0.0

        nearest = min((_km(lat, lon, d["lat"], d["lon"]) for d in DEPLOYED),
                      default=999.0)

        rows.append({
            "id": h["id"], "location": h["location"], "state": h["state"],
            "lat": round(lat, 4), "lon": round(lon, 4),
            "risk": round(float(h["live_risk"]), 3),
            "events_near": n_near,
            "sensor_fixable_misses": fixable,
            "feed_gap_rate": round(gaps, 3),
            "fatalities_near": int(harm),
            "km_to_nearest_node": round(nearest, 1),
        })

    if not rows:
        return []

    # Blind-spot pressure: misses a sensor could have helped with, per site.
    blind = _norm([r["sensor_fixable_misses"] for r in rows])
    risk = _norm([r["risk"] for r in rows])
    gaps = _norm([r["feed_gap_rate"] for r in rows])
    # coverage need saturates: past ~120 km one more kilometre changes nothing
    cover = _norm([min(r["km_to_nearest_node"], 120.0) for r in rows])
    harm = _norm([math.log1p(r["fatalities_near"]) for r in rows])

    for i, r in enumerate(rows):
        r["score"] = round(
            WEIGHTS["risk"] * risk[i] + WEIGHTS["blind"] * blind[i]
            + WEIGHTS["gaps"] * gaps[i] + WEIGHTS["coverage"] * cover[i]
            + WEIGHTS["harm"] * harm[i], 4)
        r["reasons"] = _reasons(r)

    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    _cache = rows
    return rows[:limit] if limit else rows


def _reasons(r):
    out = []
    if r["sensor_fixable_misses"]:
        out.append(
            f"{r['sensor_fixable_misses']} landslide"
            f"{'s' if r['sensor_fixable_misses'] > 1 else ''} within {int(NEAR_KM)} km "
            f"that the model missed for reasons a ground node fixes — rainfall the "
            f"satellite never recorded, or soil state it never had")
    if r["feed_gap_rate"] >= 0.4:
        out.append(
            f"satellite feeds were absent for {r['feed_gap_rate']*100:.0f}% of the "
            f"history here, so the model has been running on training medians")
    if r["km_to_nearest_node"] > 60:
        out.append(f"nearest deployed node is {r['km_to_nearest_node']:.0f} km away")
    if r["fatalities_near"] >= 3:
        out.append(f"{r['fatalities_near']} recorded deaths within {int(NEAR_KM)} km")
    if r["risk"] >= 0.6:
        out.append(f"live risk is {r['risk']*100:.0f}% today")
    if not out:
        out.append("ranked on live risk alone; no local history to learn from")
    return out


def plan(n=5):
    """A deployment order, not just a ranking.

    The ranked list puts the whole top ten in one valley, because the valley
    that most needs a sensor still most needs one after you have put a sensor
    in it. A plan has to account for the node it just placed: each pick
    updates every remaining site's distance to the nearest node, and the
    coverage term is rescored. Greedy, which is the standard approach to this
    kind of coverage problem and is transparent enough to argue with.
    """
    rows = [dict(r) for r in rank(limit=0)]
    placed = list(DEPLOYED)
    chosen = []

    for step in range(n):
        best, best_score = None, -1.0
        for r in rows:
            if any(c["id"] == r["id"] for c in chosen):
                continue
            km = min((_km(r["lat"], r["lon"], d["lat"], d["lon"]) for d in placed),
                     default=999.0)
            if km < MIN_SEPARATION_KM:
                continue
            cover = min(km, 120.0) / 120.0
            # same weights, but coverage recomputed against what is now placed
            score = (r["score"] - WEIGHTS["coverage"] * (min(r["km_to_nearest_node"], 120.0)
                     / 120.0) + WEIGHTS["coverage"] * cover)
            if score > best_score:
                best, best_score = r, score
        if best is None:
            break
        pick = dict(best)
        pick["order"] = step + 1
        pick["score_in_plan"] = round(best_score, 4)
        pick["km_to_nearest_placed"] = round(
            min((_km(best["lat"], best["lon"], d["lat"], d["lon"]) for d in placed)), 1)
        chosen.append(pick)
        placed.append({"id": best["id"], "lat": best["lat"], "lon": best["lon"]})

    return chosen


def summary(n_plan=5):
    rows = rank(limit=0)
    return {
        "candidates": len(rows),
        "deployed": DEPLOYED,
        "near_km": NEAR_KM,
        "weights": WEIGHTS,
        "ranked": rows[:10],
        "plan": plan(n_plan),
    }
