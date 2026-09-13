# Running SPIREXA on a Mac

Two stages. **Part 1** gets the dashboard, the model and the whole system
running in about ten minutes, with no Google account needed — the trained
model and a risk snapshot are committed to the repo. **Part 2** adds Google
Earth Engine, which you only need to score *new* locations or dates.

Part 3 is the Arduino sensor node, which is optional.

---

## Part 1 — get it running

### 1. Install Python

macOS ships with a Python that is missing pieces you need, so install your own.

Either download **Python 3.11 or 3.12** from
[python.org/downloads](https://www.python.org/downloads/), or use Homebrew:

```bash
brew install python@3.12
```

Check it:

```bash
python3 --version
```

Anything from 3.11 up is fine. Avoid 3.13 for now — some of the scientific
packages are still catching up.

### 2. Install Git

Usually already present. If `git --version` prompts you to install the
Xcode command line tools, accept — that is all you need.

### 3. Clone the repository

```bash
git clone https://github.com/UtkarshCodecom/spirexa-ner.git
cd spirexa-ner
```

### 4. Create the environment and install dependencies

```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

This pulls in `earthengine-api`, `pandas`, `numpy`, `scikit-learn`, `joblib`
and `pyserial`. It takes a few minutes.

### 5. Run it

```bash
./run.sh
```

That scores the hotspots, rebuilds the dashboard, starts the server and opens
**http://localhost:8000**.

On a fresh clone you will see a warning like *"scoring failed — most likely
Earth Engine isn't authenticated"*. **That is expected and harmless.** The
script falls back to the risk snapshot committed in the repo, and the whole
dashboard — all 311 hotspots, the hindcast, the validation view — works
normally. Part 2 removes the warning.

`Ctrl+C` stops everything.

---

## Part 2 — Google Earth Engine

You need this only for live scoring: refreshing the 311 hotspots against
today's weather, or using the **Check any point** panel for an arbitrary
coordinate and date. Everything else already works without it.

Earth Engine is **free for noncommercial and academic use**, but it does
require a Google Cloud project. There is no credit card step for the
noncommercial path.

### 1. Register a Cloud project for Earth Engine

Go to **[console.cloud.google.com/earth-engine](https://console.cloud.google.com/earth-engine)**
and sign in with any Google account.

Create a new Cloud project (or pick an existing one), then register it for
**noncommercial / academic** use. Access is granted immediately once the
registration form is submitted.

Note the **project ID** — it looks like `ee-yourname` or
`project-1a2b3c4d`. You need it in the next two steps.

### 2. Authenticate this machine

```bash
./venv/bin/earthengine authenticate
```

A browser window opens for Google sign-in. Approve it, and the credentials
are stored under `~/.config/earthengine/`. This is a one-time step per Mac.

### 3. Point the project at *your* Earth Engine project

This is the step people miss. The repo ships with the original author's
project ID hardcoded, and you will get a permissions error until you replace
it with your own.

Open `src/config.py` and change the first line:

```python
GEE_PROJECT = "project-77313e00-dc69-4c84-9cd"    # <- replace with YOUR project ID
```

### 4. Confirm it works

```bash
./venv/bin/python src/predict.py --lat 25.57 --lon 91.88 --explain
```

You should get a risk percentage plus the feature values behind it — slope,
rainfall totals, factor of safety and so on. It takes a few seconds, because
it is querying five satellite datasets live.

Now `./run.sh` will refresh all 311 hotspots against today's conditions
instead of falling back to the committed snapshot. That first scoring pass
takes a few minutes; afterwards it skips re-scoring if a snapshot for today
already exists. Force a fresh pass with `./run.sh --rescore`.

---

## Part 3 — the Arduino sensor node (optional)

Skip this entirely if you just want the software.

### 1. Install the Arduino IDE

Download from [arduino.cc/en/software](https://www.arduino.cc/en/software).

### 2. Install the DHT library

**Tools → Manage Libraries**, search `DHT sensor library`, install the
**Adafruit** one, and click **Install All** when it offers the dependency
(Adafruit Unified Sensor).

### 3. Upload the sketch

Open `hardware/spirexa_uno/spirexa_uno.ino`, set **Tools → Board → Arduino
Uno** and pick the port under **Tools → Port**, then Upload.

Wiring is documented at the top of the sketch: rain to A1, soil to A0, DHT11
to D2, touch to D8, alert LED on D7 and a power LED on D10.

### 4. Calibrate

Open **Tools → Serial Monitor** at **9600** baud and note the `Rain raw:`
and `Soil raw:` numbers when the sensors are dry, then when wet. Put those
into `RAIN_DRY` / `RAIN_WET` / `SOIL_DRY` / `SOIL_WET` near the top of the
sketch and re-upload.

### 5. Close the Serial Monitor, then run

**This matters.** A serial port can only be held by one program at a time.
While the Arduino IDE Serial Monitor is open, the bridge cannot read the
board and the dashboard will show no station.

Close the monitor, then:

```bash
./run.sh
```

It finds the board automatically, starts the bridge, and the station panel
on the dashboard goes live. If no board is connected, no bridge is started
and the dashboard honestly reports "no station connected" — it never
fabricates readings. To rehearse without hardware, ask for it explicitly:

```bash
./run.sh --simulate
```

### 6. A WiFi node instead of USB (experimental)

`hardware/esp32_node/esp32_node.ino` posts readings straight to the server
over WiFi, with no USB cable and no bridge process. It needs the server
listening on the network rather than just localhost:

```bash
./run.sh --lan
```

That prints the URL to paste into the sketch's `SERVER_URL`. Note that
`--lan` exposes the dashboard to everyone on that network for as long as it
runs.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `scoring failed … Earth Engine isn't authenticated` | Expected on a fresh clone. Harmless — it uses the committed snapshot. Do Part 2 to fix. |
| Permission / project errors from Earth Engine | `GEE_PROJECT` in `src/config.py` is still the original author's. Put your own project ID there. |
| Dashboard shows "no station connected" with the board plugged in | The Arduino IDE Serial Monitor is holding the port. Close it; the bridge reconnects within seconds. |
| `HTTP Error 504` in the bridge log | A proxy is set (`HTTP_PROXY`) and is intercepting localhost. The bridge already bypasses proxies; if it persists, check `echo $HTTP_PROXY`. |
| `./run.sh: Permission denied` | `chmod +x run.sh` |
| Port 8000 already in use | Something else is on it. `pkill -f src/serve.py`, or edit `PORT` in `run.sh`. |
| `No module named …` | The venv was skipped. Use `./venv/bin/python`, not a bare `python3`. |

---

## What ships in the repo vs. what you build

| | In the repo | Rebuild locally? |
|---|---|---|
| Trained model, hotspot list, road data, dashboard | committed | No |
| Python packages (`venv/`) | not committed | `pip install -r requirements.txt` |
| Live risk snapshot | a dated one is committed | Refreshed by `./run.sh` once Earth Engine is set up |
| Earth Engine credentials | never committed | One-time `earthengine authenticate` |
| Sensor readings / field reports | not committed | Generated at runtime |
