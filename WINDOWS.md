# Running SPIREXA on Windows

Two separate installs: **Python** (runs the server, the model, the website)
and **Arduino IDE** (only needed if you're plugging in the sensor node).
If you're just showing the dashboard and model, skip straight to Part 1
and ignore Part 2.

---

## Part 1 — the software (server, model, website)

### 1. Install Python

Get Python 3.11 or 3.12 from **[python.org/downloads](https://www.python.org/downloads/)**
— not the Microsoft Store version, it has permission quirks with venvs.

On the first install screen, **tick "Add python.exe to PATH"** before clicking
Install. This is the single most common Windows setup failure — if you skip
it, `python` won't be recognized in a new terminal.

Verify it worked. Open **PowerShell** and run:

```powershell
python --version
```

Should print `Python 3.11.x` or similar. If it says "not recognized", Python
wasn't added to PATH — reinstall and tick that box, or add it manually via
*Edit environment variables for your account*.

### 2. Install Git

Get it from **[git-scm.com](https://git-scm.com/download/win)**. Default
options are fine throughout the installer.

### 3. Clone the repository

```powershell
git clone https://github.com/<your-username>/SPIREXA.git
cd SPIREXA
```

### 4. Create the virtual environment and install dependencies

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

This installs `earthengine-api`, `pandas`, `scikit-learn`, `pyserial`, and
the rest. Takes a few minutes.

### 5. Everything prebuilt already works — try it now

The trained model, the dashboard, and the historical data are committed to
the repo, so you don't need to touch Earth Engine to see the system running:

```powershell
venv\Scripts\python src\serve.py
```

Open **http://localhost:8000** — full dashboard, all 311 hotspots, live and
hindcast and validation views.

### 6. Only if you want *live* predictions for a new coordinate

The **Check any point** panel makes a real Earth Engine query, which needs
your own Google account authenticated on this machine:

```powershell
venv\Scripts\earthengine --project=project-77313e00-dc69-4c84-9cd authenticate
```

This opens a browser for Google sign-in — use the same account the project
was registered under (or your own, if you register it fresh — see the main
[README](README.md) for the Earth Engine sign-up steps). One-time only.

---

## Part 2 — the Arduino sensor node

Only needed if you're bringing the physical hardware demo.

### 1. Install Arduino IDE

**Yes — Arduino IDE is per machine, not something that transfers with the
code.** Download it from **[arduino.cc/en/software](https://www.arduino.cc/en/software)**
(the free "Arduino IDE 2.x" installer). Default options are fine.

### 2. Install the USB driver

Your board most likely uses one of these chips — check the small chip near
the USB port:

| Chip printed on board | Driver needed |
|---|---|
| **FT232R** (what your Mac board uses) | Usually auto-installs on Windows 10/11. If not: [FTDI VCP driver](https://ftdichip.com/drivers/vcp-drivers/) |
| **CH340 / CH341** (common on clones) | [CH340 driver](https://www.wch.cn/downloads/CH341SER_EXE.html) — Windows won't recognize the board at all without this |

Plug the board in, then check **Device Manager → Ports (COM & LPT)**. You
should see something like `USB Serial Port (COM3)`. If it shows up under
*Other devices* with a yellow warning triangle instead, the driver didn't
install — download it manually from the table above.

**Note the COM number** (e.g. `COM3`) — you won't usually need it, since the
bridge auto-detects the board, but it's useful for troubleshooting.

### 3. Install the DHT library

Arduino IDE → **Tools → Manage Libraries** → search `DHT sensor library` →
install the one **by Adafruit** → click **Install All** when it offers the
dependency (Adafruit Unified Sensor).

### 4. Open and upload the sketch

Open this file directly (not the folder) in Arduino IDE:

```
hardware\spirexa_uno\spirexa_uno.ino
```

Then:
- **Tools → Board → Arduino Uno**
- **Tools → Port →** the COM port from step 2
- Click **Upload** (→ arrow)

The three LEDs (or the board's own LED if you haven't wired external ones)
flash green→yellow→red twice on success.

### 5. Calibrate the rain sensor

**Tools → Serial Monitor**, set baud to **9600**. You'll see JSON lines with
a `rain_pct` field. Note the value with the plate dry, then with a few drops
of water on it. Open `spirexa_uno.ino`, set:

```cpp
const int RAIN_DRY = 950;   // your dry reading
const int RAIN_WET = 380;   // your wet reading
```

Re-upload. **Then close Serial Monitor** — only one program can read the
port at a time, and the bridge needs it next.

---

## Part 3 — run everything together

From the project folder, with the board plugged in:

```powershell
run.bat
```

This starts the server, finds the Arduino automatically, starts the bridge,
and opens the dashboard in your browser. `Ctrl+C` in the window, or run
`stop.bat`, to stop everything.

No board handy? `run.bat --simulate` generates believable readings instead —
useful for rehearsing without carrying the breadboard around.

Or run the two pieces separately, in two PowerShell windows:

```powershell
venv\Scripts\python src\serve.py
```

```powershell
venv\Scripts\python hardware\serial_bridge.py
```

---

## Windows-specific troubleshooting

| Symptom | Fix |
|---|---|
| `python` not recognized | Python wasn't added to PATH — reinstall and tick the box, or search *Edit environment variables* |
| Board doesn't appear in Device Manager | Driver missing — see the chip table above |
| Bridge says "no Arduino found" | Close Serial Monitor first — it locks the port so nothing else can read it |
| `HTTP Error 504` from the bridge | Your network has a proxy set (`HTTP_PROXY` env var) that's intercepting even `localhost` traffic. The bridge already works around this automatically — if you still see it, check `echo %HTTP_PROXY%` in PowerShell and let us know |
| `curl` not found in `run.bat` | Windows 10 (1803+) and 11 ship `curl` by default. Older systems: install it or just open http://localhost:8000 manually after a few seconds |
| Firewall popup on first run | Click **Allow** — Python's server needs to listen on `localhost`, it is not reaching the internet |

---

## What's already in the repo vs. what you generate

| | In the repo | Regenerate on this machine? |
|---|---|---|
| Trained model, dashboard, all data | ✅ committed | No — just run `src/serve.py` |
| Python packages (`venv/`) | ❌ not committed | `pip install -r requirements.txt` |
| Node packages for the slide deck (`.docxbuild/node_modules/`) | ❌ not committed | Only if you're regenerating the PPTX: `cd .docxbuild && npm install` |
| Arduino IDE + its libraries | ❌ never in a git repo | Install once per machine, per Part 2 |
