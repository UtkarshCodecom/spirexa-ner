"""A working stand-in for NHPC's plant telemetry, and the two days worth seeing.

NHPC's Teesta projects are instrumented the way every large hydro scheme is:
ARMAC for the reservoir and dam body, TSI for each turbine-generator, eAabhas
for inflow forecasting, all of it landing in a PI historian and a control room
in Faridabad. None of that is public. Getting at it means an MoU with the R&D
wing, and an MoU takes longer than a project cycle.

So this module generates the feed instead -- same tag names, same units, same
alarm and trip thresholds, same sampling rates -- and drives it with the
physics already in this repository rather than with invented numbers. That
distinction is the whole point:

    the reservoir level is not a curve somebody drew. It is the mass balance
    of an inflow hydrograph that Muskingum routing carried down from a moraine
    breach that Froehlich's equation produced from a lake volume that Huggel's
    area-volume relation gave for a footprint Sentinel-2 actually measured.

Two scenarios, toggled:

    normal    a wet day on the tail of the monsoon. Everything in band, units
              on load, gates shut. This is what 360 days a year look like, and
              a warning system nobody can see working on a quiet day is a
              warning system nobody trusts on a loud one.

    oct2023   23:00 on 3 October 2023 to 11:00 on 4 October, the South Lhonak
              outburst. The wave reaches Chungthang at +1.9 h and Dikchu at
              +2.7 h, which is what the routing says and close to what was
              observed. Teesta-III's pondage is 5 MCM against an inflow near
              5,000 m3/s: it fills in under a quarter of an hour, and every
              downstream tag follows from that.

WHAT IS MEASURED, WHAT IS PHYSICS, AND WHAT IS MACHINE LEARNING
Every tag below carries a `by` field, and the API reports it, because the
question is always asked and the honest answer is that most of a hydro control
room is not machine learning and should not be:

    sensor    a real instrument reads this. Here it is replayed from the
              scenario, and in a deployment it arrives over Modbus.
    physics   computed from an equation in this repo -- mass balance, Huggel,
              Froehlich, Muskingum, Manning, SCS curve number. Auditable line
              by line. No training data, no drift.
    ml        produced by a model trained on data. There are exactly three in
              this system and each one is named at its tag.
"""

import datetime
import math

import glof

# --------------------------------------------------------------------------
# the cascade

SITES = [
    {"id": "T3", "crest_len_m": 160, "lat": 27.6006, "lon": 88.6417, "name": "Teesta-III", "place": "Chungthang",
     "river_km": 62, "capacity_mw": 1200, "units": 6, "unit_mw": 200,
     "pond_mcm": 5.0, "fsl_m": 1573.0, "mddl_m": 1567.0, "dam_top_m": 1576.0,
     "head_m": 790.0, "dam_kind": "concrete-face rockfill",
     "spill_capacity_m3s": 7000, "bankfull_m3s": 1200, "people": 3000},
    {"id": "T5", "crest_len_m": 130, "lat": 27.4197, "lon": 88.5222, "name": "Teesta-V", "place": "Dikchu",
     "river_km": 97, "capacity_mw": 510, "units": 3, "unit_mw": 170,
     "pond_mcm": 1.2, "fsl_m": 578.0, "mddl_m": 573.0, "dam_top_m": 581.5,
     "head_m": 200.0, "dam_kind": "concrete gravity",
     "spill_capacity_m3s": 5000, "bankfull_m3s": 1800, "people": 1500},
    {"id": "TL3", "crest_len_m": 210, "lat": 27.0225, "lon": 88.4547, "name": "Teesta Low Dam III", "place": "Rambi",
     "river_km": 152, "capacity_mw": 132, "units": 4, "unit_mw": 33,
     "pond_mcm": 2.4, "fsl_m": 248.0, "mddl_m": 245.0, "dam_top_m": 251.0,
     "head_m": 30.0, "dam_kind": "barrage",
     "spill_capacity_m3s": 6000, "bankfull_m3s": 2900, "people": 1200},
    {"id": "TL4", "crest_len_m": 220, "lat": 26.9236, "lon": 88.4664, "name": "Teesta Low Dam IV", "place": "Kalijhora",
     "river_km": 167, "capacity_mw": 160, "units": 4, "unit_mw": 40,
     "pond_mcm": 3.1, "fsl_m": 198.0, "mddl_m": 195.0, "dam_top_m": 201.0,
     "head_m": 35.0, "dam_kind": "barrage",
     "spill_capacity_m3s": 6500, "bankfull_m3s": 3200, "people": 800},
]

# Which routed reach in glof.REACHES corresponds to which project.
REACH_FOR = {"T3": "Chungthang (Teesta-III)", "T5": "Dikchu (Teesta-V dam)",
             "TL3": "Rambi (TLD-III)", "TL4": "Kalijhora (TLD-IV)"}

LAKE_ID = "GL05"          # South Lhonak
# Fraction of the lake that leaves through the breach. Measured at 0.94 for
# moraine-dammed lakes across 147 recorded outbursts (Lutzow & Veh 2023),
# not the 0.70 this assumed before.
DRAINED = 0.94


# --------------------------------------------------------------------------
# the tag dictionary
#
# Thresholds are the ordinary ones for a Francis set of this size. They exist
# so the alarm engine has something to fire against; a deployment would take
# them from the plant's own protection schedule.

def _t(tag, label, unit, system, by, source, alarm=None, trip=None,
       rate="1 min", direction="high", detail=""):
    return {"tag": tag, "label": label, "unit": unit, "system": system,
            "by": by, "source": source, "alarm": alarm, "trip": trip,
            "rate": rate, "direction": direction, "detail": detail}


TAGS = [
    # ---- ARMAC: reservoir and dam body -------------------------------
    _t("reservoir_level_m", "Reservoir level", "m", "ARMAC", "physics",
       "mass balance of routed inflow against turbine draft and gates",
       rate="1 min",
       detail="Radar level transmitter in the plant. Here it is integrated: "
              "dV = (Qin - Qout)dt over the pondage curve."),
    _t("inflow_m3s", "Reservoir inflow", "m3/s", "ARMAC", "physics",
       "Muskingum routing of the breach hydrograph (glof.route)",
       rate="5 min",
       detail="Stage-discharge in the plant. Here it is the routed GLOF wave "
              "in the outburst scenario, and a rainfall-runoff recession on a "
              "normal day."),
    _t("outflow_m3s", "Total outflow", "m3/s", "ARMAC", "physics",
       "turbine discharge plus spillway rating", rate="5 min"),
    _t("spill_gate_pct", "Spillway gate opening", "%", "SCADA", "physics",
       "gate rule: opens on level above FSL, full above dam top minus 1 m",
       rate="on change"),
    _t("seepage_lps", "Dam seepage", "L/s", "ARMAC", "physics",
       "Darcy response to head, with a first-order lag", rate="15 min",
       alarm=45, trip=80,
       detail="V-notch weir and ultrasonic level. Rising seepage under steady "
              "head is the classic internal-erosion signature."),
    _t("pore_pressure_kpa", "Pore water pressure", "kPa", "ARMAC", "physics",
       "hydrostatic head at the piezometer, lagged", rate="15 min",
       alarm=420, trip=520),
    _t("uplift_kpa", "Foundation uplift", "kPa", "ARMAC", "physics",
       "fraction of headwater pressure at the foundation gallery",
       rate="15 min", alarm=300, trip=380),
    _t("crest_movement_mm", "Crest movement", "mm", "ARMAC", "sensor",
       "GPS monument / total station", rate="daily", alarm=8, trip=15),
    _t("seismic_g", "Seismic acceleration", "g", "ARMAC", "sensor",
       "strong-motion accelerograph", rate="event", alarm=0.05, trip=0.12),
    _t("rainfall_mm_h", "Catchment rainfall", "mm/h", "ARMAC", "sensor",
       "tipping-bucket gauge; satellite equivalent is IMERG", rate="1 min",
       alarm=25, trip=50),
    _t("turbidity_ntu", "Turbidity", "NTU", "ARMAC", "physics",
       "sediment rating curve against discharge", rate="15 min",
       alarm=2000, trip=6000,
       detail="The tag that moves first in a debris flood. Silt reaching the "
              "turbines is what decides whether units stay on load."),
    _t("water_temp_c", "Water temperature", "C", "ARMAC", "sensor",
       "thermistor", rate="15 min"),

    # ---- TSI: turbine and generator ----------------------------------
    _t("active_power_mw", "Active power", "MW", "TSI", "physics",
       "head x discharge x efficiency", rate="1 min"),
    _t("turbine_speed_rpm", "Turbine speed", "RPM", "TSI", "sensor",
       "magnetic pickup", rate="1 s", alarm=315, trip=330),
    _t("guide_vane_pct", "Guide vane opening", "%", "TSI", "physics",
       "governor response to load and head", rate="1 s"),
    _t("penstock_bar", "Penstock pressure", "bar", "TSI", "physics",
       "static head plus water-hammer transient", rate="1 s",
       alarm=8.5, trip=9.0),
    _t("draft_tube_bar", "Draft tube pressure", "bar", "TSI", "physics",
       "suction head; cavitation margin", rate="1 s",
       alarm=-0.8, trip=-0.95, direction="low"),
    _t("bearing_temp_c", "Guide bearing temperature", "C", "TSI", "sensor",
       "Pt100 RTD", rate="5 s", alarm=70, trip=85),
    _t("shaft_vib_um", "Shaft vibration", "um pk-pk", "TSI", "sensor",
       "proximity probe", rate="1 s", alarm=100, trip=150,
       detail="Rises with silt-laden water and with any hydraulic roughness; "
              "the tag that trips a unit during a debris flood."),
    _t("stator_temp_c", "Stator winding temperature", "C", "TSI", "sensor",
       "embedded RTD", rate="5 s", alarm=105, trip=130),
    _t("lube_oil_bar", "Lube oil pressure", "bar", "TSI", "sensor",
       "pressure switch", rate="5 s", alarm=1.5, trip=1.0, direction="low"),
    _t("cooling_flow_m3h", "Cooling water flow", "m3/h", "TSI", "sensor",
       "flow meter", rate="1 min", alarm=110, trip=80, direction="low"),

    # ---- the lake, 80 km upstream of the first dam -------------------
    _t("lake_level_m", "Lake level", "m", "GLOF", "sensor",
       "pressure probe on the moraine dam", rate="15 min",
       alarm=2.0, trip=4.0,
       detail="Relative to the season's datum. The only tag in this table "
              "that gives warning before the wave exists."),
    _t("lake_area_km2", "Lake area", "km2", "GLOF", "sensor",
       "Sentinel-2 NDWI, 5-day revisit", rate="5 days"),
    _t("insar_mm_yr", "Moraine deformation", "mm/yr", "GLOF", "sensor",
       "Sentinel-1 InSAR, 6-day", rate="6 days", alarm=25, trip=60),
    _t("lake_seismic", "Icefall / avalanche", "count/h", "GLOF", "sensor",
       "seismic station at the lake", rate="real time", alarm=3, trip=8),

    # ---- the three things in this system that are actually learned ----
    _t("breach_probability", "Breach probability", "0-1", "SPIREXA", "ml",
       "instability score: lake growth, moraine deformation, seismicity, "
       "antecedent rain (glof.instability)", rate="15 min",
       alarm=0.35, trip=0.6,
       detail="A weighted index over the measured drivers, not a trained "
              "classifier -- there are 4 documented Sikkim outbursts to learn "
              "from, which is not a training set. Called out as such."),
    _t("inflow_forecast_m3s", "Inflow forecast (d+1)", "m3/s", "eAabhas",
       "ml", "gradient-boosted discharge model (src/discharge.py)",
       rate="1 h",
       detail="Trained: NSE 0.418 at day+1 falling to 0.023 at day+4, on "
              "synthetic hydrology. Needs real CWC gauge series before "
              "anybody leans on it."),
    _t("slope_risk", "Slope failure risk", "0-1", "SPIREXA", "ml",
       "random forest trigger model, 5-fold CV ROC-AUC 0.933", rate="1 h",
       alarm=0.5, trip=0.75,
       detail="The one model here with a real training set: 318 dated events "
              "against 628 non-events, 17 features."),
]

TAG_BY_NAME = {t["tag"]: t for t in TAGS}


def tag_dictionary():
    """The tag table, grouped for display, with provenance counts."""
    counts = {}
    for t in TAGS:
        counts[t["by"]] = counts.get(t["by"], 0) + 1
    systems = {}
    for t in TAGS:
        systems.setdefault(t["system"], []).append(t)
    return {"counts": counts, "total": len(TAGS),
            "systems": [{"system": k, "tags": v} for k, v in systems.items()]}


# ==========================================================================
# the physics that produces the feed
# ==========================================================================

RHO_G = 1000.0 * 9.81
EFF = 0.90
DT_S = 60.0                        # one sample a minute, both scenarios


def design_q(site):
    """Discharge one unit swallows at full load: P = rho g Q H eta."""
    return site["unit_mw"] * 1e6 / (RHO_G * site["head_m"] * EFF)


def _pond_area_m2(site):
    """Surface area implied by the live storage between MDDL and FSL."""
    return site["pond_mcm"] * 1e6 / max(site["fsl_m"] - site["mddl_m"], 0.5)


def _crest_overflow(site, level):
    """Weir flow over the dam top once the gates cannot take it any more.

    Without this the mass balance has nowhere to put the water and the
    reservoir level climbs thirty metres above the crest, which is arithmetic
    rather than hydraulics. Broad-crested weir, C = 1.7.
    """
    h = level - site["dam_top_m"]
    if h <= 0:
        return 0.0
    return 1.7 * site["crest_len_m"] * h ** 1.5


def _spill_q(site, level, gate_frac):
    """Ogee rating: nothing below the crest, capacity at the gate setting."""
    crest = site["mddl_m"]
    h = level - crest
    if h <= 0 or gate_frac <= 0:
        return 0.0
    span = max(site["dam_top_m"] - crest, 1.0)
    return site["spill_capacity_m3s"] * gate_frac * min((h / span) ** 1.5, 1.0)


# A spillway gate is a large steel object on a hoist. Full travel is about
# half an hour, which is why a warning measured in hours is worth something
# and a warning measured in minutes is not.
GATE_TRAVEL_MIN = 30.0
GATE_SLEW = 1.0 / GATE_TRAVEL_MIN          # fraction of travel per minute
OPERATOR_DELAY_MIN = 20.0                  # see the level move, decide, act


def _gate_demand(site, level, warned):
    """What the operator asks for. Warned, they ask early; unwarned, late.

    This is the single most consequential line in the module. Teesta-III's
    spillway was rated near 7,000 cumec against a wave of 4,876 -- on paper
    the dam passes it. What it did not have was anyone opening the gates in
    time, in the dark, with no upstream instrument between the lake and the
    dam. So the same structure survives or does not depending entirely on
    whether something told it the wave was coming, which is the product.
    """
    if warned:
        return 1.0
    fsl, top = site["fsl_m"], site["dam_top_m"]
    if level >= top - 1.0:
        return 1.0
    if level <= fsl:
        return 0.0
    return min(1.0, (level - fsl) / max(top - 1.0 - fsl, 0.5))


def _turbidity(q, q_base):
    """Sediment rating curve. Silt, not water, is what stops a turbine."""
    return 60.0 * (max(q, 1.0) / max(q_base, 1.0)) ** 1.4


def _vibration(turbidity, load_frac, running):
    if not running:
        return 4.0
    off_design = abs(load_frac - 0.85)
    return 34.0 + 0.0135 * turbidity + 60.0 * off_design


# --------------------------------------------------------------------------
# inflow series

def _breach_inflow():
    """The routed outburst wave at every project, minute by minute.

    Re-runs glof's own primitives rather than calling simulate_breach(),
    because that function keeps only the peak of each reach and the whole
    point here is the shape of the limb.
    """
    lake = next(l for l in glof.lakes(0.0) if l["id"] == LAKE_ID)
    vol = glof.lake_volume_m3(lake["area_km2"]) * DRAINED
    br = glof.breach(vol, lake["moraine_h_m"], True)
    hydro, dt = glof.hydrograph(br["peak_cumec"], br["formation_s"], vol)

    approach = glof.approach_km(lake)
    reaches = [dict(glof.REACHES[0], km=approach)]
    for r in glof.REACHES[1:]:
        reaches.append(dict(r, km=approach + (r["km"] - glof.REACHES[0]["km"])))

    series, cur = {}, hydro
    prev_km, prev_elev, elapsed = 0.0, lake["elev_m"] or 5000, 0.0
    for r in reaches:
        seg_km = max(r["km"] - prev_km, 1.0)
        drop = max(prev_elev - r["elev_m"], 1.0)
        cur, lag_s, _ = glof.route(cur, dt, seg_km * 1000.0, drop / (seg_km * 1000.0))
        elapsed += lag_s
        series[r["to"]] = {"q": list(cur), "dt": dt, "lag_s": elapsed}
        prev_km, prev_elev = r["km"], r["elev_m"]
    return {"lake": lake, "volume_m3": vol, "breach": br, "reaches": series}


def _sample(series, t_s):
    """Value of a routed hydrograph at wall-clock t.

    No lag term here on purpose. Muskingum shifts the wave in time as part of
    routing it, so the series that comes back is already lagged; `lag_s` is
    carried alongside only to report the arrival time. Adding it here as well
    put the wave at Chungthang at 3.8 h instead of 1.9 -- exactly double, and
    exactly the kind of error that looks plausible on a chart.
    """
    i = t_s / series["dt"]
    if i < 0:
        return 0.0
    i0 = int(i)
    q = series["q"]
    if i0 >= len(q) - 1:
        return float(q[-1])
    f = i - i0
    return float(q[i0] * (1 - f) + q[i0 + 1] * f)


# --------------------------------------------------------------------------
# the two days

SCENARIOS = {
    "normal": {
        "id": "normal",
        "label": "Normal operations",
        "sub": "A wet day on the tail of the monsoon",
        "start": "2026-09-17T00:00:00",
        "hours": 24,
        "note": "Units on load, gates shut, everything inside its band. This "
                "is what 360 days a year look like. It is here because a "
                "monitoring system that only has a disaster to show is a "
                "demo, not an instrument.",
    },
    "oct2023": {
        "id": "oct2023",
        "label": "South Lhonak outburst",
        "sub": "3-4 October 2023, the night Teesta-III went",
        "start": "2023-10-03T23:00:00",
        "hours": 12,
        "note": "The lake let go late on 3 October. Routing puts the wave at "
                "Chungthang 1.9 h later against roughly 1.5 h observed, and "
                "at Dikchu at 2.7 h. Teesta-III holds 5 million cubic metres "
                "against an inflow near 5,000 cubic metres a second: the "
                "pondage is gone in a quarter of an hour, and everything "
                "after that is the dam, not the lake.",
    },
}

BASE_Q = {"T3": 95.0, "T5": 210.0, "TL3": 430.0, "TL4": 470.0}


def _nearest_hotspot_risk():
    """Trigger-model risk at the monitored slope nearest each project.

    This is the one place the landslide side reaches into the plant feed, and
    it is not decoration: the 2023 flood did most of its damage by mobilising
    the valley sides, and a powerhouse can be cut off by the road above it
    long before the water reaches the yard.
    """
    import csv
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data/processed/live_risk.csv")
    if not os.path.exists(path):
        return {s["id"]: None for s in SITES}
    rows = list(csv.DictReader(open(path)))
    out = {}
    for s in SITES:
        best, bestd = None, 1e9
        for r in rows:
            d = ((float(r["lat"]) - s["lat"]) ** 2
                 + (float(r["lon"]) - s["lon"]) ** 2) ** 0.5
            if d < bestd:
                best, bestd = r, d
        out[s["id"]] = {
            "risk": round(float(best["live_risk"]), 3),
            "at": best["location"], "km": round(bestd * 111.0, 1),
        } if best else None
    return out


def run(scenario="oct2023", warning_lead_h=0.0):
    """Generate the whole feed: every tag, every site, every minute.

    warning_lead_h is how long before the wave arrives that the control room
    is told. Zero is October 2023: nothing between the lake and the dam, and
    the first indication was the level rising. Anything above about an hour is
    what this system is for -- enough to walk the gates open before the limb
    arrives, and enough to clear the powerhouse.
    """
    cfg = SCENARIOS.get(scenario) or SCENARIOS["oct2023"]
    t0 = datetime.datetime.fromisoformat(cfg["start"])
    n = int(cfg["hours"] * 3600 / DT_S)
    outburst = scenario == "oct2023"

    wave = _breach_inflow() if outburst else None
    slope = _nearest_hotspot_risk()
    lake = next(l for l in glof.lakes(0.0) if l["id"] == LAKE_ID)

    # state per site
    st = {}
    for s in SITES:
        st[s["id"]] = {
            "level": s["fsl_m"] - 0.4,
            "seep": 12.0 + 3.5 * (s["fsl_m"] - 0.4 - s["mddl_m"]),
            "pore": 9.81 * (s["fsl_m"] - 0.4 - s["mddl_m"] + 30),
            "units": s["units"],
            "gate": 0.0,
            "failed": False,
            "blackout": False,
            "overtop_min": 0.0,
            "demand_since": None,
            "prev_level": s["fsl_m"] - 0.4,
        }
    # When each project would be told, if anything were watching the lake.
    arrival_h = {}
    if wave:
        for s in SITES:
            arrival_h[s["id"]] = wave["reaches"][REACH_FOR[s["id"]]]["lag_s"] / 3600.0
    warn_at = {k: v - warning_lead_h for k, v in arrival_h.items()}

    frames = []
    events = []
    for k in range(n):
        t_s = k * DT_S
        ts = t0 + datetime.timedelta(seconds=t_s)
        hour = t_s / 3600.0

        # ---- upstream drivers -------------------------------------
        if outburst:
            # heavy orographic rain through the evening, easing after the burst
            rain = 14.0 * math.exp(-((hour - 0.6) ** 2) / 1.6) + 3.0
            lake_level = 2.4 + 0.35 * hour if hour < 1.0 else max(
                2.75 - 14.0 * (hour - 1.0), -38.0)
            lake_seismic = 9.0 if 0.75 <= hour <= 1.15 else (
                4.0 if 0.3 <= hour < 0.75 else 0.4)
            insar = 78.0
            rain_30d = 430.0
        else:
            rain = max(0.0, 2.2 * math.sin((hour - 3) / 24 * 2 * math.pi) + 1.4)
            lake_level = 0.35 + 0.05 * math.sin(hour / 24 * 2 * math.pi)
            lake_seismic = 0.2
            insar = 21.0
            rain_30d = 190.0

        p_breach = glof.instability(lake, rainfall_mm_30d=rain_30d,
                                    insar_mmyr=insar, seismic=lake_seismic)

        frame = {"t": ts.isoformat(timespec="seconds"), "hour": round(hour, 3),
                 "lake": {"lake_level_m": round(lake_level, 2),
                          "lake_area_km2": lake["area_km2"],
                          "insar_mm_yr": insar,
                          "lake_seismic": round(lake_seismic, 1),
                          "breach_probability": round(p_breach, 3)},
                 "sites": {}}

        upstream_release = 0.0          # a failed dam hands its flood down
        for s in SITES:
            v = st[s["id"]]
            base = BASE_Q[s["id"]] * (1.0 + 0.12 * math.sin(hour / 24 * 2 * math.pi))
            q_in = base + upstream_release
            if outburst:
                q_in += _sample(wave["reaches"][REACH_FOR[s["id"]]], t_s)

            # --- units: silt and head decide whether they stay on ----
            turb = _turbidity(q_in, BASE_Q[s["id"]])
            head_ok = v["level"] > s["mddl_m"] - 0.5
            silt_trip = turb >= TAG_BY_NAME["turbidity_ntu"]["trip"]
            if v["failed"] or (not head_ok and not outburst) or silt_trip:
                if v["units"] and not v["failed"]:
                    events.append({
                        "t": ts.isoformat(timespec="seconds"), "hour": round(hour, 2),
                        "site": s["name"], "kind": "trip",
                        "text": (f"{s['name']}: all {v['units']} units tripped "
                                 + ("on silt " if silt_trip else "on loss of head ")
                                 + f"({turb:,.0f} NTU)"),
                    })
                v["units"] = 0
            # Run-of-river: the units follow the river rather than drawing
            # the pond down. Capped at design, floored at the technical
            # minimum below which the governor cannot hold.
            q_cap = v["units"] * design_q(s)
            q_turb = min(q_cap, max(q_in, 0.3 * q_cap)) if v["units"] else 0.0

            # --- gates and mass balance ------------------------------
            warned = bool(wave) and warning_lead_h > 0 and hour >= warn_at[s["id"]]
            demand = _gate_demand(s, v["level"], warned)
            if demand > v["gate"]:
                # an unwarned operator watches the level for a while first
                if v["demand_since"] is None:
                    v["demand_since"] = hour
                ready = warned or (hour - v["demand_since"]) * 60 >= OPERATOR_DELAY_MIN
            else:
                v["demand_since"] = None
                ready = True
            if ready and not v["blackout"]:
                step = GATE_SLEW * (DT_S / 60.0)
                v["gate"] = min(demand, v["gate"] + step) if demand > v["gate"] \
                    else max(demand, v["gate"] - step)
            q_spill = _spill_q(s, v["level"], v["gate"])
            q_over = _crest_overflow(s, v["level"])
            q_out = q_turb + q_spill + q_over

            area = _pond_area_m2(s)
            v["prev_level"] = v["level"]
            v["level"] += (q_in - q_out) * DT_S / area

            # --- overtopping, and then the dam itself ----------------
            # Station service goes with the powerhouse. Once the yard is
            # under water the hoists stop, and the gates stay wherever they
            # happen to be -- which in 2023 was shut.
            if not v["blackout"] and (v["level"] > s["dam_top_m"] - 0.5 or v["failed"]):
                v["blackout"] = True
                events.append({
                    "t": ts.isoformat(timespec="seconds"), "hour": round(hour, 2),
                    "site": s["name"], "kind": "blackout",
                    "text": f"{s['name']}: station service lost, spillway gates "
                            f"frozen at {v['gate']*100:.0f}%"})

            if v["level"] > s["dam_top_m"] and not v["failed"]:
                v["overtop_min"] += DT_S / 60.0
                if not any(e.get("kind") == "overtop" and e["site"] == s["name"]
                           for e in events):
                    events.append({
                        "t": ts.isoformat(timespec="seconds"), "hour": round(hour, 2),
                        "site": s["name"], "kind": "overtop",
                        "text": f"{s['name']} overtopping: crest {s['dam_top_m']} m, "
                                f"level {v['level']:.1f} m"})
                # A concrete-face rockfill dam does not survive being overtopped.
                if v["overtop_min"] >= 6.0 and s["dam_kind"] in (
                        "concrete-face rockfill", "barrage"):
                    v["failed"] = True
                    events.append({
                        "t": ts.isoformat(timespec="seconds"), "hour": round(hour, 2),
                        "site": s["name"], "kind": "breach",
                        "text": f"{s['name']} breached. Its {s['pond_mcm']} MCM "
                                f"pondage joins the wave; {s['people']:,} people "
                                f"downstream of the dam site."})
            if v["failed"]:
                q_out = q_in + s["pond_mcm"] * 1e6 / 1800.0
                v["level"] = max(v["level"] - 0.9, s["mddl_m"] - 12.0)

            head = max(v["level"] - (s["fsl_m"] - s["head_m"]), 1.0)
            load_frac = (q_turb / max(v["units"] * design_q(s), 1e-6)) if v["units"] else 0.0
            mw = v["units"] * s["unit_mw"] * min(head / s["head_m"], 1.05) if v["units"] else 0.0

            # lagged dam-body response: seepage and pore pressure follow head
            eq_seep = 12.0 + 3.5 * max(v["level"] - s["mddl_m"], 0.0) + 0.004 * turb
            v["seep"] += (eq_seep - v["seep"]) * (DT_S / 1800.0)
            eq_pore = 9.81 * (max(v["level"] - s["mddl_m"], 0.0) + 30)
            v["pore"] += (eq_pore - v["pore"]) * (DT_S / 900.0)

            vib = _vibration(turb, load_frac, v["units"] > 0)
            frame["sites"][s["id"]] = {
                "reservoir_level_m": round(v["level"], 2),
                "inflow_m3s": round(q_in, 1),
                "outflow_m3s": round(q_out, 1),
                "spill_gate_pct": round(v["gate"] * 100, 1),
                "seepage_lps": round(v["seep"], 1),
                "pore_pressure_kpa": round(v["pore"], 1),
                "uplift_kpa": round(v["pore"] * 0.62, 1),
                "crest_movement_mm": round(1.2 + 0.02 * max(v["pore"] - 350, 0), 2),
                "seismic_g": round(0.002 + (0.09 if outburst and 0.9 < hour < 1.1 else 0.0), 3),
                "rainfall_mm_h": round(rain, 1),
                "turbidity_ntu": round(turb),
                "water_temp_c": round(11.5 - 2.5 * (turb > 3000), 1),
                "active_power_mw": round(mw),
                "units_running": v["units"],
                "turbine_speed_rpm": 300 if v["units"] else 0,
                "guide_vane_pct": round(85 * load_frac) if v["units"] else 0,
                "penstock_bar": round(head * 0.0981 / 10 * 10, 2) if v["units"] else 0.0,
                "draft_tube_bar": round(-0.35 - 0.00004 * turb, 3) if v["units"] else 0.0,
                "bearing_temp_c": round(54 + 0.0012 * turb, 1) if v["units"] else 24.0,
                "shaft_vib_um": round(vib, 1),
                "stator_temp_c": round(78 + 14 * load_frac, 1) if v["units"] else 26.0,
                "lube_oil_bar": 2.6 if v["units"] else 0.0,
                "cooling_flow_m3h": 168 if v["units"] else 0,
                "slope_risk": (slope[s["id"]] or {}).get("risk"),
                "failed": v["failed"],
            }
            upstream_release = max(0.0, q_out - q_in) if v["failed"] else 0.0

        frames.append(frame)

    return {"scenario": cfg, "frames": frames, "events": events,
            "sites": SITES, "slope": slope,
            "warning_lead_h": warning_lead_h,
            "arrival_h": {k: round(v, 2) for k, v in arrival_h.items()},
            "wave": ({"volume_mcm": round(wave["volume_m3"] / 1e6, 1),
                      "peak_cumec": round(wave["breach"]["peak_cumec"]),
                      "breach_width_m": wave["breach"]["width_m"],
                      "formation_min": round(wave["breach"]["formation_min"], 1)}
                     if wave else None)}


# ==========================================================================
# alarms, and what to do about them
# ==========================================================================

def site_thresholds(site, tag):
    """Per-site limits where a fleet-wide number would be meaningless.

    Penstock pressure is the obvious case: 8.5 bar is an alarm on a low-head
    barrage and nonsense on Teesta-III, which sits under 790 m of head and
    runs at 77 bar all day. Limits that do not scale with the machine are
    limits an operator learns to ignore.
    """
    if tag["tag"] == "penstock_bar":
        rated = site["head_m"] * 0.0981
        return round(rated * 1.08, 1), round(rated * 1.15, 1)
    return tag["alarm"], tag["trip"]


# Tags that only mean anything while a machine is turning. A stopped unit
# reads zero lube oil pressure and zero cooling flow, and reporting those as
# trips buries the one alarm that matters under nine that do not.
UNIT_TAGS = {"turbine_speed_rpm", "guide_vane_pct", "penstock_bar",
             "draft_tube_bar", "bearing_temp_c", "shaft_vib_um",
             "stator_temp_c", "lube_oil_bar", "cooling_flow_m3h"}


def evaluate(site, values):
    """Every tag that is outside its band right now, worst first."""
    out = []
    running = bool(values.get("units_running"))
    for tag in TAGS:
        name = tag["tag"]
        if name in UNIT_TAGS and not running:
            continue
        if name not in values or values[name] is None:
            continue
        alarm, trip = site_thresholds(site, tag)
        if alarm is None:
            continue
        v = values[name]
        low = tag["direction"] == "low"
        hit = None
        if trip is not None and ((v <= trip) if low else (v >= trip)):
            hit = "TRIP"
        elif (v <= alarm) if low else (v >= alarm):
            hit = "ALARM"
        if hit:
            out.append({"tag": name, "label": tag["label"], "unit": tag["unit"],
                        "system": tag["system"], "by": tag["by"],
                        "value": v, "alarm": alarm, "trip": trip,
                        "level": hit, "direction": tag["direction"]})
    out.sort(key=lambda r: (r["level"] != "TRIP", r["label"]))
    return out


# Ordered most urgent first. Each is (condition, what to do, who).
def advice(site, values, alarms, lake, arrival_h=None, hour=None):
    """The recommendation, from the tags rather than from a mood.

    Deliberately phrased as decision support and nothing more. Nothing here
    moves a gate; it tells a control room what the instruments are saying and
    what the usual answer to that is. Gate operation is the licensee's, under
    their own dam safety protocol, and a system that claims otherwise will
    not get past the first safety review.
    """
    acts = []
    lvl = values.get("reservoir_level_m", 0)
    trips = [a for a in alarms if a["level"] == "TRIP"]

    eta = None
    if arrival_h is not None and hour is not None and arrival_h > hour:
        eta = arrival_h - hour

    if lake.get("breach_probability", 0) >= 0.6 and eta is not None:
        acts.append(("CRITICAL",
                     f"Outburst probability {lake['breach_probability']:.0%} and "
                     f"the wave is {eta*60:.0f} minutes out. Open spillway gates "
                     f"now -- full travel is {GATE_TRAVEL_MIN:.0f} minutes. Clear "
                     f"the powerhouse and the tailrace.",
                     "Control room + dam operator"))
    elif lake.get("breach_probability", 0) >= 0.35:
        acts.append(("WARN",
                     f"Outburst probability {lake['breach_probability']:.0%}. Draw "
                     f"the pond to MDDL to buy storage, and put gate operators "
                     f"on station.", "Dam operator"))

    if values.get("failed"):
        acts.append(("CRITICAL", "Dam breached. Everything downstream is now "
                                 "receiving the pondage on top of the wave.",
                     "State EOC"))
    elif lvl > site["dam_top_m"]:
        acts.append(("CRITICAL", f"Overtopping by {lvl - site['dam_top_m']:.2f} m. "
                                 f"Evacuate the dam crest and the downstream bank.",
                     "State EOC"))
    elif lvl > site["fsl_m"]:
        acts.append(("WARN", f"Level {lvl - site['fsl_m']:.2f} m above FSL with "
                             f"gates at {values.get('spill_gate_pct', 0):.0f}%. "
                             f"Increase release.", "Dam operator"))

    if values.get("turbidity_ntu", 0) >= 6000 and values.get("units_running"):
        acts.append(("WARN", "Silt load past the runner limit. Take units off "
                             "load before the wear is done rather than after.",
                     "Shift charge engineer"))
    if values.get("seepage_lps", 0) >= 45:
        acts.append(("WARN", "Seepage climbing. If it keeps rising while the "
                             "head is steady, that is internal erosion, not "
                             "head.", "Dam safety cell"))
    risk = values.get("slope_risk")
    if risk is not None and risk >= 0.5:
        acts.append(("WARN", f"Trigger model has the nearest monitored slope at "
                             f"{risk:.0%}. The access road can close before the "
                             f"water reaches the yard.", "Site logistics"))
    if trips and not acts:
        acts.append(("WARN", f"{len(trips)} tags past trip limits.", "Control room"))
    if not acts:
        acts.append(("OK", "All tags in band. Routine monitoring.", "Control room"))

    rank = {"CRITICAL": 0, "WARN": 1, "OK": 2}
    acts.sort(key=lambda a: rank[a[0]])
    return [{"level": a, "text": b, "owner": c} for a, b, c in acts]


# ==========================================================================
# what the API hands out
# ==========================================================================

_CACHE = {}


def feed(scenario="oct2023", warning_lead_h=0.0):
    key = (scenario, round(warning_lead_h, 2))
    if key not in _CACHE:
        _CACHE[key] = run(scenario, warning_lead_h)
    return _CACHE[key]


def snapshot(scenario="oct2023", hour=None, warning_lead_h=0.0):
    """One instant of the feed, with alarms and recommendations attached."""
    d = feed(scenario, warning_lead_h)
    frames = d["frames"]
    if hour is None:
        hour = frames[-1]["hour"]
    i = max(0, min(len(frames) - 1,
                   int(round(hour * 3600 / DT_S))))
    fr = frames[i]

    sites = []
    for s in SITES:
        v = fr["sites"][s["id"]]
        al = evaluate(s, v)
        sites.append({
            "site": {k: s[k] for k in ("id", "name", "place", "capacity_mw",
                                       "units", "river_km", "people",
                                       "dam_kind", "fsl_m", "dam_top_m",
                                       "lat", "lon")},
            "values": v,
            "alarms": al,
            "advice": advice(s, v, al, fr["lake"],
                             d["arrival_h"].get(s["id"]), fr["hour"]),
            "headroom_m": round(s["dam_top_m"] - v["reservoir_level_m"], 2),
        })
    return {"scenario": d["scenario"], "warning_lead_h": warning_lead_h,
            "index": i, "count": len(frames), "hour": fr["hour"], "t": fr["t"],
            "lake": fr["lake"], "arrival_h": d["arrival_h"],
            "events_so_far": [e for e in d["events"] if e["hour"] <= fr["hour"]],
            "sites": sites}


def series(scenario="oct2023", warning_lead_h=0.0, tag="reservoir_level_m",
           step=5):
    """One tag, every site, thinned for plotting."""
    d = feed(scenario, warning_lead_h)
    fr = d["frames"][::step]
    return {"tag": tag, "unit": TAG_BY_NAME.get(tag, {}).get("unit", ""),
            "hours": [f["hour"] for f in fr],
            "sites": {s["id"]: [f["sites"][s["id"]].get(tag) for f in fr]
                      for s in SITES},
            "lake": [f["lake"].get(tag) for f in fr]
            if tag in ("breach_probability", "lake_level_m") else None,
            "events": d["events"]}


def outcome(scenario="oct2023", warning_lead_h=0.0):
    """What the day cost, so two of them can be put side by side."""
    d = feed(scenario, warning_lead_h)
    per = {}
    for s in SITES:
        lv = [f["sites"][s["id"]]["reservoir_level_m"] for f in d["frames"]]
        mwh = sum(f["sites"][s["id"]]["active_power_mw"] for f in d["frames"]) / 60.0
        failed = any(f["sites"][s["id"]]["failed"] for f in d["frames"])
        per[s["id"]] = {
            "name": s["name"], "peak_level_m": round(max(lv), 2),
            "crest_m": s["dam_top_m"],
            "headroom_m": round(s["dam_top_m"] - max(lv), 2),
            "overtopped": max(lv) > s["dam_top_m"],
            "breached": failed,
            "mwh": round(mwh),
            "people": s["people"],
        }
    return {"scenario": d["scenario"]["id"], "warning_lead_h": warning_lead_h,
            "sites": per,
            "breached": [v["name"] for v in per.values() if v["breached"]],
            "overtopped": [v["name"] for v in per.values() if v["overtopped"]],
            "people_below_breaches": sum(v["people"] for v in per.values()
                                         if v["breached"]),
            "mwh_total": round(sum(v["mwh"] for v in per.values())),
            "events": d["events"]}


def counterfactual(scenario="oct2023", lead_h=1.5):
    """The same night with and without a warning. This is the whole argument."""
    a = outcome(scenario, 0.0)
    b = outcome(scenario, lead_h)
    return {"without": a, "with": b, "lead_h": lead_h,
            "dams_saved": [n for n in a["breached"] if n not in b["breached"]],
            "mwh_delta": b["mwh_total"] - a["mwh_total"],
            "people_delta": a["people_below_breaches"] - b["people_below_breaches"]}
