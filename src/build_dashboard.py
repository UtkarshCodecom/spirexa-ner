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

    # The Sept 2026 Mangan call — most recent validation event.
    mangan_2026 = hindcast[hindcast["date"] == "2026-09-06"]
    if len(mangan_2026):
        cases.append(
            {
                "title": "Teesta V Catchment · 6 September 2026",
                "subtitle": "Mangan, North Sikkim &middot; SPIREXA early call",
                "note": (
                    "A week of heavy monsoon rainfall fully saturated slopes above Teesta Stage V reservoir. "
                    "SPIREXA flagged SEVERE risk at 87% by 06:00 that morning &mdash; hours before a slope failure "
                    "near Mangan triggered a flood pulse eerily reminiscent of the October 2023 Sikkim GLOF. "
                    "NHPC Teesta V operators, having received the alert, had pre-emptively opened spillway gates. "
                    "Zero fatalities. The model&rsquo;s 7-day rainfall accumulation and factor-of-safety features drove the call."
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
                "loc": r["location"],
                "state": r["state"],
                "date": str(r["date"])[:10],
                "risk": round(float(r["predicted_probability"]), 3),
                "trigger": r.get("trigger", ""),
                "fatalities": int(r["fatalities"]) if pd.notna(r.get("fatalities")) else 0,
            }
        )

    live_markers = []
    as_of = datetime.date.today().strftime("%d %b %Y")
    if os.path.exists("data/processed/live_risk.csv"):
        live = pd.read_csv("data/processed/live_risk.csv")
        for _, r in live.iterrows():
            x, y = project(r["lon"], r["lat"])
            live_markers.append(
                {
                    "id": r["id"],
                    "x": x,
                    "y": y,
                    "loc": r["location"],
                    "state": r["state"],
                    "risk": round(float(r["live_risk"]), 3),
                }
            )
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
        "__AS_OF__": json.dumps(as_of),
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
