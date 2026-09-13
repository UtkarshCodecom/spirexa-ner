#!/usr/bin/env bash
# Starts everything: scores all 311 hotspots, rebuilds the dashboard, then
# starts the SPIREXA server and the Arduino bridge.
#   ./run.sh              plug in the Arduino first; falls back to simulation
#   ./run.sh --simulate   force simulation, no board needed
#   ./run.sh --rescore    force a fresh model run even if today's snapshot exists
#   ./run.sh --lan        also listen on the network, so a WiFi node can post readings
set -u
cd "$(dirname "$0")"

PY=./venv/bin/python
PORT=8000
SIM=""
RESCORE=""
LAN=""
for arg in "$@"; do
  [ "$arg" = "--simulate" ] && SIM="--simulate"
  [ "$arg" = "--rescore" ] && RESCORE=1
  [ "$arg" = "--lan" ] && LAN=1
done

cleanup() {
  echo ""
  echo "stopping..."
  [ -n "${BRIDGE_PID:-}" ] && kill "$BRIDGE_PID" 2>/dev/null
  [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

echo "clearing anything already running..."
pkill -f "src/serve.py"      2>/dev/null
pkill -f "serial_bridge.py"  2>/dev/null
sleep 1

# --- the model must exist before anything can predict ---
if [ ! -f data/processed/model.pkl ]; then
  echo "ERROR: no trained model at data/processed/model.pkl"
  echo "Run once:  $PY src/train_model.py"
  exit 1
fi

# --- score all hotspots against today's conditions, then rebuild the dashboard ---
# Skipped if a snapshot for today already exists, so re-running this script
# a second time the same day doesn't repeat a multi-minute Earth Engine pass
# for nothing. Force it anyway with --rescore.
TODAY=$(date +%Y-%m-%d)
SNAPSHOT_DATE=$($PY -c "
import pandas as pd
try:
    df = pd.read_csv('data/processed/live_risk.csv')
    print(df['as_of_date'].iloc[0] if len(df) else '')
except Exception:
    print('')
" 2>/dev/null)

if [ -n "$RESCORE" ] || [ "$SNAPSHOT_DATE" != "$TODAY" ]; then
  echo "scoring all 311 hotspots for $TODAY (needs Earth Engine authenticated)..."
  if $PY src/compute_live_risk.py; then
    echo "  scoring done"
  else
    echo "  WARNING: scoring failed - most likely Earth Engine isn't authenticated on this machine."
    echo "  fix:  ./venv/bin/earthengine --project=project-77313e00-dc69-4c84-9cd authenticate"
    echo "  continuing with whatever snapshot is already in data/processed/live_risk.csv"
  fi
else
  echo "today's risk snapshot ($SNAPSHOT_DATE) is already current - skipping re-score"
  echo "  (force a fresh run with:  ./run.sh --rescore)"
fi

echo "rebuilding the dashboard..."
$PY src/build_dashboard.py

# --- server ---
echo "starting SPIREXA server on port $PORT..."
# Default stays localhost-only. --lan opens it to the network so an ESP32
# node can POST readings in; that also exposes it to everyone on that WiFi.
BIND="127.0.0.1"
[ -n "$LAN" ] && BIND="0.0.0.0"
$PY src/serve.py --port "$PORT" --host "$BIND" > logs_server.txt 2>&1 &
SERVER_PID=$!

for i in $(seq 1 25); do
  if curl -s --max-time 2 "http://localhost:$PORT/api/health" > /dev/null 2>&1; then break; fi
  sleep 0.5
done

if ! curl -s --max-time 2 "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
  echo "server did not come up - see logs_server.txt"
  cat logs_server.txt | tail -20
  exit 1
fi
echo "  server ready"

# --- sensor node bridge ---
# Simulation is opt-in ONLY. Falling back to it automatically meant a
# disassembled node still produced a "connected" station on the dashboard,
# which is worse than showing nothing.
BRIDGE_PID=""
if [ -n "$SIM" ]; then
  echo "starting bridge in SIMULATION mode (--simulate given)"
  $PY hardware/serial_bridge.py --simulate > logs_bridge.txt 2>&1 &
  BRIDGE_PID=$!
  sleep 3
elif $PY hardware/serial_bridge.py --list 2>/dev/null | grep -qiE "usbmodem|usbserial|arduino|ch340"; then
  echo "board found - starting bridge"
  $PY hardware/serial_bridge.py > logs_bridge.txt 2>&1 &
  BRIDGE_PID=$!
  sleep 3
else
  echo "no sensor node detected - starting no bridge"
  echo "  the dashboard will correctly show 'no station connected'"
  echo "  to rehearse without hardware:  ./run.sh --simulate"
fi

echo ""
echo "======================================================"
echo "  SPIREXA is running"
echo ""
echo "  Dashboard    http://localhost:$PORT"
if [ -n "$LAN" ]; then
  MYIP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
  [ -n "$MYIP" ] && echo "  Node URL     http://$MYIP:$PORT/api/sensor   (put this in the ESP32 sketch)"
fi
if [ -n "$SIM" ]; then
  echo "  Station      SIMULATED (not real hardware)"
elif [ -n "$BRIDGE_PID" ]; then
  echo "  Station      live node on USB"
else
  echo "  Station      none connected"
fi
echo ""
echo "  logs_server.txt   server"
[ -n "$BRIDGE_PID" ] && echo "  logs_bridge.txt   sensor readings"
echo ""
echo "  Ctrl+C to stop everything"
echo "======================================================"
echo ""

command -v open >/dev/null && open "http://localhost:$PORT"

if [ -n "$BRIDGE_PID" ]; then
  tail -f logs_bridge.txt          # stream readings so you can see the node working
else
  wait "$SERVER_PID"               # no bridge to stream; just hold the server open
fi
