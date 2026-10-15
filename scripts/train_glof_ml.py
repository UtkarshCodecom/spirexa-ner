"""Learns peak outburst discharge from 502 real glacier lake outburst floods.

Until now the GLOF chain in this project had no machine learning in it at all.
It went lake area -> Huggel volume -> Froehlich breach -> Muskingum routing:
four published equations, every one of them auditable, none of them fitted to
anything the project had measured. That is a defensible way to build a hazard
model and a poor answer to "where is the AI".

Froehlich's peak-discharge regression is the weak link. It was fitted to a few
dozen constructed-dam failures in 1995, and a moraine is not an earthfill dam:
it is poorly sorted, often ice-cored, and it fails over hours rather than
minutes. Everyone in the field knows this and uses the equation anyway, with a
correction coefficient bolted on the front -- ours is MORAINE_PEAK_COEFF = 0.45,
a number chosen because it made South Lhonak come out right.

Lutzow and Veh (2023) published the global GLOF inventory: 3,167 recorded
outbursts from 769 sources, CC-BY-4.0. Five hundred and two of them report
both the flood volume that left the lake and the peak discharge it produced.
That is a real training set for the exact quantity the equation estimates, so
the equation can stop being an assumption and start being a baseline.

WHAT IS COMPARED
    power law     Qp = a * V0^b fitted on the training split. The standard
                  empirical approach in the GLOF literature, and a genuinely
                  strong baseline -- volume alone explains r2 = 0.41 in log
                  space.
    Froehlich     the equation the project currently ships, moraine
                  coefficient and all, with dam height assumed at 40 m.
    learned       gradient boosting on volume plus what the inventory also
                  records: lake type, failure mechanism, region, glacier area,
                  latitude. All of it known before an outburst.

Scored on a held-out 25% in log10 space, because GLOF discharges span five
orders of magnitude and an absolute error in cumecs is meaningless across
them. The honest metric for this field is the median factor of error: a value
of 2 means the typical prediction is within a factor of two of what was
measured, which is roughly what the literature achieves.
"""

import json
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split

DB = "data/external/glofdatabase_V3-1.ods"
OUT_MODEL = "data/processed/glof_qp_model.pkl"
OUT_REPORT = "data/processed/glof_qp_report.json"
SEED = 42
TEST_FRAC = 0.25

# The project's current constants, so the baseline is what actually ships.
MORAINE_PEAK_COEFF = 0.45
ASSUMED_MORAINE_M = 40.0


def load():
    x = pd.ExcelFile(DB, engine="odf")
    df = pd.concat([pd.read_excel(x, sheet_name=s).assign(Region_sheet=s)
                    for s in x.sheet_names], ignore_index=True)
    num = lambda c: pd.to_numeric(df[c], errors="coerce")
    df["V0"] = num("Mean_Flood_Volume_V0")        # 10^6 m3
    df["Qp"] = num("Peak_discharge_Qp")           # m3/s
    df["glacier_area"] = num("RGI_Glacier_Area")
    df["lat"] = num("Latitude")
    keep = df.V0.notna() & df.Qp.notna() & (df.V0 > 0) & (df.Qp > 0)
    d = df[keep].copy()
    d["log_v0"] = np.log10(d.V0 * 1e6)            # m3
    d["log_qp"] = np.log10(d.Qp)
    return d


def featurise(d, with_mechanism=True):
    """Lake volume, type, region, glacier size and latitude.

    `Mechanism` -- overtopping, breach, subglacial drainage -- is how the dam
    actually gave way, which nobody knows until it has. Including it inflates
    the score with information an operator will not have on the night, so the
    honest operational model is trained without it and both are reported. The
    gap between them is the size of that hindsight.
    """
    X = pd.DataFrame(index=d.index)
    X["log_v0"] = d["log_v0"]
    X["glacier_area"] = d["glacier_area"]
    X["lat_abs"] = d["lat"].abs()
    cols = [("Lake_type", "lt"), ("Region_sheet", "reg")]
    if with_mechanism:
        cols.insert(1, ("Mechanism", "mech"))
    for col, prefix in cols:
        top = d[col].value_counts().head(8).index
        for v in top:
            X[f"{prefix}_{str(v).replace(' ', '_')[:16]}"] = (d[col] == v).astype(int)
    return X


def froehlich_peak(v0_m3, h_m=ASSUMED_MORAINE_M, coeff=MORAINE_PEAK_COEFF):
    """The equation the project currently ships."""
    return coeff * 0.607 * (v0_m3 ** 0.295) * (h_m ** 1.24)


def factor_error(true_log, pred_log):
    """Median factor by which a prediction is out. 2.0 = within 2x, typically."""
    return float(10 ** np.median(np.abs(true_log - pred_log)))


def score(name, y_log, pred_log):
    resid = y_log - pred_log
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y_log - y_log.mean()) ** 2))
    return {
        "model": name,
        "median_factor_error": round(factor_error(y_log, pred_log), 2),
        "mae_log10": round(float(np.mean(np.abs(resid))), 4),
        "r2_log10": round(1 - ss_res / ss_tot, 4),
        "within_2x_pct": round(float(np.mean(np.abs(resid) < math.log10(2)) * 100), 1),
        "within_5x_pct": round(float(np.mean(np.abs(resid) < math.log10(5)) * 100), 1),
    }


def main():
    d = load()
    print(f"{len(d)} recorded outbursts with both flood volume and peak discharge")
    print(f"  High Mountain Asia: {(d.Region_sheet == 'High Mountain Asia').sum()}"
          f"   moraine-dammed: {(d.Lake_type == 'moraine').sum()}")

    X, y = featurise(d, with_mechanism=False), d["log_qp"].to_numpy()
    X_hind = featurise(d, with_mechanism=True)
    idx_tr, idx_te = train_test_split(
        np.arange(len(d)), test_size=TEST_FRAC, random_state=SEED,
        stratify=(d.Region_sheet == "High Mountain Asia").to_numpy())
    Xtr, Xte = X.iloc[idx_tr], X.iloc[idx_te]
    ytr, yte = y[idx_tr], y[idx_te]
    print(f"  train {len(ytr)}  test {len(yte)}\n")

    results = []

    # --- baseline 1: the field's standard power law, fitted on train ---------
    b, a = np.polyfit(Xtr["log_v0"], ytr, 1)
    print(f"power law fitted on train:  Qp = {10**a:.3g} * V0^{b:.3f}")
    results.append(score("power law on volume", yte, a + b * Xte["log_v0"].to_numpy()))

    # --- baseline 2: what the project currently ships ------------------------
    froe = np.log10(froehlich_peak(10 ** Xte["log_v0"].to_numpy()))
    results.append(score("Froehlich (shipped)", yte, froe))

    # --- the learned model ---------------------------------------------------
    def gb():
        return HistGradientBoostingRegressor(
            max_iter=400, max_depth=4, learning_rate=0.06,
            min_samples_leaf=12, l2_regularization=1.0, random_state=SEED)

    m = gb()
    m.fit(Xtr, ytr)
    results.append(score("learned, operational", yte, m.predict(Xte)))

    # The same model given the failure mechanism, which is hindsight. Reported
    # so the operational number cannot be mistaken for the flattering one.
    mh = gb()
    mh.fit(X_hind.iloc[idx_tr], ytr)
    results.append(score("learned + hindsight mechanism", yte,
                         mh.predict(X_hind.iloc[idx_te])))

    print(f"\n{'model':<24} {'factor':>7} {'MAE log':>8} {'R2 log':>7} "
          f"{'<2x':>6} {'<5x':>6}")
    for r in results:
        print(f"  {r['model']:<22} {r['median_factor_error']:>7.2f} "
              f"{r['mae_log10']:>8.3f} {r['r2_log10']:>7.3f} "
              f"{r['within_2x_pct']:>5.1f}% {r['within_5x_pct']:>5.1f}%")

    # --- how it does where we actually deploy -------------------------------
    hma_te = (d.Region_sheet.to_numpy()[idx_te] == "High Mountain Asia")
    hma = {}
    if hma_te.sum() >= 15:
        hma = {
            "n": int(hma_te.sum()),
            "power_law": score("power law", yte[hma_te],
                               (a + b * Xte["log_v0"].to_numpy())[hma_te]),
            "froehlich": score("Froehlich", yte[hma_te], froe[hma_te]),
            "learned": score("learned, operational", yte[hma_te],
                             m.predict(Xte)[hma_te]),
        }
        print(f"\nHigh Mountain Asia only ({hma['n']} held-out events):")
        for k in ("power_law", "froehlich", "learned"):
            r = hma[k]
            print(f"  {r['model']:<22} factor {r['median_factor_error']:>5.2f}  "
                  f"within 2x {r['within_2x_pct']:>5.1f}%")

    # --- the one event everybody knows --------------------------------------
    # South Lhonak, 3 Oct 2023: our chain releases 52.9 Mm3 from a moraine lake
    # in High Mountain Asia. Published peak at Chungthang: 5,000-7,000 m3/s.
    probe = pd.DataFrame(index=[0])
    probe["log_v0"] = math.log10(52.9e6)
    probe["glacier_area"] = 5.0
    probe["lat_abs"] = 27.91
    for c in X.columns:
        if c not in probe.columns:
            probe[c] = 0
    for c, v in (("lt_moraine", 1), ("mech_overtopping", 1),
                 ("reg_High_Mountain_As", 1)):
        if c in probe.columns:
            probe[c] = v
    probe = probe[X.columns]
    south_lhonak = {
        "volume_mcm": 52.9,
        "learned_qp": round(float(10 ** m.predict(probe)[0])),
        "power_law_qp": round(float(10 ** (a + b * probe["log_v0"].iloc[0]))),
        "froehlich_qp": round(float(froehlich_peak(52.9e6))),
        "published_range": "5,000-7,000 m3/s at Chungthang",
    }
    print(f"\nSouth Lhonak, 3 Oct 2023 (52.9 Mm3 released):")
    print(f"  learned model   {south_lhonak['learned_qp']:>7,} m3/s")
    print(f"  power law       {south_lhonak['power_law_qp']:>7,} m3/s")
    print(f"  Froehlich       {south_lhonak['froehlich_qp']:>7,} m3/s")
    print(f"  published       {south_lhonak['published_range']}")

    import joblib
    os.makedirs("data/processed", exist_ok=True)
    joblib.dump({"model": m, "feature_cols": list(X.columns),
                 "power_law": {"a": float(a), "b": float(b)},
                 "results": results, "hma": hma,
                 "n_train": int(len(ytr)), "n_test": int(len(yte)),
                 "source": "Lutzow & Veh (2023) global GLOF database V3.1, CC-BY-4.0"},
                OUT_MODEL)
    json.dump({"results": results, "hma": hma, "south_lhonak": south_lhonak,
               "n_events": int(len(d)), "n_train": int(len(ytr)),
               "n_test": int(len(yte)),
               "power_law": {"a": float(a), "b": float(b)},
               "source": "Lutzow, N. & Veh, G. (2023) Glacier Lake Outburst Flood "
                         "Database V3.1, Zenodo 7924369, CC-BY-4.0"},
              open(OUT_REPORT, "w"), indent=1)
    print(f"\n-> {OUT_MODEL}\n-> {OUT_REPORT}")


if __name__ == "__main__":
    main()
