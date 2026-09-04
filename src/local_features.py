"""Features computed locally rather than from Earth Engine.

Two additions, each taken from an established operational model:

  dist_to_road_m
      NASA LHASA uses road networks as a susceptibility input: cut slopes
      above and below hill roads are among the most reliable predictors of
      shallow failure, and in the NER specifically, unengineered hill-cutting
      for roads and construction is repeatedly named as a driver.

  factor_of_safety
      The USGS shallow-landslide approach: an infinite-slope stability
      calculation in which rainfall raises pore pressure and lowers the
      factor of safety. FS < 1 means the slope is theoretically unstable.
"""

import math
import pickle

import numpy as np
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_000.0

# Geotechnical constants. We have no per-site soil tests, so these are fixed
# regional values: weathered colluvium over the Bhuban/Surma shale-sandstone
# sequence that underlies much of the NER hill country. Published back-analysis
# from the Hunthar Veng (Aizawl) failure gives c'=20 kPa / phi=11 deg for
# surficial debris and c'=100 kPa / phi=38 deg for the weathered rock beneath;
# we sit between those. The absolute FS value is therefore indicative only --
# it is used as a relative index across sites, not as a site-specific verdict.
COHESION_PA = 5_000.0
FRICTION_ANGLE_DEG = 30.0
SOIL_UNIT_WEIGHT = 19_000.0  # N/m3
WATER_UNIT_WEIGHT = 9_810.0  # N/m3
SOIL_DEPTH_M = 2.0  # shallow planar failure depth typical of NER events

_road_tree = None


def _load_road_tree(path="data/processed/road_points.pkl"):
    global _road_tree
    if _road_tree is None:
        with open(path, "rb") as f:
            pts = pickle.load(f)
        radians = np.radians(np.array(pts, dtype=np.float64))
        _road_tree = BallTree(radians, metric="haversine")
    return _road_tree


def distance_to_road_m(lat, lon):
    tree = _load_road_tree()
    query = np.radians(np.array([[lat, lon]], dtype=np.float64))
    dist, _ = tree.query(query, k=1)
    return float(dist[0][0] * EARTH_RADIUS_M)


def factor_of_safety(slope_deg, soil_moisture=None):
    """Infinite-slope factor of safety (USGS shallow-landslide form).

        FS = c' / (gamma_s * z * sin(b) * cos(b))
             + (1 - m * gamma_w / gamma_s) * tan(phi') / tan(b)

    `m` is the wetness ratio -- the fraction of the soil column that is
    saturated -- which is what rainfall actually modulates. Volumetric soil
    moisture from SMAP is used as its proxy, scaled by porosity; when soil
    moisture is unavailable we assume a moderately wet column rather than a
    dry one, which is the conservative direction for a hazard model.
    """
    if slope_deg is None:
        return None
    beta = math.radians(max(float(slope_deg), 1.0))  # avoid divide-by-zero on flats

    porosity = 0.45
    m = 0.5 if soil_moisture is None else min(max(float(soil_moisture) / porosity, 0.0), 1.0)

    cohesion_term = COHESION_PA / (SOIL_UNIT_WEIGHT * SOIL_DEPTH_M * math.sin(beta) * math.cos(beta))
    friction_term = (1.0 - m * WATER_UNIT_WEIGHT / SOIL_UNIT_WEIGHT) * (
        math.tan(math.radians(FRICTION_ANGLE_DEG)) / math.tan(beta)
    )
    return cohesion_term + friction_term


def add_local_features(feats, lat, lon):
    """Augments a GEE feature dict in place with the locally computed features."""
    feats["dist_to_road_m"] = distance_to_road_m(lat, lon)

    # Factor of safety is driven by the steepest slope in the neighbourhood:
    # that is where failure initiates, not necessarily at the reported point.
    slope = feats.get("slope_max_nbhd")
    if slope is None:
        slope = feats.get("slope")
    feats["factor_of_safety"] = factor_of_safety(slope, feats.get("soil_moisture_surface"))
    return feats
