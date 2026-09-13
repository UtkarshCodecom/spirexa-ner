# SPIREXA

AI-based early warning and landslide risk monitoring for the North Eastern
Region — Smart India Hackathon, Problem Statement 26001.

Landslide risk monitoring for the eight North Eastern states of India, built on
satellite data and a model trained on 318 recorded landslides (2007–2025).

Everything here runs on a laptop. Earth Engine does the heavy geospatial work
server-side; only a small table of numbers is trained on locally.

**Setting this up from scratch?** See **[MACOS.md](MACOS.md)** or
**[WINDOWS.md](WINDOWS.md)** for the full setup including Google Earth Engine
registration, the Arduino IDE and the ground sensor node.

The trained model and a risk snapshot are committed, so the dashboard runs
immediately after `pip install` — Earth Engine is only needed to score new
locations or dates.

---

## What is actually built

| Piece | Status |
|---|---|
| Satellite data ingestion (rainfall, soil moisture, terrain, radar, vegetation) | working |
| Road network ingestion (OpenStreetMap) | working |
| Tabular ML model + honest cross-validated hindcast | working |
| GIS dashboard with risk heat markers, roads, pan/zoom | working |
| Live prediction API + CLI for any coordinate/date | working |
| Alert generation with console / file / webhook channels | working |
| Multilingual alerts in 9 NER languages | working — translations need native review |
| Offline field reporting with automatic sync | working |
| Offline map caching (service worker) | working — needs a real browser to verify |
| SMS delivery | **not built** — needs a gateway account; message rendering is done |
| Satellite-imagery CNN | **not built** — the tabular model is the predictor |
| IoT ground sensors | **not built** — design only |

### Why multilingual and offline turned out to be cheap

Neither is the hard problem it looks like.

**Multilingual is a translation table, not a translation engine.** Alert text is
about fifteen templated strings. They are translated once into
`src/locales/*.json` and rendered at send time; nothing is machine-translated at
runtime. Adding a language means adding one JSON file.

**Offline is three separate problems** with three different answers:

| Need | Answer here |
|---|---|
| Villager receives a warning with no data connection | SMS — works on 2G feature phones. Message rendering and segment counting are built; only the gateway account is missing. |
| Field officer reads the risk map with no connection | Service worker caches the app and the last `/api/sync` snapshot (36 KB for all 311 hotspots). |
| Field officer reports a hazard with no connection | The report is written to IndexedDB *before* any upload is attempted, then flushed automatically when the signal returns. |

---

## One-time setup

```bash
cd /Users/utkarsh/Desktop/ml
./venv/bin/earthengine --project=project-77313e00-dc69-4c84-9cd authenticate
```

That opens a browser for Google sign-in. It only needs doing once per machine.

All commands below assume you are in the project root. Either prefix python with
`./venv/bin/` as shown, or activate the environment once per terminal session:

```bash
source venv/bin/activate
```

---

## Running the model from the command line

**Score a single coordinate and date.** This is the core question the system answers.

```bash
./venv/bin/python src/predict.py --lat 23.73 --lon 92.72 --date 2024-05-28
```

**Show why it gave that score** — slope, factor of safety, rainfall, soil moisture:

```bash
./venv/bin/python src/predict.py --lat 23.73 --lon 92.72 --date 2024-05-28 --explain
```

Omit `--date` to score today. Each call takes a few seconds because it queries
Earth Engine live.

**Refresh the risk snapshot for every known hotspot** (~15 min, 311 locations):

```bash
./venv/bin/python src/compute_live_risk.py
```

**Issue alerts** for anything currently above the threshold:

```bash
./venv/bin/python src/alerts.py
./venv/bin/python src/alerts.py --threshold 0.7
./venv/bin/python src/alerts.py --refresh          # recompute risk first
./venv/bin/python src/alerts.py --dry-run          # preview, log nothing
```

Alerts print to the console and append to `data/processed/alert_log.jsonl`.
To also push them to Slack, Teams, or any HTTP endpoint, set a webhook URL:

```bash
export ALERT_WEBHOOK_URL="https://hooks.slack.com/services/..."
./venv/bin/python src/alerts.py
```

Repeat alerts for the same location are suppressed for 12 hours unless the
severity band gets worse.

### Languages

```bash
./venv/bin/python src/alerts.py --list-languages
./venv/bin/python src/alerts.py --dry-run --show-messages          # per-state languages
./venv/bin/python src/alerts.py --dry-run --lang lus,en            # force specific ones
```

Each state's recipients get their own languages automatically
(`i18n.STATE_LANGUAGES`): Mizoram gets Mizo + English, Meghalaya gets Khasi +
English, Manipur gets Meitei + Hindi + English, and so on.

**Every translation except English is currently unverified.** Until a native
speaker signs one off, the system sends it *paired with the English text* rather
than alone, so a recipient always has one string that is known to be correct —
a mistranslated severity word in a disaster warning is worse than English. To
mark a language as checked, set `"_verified": true` in its locale file; the
pairing then stops. The four lowest-confidence drafts are Mizo, Khasi, Nagamese
and Meitei, each flagged with `_translation_confidence` in its file.

Script choice has a real cost: Devanagari and Bengali script are UCS-2 in SMS,
which is 70 characters per segment against Latin's 160. The same alert is 2
segments in English and 8 in Hindi — roughly four times the SMS bill per
recipient. `sms_segments` is reported per message so this is visible before you
commit to a gateway.

### Wiring up real SMS

`src/alerts.py` renders the message and counts segments; it does not send.
Adding a provider is a `_send_sms(alert)` function plus `"sms"` in
`ACTIVE_CHANNELS`. It is left unwired on purpose — it needs billable
credentials, and a send path that can spend money should be added deliberately
rather than inherited.

---

## Offline field use

Open the dashboard on a phone at `http://<your-machine-ip>:8000` while on the
same network, or deploy it. The **Report from the field** panel appears whenever
the API is reachable.

What works with no signal:

- The dashboard and the last risk snapshot load from cache.
- A hazard report — location (GPS or typed), hazard type, note, and a photo —
  is saved to the device immediately.
- The queue shows how many reports are waiting.
- When the signal returns, queued reports upload on their own. The connection
  pill in the header flips between *online* and *offline · using last sync*.

The ordering matters: the report is written to IndexedDB **before** the upload
is attempted, so a submission made as the signal drops is never lost, even if
the app is closed straight afterwards.

```bash
curl http://localhost:8000/api/reports          # everything received
curl http://localhost:8000/api/sync             # the 36 KB offline snapshot
ls data/reports/                                # uploaded photos
```

Service workers only run in a secure context, which means `localhost` or HTTPS —
over plain HTTP from another machine the offline *cache* is skipped, though the
offline *report queue* still works, since IndexedDB has no such restriction.

**Run it on a schedule** — daily at 06:00, via `crontab -e`:

```bash
0 6 * * * cd /Users/utkarsh/Desktop/ml && ./venv/bin/python src/alerts.py --refresh >> data/processed/cron.log 2>&1
```

---

## Running the website on localhost

```bash
./venv/bin/python src/serve.py
```

Then open **http://localhost:8000**.

Use `--port 9000` to change the port.

Served locally, the dashboard gets a **Check any point** panel that runs the model
live on any coordinate you type. The published/static copy cannot do this — it
falls back to instructions — because a static page has no model behind it.

### API endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/health` | server and model status |
| `GET /api/risk` | current risk for all monitored hotspots |
| `GET /api/sync` | compact snapshot for offline caching (~36 KB) |
| `GET /api/alerts?threshold=0.6` | locations currently above threshold, with translated messages |
| `GET /api/predict?lat=&lon=&date=` | live prediction plus the feature values behind it |
| `GET /api/reports` | field reports received |
| `POST /api/reports` | submit a field report (used by the offline queue) |

```bash
curl "http://localhost:8000/api/predict?lat=23.73&lon=92.72&date=2024-05-28"
curl "http://localhost:8000/api/alerts?threshold=0.7"
```

---

## Rebuilding from scratch

Only needed if you change features, add training data, or want fresh numbers.

```bash
./venv/bin/python src/build_dataset.py      # fetch satellite features   (~25 min)
./venv/bin/python src/train_model.py        # train + cross-validate     (~1 min)
./venv/bin/python src/compute_live_risk.py  # today's risk per hotspot   (~15 min)
./venv/bin/python src/build_dashboard.py    # render the dashboard       (instant)
```

`build_dataset.py` and `compute_live_risk.py` make one Earth Engine call per
point, which is what makes them slow. They are safe to re-run.

---

## How the model works

Two established operational systems informed the design:

**NASA LHASA** (Landslide Hazard Assessment for Situational Awareness) treats
landslide risk as a *static susceptibility* layer — slope, terrain, road
networks, vegetation — modulated by *dynamic triggers* — current rainfall,
antecedent rainfall, soil moisture. LHASA v2 feeds these to gradient boosting.

**USGS shallow-landslide modelling** computes an infinite-slope factor of
safety, where rainfall raises pore pressure and drives the factor of safety
below 1.

This project uses both. The feature set splits the same way:

| Static susceptibility | Dynamic trigger | Physics |
|---|---|---|
| elevation, slope, aspect | rain over 1/3/7/15/30 days | factor of safety |
| steepest slope within 300 m | surface + root-zone soil moisture | |
| mean slope, local relief | radar backscatter anomaly | |
| distance to nearest road | | |
| NDVI (vegetation cover) | | |

Two design decisions worth knowing about:

**Terrain is sampled over a 300 m neighbourhood, not just the exact point.**
Reported landslide coordinates usually mark where the debris stopped — a road,
a house, a valley floor — not where the slope failed. A point sample often lands
on flat ground below the actual source area and looks deceptively safe.

**Rainfall comes from GPM IMERG, not CHIRPS.** CHIRPS is more accurate for
historical analysis but its final product lags real time by weeks, which
silently starves the recent-rainfall features on any live query. That made
recent events score far too low until it was switched.

### Data sources

| Input | Source |
|---|---|
| Rainfall | NASA GPM IMERG v07 |
| Soil moisture | NASA SMAP L4 (from Apr 2015) |
| Terrain | SRTM 30 m |
| Vegetation | MODIS NDVI |
| Radar backscatter | Sentinel-1 GRD (from late 2014) |
| Roads | OpenStreetMap |
| Landslide records | NASA Global Landslide Catalog + published GSI-derived inventories |

---

## Known limitations

- **Coordinate precision varies.** Many catalogue entries are accurate only to
  5–50 km. Events with exact coordinates are caught noticeably more often than
  those with vague ones — the model is being scored against the wrong hillside
  in some cases.
- **Soil moisture and radar do not exist before 2015.** Those features are
  median-filled for earlier events, so pre-2015 rows carry less information.
- **311 monitored hotspots are past landslide locations**, not a full grid.
  A slope that has never failed before is not currently watched.
- **Not a warning service.** This is a research prototype. Official warnings for
  the region come from GSI and the state disaster management authorities.

---

## Project layout

```
src/
  config.py              feature list, paths, GEE project id
  gee_features.py        satellite features for one point/date
  local_features.py      distance-to-road, USGS factor of safety
  build_dataset.py       assembles the training table
  train_model.py         trains, cross-validates, reports importance
  compute_live_risk.py   today's risk for every hotspot
  predict.py             CLI for any coordinate/date
  alerts.py              alert generation and dispatch
  i18n.py                multilingual message rendering
  locales/*.json         one file per language
  serve.py               local server + API
  build_dashboard.py     renders the dashboard
  dashboard_template.html

static/
  sw.js                  service worker (offline cache)
  manifest.json          installable-app metadata

data/
  raw/                   landslide inventories
  geo/                   state boundaries, road network
  processed/             training table, model, snapshots, dashboard
  reports/               field reports and uploaded photos
```
