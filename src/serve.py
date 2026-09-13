"""Local web server: serves the dashboard and a live prediction API.

Standard library only, so it runs without installing a web framework.

    python src/serve.py            # http://localhost:8000
    python src/serve.py --port 9000

Endpoints
---------
GET /                                  the dashboard
GET /api/health                        server + model status
GET /api/risk                          current risk snapshot for all hotspots
GET /api/alerts?threshold=0.6          locations currently above threshold
GET /api/predict?lat=&lon=&date=       on-demand prediction for any point

/api/predict runs a live Earth Engine query, so it takes a few seconds and
needs `earthengine authenticate` to have been run.
"""

import argparse
import base64
import datetime
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DASHBOARD_PATH = "data/processed/dashboard.html"
LIVE_RISK_CSV = "data/processed/live_risk.csv"
STATIC_DIR = "static"
REPORTS_DIR = "data/reports"
REPORTS_INDEX = "data/reports/reports.jsonl"
SENSOR_INDEX = "data/reports/sensors.jsonl"
STATION_FRESH_SECONDS = 30   # a node is "connected" if heard from this recently
_predict_cache = {}          # (lat, lon, date) -> result, so the panel stays responsive
_feature_cache = {}          # (lat, lon, date) -> raw feature dict, for simulate/whatchanged
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    # Service worker registration refuses HTTP/1.0 responses, and BaseHTTP
    # defaults to 1.0. Every response below sends an accurate Content-Length,
    # which is what 1.1 keep-alive requires.
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def _json(self, payload, status=200):
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, path):
        if not os.path.exists(path):
            self._json(
                {
                    "error": "dashboard not built",
                    "fix": "run: python src/build_dashboard.py",
                },
                status=404,
            )
            return
        with open(path, "rb") as f:
            body = f.read()
        # The dashboard file is a fragment (no <html> wrapper) because it is
        # also published as an Artifact; wrap it for standalone browsing.
        page = b"<!doctype html><html><head></head><body>" + body + b"</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def _static(self, route):
        rel = route[len("/static/") :]
        path = os.path.normpath(os.path.join(STATIC_DIR, rel))
        if not path.startswith(STATIC_DIR) or not os.path.exists(path):
            self._json({"error": "not found"}, status=404)
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # The worker must be served from the root scope to control "/".
        if path.endswith("sw.js"):
            self.send_header("Service-Worker-Allowed", "/")
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        params = parse_qs(parsed.query)

        try:
            if route in ("/", "/index.html"):
                self._html(DASHBOARD_PATH)
            elif route == "/sw.js":
                # Served from root so its scope covers the whole app.
                self._static("/static/sw.js")
            elif route.startswith("/static/"):
                self._static(route)
            elif route == "/api/health":
                self._json(
                    {
                        "status": "ok",
                        "model_present": os.path.exists("data/processed/model.pkl"),
                        "snapshot_present": os.path.exists(LIVE_RISK_CSV),
                        "dashboard_present": os.path.exists(DASHBOARD_PATH),
                    }
                )
            elif route == "/api/risk":
                self._json(self._risk_snapshot())
            elif route == "/api/sync":
                self._json(self._sync_payload())
            elif route == "/api/alerts":
                threshold = float(params.get("threshold", ["0.6"])[0])
                self._json(self._alerts(threshold))
            elif route == "/api/predict":
                self._json(self._predict(params))
            elif route == "/api/reports":
                self._json(self._list_reports())
            elif route == "/api/sensor":
                self._json(self._list_sensors())
            elif route == "/api/live":
                self._json(self._live(params))
            elif route == "/api/simulate":
                self._json(self._simulate(params))
            elif route == "/api/whatchanged":
                self._json(self._whatchanged(params))
            elif route == "/api/decision":
                self._json(self._decision(params))
            else:
                self._json({"error": "not found", "path": route}, status=404)
        except Exception as exc:  # surface the real problem to the caller
            traceback.print_exc()
            self._json({"error": str(exc)}, status=500)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/reports":
                self._json(self._receive_report())
            elif parsed.path == "/api/sensor":
                self._json(self._receive_sensor())
            else:
                self._json({"error": "not found", "path": parsed.path}, status=404)
        except Exception as exc:
            traceback.print_exc()
            self._json({"error": str(exc)}, status=500)

    # ---- handlers -------------------------------------------------------

    def _risk_snapshot(self):
        import pandas as pd

        if not os.path.exists(LIVE_RISK_CSV):
            return {"error": "no snapshot", "fix": "python src/compute_live_risk.py"}
        df = pd.read_csv(LIVE_RISK_CSV)
        return {
            "count": len(df),
            "as_of": str(df["as_of_date"].iloc[0]) if len(df) else None,
            "locations": df.to_dict(orient="records"),
        }

    def _alerts(self, threshold):
        import pandas as pd

        import alerts as alerts_mod

        if not os.path.exists(LIVE_RISK_CSV):
            return {"error": "no snapshot", "fix": "python src/compute_live_risk.py"}
        df = pd.read_csv(LIVE_RISK_CSV)
        issued = alerts_mod.build_alerts(df, threshold)
        return {"threshold": threshold, "count": len(issued), "alerts": issued}

    def _sync_payload(self):
        """Compact snapshot for offline caching on a field device.

        Trimmed deliberately: this is what has to cross a weak 2G link and
        then sit in browser storage, so it carries only what the offline map
        needs to render.
        """
        import pandas as pd

        if not os.path.exists(LIVE_RISK_CSV):
            return {"error": "no snapshot"}
        df = pd.read_csv(LIVE_RISK_CSV)
        return {
            "version": int(os.path.getmtime(LIVE_RISK_CSV)),
            "as_of": str(df["as_of_date"].iloc[0]) if len(df) else None,
            "count": len(df),
            "points": [
                {
                    "i": str(r["id"]),
                    # A few catalogue rows have no location text at all, which
                    # pandas reads as NaN rather than a string.
                    "n": ("" if pd.isna(r["location"]) else str(r["location"]))[:60],
                    "s": "" if pd.isna(r["state"]) else str(r["state"]),
                    "y": round(float(r["lat"]), 4),
                    "x": round(float(r["lon"]), 4),
                    "r": round(float(r["live_risk"]), 3),
                }
                for _, r in df.iterrows()
            ],
        }

    def _receive_report(self):
        """Accepts one field report, including any queued while offline."""
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_UPLOAD_BYTES:
            return {"error": f"body must be 1..{MAX_UPLOAD_BYTES} bytes"}
        payload = json.loads(self.rfile.read(length))

        os.makedirs(REPORTS_DIR, exist_ok=True)
        report_id = payload.get("client_id") or uuid.uuid4().hex[:12]

        photo_name = None
        photo = payload.get("photo")
        if photo and "," in photo:
            header, b64 = photo.split(",", 1)
            ext = ".jpg" if "jpeg" in header else ".png" if "png" in header else ".bin"
            photo_name = f"{report_id}{ext}"
            with open(os.path.join(REPORTS_DIR, photo_name), "wb") as f:
                f.write(base64.b64decode(b64))

        record = {
            "id": report_id,
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "hazard": payload.get("hazard"),
            "note": (payload.get("note") or "")[:1000],
            "reporter": (payload.get("reporter") or "")[:120],
            "observed_at": payload.get("observed_at"),
            "queued_offline": bool(payload.get("queued_offline")),
            "received_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "photo": photo_name,
        }
        with open(REPORTS_INDEX, "a") as f:
            f.write(json.dumps(record) + "\n")

        print(
            f"  field report {report_id} "
            f"({record['hazard']}) at {record['lat']},{record['lon']}"
            f"{' [was queued offline]' if record['queued_offline'] else ''}"
        )
        return {"ok": True, "id": report_id, "received_at": record["received_at"]}

    def _receive_sensor(self):
        """Accepts one reading from a SPIREXA field node.

        The node reports what it measures on the ground; it does not run the
        model. A ground soil-moisture reading is worth keeping because the
        satellite equivalent is an 11 km average, and a tilt reading has no
        satellite equivalent at all.
        """
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 8192:
            return {"error": "empty or oversized body"}
        reading = json.loads(self.rfile.read(length).decode())

        reading["received_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(SENSOR_INDEX, "a") as f:
            f.write(json.dumps(reading) + "\n")

        print(f"  sensor {reading.get('node_id')}: soil "
              f"{reading.get('soil_moisture_pct')}% tilt "
              f"{reading.get('tilt_deg')} deg -> field risk "
              f"{reading.get('field_risk')}%")
        return {"status": "stored", "node_id": reading.get("node_id")}

    def _list_sensors(self):
        if not os.path.exists(SENSOR_INDEX):
            return {"count": 0, "readings": []}
        with open(SENSOR_INDEX) as f:
            rows = [json.loads(x) for x in f if x.strip()]
        latest = {}
        for r in rows:
            latest[r.get("node_id")] = r
        return {"count": len(rows), "nodes": list(latest.values()), "readings": rows[-50:]}

    def _live(self, params):
        """Everything the live panel needs in one call.

        Combines the attached ground station with a model prediction for
        wherever the browser says it is. The station measures the air and
        the ground movement; the satellite side supplies rainfall history,
        soil moisture and terrain. Neither alone answers the question.
        """
        import datetime as _dt

        station = {"connected": False}
        if os.path.exists(SENSOR_INDEX):
            with open(SENSOR_INDEX) as f:
                rows = [json.loads(x) for x in f if x.strip()]
            if rows:
                last = rows[-1]
                seen = _dt.datetime.fromisoformat(last["received_at"])
                age = (_dt.datetime.now() - seen).total_seconds()
                station = {
                    "connected": age <= STATION_FRESH_SECONDS,
                    "age_seconds": round(age, 1),
                    "node_id": last.get("node_id"),
                    "simulated": bool(last.get("simulated")),
                    "readings": {
                        k: last.get(k) for k in
                        ("rain_pct", "temperature_c", "humidity_pct",
                         "soil_moisture_pct", "wetness_pct")
                        if last.get(k) is not None
                    },
                }

        out = {"station": station}

        if "lat" in params and "lon" in params:
            lat = round(float(params["lat"][0]), 4)
            lon = round(float(params["lon"][0]), 4)
            date = params.get("date", [_dt.date.today().isoformat()])[0]
            key = (lat, lon, date)

            if key in _predict_cache:
                out["model"] = dict(_predict_cache[key], cached=True)
            else:
                import predict as predict_mod

                risk, feats = predict_mod.predict(lat, lon, date, with_features=True)
                result = {
                    "lat": lat, "lon": lon, "date": date,
                    "risk_percent": round(risk * 100, 1),
                    "severity": _band(risk),
                    "features": feats,
                }
                _predict_cache[key] = result
                out["model"] = dict(result, cached=False)

        return out

    def _list_reports(self):
        if not os.path.exists(REPORTS_INDEX):
            return {"count": 0, "reports": []}
        reports = []
        with open(REPORTS_INDEX) as f:
            for line in f:
                line = line.strip()
                if line:
                    reports.append(json.loads(line))
        reports.reverse()
        return {"count": len(reports), "reports": reports[:200]}

    def _features_for(self, lat, lon, date):
        """Feature vector for a point/date, cached - each miss is a live
        Earth Engine query and costs several seconds."""
        key = (round(lat, 4), round(lon, 4), date)
        if key not in _feature_cache:
            import predict as predict_mod

            _, feats = predict_mod.predict(lat, lon, date, with_features=True)
            _feature_cache[key] = feats
        return dict(_feature_cache[key])

    def _simulate(self, params):
        """Counterfactual: score the same place under altered conditions.

        With no overrides supplied this returns the baseline plus the slider
        definitions, which is what the panel uses to build itself.
        """
        import datetime

        import scenarios

        if "lat" not in params or "lon" not in params:
            return {"error": "lat and lon are required"}
        lat = float(params["lat"][0])
        lon = float(params["lon"][0])
        date = params.get("date", [datetime.date.today().isoformat()])[0]

        feats = self._features_for(lat, lon, date)

        overrides = {}
        for slider in scenarios.SIMULATABLE:
            k = slider["key"]
            if k in params:
                try:
                    overrides[k] = float(params[k][0])
                except (TypeError, ValueError):
                    return {"error": f"{k} must be a number"}

        result = scenarios.simulate(feats, overrides)
        result["lat"], result["lon"], result["date"] = lat, lon, date
        result["sliders"] = [
            dict(s, label=scenarios.LABELS.get(s["key"], (s["key"], ""))[0],
                 unit=scenarios.LABELS.get(s["key"], ("", ""))[1],
                 current=(round(float(feats[s["key"]]), 3)
                          if feats.get(s["key"]) is not None else None))
            for s in scenarios.SIMULATABLE
        ]
        result["decision"] = scenarios.decision_for(result["simulated"]["risk"])
        return result

    def _whatchanged(self, params):
        """Why risk moved between two dates, attributed by ablation."""
        import datetime

        import scenarios

        if "lat" not in params or "lon" not in params:
            return {"error": "lat and lon are required"}
        lat = float(params["lat"][0])
        lon = float(params["lon"][0])
        date = params.get("date", [datetime.date.today().isoformat()])[0]
        try:
            days = max(1, min(30, int(params.get("days", ["1"])[0])))
        except (TypeError, ValueError):
            return {"error": "days must be a whole number"}

        earlier = scenarios.days_ago(date, days)
        feats_now = self._features_for(lat, lon, date)
        feats_then = self._features_for(lat, lon, earlier)

        result = scenarios.attribute(feats_then, feats_now)
        result.update({"lat": lat, "lon": lon, "date": date,
                       "compared_with": earlier, "days": days})
        return result

    def _decision(self, params):
        import scenarios

        if "risk" in params:
            risk = float(params["risk"][0])
        elif "risk_percent" in params:
            risk = float(params["risk_percent"][0]) / 100.0
        else:
            return {"error": "risk or risk_percent is required"}
        return scenarios.decision_for(max(0.0, min(1.0, risk)))

    def _predict(self, params):
        import datetime

        if "lat" not in params or "lon" not in params:
            return {"error": "lat and lon are required"}
        lat = float(params["lat"][0])
        lon = float(params["lon"][0])
        date = params.get("date", [datetime.date.today().isoformat()])[0]

        import predict as predict_mod

        risk, feats = predict_mod.predict(lat, lon, date, with_features=True)
        return {
            "lat": lat,
            "lon": lon,
            "date": date,
            "risk": round(risk, 4),
            "risk_percent": round(risk * 100, 1),
            "severity": _band(risk),
            "features": feats,
        }


def _band(risk):
    if risk >= 0.75:
        return "SEVERE"
    if risk >= 0.5:
        return "HIGH"
    if risk >= 0.25:
        return "MODERATE"
    return "LOW"


REFRESH_INTERVAL_HOURS = 20


def _daily_refresh_loop():
    """Background thread: rebuild the dashboard once per day."""
    while True:
        time.sleep(3600)  # check every hour
        try:
            live_csv = LIVE_RISK_CSV
            if os.path.exists(live_csv):
                age_hours = (time.time() - os.path.getmtime(live_csv)) / 3600
            else:
                age_hours = float("inf")

            if age_hours >= REFRESH_INTERVAL_HOURS:
                print(f"[refresh] live_risk.csv is {age_hours:.1f}h old — rebuilding…")
                base = os.path.dirname(os.path.abspath(__file__))
                python = sys.executable
                for script in ("compute_live_risk.py", "build_dashboard.py"):
                    result = subprocess.run(
                        [python, os.path.join(base, script)],
                        capture_output=True, text=True
                    )
                    if result.returncode != 0:
                        print(f"[refresh] {script} failed:\n{result.stderr}")
                        break
                    else:
                        print(f"[refresh] {script} done")
        except Exception as exc:
            print(f"[refresh] error: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    t = threading.Thread(target=_daily_refresh_loop, daemon=True)
    t.start()
    print("  auto-refresh every 20 h (background thread)")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"NER Slope Watch running at http://{args.host}:{args.port}")
    print("  dashboard   /")
    print("  health      /api/health")
    print("  snapshot    /api/risk")
    print("  alerts      /api/alerts?threshold=0.6")
    print("  prediction  /api/predict?lat=23.73&lon=92.72&date=2024-05-28")
    print("  sensors     /api/sensor   (GET readings, POST from a node)")
    print("  live panel  /api/live?lat=&lon=")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
