"""Map geometry sized for a phone.

The dashboard ships 490 KB of road geometry because it draws into a 900px
frame on a laptop. The same data on a 360dp phone screen is both invisible
and slow: 8,700 road fragments, most of them shorter than one screen pixel.
This module projects the same source geometry into the same frame and then
throws away everything the phone could not resolve anyway.
"""

import json
import math
import os

GEO_DIR = os.environ.get("SLOPEWATCH_GEO_DIR", "data/geo")

# Identical frame to build_dashboard, so markers, states and roads from
# either source line up in the same coordinate space.
LON_MIN, LON_MAX = 87.5, 97.8
LAT_MIN, LAT_MAX = 21.5, 29.8
COS_LAT = math.cos(math.radians((LAT_MIN + LAT_MAX) / 2))
WIDTH = 900.0
HEIGHT = (LAT_MAX - LAT_MIN) / ((LON_MAX - LON_MIN) * COS_LAT) * WIDTH

# A phone draws this frame about 360dp wide, so one unit here is roughly
# 0.4dp. Anything finer than a few units cannot be seen.
MIN_WAY_LENGTH = 6.0        # drop road fragments shorter than this
POINT_TOLERANCE = 1.5       # drop points closer together than this

_cache = None


def _project(lon, lat):
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * WIDTH
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * HEIGHT
    return round(x, 1), round(y, 1)


def _thin(points, tolerance):
    """Keeps the first and last point, and any point far enough from the last
    one kept. Cheap, order-preserving, and good enough at this scale."""
    if len(points) < 3:
        return points
    kept = [points[0]]
    for p in points[1:-1]:
        lx, ly = kept[-1]
        if (p[0] - lx) ** 2 + (p[1] - ly) ** 2 >= tolerance * tolerance:
            kept.append(p)
    kept.append(points[-1])
    return kept


def _length(points):
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def _polyline(points, close=False):
    body = "M %s,%s " % points[0] + " ".join("L %s,%s" % p for p in points[1:])
    return body + " Z" if close else body


def _rings_to_path(rings):
    return " ".join(_polyline([_project(*c) for c in ring], close=True) for ring in rings)


def _ways_to_path(ways, min_length, tolerance):
    parts = []
    for way in ways:
        points = _thin([_project(*c) for c in way], tolerance)
        if len(points) < 2 or _length(points) < min_length:
            continue
        parts.append(_polyline(points))
    return " ".join(parts)


def payload():
    """Cached: the files never change while the server is up."""
    global _cache
    if _cache is not None:
        return _cache

    with open(os.path.join(GEO_DIR, "ner_state_rings.json")) as f:
        rings = json.load(f)
    with open(os.path.join(GEO_DIR, "roads_classified.json")) as f:
        roads = json.load(f)

    _cache = {
        "width": round(WIDTH, 1),
        "height": round(HEIGHT, 1),
        "bounds": {"lon_min": LON_MIN, "lon_max": LON_MAX,
                   "lat_min": LAT_MIN, "lat_max": LAT_MAX},
        "states": {name: _rings_to_path(r) for name, r in rings.items()},
        "roads_major": _ways_to_path(roads["major"], MIN_WAY_LENGTH, POINT_TOLERANCE),
        # secondary roads are kept, but only the long ones -- at phone scale
        # the rest is a brown haze over the whole region
        "roads_minor": _ways_to_path(roads["secondary"], MIN_WAY_LENGTH * 2.5,
                                     POINT_TOLERANCE * 1.6),
    }
    return _cache
