"""Multilingual alert rendering.

Alert text is a small fixed catalogue of templated strings, so this needs a
translation table, not a translation engine. Nothing is translated at runtime.

Safety rule enforced here: a locale whose translations have not been checked
by a native speaker is never sent on its own. It is paired with English, so a
recipient always has one string that is known to be correct. Getting a
severity word wrong in a disaster warning is worse than sending English.

Set "verified": true in a locale file only after a native speaker has
reviewed every string in it.
"""

import json
import os

LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
FALLBACK = "en"

_cache = {}


def available():
    """Returns {code: {name, native_name, verified}} for every locale on disk."""
    out = {}
    for fname in sorted(os.listdir(LOCALE_DIR)):
        if not fname.endswith(".json"):
            continue
        code = fname[:-5]
        data = load(code)
        out[code] = {
            "name": data.get("_name", code),
            "native_name": data.get("_native_name", code),
            "verified": bool(data.get("_verified", False)),
        }
    return out


def load(code):
    if code not in _cache:
        path = os.path.join(LOCALE_DIR, f"{code}.json")
        if not os.path.exists(path):
            if code == FALLBACK:
                raise FileNotFoundError(f"base locale missing: {path}")
            return load(FALLBACK)
        with open(path, encoding="utf-8") as f:
            _cache[code] = json.load(f)
    return _cache[code]


def t(key, code=FALLBACK, **kwargs):
    """Looks up one string, falling back to English if the key is absent."""
    strings = load(code)
    template = strings.get(key)
    if template is None:
        template = load(FALLBACK).get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def render_alert(alert, code=FALLBACK):
    """Builds the message body for one alert in one language.

    Returns a dict with the rendered text and whether it was paired with
    English because the locale is unverified.
    """
    severity_key = f"severity_{alert['severity'].lower()}"
    body = t(
        "alert_body",
        code,
        severity=t(severity_key, code),
        location=alert["location"],
        state=alert["state"],
        percent=round(alert["risk"] * 100),
    )
    action = t(f"action_{alert['severity'].lower()}", code)
    signature = t("signature", code)
    message = f"{body}\n{action}\n{signature}"

    meta = load(code)
    verified = bool(meta.get("_verified", False))

    if code != FALLBACK and not verified:
        english = render_alert(alert, FALLBACK)["message"]
        message = f"{message}\n---\n{english}"

    return {
        "language": code,
        "native_name": meta.get("_native_name", code),
        "verified": verified,
        "paired_with_english": code != FALLBACK and not verified,
        "message": message,
        "characters": len(message),
        "sms_segments": _sms_segments(message),
    }


def _sms_segments(text):
    """SMS segment count. Non-Latin scripts use UCS-2 at 70 chars per part."""
    ascii_only = all(ord(ch) < 128 for ch in text)
    per_segment = 160 if ascii_only else 70
    single = 160 if ascii_only else 70
    if len(text) <= single:
        return 1
    concat = 153 if ascii_only else 67  # multipart headers eat a few chars
    return -(-len(text) // concat)


# Which languages a given state's recipients should get by default.
STATE_LANGUAGES = {
    "Assam": ["as", "bn", "hi", "en"],
    "Arunachal Pradesh": ["hi", "en"],
    "Manipur": ["mni", "hi", "en"],
    "Meghalaya": ["kha", "en"],
    "Mizoram": ["lus", "en"],
    "Nagaland": ["nag", "en"],
    "Sikkim": ["ne", "hi", "en"],
    "Tripura": ["bn", "hi", "en"],
}


def languages_for_state(state):
    return STATE_LANGUAGES.get(state, ["hi", "en"])
