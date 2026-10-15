"""What actually follows what, counted over 7,498 field-recorded landslides.

The usual version of this is a diagram: rainfall, arrow, saturation, arrow,
landslide, arrow, road blocked. Everybody draws it, nobody measures it, and
it tells an operator nothing they did not already believe.

The GSI inventory makes it measurable. Every record carries what triggered
the slide, what the ground was made of, how the slope failed, how the
material moved, what it landed on, and whether the same site had gone before.
So the chain can be counted instead of asserted, and the conditional
probabilities fall out:

    Rainfall on an extensively cut slope -> how often is that road blocked,
    and how does that compare with rainfall on a forested one?

The free text has to be canonicalised first. "Road blocked", "Road block",
"Road blocked and damaged" and "road blockage" are the same event recorded by
four surveyors over fifteen years, and counting them separately would put the
real total fourth on its own list. What is deliberately NOT done here is
inventing a category for the blanks: 2,344 of 7,498 records say anything at
all about what was affected, and the rest are unknown rather than unaffected.
Every rate below is stated over the records that answered the question.
"""

import collections
import json
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INVENTORY = os.path.join(_ROOT, "gsi_landslide_inventory.geojson")

_graph = None
_rows = None

BLANK = {"", " ", ".", "-", "na", "n/a", "nil", "none", "nan", "null", "0"}


def _clean(v):
    s = str(v or "").strip()
    return "" if s.lower() in BLANK else s


# --------------------------------------------------------------------------
# canonicalisation
#
# Each list is (canonical name, patterns). First match wins, so the more
# specific patterns are listed first.

def _match(text, table, default="Other"):
    t = text.lower()
    for name, pats in table:
        for p in pats:
            if re.search(p, t):
                return name
    return default if text else None


TRIGGER = [
    ("Rainfall and human activity", [r"rain.*(anthropog|human|cut)",
                                     r"(anthropog|human).*rain"]),
    ("Rainfall", [r"rain", r"monsoon", r"cloud ?burst", r"downpour",
                  r"precipitat"]),
    ("Human activity", [r"anthropog", r"human", r"construction", r"road cut",
                        r"blast", r"mining", r"quarry", r"excavat"]),
    ("Earthquake", [r"earthquak", r"seismic", r"tremor"]),
    ("Toe erosion", [r"toe erosion", r"river erosion", r"undercut", r"fluvial"]),
]

MATERIAL = [
    ("Debris", [r"debris"]),
    ("Rock", [r"\brock"]),
    ("Earth", [r"earth"]),
    ("Soil", [r"soil"]),
]

MECHANISM = [
    ("Shallow translational", [r"translation"]),
    ("Rotational", [r"rotation"]),
    ("Planar", [r"planar"]),
    ("Wedge", [r"wedge"]),
    ("Toppling", [r"toppl"]),
    ("Debris flow", [r"debris flow", r"flow"]),
]

MOVEMENT = [
    ("Slide", [r"slide"]),
    ("Fall", [r"fall"]),
    ("Flow", [r"flow"]),
    ("Subsidence", [r"subsid"]),
    ("Topple", [r"toppl"]),
]

COVER = [
    ("Cut slope", [r"slope cut", r"cut slope", r"extensive slope"]),
    ("Thick vegetation", [r"thick veg", r"dense veg", r"forest"]),
    ("Moderate vegetation", [r"moderate veg"]),
    ("Sparse vegetation", [r"sparse veg", r"barren", r"bare"]),
    ("Built up", [r"settlement", r"built", r"habitat"]),
    ("Agriculture", [r"agri", r"cultivat", r"jhum", r"planta"]),
]

# The consequence layer. "Nil" is a real answer here and kept separate from a
# blank, because a surveyor writing Nil looked and saw nothing damaged.
CONSEQUENCE = [
    ("Road blocked", [r"block"]),
    ("Road damaged", [r"road.*(damag|crack|subsid|sink|wash)", r"damag.*road",
                      r"\bnh\b.*damag", r"highway.*damag"]),
    ("Bridge or culvert", [r"bridge", r"culvert"]),
    ("Buildings", [r"house", r"building", r"school", r"hospital", r"dwelling"]),
    ("Power or telecom", [r"power", r"electric", r"transmission", r"telecom",
                          r"tower", r"cable"]),
    ("Water supply", [r"water suppl", r"pipeline", r"water line"]),
    ("Footpath or track", [r"foot ?path", r"track", r"trail", r"mule"]),
    ("Nothing affected", [r"^nil$", r"^no damage", r"^none$", r"not affected"]),
    ("Road, unspecified", [r"road", r"highway", r"\bnh\b", r"\bsh\b"]),
]

HYDRO = [
    ("Dry", [r"^dry"]),
    ("Damp", [r"damp"]),
    ("Wet", [r"^wet", r"saturat"]),
    ("Flowing", [r"flow", r"seep", r"spring"]),
]

ACTIVITY = [
    ("Active", [r"active"]),
    ("Reactivated", [r"reactivat"]),
    ("Suspended", [r"suspend"]),
    ("Dormant", [r"dormant"]),
    ("Stabilised", [r"stabilis", r"stabiliz", r"relict"]),
]

LAYERS = [
    ("trigger", "What set it off", TRIGGER),
    ("cover", "What was on the slope", COVER),
    ("material", "What the slope is made of", MATERIAL),
    ("mechanism", "How it failed", MECHANISM),
    ("movement", "How it moved", MOVEMENT),
    ("consequence", "What it hit", CONSEQUENCE),
]

FIELD_FOR = {
    "trigger": "TRIGGERING",
    "cover": "LANDUSE_LANDCOVER",
    "material": "MATERIAL_TYPE",
    "mechanism": "FAILURE_MECHANISM",
    "movement": "MOVEMENT_TYPE",
    "consequence": None,          # built from two fields, see below
    "hydro": "HYDROLOGICAL_CONDITION",
    "activity": "ACTIVITY",
}


def rows():
    """One canonical record per mapped landslide."""
    global _rows
    if _rows is not None:
        return _rows
    with open(INVENTORY) as f:
        feats = json.load(f)["features"]

    out = []
    for ft in feats:
        p = ft["properties"]
        # Two fields answer "what was hit" and surveyors used them
        # interchangeably. Prefer the more specific answer of the two.
        cons_text = " ; ".join(t for t in (_clean(p.get("COMMUNICATION_AFFECTED")),
                                           _clean(p.get("INFRASTRUCTURE_AFFECTED")))
                               if t)
        rec = {
            "id": p.get("SLIDE_NO") or p.get("OBJECTID"),
            "state": _clean(p.get("STATE")),
            "district": _clean(p.get("DISTRICT")),
            "lat": p.get("LATITUDE"), "lon": p.get("LONGITUDE"),
            "trigger": _match(_clean(p.get("TRIGGERING")), TRIGGER),
            "cover": _match(_clean(p.get("LANDUSE_LANDCOVER")), COVER),
            "material": _match(_clean(p.get("MATERIAL_TYPE")), MATERIAL),
            "mechanism": _match(_clean(p.get("FAILURE_MECHANISM")), MECHANISM),
            "movement": _match(_clean(p.get("MOVEMENT_TYPE")), MOVEMENT),
            "consequence": _match(cons_text, CONSEQUENCE),
            "hydro": _match(_clean(p.get("HYDROLOGICAL_CONDITION")), HYDRO),
            "activity": _match(_clean(p.get("ACTIVITY")), ACTIVITY),
            "volume": p.get("LS_VOLUME"),
            "runout_m": p.get("RUNOUT_DISTANCE"),
            "on_highway": bool(_clean(p.get("NH_SH_LOCATION"))),
        }
        ry = _clean(p.get("REACTIVATION"))
        rec["reactivated"] = bool(ry and ry.isdigit() and int(ry) > 1900)
        rec["reactivation_year"] = int(ry) if rec["reactivated"] else None
        out.append(rec)
    _rows = out
    return out


# --------------------------------------------------------------------------
# the graph

def build():
    """Layered graph with observed counts on every edge."""
    global _graph
    if _graph is not None:
        return _graph
    rs = rows()

    nodes, edges = [], []
    for key, label, _ in LAYERS:
        c = collections.Counter(r[key] for r in rs if r[key])
        for name, n in c.most_common():
            nodes.append({"layer": key, "layer_label": label,
                          "name": name, "n": n})

    for i in range(len(LAYERS) - 1):
        a_key = LAYERS[i][0]
        b_key = LAYERS[i + 1][0]
        pair = collections.Counter()
        a_tot = collections.Counter()
        for r in rs:
            a, b = r[a_key], r[b_key]
            if not a or not b:
                continue
            pair[(a, b)] += 1
            a_tot[a] += 1
        for (a, b), n in pair.most_common():
            edges.append({"from_layer": a_key, "to_layer": b_key,
                          "from": a, "to": b, "n": n,
                          "p": round(n / a_tot[a], 4)})

    _graph = {"layers": [{"key": k, "label": l} for k, l, _ in LAYERS],
              "nodes": nodes, "edges": edges, "n_records": len(rs)}
    return _graph


def chain(**where):
    """Follow the record from a set of conditions and report what followed.

    chain(trigger="Rainfall", cover="Cut slope") answers: of the slides that
    match, what did they hit, how often did they reactivate, and how does that
    compare with the inventory as a whole. The comparison is the point -- a
    consequence rate means nothing without the base rate beside it.
    """
    rs = rows()
    sel = [r for r in rs
           if all(r.get(k) == v for k, v in where.items() if v)]
    if not sel:
        return {"where": where, "n": 0}

    def dist(key, pool):
        answered = [r[key] for r in pool if r[key]]
        c = collections.Counter(answered)
        return {"answered": len(answered), "of": len(pool),
                "top": [{"name": k, "n": v, "p": round(v / len(answered), 4)}
                        for k, v in c.most_common(8)]}

    def road_rate(pool):
        answered = [r["consequence"] for r in pool if r["consequence"]]
        if not answered:
            return None
        hit = sum(1 for c in answered
                  if c in ("Road blocked", "Road damaged", "Road, unspecified"))
        return {"answered": len(answered), "road": hit,
                "rate": round(hit / len(answered), 4)}

    def reactivation_rate(pool):
        return round(sum(1 for r in pool if r["reactivated"]) / len(pool), 4)

    return {
        "where": where,
        "n": len(sel),
        "share_of_inventory": round(len(sel) / len(rs), 4),
        "consequence": dist("consequence", sel),
        "mechanism": dist("mechanism", sel),
        "movement": dist("movement", sel),
        "hydro": dist("hydro", sel),
        "activity": dist("activity", sel),
        "road_blocked_or_damaged": road_rate(sel),
        "road_baseline": road_rate(rs),
        "reactivation": reactivation_rate(sel),
        "reactivation_baseline": reactivation_rate(rs),
        "on_highway": round(sum(1 for r in sel if r["on_highway"]) / len(sel), 4),
        "states": [{"name": k, "n": v} for k, v in
                   collections.Counter(r["state"] for r in sel).most_common(6)],
    }


def findings(min_n=120):
    """Combinations whose consequence rate departs most from the base rate.

    This is the part that could not be written down in advance: the inventory
    is asked which conditions actually change the odds of a road being cut,
    and it answers with a number and a sample size attached. Anything under
    min_n records is dropped rather than reported with a wide interval and a
    confident sentence.
    """
    rs = rows()
    answered_all = [r for r in rs if r["consequence"]]
    base = sum(1 for r in answered_all
               if r["consequence"].startswith("Road")) / max(len(answered_all), 1)

    # 91% of answered records name a road, which is too high to be read as
    # "91% of landslides block a road". Two things are mixed in: roads are
    # genuinely what there is to damage on a cut hillside, and a surveyor who
    # walked a road is far likelier to write down that the road was hit than
    # that a forest was. So the absolute rate is inflated by the survey, and
    # only the differences between categories -- which share the bias -- are
    # worth reading. Blocked-versus-damaged is reported alongside because it
    # is not saturated and therefore discriminates.
    def blocked_share(pool):
        road = [r for r in pool if r["consequence"]
                and r["consequence"].startswith("Road")]
        if len(road) < 40:
            return None
        return round(sum(1 for r in road
                         if r["consequence"] == "Road blocked") / len(road), 4)

    base_blocked = blocked_share(answered_all)

    out = []
    for a_key in ("trigger", "cover", "material", "mechanism", "hydro"):
        groups = collections.defaultdict(list)
        for r in answered_all:
            if r[a_key]:
                groups[r[a_key]].append(r)
        for name, pool in groups.items():
            if len(pool) < min_n:
                continue
            rate = sum(1 for r in pool
                       if r["consequence"].startswith("Road")) / len(pool)
            bs = blocked_share(pool)
            out.append({
                "factor": a_key, "value": name, "n": len(pool),
                "road_rate": round(rate, 4), "baseline": round(base, 4),
                "lift": round(rate / base, 3) if base else None,
                "blocked_share": bs,
                "blocked_baseline": base_blocked,
                "blocked_lift": round(bs / base_blocked, 3)
                if bs and base_blocked else None,
            })
    out.sort(key=lambda r: -abs((r["blocked_lift"] or r["lift"] or 1) - 1))

    # And the same question for reactivation, which is the one that says
    # where money spent once will have to be spent again.
    react = []
    for a_key in ("trigger", "cover", "material", "mechanism"):
        groups = collections.defaultdict(list)
        for r in rs:
            if r[a_key]:
                groups[r[a_key]].append(r)
        rb = sum(1 for r in rs if r["reactivated"]) / len(rs)
        for name, pool in groups.items():
            if len(pool) < min_n:
                continue
            rate = sum(1 for r in pool if r["reactivated"]) / len(pool)
            react.append({"factor": a_key, "value": name, "n": len(pool),
                          "reactivation_rate": round(rate, 4),
                          "baseline": round(rb, 4),
                          "lift": round(rate / rb, 3) if rb else None})
    react.sort(key=lambda r: -(r["lift"] or 0))

    return {"n_records": len(rs), "n_answered": len(answered_all),
            "road_baseline": round(base, 4),
            "blocked_baseline": base_blocked,
            "bias_note": (
                f"{len(answered_all):,} of {len(rs):,} records answer what was "
                f"affected, and {base*100:.0f}% of those name a road. Read that "
                "as a property of the survey as much as of the hazard: GSI "
                "walks roads, and a surveyor on a road records the road. The "
                "comparisons below share that bias, so their differences hold "
                "even though the absolute rate does not. Blocked-versus-damaged "
                "is the cleaner measure and is given beside it."),
            "road": out[:14], "reactivation": react[:10]}
