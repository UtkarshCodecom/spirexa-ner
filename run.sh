#!/usr/bin/env bash
# Starts everything: the SPIREXA server, the Arduino bridge, and the dashboard.
#   ./run.sh              plug in the Arduino first; falls back to simulation
#   ./run.sh --simulate   force simulation, no board needed
set -u
cd "$(dirname "$0")"

PY=./venv/bin/python
PORT=8000
SIM=""
[ "${1:-}" = "--simulate" ] && SIM="--simulate"

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

# --- server ---
echo "starting SPIREXA server on port $PORT..."
$PY src/serve.py --port "$PORT" > logs_server.txt 2>&1 &
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

# --- Arduino bridge ---
if [ -z "$SIM" ]; then
  if $PY hardware/serial_bridge.py --list 2>/dev/null | grep -qiE "usbmodem|usbserial|arduino|ch340"; then
    echo "Arduino found - starting bridge"
  else
    echo "no Arduino detected - running in simulation instead"
    SIM="--simulate"
  fi
fi

$PY hardware/serial_bridge.py $SIM > logs_bridge.txt 2>&1 &
BRIDGE_PID=$!
sleep 3

echo ""
echo "======================================================"
echo "  SPIREXA is running"
echo ""
echo "  Dashboard    http://localhost:$PORT"
[ -n "$SIM" ] && echo "  Station      SIMULATED (no board attached)" \
             || echo "  Station      live Arduino"
echo ""
echo "  logs_server.txt   server"
echo "  logs_bridge.txt   sensor readings"
echo ""
echo "  Ctrl+C to stop everything"
echo "======================================================"
echo ""

command -v open >/dev/null && open "http://localhost:$PORT"

# stream the sensor readings so you can see the board working
tail -f logs_bridge.txt
