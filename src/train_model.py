"""Trains the landslide risk classifier and reports leakage-free validation.

Two candidate models are cross-validated and the better one is kept:
Random Forest, and histogram gradient boosting (the same family as the
XGBoost model NASA's LHASA v2 uses for global landslide nowcasting).

Validation is 5-fold stratified cross-validation. Every score reported here
comes from a fold that did not see that row during training, so the hindcast
numbers are honest out-of-sample predictions rather than memorisation.
"""

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from config import FEATURE_COLUMNS, MODEL_PATH, TRAINING_CSV

HINDCAST_CSV = "data/processed/hindcast_results.csv"
IMPORTANCE_CSV = "data/processed/feature_importance.csv"


def candidates():
    return {
        "random_forest": RandomForestClassifier(
            n_estimators=400, max_depth=8, class_weight="balanced", random_state=42
        ),
        "gradient_boosting": HistGradientBoostingClassifier(
            max_iter=300, max_depth=6, learning_rate=0.08, random_state=42
        ),
    }


def main():
    df = pd.read_csv(TRAINING_CSV)
    medians = df[FEATURE_COLUMNS].median()
    X = df[FEATURE_COLUMNS].fillna(medians)
    y = df["label"]

    print(f"Training rows: {len(df)}  ({y.sum()} landslides, {len(y) - y.sum()} non-events)")
    print(f"Features: {len(FEATURE_COLUMNS)}")
    print("Validation: 5-fold stratified cross-validation\n")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    results = {}
    for name, model in candidates().items():
        probs = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
        auc = roc_auc_score(y, probs)
        results[name] = (auc, probs, model)
        print(f"  {name:<20} ROC-AUC {auc:.4f}")

    best_name = max(results, key=lambda k: results[k][0])
    best_auc, probs, best_model = results[best_name]
    print(f"\nSelected: {best_name} (ROC-AUC {best_auc:.4f})\n")

    preds = (probs >= 0.5).astype(int)
    print("=== Cross-validated performance ===")
    print(classification_report(y, preds, target_names=["no landslide", "landslide"]))

    # Hindcast: how many real events would have been flagged in advance?
    df["predicted_probability"] = probs
    events = df[df["label"] == 1].copy()
    flagged = (events["predicted_probability"] >= 0.5).sum()
    print("=== Hindcast on real landslides ===")
    print(
        f"{flagged}/{len(events)} real events flagged >=50% "
        f"({flagged / len(events) * 100:.1f}%)\n"
    )

    for label, lo, hi in [
        ("caught with high confidence (>=75%)", 0.75, 1.01),
        ("caught (50-75%)", 0.50, 0.75),
        ("missed (25-50%)", 0.25, 0.50),
        ("missed badly (<25%)", 0.0, 0.25),
    ]:
        n = ((events["predicted_probability"] >= lo) & (events["predicted_probability"] < hi)).sum()
        print(f"  {label:<38} {n:>4}  ({n / len(events) * 100:4.1f}%)")

    cols = ["id", "date", "location", "state", "lat", "lon", "predicted_probability"]
    for extra in ("fatalities", "trigger", "type", "location_accuracy"):
        if extra in events.columns:
            cols.append(extra)
    events.sort_values("predicted_probability", ascending=False)[cols].to_csv(
        HINDCAST_CSV, index=False
    )
    print(f"\nHindcast detail -> {HINDCAST_CSV}")

    # Fit on everything, then measure which features actually carry the signal.
    best_model.fit(X, y)
    perm = permutation_importance(best_model, X, y, n_repeats=8, random_state=42, n_jobs=-1)
    importance = (
        pd.DataFrame(
            {
                "feature": FEATURE_COLUMNS,
                "importance": perm.importances_mean,
                "std": perm.importances_std,
            }
        )
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
    importance.to_csv(IMPORTANCE_CSV, index=False)

    print("\n=== Feature importance (permutation) ===")
    for _, r in importance.iterrows():
        bar = "#" * max(int(r["importance"] * 260), 0)
        print(f"  {r['feature']:<26} {r['importance']:.4f}  {bar}")

    joblib.dump(
        {
            "model": best_model,
            "model_name": best_name,
            "feature_cols": FEATURE_COLUMNS,
            "medians": medians.to_dict(),
            "cv_auc": float(best_auc),
            "hindcast_rate": float(flagged / len(events)),
        },
        MODEL_PATH,
    )
    print(f"\nModel -> {MODEL_PATH}")


if __name__ == "__main__":
    main()
