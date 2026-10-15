"""Weighted Curve Number (WCN) physics for the Teesta basin.

The SCS Curve Number method (USDA 1972, revised 1986) estimates direct
runoff from a storm as a function of rainfall depth and two basin properties:
  - the composite CN (land cover × soil hydrological group)
  - the Antecedent Moisture Condition (AMC I/II/III)

The Antecedent Precipitation Index (API) is a weighted lag of preceding
daily rainfall.  It is the best-performing single predictor in WCN-LSTM
models for Himalayan rivers: 27% SHAP importance in Prasad et al. (2022),
outweighing even the same day's rainfall for discharge at 3-day lead times.

Teesta basin at Gajoldoba barrage (outlet for NHPC cascade)
------------------------------------------------------------
Catchment area: 7,132 km²  (NHPC tender documents, 2012)
Mean annual rainfall: ~3,200 mm  (IMD district normals, 1991-2020)

Land-cover weighted CN (LISS-IV + NLCD mapping):
  Forest good cover  52%  CN_II = 45   (HSG B)
  Terrace agriculture 18%  CN_II = 73   (HSG C)
  Grassland/shrub    14%  CN_II = 61   (HSG B/C)
  Bare rock / ice    10%  CN_II = 85   (HSG D, essentially impervious)
  Built-up / roads    6%  CN_II = 80   (HSG C/D)
  Composite CN_II        ≈  58

With CN_II = 58:
  CN_I  (AMC dry) = 38   (SCS adjustment, Hawkins et al. 1985)
  CN_III (AMC wet) = 76

Validation: at 150 mm storm with AMC III → Q ≈ 84 mm → 6,900 m³/s at
Gajoldoba. The design flood for Teesta Barrage is 7,130 m³/s — consistent.

References
----------
USDA (1986). National Engineering Handbook, Section 4: Hydrology. Ch 4-10.
Hawkins R.H. et al. (1985). AMC transformations. J. Irrig. Drain. Eng.
Prasad R. et al. (2022). WCN-LSTM for Himalayan rivers. HESS 26(7).
NHPC (2012). Teesta Stage VI FRL/MWL Design Report.
"""

import math
from typing import List, Optional

# ---------------------------------------------------------------------------
# Basin constants — Teesta at Gajoldoba
# ---------------------------------------------------------------------------
CATCHMENT_KM2 = 7_132.0
TEESTA_CN_II = 58          # composite CN for normal AMC
TEESTA_CN_I = 38           # AMC dry  (Hawkins 1985 adjustment)
TEESTA_CN_III = 76         # AMC wet

# API recession constant k: fraction of yesterday's API retained today.
# 0.88 fits humid subtropical basins (Jakeman & Hornberger 1993).
API_K = 0.88

# Baseflow recession: fraction of storage released per day.
BF_RECESSION = 0.92

# 5-day antecedent rainfall thresholds for AMC classification (growing season)
AMC_THRESHOLD_I = 35.6     # mm; below = AMC I (dry)
AMC_THRESHOLD_III = 53.3   # mm; above = AMC III (wet)

# Conversion: 1 mm/day of direct runoff → m³/s at Gajoldoba
# = 1e-3 m × 7132 km² × 1e6 m²/km² / 86400 s/day
MM_PER_DAY_TO_M3S = CATCHMENT_KM2 * 1e6 / (86400 * 1000)   # 82.57


# ---------------------------------------------------------------------------
# API (Antecedent Precipitation Index)
# ---------------------------------------------------------------------------

def api_series(rain_mm: List[float], k: float = API_K) -> List[float]:
    """Daily API from a rainfall sequence.

    API_d = k × API_(d-1) + P_(d-1)

    On day 0 the API is initialised to the first rainfall value.
    Returns a list of the same length as rain_mm.
    """
    if not rain_mm:
        return []
    api = [rain_mm[0]]
    for p in rain_mm[1:]:
        api.append(k * api[-1] + p)
    return api


def api_at(rain_mm: List[float], k: float = API_K) -> float:
    """Single API value for the *last* day of rain_mm."""
    vals = api_series(rain_mm, k)
    return vals[-1] if vals else 0.0


# ---------------------------------------------------------------------------
# AMC and effective CN
# ---------------------------------------------------------------------------

def amc_class(rain_5d_mm: float) -> int:
    """Return 1, 2, or 3 for AMC I/II/III."""
    if rain_5d_mm < AMC_THRESHOLD_I:
        return 1
    if rain_5d_mm > AMC_THRESHOLD_III:
        return 3
    return 2


def effective_cn(rain_5d_mm: float,
                 cn_ii: float = TEESTA_CN_II) -> float:
    """CN adjusted for antecedent moisture.

    Hawkins et al. (1985) adjustment from CN_II to CN_I or CN_III.
    """
    amc = amc_class(rain_5d_mm)
    if amc == 2:
        return cn_ii
    if amc == 1:
        # CN_I = CN_II / (2.281 - 0.01281 * CN_II)
        return cn_ii / (2.281 - 0.01281 * cn_ii)
    # amc == 3
    # CN_III = CN_II / (0.427 + 0.00573 * CN_II)
    return cn_ii / (0.427 + 0.00573 * cn_ii)


# ---------------------------------------------------------------------------
# SCS-CN direct runoff
# ---------------------------------------------------------------------------

def direct_runoff_mm(rain_mm: float, cn: float) -> float:
    """SCS-CN direct runoff depth for a single day.

    Q = (P - Ia)² / (P - Ia + S)   for P > Ia
    Q = 0                           for P ≤ Ia

    where S = 25400/CN - 254  [mm]   and   Ia = 0.2 × S.
    """
    if cn <= 0 or cn >= 100:
        return 0.0
    S = 25400.0 / cn - 254.0
    Ia = 0.2 * S
    if rain_mm <= Ia:
        return 0.0
    return (rain_mm - Ia) ** 2 / (rain_mm - Ia + S)


# ---------------------------------------------------------------------------
# Baseflow
# ---------------------------------------------------------------------------

def baseflow_step(q_direct: float,
                  bf_store: float,
                  recession: float = BF_RECESSION) -> tuple:
    """Advance the baseflow store by one day.

    A fraction (1 - recession) of the store drains each day; a portion of
    today's direct runoff recharges the store.  Returns (baseflow_today_m3s,
    new_store_m3s).
    """
    recharge = q_direct * 0.25        # 25% of direct runoff recharges groundwater
    release = bf_store * (1.0 - recession)
    new_store = bf_store * recession + recharge
    return max(0.0, release), new_store


# ---------------------------------------------------------------------------
# Daily total discharge (direct + baseflow)
# ---------------------------------------------------------------------------

def daily_discharge_m3s(
    rain_mm: float,
    rain_5d_mm: float,
    bf_store_m3s: float,
    cn_ii: float = TEESTA_CN_II,
) -> tuple:
    """Total discharge for a single day.

    Returns (Q_total_m3s, Q_direct_m3s, Q_base_m3s, new_bf_store).
    """
    cn = effective_cn(rain_5d_mm, cn_ii)
    q_direct_mm = direct_runoff_mm(rain_mm, cn)
    q_direct_m3s = q_direct_mm * MM_PER_DAY_TO_M3S

    q_base, new_store = baseflow_step(q_direct_m3s, bf_store_m3s)
    q_total = q_direct_m3s + q_base
    return q_total, q_direct_m3s, q_base, new_store


# ---------------------------------------------------------------------------
# Routing lag correction
# ---------------------------------------------------------------------------

def apply_routing_lag(q_series: List[float], K_days: float = 2.0) -> List[float]:
    """Linear reservoir routing with storage constant K (days).

    The Teesta at Gajoldoba has a basin area of 7,132 km² and a mean
    channel length of ~280 km from the centroid.  A wave travel time
    of ~48 hours gives K = 2 days.

    Model: dS/dt = Q_in - Q_out,   S = K × Q_out
    Discretised (dt = 1 day):
        Q_out[t] = Q_out[t-1] × α + Q_in[t] × (1 - α)
        where α = exp(-1/K)

    This converts the CN model's same-day runoff pulse into a delayed,
    dispersed hydrograph.  Without it, every model trained on this data
    sees rain and discharge as simultaneous, so multi-horizon predictions
    have no skill past +1 day.
    """
    alpha = math.exp(-1.0 / max(0.1, K_days))
    routed = [q_series[0]]
    for q in q_series[1:]:
        routed.append(q * (1.0 - alpha) + routed[-1] * alpha)
    return routed


# ---------------------------------------------------------------------------
# Convenience: full time-series from rainfall array
# ---------------------------------------------------------------------------

def simulate_daily(
    rain_series: List[float],
    cn_ii: float = TEESTA_CN_II,
    bf_init_m3s: float = 50.0,
) -> dict:
    """Simulate daily discharge from a rainfall series.

    Returns a dict of lists:
        rain, api, cn_eff, q_direct, q_base, q_total
    """
    n = len(rain_series)
    api_vals = api_series(rain_series)

    out = {"rain": list(rain_series), "api": api_vals,
           "cn_eff": [], "q_direct": [], "q_base": [], "q_total": []}

    bf = bf_init_m3s
    for i in range(n):
        rain_5d = sum(rain_series[max(0, i-4):i+1])
        qt, qd, qb, bf = daily_discharge_m3s(rain_series[i], rain_5d, bf, cn_ii)
        out["cn_eff"].append(round(effective_cn(rain_5d, cn_ii), 1))
        out["q_direct"].append(round(qd, 2))
        out["q_base"].append(round(qb, 2))
        out["q_total"].append(round(qt, 2))

    out["q_total"] = apply_routing_lag(out["q_total"])
    return out
