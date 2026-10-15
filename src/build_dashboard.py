"""Renders the GIS dashboard to data/processed/dashboard.html.

Projects every geometry (state boundaries, roads, event markers) into one
shared SVG coordinate space, then injects it into the template.

    python src/build_dashboard.py
"""

import datetime
import json
import math
import os

import pandas as pd

GEO_DIR = os.environ.get("SLOPEWATCH_GEO_DIR", "data/geo")
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")
OUTPUT = "data/processed/dashboard.html"

# Map frame covering the eight NER states.
LON_MIN, LON_MAX = 87.5, 97.8
LAT_MIN, LAT_MAX = 21.5, 29.8
COS_LAT = math.cos(math.radians((LAT_MIN + LAT_MAX) / 2))
WIDTH = 900
HEIGHT = (LAT_MAX - LAT_MIN) / ((LON_MAX - LON_MIN) * COS_LAT) * WIDTH


def project(lon, lat):
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * WIDTH
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * HEIGHT
    return round(x, 1), round(y, 1)


def rings_to_path(rings):
    parts = []
    for ring in rings:
        pts = [project(lon, lat) for lon, lat in ring]
        parts.append("M " + " L ".join(f"{x},{y}" for x, y in pts) + " Z")
    return " ".join(parts)


def ways_to_path(ways):
    parts = []
    for way in ways:
        pts = [project(lon, lat) for lon, lat in way]
        if all(
            x < -30 or x > WIDTH + 30 or y < -30 or y > HEIGHT + 30 for x, y in pts
        ):
            continue
        parts.append("M " + " L ".join(f"{x},{y}" for x, y in pts))
    return " ".join(parts)


def build_case_studies(hindcast):
    """Picks events that make the strongest validation story."""
    cases = []

    # A demonstration scenario, and labelled as one.
    #
    # This row is SIH2026-001: a point in the Teesta V catchment scored by the
    # live model, not a landslide that happened. It sat in this card narrated
    # as a past success -- "SPIREXA flagged it, NHPC opened the gates, zero
    # fatalities" -- next to nineteen years of real events, with nothing
    # telling a reader which was which. The model's output on it is genuine;
    # the story around it was not, and inventing a save is the one thing a
    # warning system cannot be caught doing. Every real validation case is
    # below it.
    mangan_2026 = hindcast[hindcast["date"] == "2026-09-06"]
    if len(mangan_2026):
        cases.append(
            {
                "title": "SCENARIO · Teesta V catchment, Mangan",
                "subtitle": "A worked example, not a recorded event",
                "note": (
                    "This is the model run forward on a what-if: a week of heavy monsoon "
                    "rain saturating the slopes above the Teesta Stage V reservoir. The "
                    "score below is the real model&rsquo;s real output for that point and "
                    "those conditions, driven by 7-day rainfall accumulation and the "
                    "factor of safety. <b>No landslide occurred here and no alert was ever "
                    "issued.</b> It is included to show what an operator would see the "
                    "morning before, and to make the cascade in /nhpc concrete. Every "
                    "other case on this page is a recorded event."
                ),
                "events": [
                    {
                        "loc": r["location"],
                        "risk": round(float(r["predicted_probability"]), 3),
                        "fatalities": int(r.get("fatalities", 0) or 0),
                    }
                    for _, r in mangan_2026.iterrows()
                ],
            }
        )

    # The deadliest events on record in the inventory.
    if "fatalities" in hindcast.columns:
        deadly = hindcast[hindcast["fatalities"] > 0].nlargest(8, "fatalities")
        if len(deadly):
            cases.append(
                {
                    "title": "Deadliest events on record",
                    "subtitle": "Ranked by lives lost",
                    "note": (
                        "The events where a working early warning would have "
                        "mattered most, and what the model gave them."
                    ),
                    "events": [
                        {
                            "loc": f"{r['location']} ({str(r['date'])[:10]})",
                            "risk": round(float(r["predicted_probability"]), 3),
                            "fatalities": int(r["fatalities"]),
                        }
                        for _, r in deadly.iterrows()
                    ],
                }
            )

    return cases


def main():
    with open(f"{GEO_DIR}/ner_state_rings.json") as f:
        state_rings = json.load(f)
    with open(f"{GEO_DIR}/roads_classified.json") as f:
        roads = json.load(f)

    state_paths = {name: rings_to_path(rings) for name, rings in state_rings.items()}
    roads_major = ways_to_path(roads["major"])
    roads_secondary = ways_to_path(roads["secondary"])

    hindcast = pd.read_csv("data/processed/hindcast_results.csv")
    hist_markers = []
    for _, r in hindcast.iterrows():
        x, y = project(r["lon"], r["lat"])
        hist_markers.append(
            {
                "id": r["id"],
                "x": x,
                "y": y,
                # kept alongside the projected x/y so clicking a marker can
                # populate the coordinate inputs in the sidebar
                "lat": round(float(r["lat"]), 5),
                "lon": round(float(r["lon"]), 5),
                "loc": r["location"],
                "state": r["state"],
                "date": str(r["date"])[:10],
                "risk": round(float(r["predicted_probability"]), 3),
                "trigger": r.get("trigger", ""),
                "fatalities": int(r["fatalities"]) if pd.notna(r.get("fatalities")) else 0,
            }
        )

    # Susceptibility is static, so it is scored offline by
    # scripts/score_hotspots.py and baked in here. Crossing it with today's
    # rainfall risk is what turns a column of probabilities into four piles
    # an officer can work through in order.
    susc_table, susc_card = {}, None
    susc_path = "data/processed/hotspot_susceptibility.json"
    if os.path.exists(susc_path):
        with open(susc_path) as f:
            sd = json.load(f)
        susc_table = {r["id"]: r for r in sd["hotspots"]}
        susc_card = sd.get("model")

    def _action(trigger, with_roads, terrain_only):
        hot = trigger >= 0.5
        prone = terrain_only >= 0.5 or with_roads >= 0.6
        if hot and prone:
            return "ACT"
        if hot:
            return "WATCH"
        return "PREPARE" if prone else "CLEAR"

    live_markers = []
    as_of = datetime.date.today().strftime("%d %b %Y")
    if os.path.exists("data/processed/live_risk.csv"):
        live = pd.read_csv("data/processed/live_risk.csv")
        for _, r in live.iterrows():
            x, y = project(r["lon"], r["lat"])
            m = {
                "id": r["id"],
                "x": x,
                "y": y,
                "lat": round(float(r["lat"]), 5),
                "lon": round(float(r["lon"]), 5),
                "loc": r["location"],
                "state": r["state"],
                "risk": round(float(r["live_risk"]), 3),
            }
            h = susc_table.get(r["id"])
            if h:
                m["susc"] = h["with_roads"]
                m["suscNr"] = h["terrain_only"]
                m["ground"] = h["ground"]
                m["groundLabel"] = h["ground_label"]
                m["distRoad"] = h["dist_road_m"]
                m["slopeDeg"] = h["slope"]
                m["action"] = _action(m["risk"], h["with_roads"], h["terrain_only"])
            live_markers.append(m)
        if len(live):
            as_of = pd.to_datetime(live["as_of_date"].iloc[0]).strftime("%d %b %Y")

    importance = []
    if os.path.exists("data/processed/feature_importance.csv"):
        imp = pd.read_csv("data/processed/feature_importance.csv")
        importance = [
            {"feature": r["feature"], "importance": round(float(r["importance"]), 5)}
            for _, r in imp.head(10).iterrows()
        ]

    model_meta = {"auc": None, "hindcast_rate": None, "name": None}
    if os.path.exists("data/processed/model.pkl"):
        import joblib

        bundle = joblib.load("data/processed/model.pkl")
        model_meta = {
            "auc": round(bundle.get("cv_auc", 0), 3),
            "hindcast_rate": round(bundle.get("hindcast_rate", 0), 3),
            "name": bundle.get("model_name", "model"),
        }

    # Load locale strings for the warning SMS modal.
    locale_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
    locales = {}
    for fname in sorted(os.listdir(locale_dir)):
        if fname.endswith(".json"):
            code = fname[:-5]
            with open(os.path.join(locale_dir, fname), encoding="utf-8") as f:
                locales[code] = json.load(f)

    state_languages = {
        "Assam": ["as", "bn", "hi", "en"],
        "Arunachal Pradesh": ["hi", "en"],
        "Manipur": ["mni", "hi", "en"],
        "Meghalaya": ["kha", "en"],
        "Mizoram": ["lus", "en"],
        "Nagaland": ["nag", "en"],
        "Sikkim": ["ne", "hi", "en"],
        "Tripura": ["bn", "hi", "en"],
    }

    with open(TEMPLATE) as f:
        html = f.read()

    replacements = {
        "__WIDTH__": str(round(WIDTH)),
        "__HEIGHT__": str(round(HEIGHT)),
        "__LON_MIN__": str(LON_MIN),
        "__LON_MAX__": str(LON_MAX),
        "__LAT_MIN__": str(LAT_MIN),
        "__LAT_MAX__": str(LAT_MAX),
        "__STATE_PATHS__": json.dumps(state_paths),
        "__ROADS_MAJOR__": json.dumps(roads_major),
        "__ROADS_SECONDARY__": json.dumps(roads_secondary),
        "__HIST_MARKERS__": json.dumps(hist_markers),
        "__LIVE_MARKERS__": json.dumps(live_markers),
        "__CASE_STUDIES__": json.dumps(build_case_studies(hindcast)),
        "__IMPORTANCE__": json.dumps(importance),
        "__MODEL_META__": json.dumps(model_meta),
        "__SUSC_CARD__": json.dumps(susc_card),
        "__AS_OF__": json.dumps(as_of),
        "__BUILD_ID__": json.dumps(
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        "__LOCALES__": json.dumps(locales, ensure_ascii=False),
        "__STATE_LANGUAGES__": json.dumps(state_languages),
    }
    for key, value in replacements.items():
        html = html.replace(key, value)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        f.write(html)
    print(f"Dashboard -> {OUTPUT}  ({len(html) / 1024:.0f} KB)")
    print(f"  states {len(state_paths)}  hindcast {len(hist_markers)}  live {len(live_markers)}")


if __name__ == "__main__":
    main()
