"""Bridges an Arduino UNO field node into SPIREXA.

The UNO has no network, so it prints one JSON object per line over USB.
This finds the board, reads those lines, and posts them to the server.

    python hardware/serial_bridge.py            # auto-detect
    python hardware/serial_bridge.py --list
    python hardware/serial_bridge.py --simulate # no hardware needed
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request

DEFAULT_SERVER = "http://localhost:8000/api/sensor"

# This machine may sit behind an HTTP proxy (HTTP_PROXY is set on many
# campus and office networks). urllib would otherwise send even localhost
# traffic to that proxy, which answers 504 because it cannot reach your
# own laptop. Build an opener that never uses a proxy.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# USB vendor IDs that ship on UNO boards and the common clones.
ARDUINO_VIDS = {0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4}
NAME_HINTS = ("arduino", "usbmodem", "usbserial", "ch340", "wch", "cp210")


def band(risk):
    return ("SEVERE" if risk >= 75 else "HIGH" if risk >= 60
            else "MODERATE" if risk >= 25 else "LOW")


def find_board():
    """Returns the port a board appears to be on, or None."""
    from serial.tools import list_ports

    for p in list_ports.comports():
        blob = f"{p.device} {p.description} {p.manufacturer or ''}".lower()
        if p.vid in ARDUINO_VIDS or any(h in blob for h in NAME_HINTS):
            if "bluetooth" in blob or "debug-console" in blob:
                continue
            return p
    return None


def list_ports_cmd():
    from serial.tools import list_ports

    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found. Is the board plugged in?")
        return
    for p in ports:
        vid = f"{p.vid:#06x}" if p.vid else "-"
        print(f"  {p.device:32} vid={vid:8} {p.description}")


def post(server, reading):
    body = json.dumps(reading).encode()
    req = urllib.request.Request(
        server, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with _opener.open(req, timeout=5) as r:
            return r.status
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"    server unreachable ({exc}) - is src/serve.py running?")
        return None


def _num(value, spec, suffix=""):
    """Formats a reading, or '--' when the node sent null for it.

    A DHT that misses a read sends JSON null, which arrives as None. Passing
    that to a format spec raises, and an unhandled raise here would take the
    whole bridge down mid-demo over one dropped temperature reading.
    """
    if value is None:
        return f"{'--':>{len(format(0, spec))}}{suffix}"
    try:
        return f"{value:{spec}}{suffix}"
    except (TypeError, ValueError):
        return f"{value}{suffix}"


def show(reading):
    parts = [
        "rain " + _num(reading.get("rain_pct"), "5.1f", "%"),
        _num(reading.get("temperature_c"), "5.1f", "C"),
        "hum " + _num(reading.get("humidity_pct"), "4.0f", "%"),
    ]

    soil = reading.get("soil_moisture_pct")
    if soil is not None and soil >= 0:
        parts.append("soil " + _num(soil, "5.1f", "%"))

    if reading.get("touch"):
        parts.append("TOUCH")

    wet = reading.get("wetness_pct")
    print("  " + "   ".join(parts)
          + "   -> site wetness " + _num(wet, "3d", "%"))


def simulate(server):
    """Emits believable readings so the whole chain can be demonstrated
    or rehearsed without the board attached."""
    print("SIMULATION MODE - no hardware, generating readings\nCtrl+C to stop.\n")
    rain = 5.0
    while True:
        rain = min(95.0, max(0.0, rain + random.uniform(-4, 7)))
        hum = random.uniform(70, 98)
        wet = 0
        if rain > 75: wet += 55
        elif rain > 45: wet += 38
        elif rain > 20: wet += 20
        elif rain > 5: wet += 8
        if hum > 92: wet += 20
        elif hum > 80: wet += 12
        elif hum > 65: wet += 5
        reading = {
            "node_id": "NODE-01", "lat": 23.7348, "lon": 92.7187,
            "rain_pct": round(rain, 1),
            "temperature_c": round(random.uniform(21, 27), 1),
            "humidity_pct": round(hum, 1),
            "wetness_pct": min(wet, 100),
            "simulated": True,
        }
        show(reading)
        post(server, reading)
        time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="serial port (default: auto-detect)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--server", default=DEFAULT_SERVER)
    ap.add_argument("--list", action="store_true", help="show serial ports and exit")
    ap.add_argument("--simulate", action="store_true", help="run without hardware")
    args = ap.parse_args()

    try:
        import serial
    except ImportError:
        sys.exit("pyserial missing.  Run:  ./venv/bin/pip install pyserial")

    if args.list:
        list_ports_cmd()
        return
    if args.simulate:
        simulate(args.server)
        return

    port = args.port
    if not port:
        print("Looking for a board...")
        found = find_board()
        if not found:
            sys.exit("No Arduino found. Plug it in, or use --list, or --simulate.")
        port = found.device
        print(f"Found {found.description} on {port}")

    print(f"Listening on {port} -> {args.server}\nCtrl+C to stop.\n")

    ser = None
    while True:
        # (Re)connect. exclusive=True stops anything else - notably the
        # Arduino IDE's Serial Monitor - stealing the port mid-run, which
        # is what produces "readiness to read but returned no data".
        if ser is None:
            try:
                ser = serial.Serial(port, args.baud, timeout=2, exclusive=True)
                ser.reset_input_buffer()
                time.sleep(2)      # the UNO reboots when the port opens
            except serial.SerialException as exc:
                if "Resource busy" in str(exc):
                    print("  port busy - close the Arduino IDE Serial Monitor, retrying in 3s")
                else:
                    print(f"  cannot open {port}: {exc} - retrying in 3s")
                time.sleep(3)
                continue

        try:
            line = ser.readline().decode("utf-8", errors="replace").strip()
        except (serial.SerialException, OSError) as exc:
            print(f"  connection lost ({exc}) - reconnecting")
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(2)
            continue
        if not line:
            continue
        if line.startswith("#"):
            print(f"  arduino: {line[1:].strip()}")
            continue
        if not line.startswith("{"):
            continue
        try:
            reading = json.loads(line)
        except json.JSONDecodeError:
            continue
        show(reading)
        post(args.server, reading)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
