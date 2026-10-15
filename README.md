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

### Pages

| Page | What it is |
|---|---|
| `/` | the GIS dashboard: 311 hotspots, four action piles, impact panel, event graph |
| `/simulator` | the 3D slope in three modes — simulate, live, replay |
| `/nhpc` | the Teesta control feed, normal day or 3–4 October 2023 |
| `/flood` | the three-dam Teesta cascade with per-dam controls |
| `/glof` | the glacial lake inventory and breach simulation |
| `/monitor` | the basin monitor and cascading hazard timeline |
| `/discharge` | the river discharge forecast and its hindcast |

### 3D slope simulator

**http://localhost:8000/simulator** — also linked from the dashboard header.

A hillside, a bench-cut mountain road and a forest, rendered in three.js. Four
sliders (7-day rainfall, soil moisture, slope angle, forest cover) reshape the
terrain and re-score the *same* Random Forest on every drag, through
`/api/score`, which scores raw feature values with no Earth Engine call — 7–11 ms,
and it keeps working with no internet. Push the risk past SEVERE and the slope
fails on its own: the scar opens, debris runs out across the carriageway and a
vehicle gets shoved into the rail.

Alongside the model it shows the textbook infinite-slope **factor of safety**,
which is computed from slope and moisture rather than learned. The two disagree
in interesting places, which is the point: rainfall drives the model, geometry
drives the physics.

three.js is vendored to `static/vendor/` — an exhibition hall is no place to
depend on a CDN.

### Android app

`android/` is a Jetpack Compose client for the same server — pushed alerts in
every district language, the live risk map, and the ground sensor readout,
over the local network. Build and setup instructions are in
[android/README.md](android/README.md).

### API endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/health` | server and model status |
| `GET /api/risk` | current risk for all monitored hotspots |
| `GET /api/sync` | compact snapshot for offline caching (~36 KB) |
| `GET /api/alerts?threshold=0.6` | locations currently above threshold, with translated messages |
| `GET /api/predict?lat=&lon=&date=` | live prediction, the feature values behind it, both susceptibility scores, confidence/freshness, and the verdict that follows |
| `GET /api/susceptibility` | the static ground model for all 311 hotspots (`?ground=road_cut`, `?id=`, `?limit=`) |
| `GET /api/impact?lat=&lon=` | what a slide there cuts: road segments, villages isolated, detour distances |
| `GET /api/eventgraph/findings` | what follows what, counted over 7,498 GSI field records |
| `GET /api/replay?id=` | a recorded failure scored day by day over the month before it |
| `GET /api/scada?scenario=&hour=&lead=` | the NHPC Teesta plant feed, normal day or 3–4 Oct 2023 |
| `GET /api/scada/counterfactual` | the same night with and without a warning |
| `GET /api/scada/tags` | the tag dictionary: which tags are sensors, physics, or machine learning |
| `GET /api/score?rain_7d=&slope=&...` | scores raw feature values directly, no satellite call (drives the 3D simulator) |
| `GET /api/geo` | state outlines and roads, projected and thinned for the Android map |
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

### The NHPC feed, and which parts are machine learning

`/nhpc` is a control-room view of the four Teesta projects — Teesta-III at
Chungthang, Teesta-V at Dikchu, and the two low dams at Rambi and Kalijhora —
with a tag dictionary that follows NHPC's real structure: ARMAC for the
reservoir and dam body, TSI for each turbine-generator, eAabhas for inflow
forecasting, the same units, sampling rates and trip limits. The data is
generated, because the real tags sit behind an MoU with NHPC's R&D wing. What
makes it worth looking at is that it is not invented: it is produced by the
physics already in this repository.

    Sentinel-2 measures the lake footprint
      → Huggel's area–volume relation gives the volume
        → Froehlich's breach equation gives the peak and the formation time
          → Muskingum routing carries the wave down six reaches
            → mass balance turns that inflow into a reservoir level
              → and every other tag follows from the level and the discharge

Two days, toggled. **Normal operations** is a wet day on the tail of the
monsoon: units on load, gates shut, everything in band. **3–4 October 2023**
is the South Lhonak outburst. The routing puts the wave at Chungthang at
+1.9 h against roughly 1.5 h observed, and Teesta-III's 5 MCM pondage against
a 4,876 m³/s inflow is gone in under a quarter of an hour.

Then the switch that matters: **warning, or no warning**. A spillway gate
takes about thirty minutes to travel, and the operator has to decide before
that. With no warning the gates are still shut when the level passes the
crest, station service goes with the powerhouse, and the model breaches
Teesta-III at +2.5 h — close to when it actually went. Give the same night
1.5 hours of notice and the gates are open before the limb arrives:

| | No warning | 1.5 h warning |
|---|---|---|
| Dams breached | Teesta-III, TLD-III, TLD-IV | none |
| Teesta-III peak level | 1,577.0 m (crest 1,576.0) | 1,573.9 m |
| People below a breach | 5,000 | 0 |
| Generation over the window | 6,331 MWh | 12,368 MWh |

At +0.5 h — 83 minutes before the wave reaches Chungthang — the page is
already saying *"outburst probability 73%, the wave is 83 minutes out, open
the spillway gates now, full travel is 30 minutes, clear the powerhouse."*

**Of the 29 tags in the feed, 14 are sensors, 12 are physics, and 3 are
machine learning.** That ratio is deliberate and the page prints it:

| Tag | Model | How it was trained | What it scores |
|---|---|---|---|
| Slope failure risk | Random forest, 17 features | 318 real dated events against 628 non-events | 5-fold CV ROC-AUC **0.933**; 80/20 holdout **0.9251** |
| Inflow forecast (d+1) | Gradient boosting | **synthetic hydrology** — needs real CWC gauge series | NSE 0.418 at d+1, 0.023 at d+4 |
| Breach probability | Weighted index, **not trained** | there are four documented Sikkim outbursts, which is not a training set | no score claimed, and the page says so |

Everything else — reservoir level, inflow, outflow, gate position, seepage,
pore pressure, turbidity, power output, penstock and draft-tube pressure — is
an equation you can read, or a sensor reading. Most of a hydro control room
is not machine learning and should not be: a trip limit off a protection
schedule beats a model you have to trust.

Nothing on the page moves a gate. Gate operation is the licensee's under
their own dam safety protocol, and a system claiming otherwise would not
survive its first safety review.

### What a red zone actually cuts

`/api/impact` answers the question a hazard map leaves hanging. The OSM road
dump is collapsed to a routable graph — 492,257 junctions, 560,385 edges —
and a landslide is a point with a run-out radius. Every edge whose geometry
passes through it is cut; then every village within 45 km has its shortest
path to the nearest service centre computed twice, once with the network
whole and once with those edges removed.

The difference is the finding. On the Anini–Roing road in Dibang Valley, two
cut segments isolate **13 villages** — Anini is the district headquarters,
2,384 people, and its route out was 215 km. Across the first 120 monitored
hotspots, **50 produce a measurable connectivity effect**.

Settlements come from the GeoNames India dump rather than Overpass, which
answered a whole-region query with a steady alternation of 504 and 429.
GeoNames carries population where OSM usually does not, and has almost no
hospitals, so villages are routed to a *service centre* — a hospital where
one is recorded, otherwise a town or a settlement of 5,000 or more. The API
reports which kind it used, because "cut off from a town" and "cut off from a
hospital" are different claims.

### What follows what

The usual causal chain — rainfall, arrow, saturation, arrow, landslide, arrow,
road blocked — is a diagram nobody measured. The GSI inventory makes it
countable: every record carries what triggered the slide, what the slope was
made of, how it failed, how it moved, what it hit, and whether the site had
gone before. `/api/eventgraph` counts the arrows.

Of the 3,166 records that say what was affected, 61% name a road *blocked*
rather than merely damaged. Against that baseline:

- **Rainfall acting on a man-made cut blocks the road 95% of the time** (n=296, 1.56×). Rain alone, or a cut alone, does not do that.
- Rotational and planar failures block at 84–86%; where the ground was already flowing, only 43% — the material had somewhere to go.
- **Sites under settlements reactivate at 12.1% against a 5.5% baseline** (2.2×). Money spent on those slopes gets spent again.

The absolute road rate is inflated by the survey — GSI walks roads, and a
surveyor on a road records the road — and the page says so. The comparisons
share that bias, so their differences hold even where the level does not.

### Replaying a real failure

`/simulator` runs in three modes on one engine. **Simulate** is the visitor's
sliders. **Live** pulls a monitored slope's actual conditions this morning
from IMERG, SMAP and the DEM. **Replay** takes a recorded failure and scores
each of the thirty days before it, using only what would have been known that
morning — so the question stops being "would the model have flagged it" and
becomes "how much notice would there have been".

Daily rainfall is reconstructed from the recorded 1, 3, 7, 15 and 30 day
totals by filling each shell evenly. That reproduces every recorded total but
not the true daily sequence, and where the rain actually fell in one night the
crossing would be later and sharper. The lead time it reports is an upper
bound, and the page says that too.

### How much of the answer to believe

Every risk figure now carries two more: **confidence**, which is how much of
the feature vector was real rather than median-filled, tempered by how
decisive the model was; and **freshness**, the age of the feeds that move the
answer today. A feed that did not arrive scores worse than one that arrived
late — the first version scored a missing SMAP as perfectly fresh, because
there was nothing old to count.

And when a ground node is attached, the two are compared directly. An 11 km
satellite grid cell averages away the convective cell sitting on one
hillside, which is usually the hillside that goes. So when the node reads 88%
soil moisture against SMAP's 31%, the dashboard does not pick a winner — it
says *local anomaly*, shows both numbers, and tells the operator to work from
the higher one until somebody has looked.

### The ground model, and why there are two of them

The rainfall model answers *when*. It has no idea what it is raining on. A
second model, trained separately, answers *where*: 7,498 field-mapped GSI
landslides against 11,996 background points drawn only where GSI actually
surveyed, on 33 static covariates — Copernicus and SRTM terrain, curvature,
ruggedness, landform class, MERIT Hydro drainage, OpenLandMap soils, MODIS
NDVI, CHIRPS climatology, ESA WorldCover, Hansen forest loss, and distance to
the nearest road.

It is evaluated on a **spatially blocked** split, not a random one. Landslides
cluster; a random 80/20 puts a slide and its neighbour 40 m away on opposite
sides of the partition and the test set is half memorised before training
starts. The gap between the two numbers is the size of that illusion:

| Split | With road features | Terrain only |
|---|---|---|
| random 80/20 | 0.9512 | 0.8853 |
| **spatially blocked** | **0.9369** | **0.8622** |
| background matched on road distance | 0.8975 | — |
| background matched on slope | — | 0.8454 |

Those numbers include two external inventories (Zenodo eastern Himalaya and
Sikkim multitemporal, both CC-BY) added after the first run: 243 further real
positives, 108 of them in **Arunachal Pradesh**, which GSI has never
inventoried. Adding them moved the headline slightly *down* — 0.9467 to
0.9369 — and both bias-controlled tests *up*, slope-matched 0.8265 to 0.8454
and road-matched 0.8882 to 0.8975. That is the right direction: the test set
now contains terrain the model has not seen much of, and the model got better
at the part that is not survey artifact.

Those inventories also settle the road argument empirically. They were mapped
from satellite imagery rather than walked to, and their slides sit a median
**1,796 m** from the nearest road against GSI's **21 m**. Same hazard, same
mountains, and a completely different distance distribution — which is the
survey bias measured rather than argued about.

Both spatially blocked models ship. The stronger one draws 46% of its
importance from distance to a road. Some of that is real — cutting a bench
into a hillside removes the toe support holding it up, and hundreds of GSI
records name road cutting as the trigger — and some of it is that GSI
surveyors walk roads and cannot map what they cannot reach. Arunachal Pradesh
has no inventory at all and is excluded from training for that reason.

So the road-free model drives every decision, and the *disagreement* between
the two is reported rather than hidden. It turns out to be the most useful
output of the pair:

| The two models | What it means | Who fixes it |
|---|---|---|
| both high | the hillside itself is unstable | drainage, toe support, vegetation |
| roads high, terrain low | the road cut is the hazard, not the slope | retaining wall, benching, cut drainage |
| terrain high, roads low | steep ground nobody has walked | survey it — this is the unmapped case |

Crossed with today's rainfall score, that becomes four piles instead of 311
probabilities:

```
                 ground prone        ground stable
rain triggering  ACT                 WATCH
rain low         PREPARE             CLEAR
```

On a recent morning the rainfall model put 84 of 311 hotspots above 50%.
Crossing them with the ground left **73 ACT** and 11 WATCH — eleven places
where heavy rain was falling on terrain with no signature of failing. The
dashboard shows the four piles and filters the map by them; `/api/risk`
carries `action` on every row; the Android app sorts by it and the offline
sync payload carries it in two extra characters per point.

```bash
./venv/bin/python scripts/build_susceptibility_points.py     # positives + background
./venv/bin/python scripts/distance_to_road.py                # KD-tree over 12.4M road vertices
./venv/bin/python scripts/extract_susceptibility_features.py # pass 1  (~2 h)
./venv/bin/python scripts/extract_susceptibility_features2.py# pass 2  (~2 h)
./venv/bin/python scripts/merge_external_inventories.py      # the two Zenodo inventories
./venv/bin/python scripts/extract_external_features.py       # and their features
./venv/bin/python scripts/extract_external_features2.py
./venv/bin/python scripts/train_susceptibility.py            # both variants  (~1 min)
./venv/bin/python scripts/score_hotspots.py                  # score the 311 hotspots (~4 min)
./venv/bin/python src/build_dashboard.py                     # bake them into the dashboard
```

The impact graph and its assets are built once and reused:

```bash
./venv/bin/python scripts/build_road_graph.py       # 12.4M vertices -> 492k junctions (~4 min)
./venv/bin/python scripts/build_infrastructure.py   # GeoNames settlements (~1 min)
./venv/bin/python scripts/fetch_infrastructure.py   # optional: OSM hospitals, rate-limited
```

Only the last two need re-running when the hotspot list changes; the model
itself is static and does not move when it rains.

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
  A slope that has never failed before is not currently watched. The ground
  model would score a full raster, but scoring one has not been run yet: what
  ships is the 311 points, and the gap between "everywhere" and "everywhere we
  already know about" is real.
- **The ground model inherits GSI's survey pattern.** Mapped slides sit a
  median 21 m from a road against 1,171 m for background points. The road-free
  variant is the answer to that and is what drives every decision here, but it
  cannot conjure evidence from districts nobody surveyed — Arunachal Pradesh
  is not in the training set at all.
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
  susceptibility.py      the ground model: both variants, and the verdict
  impact.py              what a red zone cuts: roads, villages, detours
  eventgraph.py          what follows what, counted over the GSI records
  replay.py              a recorded failure scored day by day
  scada.py               the NHPC Teesta plant feed and its two days
  trust.py               confidence, freshness, and satellite-vs-ground
  alerts.py              alert generation and dispatch
  i18n.py                multilingual message rendering
  locales/*.json         one file per language
  serve.py               local server + API
  build_dashboard.py     renders the dashboard
  dashboard_template.html

static/
  nhpc.html              the Teesta control feed and its two days
  simulator.html         3D slope: simulate / live / replay
  flood.html glof.html monitor.html discharge.html
  sw.js                  service worker (offline cache)
  manifest.json          installable-app metadata

scripts/
  build_susceptibility_points.py   GSI slides + matched background
  distance_to_road.py              KD-tree over the OSM road network
  extract_susceptibility_features*.py  the two Earth Engine passes
  train_susceptibility.py          trains and honestly evaluates both variants
  score_hotspots.py                scores the 311 monitored slopes, once
  build_road_graph.py              OSM dump -> routable junction graph
  build_infrastructure.py          GeoNames settlements, hospitals, dams

data/
  raw/                   landslide inventories
  geo/                   state boundaries, road network
  processed/             training table, model, snapshots, dashboard
  reports/               field reports and uploaded photos
```
