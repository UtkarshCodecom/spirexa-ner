"""Glacial lake outburst floods: breach, wave, and arrival at the projects.

NHPC already forecasts rainfall floods and already instruments the lakes.
What its published architecture does not do is turn a lake into a hydrograph
at a powerhouse: eAabhas gives two to three hours on a rising river, which is
the time the water takes to arrive, not the time a lake takes to decide.

This module is the missing middle. Given a lake volume and a moraine, it
produces the breach, the outflow hydrograph, and the routed peak and arrival
time at every downstream project -- which is what an operator needs in order
to do anything before the water is already there.

The equations are the standard empirical dam-break set, cited so an engineer
can check each one against the source rather than trust the code:

    Froehlich (1995)  peak outflow      Qp = 0.607 V^0.295 h^1.24
    Froehlich (2008)  breach width      B  = 0.27 Ko V^0.32 h^0.04
    Froehlich (2008)  formation time    tf = 63.2 sqrt(V / (g h^2))
    Huggel (2004)     lake volume       V  = 0.104 A^1.42   (A in m2, V in m3)
    Muskingum         channel routing   attenuation and lag down each reach

Moraine dams are not concrete and not earthfill, and the empirical set above
was fitted mostly to the latter. Treat the numbers as an order of magnitude
with the right shape, which is what they are, and which is still a great
deal more than nothing.
"""

import json
import math
import os

G = 9.81

# ---------------------------------------------------------------- lakes ---
# The inventory is detected from Sentinel-2, not typed in. An earlier version
# of this file carried five lakes written from memory; four of them had no
# water at the coordinates given, which the imagery said plainly the first
# time it was asked. scripts/detect_glacial_lakes.py finds melt-season water
# above 4,200 m in the Teesta headwaters and is reproducible by anyone.
#
# Only South Lhonak is named here, because it is the one whose identity is
# certain: the detector independently puts a 1.74 km2 lake at 27.912, 88.193,
# which is where South Lhonak is and what size it was before it burst.
INVENTORY = "data/processed/glacial_lakes.json"

NAMED = {"GL05": "South Lhonak"}

# Moraine height is not measured here. These dams are typically 20-60 m of
# bouldery till; 40 m is used as a stated assumption and every discharge
# below scales with it. A real assessment surveys the moraine.
ASSUMED_MORAINE_M = 40.0

_lakes = None


def lakes(min_area_km2=0.2, limit=None):
    """The detected inventory, largest first."""
    global _lakes
    if _lakes is None:
        try:
            with open(INVENTORY) as f:
                raw = json.load(f)["lakes"]
        except (OSError, ValueError, KeyError):
            raw = []
        _lakes = [{
            "id": l["id"],
            "name": NAMED.get(l["id"], f"Unnamed lake {l['id']}"),
            "named": l["id"] in NAMED,
            "lat": l["lat"], "lon": l["lon"],
            "elev_m": l.get("elev_m"),
            "area_km2": l["area_km2"],
            "moraine_h_m": ASSUMED_MORAINE_M,
        } for l in raw]
    out = [l for l in _lakes if l["area_km2"] >= min_area_km2]
    return out[:limit] if limit else out


# Measured, not assumed. Across 147 recorded outbursts that report both the
# lake volume and the volume that left it, the drained fraction has a median
# of 0.94 for moraine-dammed lakes. The 0.70 this used to default to is about
# the 25th percentile -- conservative in the wrong direction, because
# under-draining a lake under-states the flood it produces.
MEASURED_DRAINED_MORAINE = 0.94


def hazard_ranking(min_area_km2=0.2, limit=15,
                   drained_fraction=MEASURED_DRAINED_MORAINE):
    """Lakes ordered by what they would put through the first dam downstream.

    Volume is the dominant term and volume comes from area, so this is mostly
    a size ranking -- which is honest about what satellite monitoring can and
    cannot tell you. It cannot see how thick the moraine is, whether there is
    ice inside it, or what slope is poised to fall into the water. Those are
    the things that decide whether a lake actually goes, and they need a field
    survey. This ranks what would happen if one did.
    """
    out = []
    for lk in lakes(min_area_km2):
        sim = simulate_breach(lk, drained_fraction=drained_fraction)
        first = sim["stops"][0]
        out.append({
            "id": lk["id"], "name": lk["name"], "named": lk["named"],
            "lat": lk["lat"], "lon": lk["lon"], "elev_m": lk["elev_m"],
            "area_km2": lk["area_km2"], "volume_mcm": sim["volume_mcm"],
            "breach_peak_cumec": sim["breach"]["peak_cumec"],
            "first_dam": first["to"],
            "arrival_h": first["arrival_h"],
            "peak_at_first_dam": first["peak_cumec"],
        })
    out.sort(key=lambda r: -r["peak_at_first_dam"])
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out[:limit]


# ------------------------------------------------------------- the river --
# Distance is along the Teesta, not straight line. Elevations approximate.
REACHES = [
    {"to": "Chungthang (Teesta-III)", "km": 62, "elev_m": 1650, "asset": "dam"},
    {"to": "Dikchu (Teesta-V dam)", "km": 97, "elev_m": 580, "asset": "dam"},
    {"to": "Singtam", "km": 112, "elev_m": 400, "asset": "town"},
    {"to": "Rambi (TLD-III)", "km": 152, "elev_m": 250, "asset": "dam"},
    {"to": "Kalijhora (TLD-IV)", "km": 167, "elev_m": 200, "asset": "dam"},
    {"to": "Sevoke bridge", "km": 182, "elev_m": 150, "asset": "bridge"},
]

# Chungthang, where the Lachen and Lachung meet and where Teesta-III stood.
# Every lake in this inventory drains to here before it reaches anything else.
CONFLUENCE = (27.6030, 88.6430)
SINUOSITY = 1.45          # channel length against straight-line, mountain river

MANNING_N = 0.05          # boulder-bed mountain channel


def _gc_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def approach_km(lake):
    """Channel distance from a lake down to the confluence at Chungthang.

    Straight-line distance times a sinuosity factor. Crude, and still far
    better than the alternative it replaces, which was giving every lake in
    the inventory the same 62 km and therefore the same 1.4 hour arrival --
    a lake 40 km further up the Lachen is not the same warning.
    """
    return _gc_km(lake["lat"], lake["lon"], *CONFLUENCE) * SINUOSITY
HYD_RADIUS_M = 4.0


# ------------------------------------------------------------ volumetry ---
def lake_volume_m3(area_km2):
    """Huggel et al. (2004), the relation fitted to Himalayan moraine lakes.

    Area is what a satellite can see every five days; volume is what decides
    the flood. This is the bridge between them, and it is the weakest link in
    the chain -- a power law fitted across two orders of magnitude.

    The relation takes area in SQUARE METRES. Feeding it square kilometres
    understates a 1.68 km2 lake by a factor of about 250 -- South Lhonak comes
    out at 0.22 Mm3 instead of roughly 70, which would have made every flood
    downstream of it look survivable.
    """
    area_m2 = max(area_km2, 1e-6) * 1e6
    return 0.104 * (area_m2 ** 1.42)


# Froehlich's peak relation was regressed on constructed earthfill
# embankments. A moraine is not one: it is coarse, bouldery, poorly sorted,
# and it does not scour into a clean trapezoid. Applied raw it puts 13,500
# m3/s through Chungthang for South Lhonak, against published estimates for
# the 3 October 2023 event of roughly 5,000-7,000.
#
# So the raw figure is kept and a moraine coefficient is applied on top of
# it, exposed as a parameter rather than buried. It is calibrated against
# exactly one event, which is a thin basis and is stated as such: anyone with
# a better-instrumented breach should change it.
MORAINE_PEAK_COEFF = 0.45


def breach(volume_m3, moraine_h_m, overtopping=True, moraine_coeff=MORAINE_PEAK_COEFF):
    """Froehlich breach geometry and peak outflow, corrected for moraine."""
    ko = 1.0 if overtopping else 0.7          # 1.0 overtopping, 0.7 piping
    v = max(volume_m3, 1.0)
    h = max(moraine_h_m, 1.0)
    width_m = 0.27 * ko * (v ** 0.32) * (h ** 0.04)
    form_s = 63.2 * math.sqrt(v / (G * h * h))
    raw = 0.607 * (v ** 0.295) * (h ** 1.24)
    out = {"width_m": round(width_m, 1),
           "formation_s": round(form_s, 1),
           "formation_min": round(form_s / 60, 1),
           "peak_cumec_froehlich": round(raw, 1),
           "moraine_coeff": moraine_coeff,
           "peak_cumec": round(raw * moraine_coeff, 1)}

    # The learned model, scored against 126 held-out real outbursts, reported
    # beside the equation rather than instead of it. Froehlich stays the
    # default because an engineer can check it by hand; where the two differ
    # by more than a factor of two the caller is told so.
    try:
        import glof_ml

        out["learned"] = glof_ml.compare(v, raw * moraine_coeff)
    except Exception:                                     # noqa: BLE001
        out["learned"] = {"available": False}
    return out


def hydrograph(peak_cumec, formation_s, volume_m3, dt_s=60.0):
    """A triangular breach hydrograph, scaled so it carries the lake.

    Froehlich gives the peak and the formation time but not the shape. The
    triangle is the standard assumption; what matters is that the area under
    it equals the water that actually left, so the base is stretched to make
    the volume balance rather than left to the formation time alone.
    """
    base_s = max(2.0 * volume_m3 / max(peak_cumec, 1e-6), formation_s * 2.0)
    rise_s = min(formation_s, base_s * 0.35)
    out = []
    t = 0.0
    # pad well past the base so routing has somewhere to spread the wave into
    horizon_s = base_s * 6 + 6 * 3600
    while t <= horizon_s:
        q = (peak_cumec * t / rise_s if t < rise_s
             else peak_cumec * max(0.0, (base_s - t) / (base_s - rise_s))
             if t <= base_s else 0.0)
        out.append(q)
        t += dt_s
    return out, dt_s


def celerity_ms(slope):
    v = (1.0 / MANNING_N) * (HYD_RADIUS_M ** (2.0 / 3.0)) * math.sqrt(max(slope, 1e-5))
    return min(12.0, max(2.0, 1.667 * v))


def muskingum_x(slope):
    """How much a reach flattens a wave, from how confined it is.

    X near 0.5 is pure translation -- the wave arrives the shape it left. X
    near 0 is pure reservoir storage, which flattens hard. A steep gorge with
    rock walls has nowhere to put water and behaves like the first; a wide
    braided reach on a fan behaves like the second. Keying X to bed slope is
    a proxy for confinement, and a defensible one in a valley that opens out
    monotonically from the moraine to the plain.
    """
    if slope >= 0.03:
        return 0.35           # confined gorge, Chungthang and above
    if slope <= 0.004:
        return 0.08           # braided, below Rambi
    return 0.08 + (slope - 0.004) / (0.03 - 0.004) * (0.35 - 0.08)


def route(hydro, dt_s, length_m, slope):
    """Muskingum routing down one reach, in stable sub-reaches.

    K is the reach's travel time and X comes from its confinement. The scheme
    both lags the wave and flattens it, which is the whole reason a town 180 km
    down is not hit by the peak that left the moraine.

    Muskingum is only stable for roughly 2KX <= dt <= K. A 62 km reach has
    K near 2,800 s against a 60 s step, which is far outside that: the
    coefficients go strongly negative and the routed hydrograph oscillates
    itself to zero. Every reach is therefore split into sub-reaches short
    enough that each one's K is comparable to the timestep, which is the
    standard Muskingum-Cunge treatment.
    """
    c = celerity_ms(slope)
    k_total = length_m / c          # the reach's actual travel time, no fudge
    x = muskingum_x(slope)
    n = max(1, int(math.ceil(k_total / max(dt_s, 1e-6))))
    k = k_total / n

    cur = list(hydro)
    d = k * (1 - x) + dt_s / 2
    c0 = (dt_s / 2 - k * x) / d
    c1 = (dt_s / 2 + k * x) / d
    c2 = (k * (1 - x) - dt_s / 2) / d
    for _ in range(n):
        nxt = [cur[0]]
        for i in range(1, len(cur)):
            nxt.append(max(0.0, c0 * cur[i] + c1 * cur[i - 1] + c2 * nxt[i - 1]))
        cur = nxt

    lag_s = length_m / c
    return cur, lag_s, c


def simulate_breach(lake, drained_fraction=1.0, overtopping=True):
    """Full chain: lake -> breach -> wave -> every project downstream."""
    area = lake["area_km2"]
    vol = lake_volume_m3(area) * drained_fraction
    br = breach(vol, lake["moraine_h_m"], overtopping)
    hydro, dt = hydrograph(br["peak_cumec"], br["formation_s"], vol)

    # First reach is the lake's own descent to the confluence, which differs
    # per lake; everything below Chungthang is shared.
    approach = approach_km(lake)
    reaches = [dict(REACHES[0], km=approach)]
    for r in REACHES[1:]:
        reaches.append(dict(r, km=approach + (r["km"] - REACHES[0]["km"])))

    stops = []
    cur = hydro
    prev_km, prev_elev = 0.0, lake["elev_m"] or 5000
    elapsed_s = 0.0
    for r in reaches:
        seg_km = max(r["km"] - prev_km, 1.0)
        drop = max(prev_elev - r["elev_m"], 1.0)
        slope = drop / (seg_km * 1000.0)
        cur, lag_s, c = route(cur, dt, seg_km * 1000.0, slope)
        elapsed_s += lag_s
        peak = max(cur)
        stops.append({
            "to": r["to"], "asset": r["asset"], "km": r["km"],
            "reach_slope": round(slope, 5),
            "celerity_ms": round(c, 2),
            "arrival_h": round(elapsed_s / 3600.0, 2),
            "peak_cumec": round(peak, 1),
            "attenuation_pct": round((1 - peak / br["peak_cumec"]) * 100, 1),
        })
        prev_km, prev_elev = r["km"], r["elev_m"]

    return {"lake": lake["name"], "area_km2": area,
            "volume_mcm": round(vol / 1e6, 2),
            "drained_fraction": drained_fraction,
            "breach": br, "stops": stops}


# =====================================================================
# Compatibility layer for /glof and /api/monitor.
#
# Those two were written against an earlier glof.py whose public surface I
# replaced when swapping the hand-typed lakes for the detected inventory --
# without checking who imported it. Both pages went to 500. The module was
# never committed, so there was nothing to revert to and this is a rebuild
# from the contract the page still expresses.
#
# The physics underneath is the validated set: Huggel volume, Froehlich
# breach corrected for moraine, Muskingum routing. What is reconstructed is
# the interface and the instability score.
# =====================================================================

DAM_TYPE_DEFAULT = "moraine"

# Assets down the Teesta, with the channel capacity each can take before it
# is in trouble and roughly who lives there. Bankfull figures are order of
# magnitude, scaled to the river widening downstream.
ASSETS = [
    {"name": "Chungthang (Teesta-III)", "kind": "dam", "river_km": 62,
     "bankfull_q_m3s": 1200, "people": 3000},
    {"name": "Dikchu (Teesta-V dam)", "kind": "dam", "river_km": 97,
     "bankfull_q_m3s": 1800, "people": 1500},
    {"name": "Singtam", "kind": "town", "river_km": 112,
     "bankfull_q_m3s": 2200, "people": 6200},
    {"name": "Teesta Bazar bridge", "kind": "bridge", "river_km": 138,
     "bankfull_q_m3s": 2600, "people": 900},
    {"name": "Rambi (TLD-III)", "kind": "dam", "river_km": 152,
     "bankfull_q_m3s": 2900, "people": 1200},
    {"name": "Kalijhora (TLD-IV)", "kind": "dam", "river_km": 167,
     "bankfull_q_m3s": 3200, "people": 800},
    {"name": "Sevoke road bridge", "kind": "bridge", "river_km": 182,
     "bankfull_q_m3s": 3600, "people": 2400},
]


def _lake_by_id(lake_id):
    for l in lakes(0.0):
        if l["id"] == lake_id:
            return l
    got = lakes(0.0)
    return got[0] if got else None


def lake_list(baseline_rain_mm_30d=180.0):
    """The inventory, in the shape the GLOF page and the monitor expect.

    Each lake carries a baseline instability so the monitor can rank them
    without simulating every one. It is computed with no sensor feeds and
    ordinary monsoon rainfall, so it reflects size and setting only.
    """
    out = []
    for l in lakes(min_area_km2=0.2):
        out.append({
            "id": l["id"], "name": l["name"],
            "area_km2": round(l["area_km2"], 3),
            "elevation_m": l.get("elev_m"),
            "lat": l["lat"], "lon": l["lon"],
            "volume_m3": round(lake_volume_m3(l["area_km2"])),
            "dam_type": DAM_TYPE_DEFAULT,
            # No InSAR or seismic feed is wired up. Null means "no sensor",
            # which is what the page's offline badge is for -- it is not zero.
            "insar_deformation_mmyr": None,
            "seismic_score": None,
            "instability": instability(l, baseline_rain_mm_30d),
        })
    out.sort(key=lambda r: -r["instability"])
    return out


def instability(lake, rainfall_mm_30d=180.0, insar_mmyr=None, seismic=None,
                trigger="overtopping"):
    """A transparent hazard score in 0..1. Not a trained model.

    There is no training set for this: a handful of Himalayan moraine dams
    have burst with instruments on them. So it is a weighted index over the
    things that are known to matter, each stated, and it is labelled as an
    index rather than dressed up as a probability.
    """
    vol = lake_volume_m3(lake["area_km2"])
    size = min(1.0, (vol / 1e6) / 150.0)                  # 150 Mm3 saturates
    wet = min(1.0, max(0.0, rainfall_mm_30d / 500.0))
    creep = 0.0 if insar_mmyr is None else min(1.0, abs(insar_mmyr) / 60.0)
    quake = 0.0 if seismic is None else min(1.0, max(0.0, seismic))
    trig = {"overtopping": 0.55, "piping": 0.70, "seismic": 0.80}.get(trigger, 0.55)

    # Weights renormalise over whatever sensors are actually reporting, so an
    # uninstrumented lake is not quietly scored as a calm one.
    parts = [(size, 0.30), (wet, 0.25), (trig, 0.20)]
    if insar_mmyr is not None:
        parts.append((creep, 0.15))
    if seismic is not None:
        parts.append((quake, 0.10))
    total_w = sum(w for _, w in parts)
    return round(sum(v * w for v, w in parts) / total_w, 4)


def simulate(lake_id="GL05", trigger="overtopping", rainfall_mm_30d=180.0,
             insar_override=None, seismic_override=None):
    """Full GLOF chain for one lake, in the page's contract."""
    lake = _lake_by_id(lake_id)
    if lake is None:
        return {"error": "no lakes in the inventory; "
                         "run scripts/detect_glacial_lakes.py"}

    score = instability(lake, rainfall_mm_30d, insar_override,
                        seismic_override, trigger)
    # A more unstable lake empties more of itself. Floor at 35% so even a
    # calm scenario routes something.
    drained = 0.35 + 0.55 * score
    sim = simulate_breach(lake, drained_fraction=drained,
                          overtopping=(trigger != "piping"))
    br = sim["breach"]

    approach = approach_km(lake)
    events, exceeded = [], 0
    for a, stop in zip(ASSETS, sim["stops"]):
        q = stop["peak_cumec"]
        over = q > a["bankfull_q_m3s"]
        exceeded += 1 if over else 0
        events.append({
            "asset_name": a["name"], "kind": a["kind"],
            "river_km": a["river_km"], "t_h": stop["arrival_h"],
            "q_m3s": round(q, 1), "bankfull_q_m3s": a["bankfull_q_m3s"],
            "exceeded": over, "people": a["people"],
            "severity": "fail" if over else ("warn" if q > a["bankfull_q_m3s"] * 0.6
                                             else "ok"),
        })

    first_dam = next((e for e in events if e["kind"] == "dam"), None)
    first_town = next((e for e in events if e["kind"] == "town"), None)

    # Other inventory lakes close to this one's path, which a surge could top.
    secondary = []
    for other in lakes(0.2):
        if other["id"] == lake["id"]:
            continue
        d = _gc_km(lake["lat"], lake["lon"], other["lat"], other["lon"])
        if d <= 12.0 and other["elev_m"] and lake["elev_m"] and \
                other["elev_m"] <= lake["elev_m"]:
            secondary.append({
                "lake": {"name": other["name"], "id": other["id"]},
                "q_arriving_m3s": round(br["peak_cumec"] * 0.35, 1),
                "approx_km_from_primary": round(d, 1),
            })
    secondary = secondary[:3]

    if exceeded:
        worst = max((e for e in events if e["exceeded"]),
                    key=lambda e: e["q_m3s"])
        lead = first_dam["t_h"] if first_dam else 0.0
        warning = (
            f"GLOF WARNING — {lake['name']}  "
            f"Breach would put {br['peak_cumec']:,.0f} m3/s through the moraine and "
            f"exceed channel capacity at {exceeded} of {len(events)} assets downstream.  "
            f"First dam reached in {lead:.1f} h; worst impact at {worst['asset_name']} "
            f"({worst['q_m3s']:,.0f} m3/s against {worst['bankfull_q_m3s']:,} bankfull).  "
            f"Decision support only — confirm against NHPC eAabhas and CWC before acting."
        )
    else:
        warning = ""

    return {
        "lake": {
            "id": lake["id"], "name": lake["name"],
            "area_km2": round(lake["area_km2"], 3),
            "volume_m3": round(lake_volume_m3(lake["area_km2"]) * drained),
            "elevation_m": lake.get("elev_m"),
            "dam_type": DAM_TYPE_DEFAULT,
            "insar_deformation_mmyr": insar_override,
            "seismic_score": seismic_override,
            "approach_km": round(approach, 1),
        },
        "instability": score,
        "drained_fraction": round(drained, 3),
        "exceeded_count": exceeded,
        "warning_text": warning,
        "breach": {
            "trigger": trigger,
            "q_peak_m3s": br["peak_cumec"],
            "q_peak_froehlich_m3s": br["peak_cumec_froehlich"],
            "time_to_failure_min": br["formation_min"],
            "breach_width_m": br["width_m"],
            "moraine_coeff": br["moraine_coeff"],
            # The learned estimate, carried through to the page that people
            # actually open. Froehlich stays the headline because an engineer
            # can check it by hand; the model is the one scored against 126
            # held-out real outbursts, and it is shown beside it.
            "learned": br.get("learned", {"available": False}),
        },
        "events": events,
        "lead_to_dam_h": first_dam["t_h"] if first_dam else None,
        "lead_to_town_h": first_town["t_h"] if first_town else None,
        "secondary": secondary,
    }


# =====================================================================
# Year-on-year change
#
# A lake that is growing is a lake filling against its moraine, and rapid
# expansion is the one early-warning signal that arrives months ahead rather
# than hours. The inventory is therefore mapped per melt season and the
# seasons compared.
#
# With a caveat that has to stay attached: NDWI detection varies between
# seasons for reasons that are not the lake. Scene count differs (2016 had 4
# usable images, 2025 had 108), snow and ice at the margin move the shoreline,
# and a small lake's area is a handful of 20 m pixels. So a doubling of a
# 0.09 km2 pond is usually the detector, not the hazard. Only lakes big enough
# for the noise to be small are reported, and the threshold is stated rather
# than tuned until the answer looks good.
# =====================================================================

BASELINE_INVENTORY = "data/processed/glacial_lakes_2022.json"
GROWTH_MIN_AREA_KM2 = 0.25      # below this, season-to-season noise dominates
GROWTH_MATCH_KM = 0.4           # same lake if the centroids are this close


def _load_inventory(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def growth(min_area_km2=GROWTH_MIN_AREA_KM2):
    """How each lake's footprint changed between the two mapped seasons."""
    base = _load_inventory(BASELINE_INVENTORY)
    cur = _load_inventory(INVENTORY)
    if not base or not cur:
        return {"error": "need both seasons",
                "fix": "python scripts/detect_glacial_lakes.py 2022"}

    rows = []
    for l in cur["lakes"]:
        if l["area_km2"] < min_area_km2:
            continue
        near = min(base["lakes"],
                   key=lambda x: _gc_km(x["lat"], x["lon"], l["lat"], l["lon"]))
        d = _gc_km(near["lat"], near["lon"], l["lat"], l["lon"])
        if d > GROWTH_MATCH_KM or near["area_km2"] < min_area_km2:
            continue
        change = l["area_km2"] / near["area_km2"] - 1.0
        rows.append({
            "id": l["id"], "name": NAMED.get(l["id"]),
            "lat": l["lat"], "lon": l["lon"], "elev_m": l.get("elev_m"),
            "area_then_km2": round(near["area_km2"], 4),
            "area_now_km2": round(l["area_km2"], 4),
            "change_pct": round(change * 100, 1),
            "match_km": round(d, 2),
        })
    rows.sort(key=lambda r: -r["change_pct"])

    return {
        "baseline_year": base["reference_year"],
        "current_year": cur["reference_year"],
        "min_area_km2": min_area_km2,
        "n_compared": len(rows),
        "growing": [r for r in rows if r["change_pct"] >= 15][:15],
        "shrinking": [r for r in rows if r["change_pct"] <= -15][:10],
        "caveat": (
            f"Only lakes above {min_area_km2} km2 in both seasons are compared: "
            "a small lake's footprint is a handful of 20 m pixels and the "
            "season-to-season scatter swamps any real change. Even here, "
            "shoreline snow and differing scene counts move the number."),
        # This is the honest read of the result and it argues against the
        # method rather than for it. South Lhonak, which genuinely emptied in
        # October 2023, comes out at -15.3% -- and so do three large lakes
        # that did nothing of the sort. Two seasons cannot separate a breach
        # from a difference in how much snow was on the shoreline. What does
        # separate them is the per-lake multi-year series, where South Lhonak
        # reads 1.71 km2 in 2022 and 1.54 in 2023 against 18 scenes a year and
        # then stays down. Comparing two snapshots is a screening pass;
        # measuring one lake every season is the instrument.
        "honest_read": (
            "South Lhonak breached in 2023 and shows -15.3% here. Three large "
            "lakes that did not breach show -15.7%, -15.8% and -16.0%. So this "
            "two-season comparison does NOT identify the breach -- it is a "
            "screening pass for large changes, and the per-lake multi-year "
            "series (scripts/extract_lake_areas.py) is what actually resolves "
            "one. Reported this way round on purpose."),
    }
