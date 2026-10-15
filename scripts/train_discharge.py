"""Train the physics-informed Teesta discharge forecaster.

Generates 12 years of synthetic daily data from the WCN physics model,
builds features (rainfall lags, API, WCN runoff, discharge lags, seasonal),
and trains HistGradientBoosting models for horizons 1–7 days at three
quantile levels (p10, p50, p90).

Usage
-----
    python scripts/train_discharge.py

Output
------
    data/processed/discharge_model.pkl

Replacing synthetic data with real gauge data
---------------------------------------------
    1. Load IMD gridded rainfall (or CHIRPS v2) and CWC/WRIS discharge
       for Teesta at Gajoldoba into a DataFrame with columns:
       date, rain_mm, q_true_m3s
    2. Compute WCN physics features:
         import sys; sys.path.insert(0,'src')
         import wcn
         result = wcn.simulate_daily(df['rain_mm'].tolist())
         df['api'] = result['api']
         df['cn_eff'] = result['cn_eff']
         df['wcn_runoff_mm'] = result['q_direct']
    3. Call discharge.train(df)
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import discharge

def main():
    t0 = time.time()
    print("Training physics-informed Teesta discharge forecaster")
    print("=" * 56)
    bundle = discharge.train()
    elapsed = time.time() - t0
    print()
    print(f"Done in {elapsed:.1f}s")
    print()
    print("Top 10 features by importance:")
    for item in bundle["importance"][:10]:
        bar = "█" * int(item["importance"] * 200)
        print(f"  {item['feature']:25s}  {bar}  {item['importance']:.4f}")
    print()
    print("Forecast accuracy by horizon:")
    for h, m in bundle["metrics"].items():
        nse_bar = "▓" * int(max(0, m["nse"]) * 20)
        print(f"  +{h}d: NSE={m['nse']:.3f} {nse_bar}  "
              f"KGE={m['kge']:.3f}  RMSE={m['rmse']:.0f} m³/s")

if __name__ == "__main__":
    main()
