"""Delivery queue for alerts pushed from the dashboard to the mobile app.

The web side decides an alert is worth sending and POSTs it here; the app
polls for anything newer than the last id it saw. Deliberately a pull model:
it needs no Firebase account, no internet, and works on a field laptop
serving a phone over the same WiFi, which is the situation this is for.

Messages arrive already rendered in each language. Translation belongs to
i18n.py and the locale files, not here -- this module only carries them.
"""

import datetime
import json
import os
import threading

STORE = "data/reports/notifications.jsonl"
_lock = threading.Lock()          # two authorities can send at once


def _read_all():
    if not os.path.exists(STORE):
        return []
    out = []
    with open(STORE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue      # a torn final line should not kill the feed
    return out


def send(payload):
    """Queues one alert for delivery. Returns the stored record."""
    messages = payload.get("messages") or []
    if not messages:
        return {"error": "at least one message is required"}

    with _lock:
        existing = _read_all()
        next_id = (max((r.get("id", 0) for r in existing), default=0)) + 1

        record = {
            "id": next_id,
            "sent_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "location": (payload.get("location") or "")[:160],
            "state": (payload.get("state") or "")[:80],
            "lat": payload.get("lat"),
            "lon": payload.get("lon"),
            "risk_percent": payload.get("risk_percent"),
            "severity": (payload.get("severity") or "").upper()[:12],
            "sent_by": (payload.get("sent_by") or "dashboard")[:80],
            # [{language, native_name, code, text, verified}]
            "messages": messages[:6],
        }

        os.makedirs(os.path.dirname(STORE), exist_ok=True)
        with open(STORE, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def since(last_id=0, limit=50):
    """Everything newer than `last_id`, oldest first, so the app can replay
    in order and then remember the highest id it has seen."""
    try:
        last_id = int(last_id)
    except (TypeError, ValueError):
        last_id = 0

    rows = [r for r in _read_all() if r.get("id", 0) > last_id]
    rows.sort(key=lambda r: r.get("id", 0))
    rows = rows[:limit]
    return {
        "count": len(rows),
        "latest_id": max((r.get("id", 0) for r in _read_all()), default=0),
        "notifications": rows,
    }
