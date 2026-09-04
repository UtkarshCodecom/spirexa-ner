"""Alert generation and dispatch.

Scans the current risk snapshot, decides which locations warrant an alert, and
sends them to the configured channels.

Channels
--------
console  always on; prints to stdout
file     always on; appends JSON lines to data/processed/alert_log.jsonl
webhook  off unless ALERT_WEBHOOK_URL is set (Slack/Teams/any HTTP endpoint)

SMS/push are deliberately not wired up here. Adding a real SMS provider means
putting account credentials and a billable send path into the repo, so that is
left as an explicit opt-in: implement `_send_sms` against your provider and add
"sms" to ACTIVE_CHANNELS once you have credentials you are willing to spend.

Usage
-----
    python src/alerts.py                 # alert off the saved snapshot
    python src/alerts.py --refresh       # recompute live risk first
    python src/alerts.py --threshold 0.6 # override the alert threshold
"""

import argparse
import datetime
import json
import os
import urllib.error
import urllib.request

import pandas as pd

import i18n

LIVE_RISK_CSV = "data/processed/live_risk.csv"
ALERT_LOG = "data/processed/alert_log.jsonl"

# A location must exceed this to alert at all.
DEFAULT_THRESHOLD = 0.60

# Don't re-alert the same location inside this window unless it escalates a band.
COOLDOWN_HOURS = 12

SEVERITY_BANDS = [
    (0.75, "SEVERE"),
    (0.60, "HIGH"),
    (0.25, "MODERATE"),
    (0.00, "LOW"),
]

ACTIVE_CHANNELS = ["console", "file", "webhook"]


def band_for(risk):
    for cutoff, label in SEVERITY_BANDS:
        if risk >= cutoff:
            return label
    return "LOW"


def load_recent_alerts():
    """Returns {location_id: (timestamp, severity)} from the alert log."""
    if not os.path.exists(ALERT_LOG):
        return {}
    recent = {}
    with open(ALERT_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = datetime.datetime.fromisoformat(rec["issued_at"])
            prev = recent.get(rec["id"])
            if prev is None or ts > prev[0]:
                recent[rec["id"]] = (ts, rec["severity"])
    return recent


def should_alert(row, threshold, recent):
    if row["live_risk"] < threshold:
        return False
    severity = band_for(row["live_risk"])
    prior = recent.get(row["id"])
    if prior is None:
        return True
    prior_time, prior_severity = prior
    age_hours = (datetime.datetime.now() - prior_time).total_seconds() / 3600.0
    if age_hours >= COOLDOWN_HOURS:
        return True
    # Inside the cooldown, still alert if the situation got worse.
    order = [label for _, label in SEVERITY_BANDS][::-1]
    return order.index(severity) > order.index(prior_severity)


def build_alerts(df, threshold, languages=None):
    """Builds alert records, each carrying its message in every language the
    recipients of that state should receive."""
    recent = load_recent_alerts()
    alerts = []
    for _, row in df.iterrows():
        if not should_alert(row, threshold, recent):
            continue
        alert = {
            "id": row["id"],
            "location": row["location"],
            "state": row["state"],
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "risk": round(float(row["live_risk"]), 4),
            "severity": band_for(row["live_risk"]),
            "as_of": str(row.get("as_of_date", "")),
            "issued_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        codes = languages or i18n.languages_for_state(row["state"])
        alert["messages"] = [i18n.render_alert(alert, code) for code in codes]
        alerts.append(alert)
    alerts.sort(key=lambda a: a["risk"], reverse=True)
    return alerts


def _send_console(alerts, show_messages=False):
    if not alerts:
        print("No locations above the alert threshold.")
        return
    print(f"\n{len(alerts)} ALERT(S) ISSUED  {datetime.datetime.now():%Y-%m-%d %H:%M}")
    print("-" * 78)
    for a in alerts:
        print(
            f"  [{a['severity']:<8}] {a['risk'] * 100:5.1f}%  "
            f"{a['location'][:44]:<44} {a['state']}"
        )
        print(f"             {a['lat']:.4f}, {a['lon']:.4f}")
        langs = a.get("messages", [])
        if langs:
            summary = ", ".join(
                f"{m['language']}{'*' if m['paired_with_english'] else ''}"
                f"({m['sms_segments']} sms)"
                for m in langs
            )
            print(f"             languages: {summary}")
        if show_messages:
            for m in langs:
                print(f"\n             --- {m['language']} ({m['native_name']}) ---")
                for line in m["message"].splitlines():
                    print(f"             {line}")
            print()
    print("-" * 78)
    if any(m["paired_with_english"] for a in alerts for m in a.get("messages", [])):
        print("* translation not yet verified by a native speaker; sent paired with English")


def _send_file(alerts):
    os.makedirs(os.path.dirname(ALERT_LOG), exist_ok=True)
    with open(ALERT_LOG, "a") as f:
        for a in alerts:
            f.write(json.dumps(a) + "\n")
    if alerts:
        print(f"Logged {len(alerts)} alert(s) to {ALERT_LOG}")


def _send_webhook(alerts):
    url = os.environ.get("ALERT_WEBHOOK_URL")
    if not url:
        return
    if not alerts:
        return
    lines = [f"*{len(alerts)} landslide risk alert(s)*"]
    for a in alerts[:20]:
        lines.append(
            f"• [{a['severity']}] {a['risk'] * 100:.0f}% — {a['location']} ({a['state']})"
        )
    payload = json.dumps({"text": "\n".join(lines)}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Webhook delivered ({resp.status})")
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Webhook failed: {exc}")


def dispatch(alerts, show_messages=False):
    if "console" in ACTIVE_CHANNELS:
        _send_console(alerts, show_messages=show_messages)
    if "file" in ACTIVE_CHANNELS:
        _send_file(alerts)
    if "webhook" in ACTIVE_CHANNELS:
        _send_webhook(alerts)


def main():
    parser = argparse.ArgumentParser(description="Issue landslide risk alerts.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--refresh", action="store_true", help="recompute live risk before alerting"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print alerts without logging or sending"
    )
    parser.add_argument(
        "--lang",
        help="comma-separated language codes; default is per-state (e.g. lus,en)",
    )
    parser.add_argument(
        "--show-messages", action="store_true", help="print the full translated text"
    )
    parser.add_argument(
        "--list-languages", action="store_true", help="list available locales and exit"
    )
    args = parser.parse_args()

    if args.list_languages:
        print(f"{'code':<6} {'language':<20} {'native':<20} status")
        for code, meta in i18n.available().items():
            status = "verified" if meta["verified"] else "NEEDS NATIVE REVIEW"
            print(f"{code:<6} {meta['name']:<20} {meta['native_name']:<20} {status}")
        return

    if args.refresh:
        import compute_live_risk

        compute_live_risk.main()

    if not os.path.exists(LIVE_RISK_CSV):
        raise SystemExit(
            f"{LIVE_RISK_CSV} not found. Run: python src/compute_live_risk.py"
        )

    df = pd.read_csv(LIVE_RISK_CSV)
    languages = [c.strip() for c in args.lang.split(",")] if args.lang else None
    alerts = build_alerts(df, args.threshold, languages)

    if args.dry_run:
        _send_console(alerts, show_messages=args.show_messages)
        print("(dry run - nothing logged or sent)")
    else:
        dispatch(alerts, show_messages=args.show_messages)


if __name__ == "__main__":
    main()
