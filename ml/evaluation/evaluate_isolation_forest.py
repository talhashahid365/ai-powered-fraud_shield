"""
Basic evaluation for a trained Isolation Forest anomaly model.

This is unsupervised, so there is no ground-truth fraud label to compute
precision/recall against (real fraud labels come later via analyst feedback,
see backend/app/models/feedback.py -- once enough of those accumulate, a
supervised classifier becomes worth training and evaluating with real
precision/recall/AUC). Until then, this script reports what CAN be checked
without labels:

  1. Score distribution sanity (is the calibrated 0-100 range actually being
     used, or is everything bunched at one end?)
  2. Agreement with the simple heuristic fallback (app/ai/anomaly_detection.py
     ::AnomalyDetector._heuristic_score) -- if the trained model and the
     heuristic wildly disagree on which transactions look risky, that's
     worth a closer look before trusting the model in production.
  3. Feature importance via permutation: which inputs actually move the
     anomaly score? Isolation Forest doesn't have coefficients like a linear
     model, so permutation importance (how much shuffling one column changes
     the average score) is the practical way to sanity-check that the model
     leans on sensible signals (amount deviation, velocity, new device/
     location) rather than something spurious.

Usage:
    python evaluate_isolation_forest.py --input ../data/mock_transactions.csv \
        --model ../models/isolation_forest.joblib
"""
import argparse
import os
import sys

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "training"))
from train_isolation_forest import FEATURE_NAMES, engineer_features  # noqa: E402


def load_model(path: str):
    payload = joblib.load(path)
    if isinstance(payload, dict):
        return payload["model"], payload.get("score_min"), payload.get("score_max")
    return payload, None, None


def normalize(raw: np.ndarray, score_min: float | None, score_max: float | None) -> np.ndarray:
    if score_min is not None and score_max is not None and score_max > score_min:
        return np.clip((score_max - raw) / (score_max - score_min) * 100, 0, 100)
    return np.clip((0.5 - raw) * 100, 0, 100)


def heuristic_scores(features_df: pd.DataFrame) -> np.ndarray:
    scores = np.zeros(len(features_df))
    scores += np.minimum(40, np.abs(features_df["amount_deviation_from_avg"]) * 10)
    scores += np.minimum(20, features_df["txn_count_last_10min"] * 4)
    scores += np.where(features_df["is_new_device"] == 1, 15, 0)
    scores += np.where(features_df["is_new_location"] == 1, 15, 0)
    scores += np.minimum(10, features_df["num_devices_used"] * 2)
    scores += np.where(features_df["is_new_account_high_value"] == 1, 20, 0)
    scores += np.where(features_df["is_unusual_hour"] == 1, 10, 0)
    return np.minimum(100.0, scores)


def permutation_importance(model, X: np.ndarray, score_min, score_max, n_repeats: int = 3) -> dict:
    rng = np.random.default_rng(42)
    baseline = normalize(model.decision_function(X), score_min, score_max)
    importances = {}
    for i, name in enumerate(FEATURE_NAMES):
        deltas = []
        for _ in range(n_repeats):
            X_perm = X.copy()
            rng.shuffle(X_perm[:, i])
            perturbed = normalize(model.decision_function(X_perm), score_min, score_max)
            deltas.append(np.mean(np.abs(perturbed - baseline)))
        importances[name] = float(np.mean(deltas))
    return importances


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--model", type=str, default="../models/isolation_forest.joblib")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"No model found at {args.model}. Train one first with train_isolation_forest.py.")
        return

    df = pd.read_csv(args.input)
    features_df = engineer_features(df)
    X = features_df.values

    model, score_min, score_max = load_model(args.model)
    ml_scores = normalize(model.decision_function(X), score_min, score_max)
    heur_scores = heuristic_scores(features_df)

    print("=== Score distribution (ML model, 0-100) ===")
    print(f"min={ml_scores.min():.1f} p25={np.percentile(ml_scores, 25):.1f} "
          f"median={np.median(ml_scores):.1f} p75={np.percentile(ml_scores, 75):.1f} "
          f"p95={np.percentile(ml_scores, 95):.1f} max={ml_scores.max():.1f}")

    corr = float(np.corrcoef(ml_scores, heur_scores)[0, 1])
    print(f"\n=== Agreement with heuristic fallback ===")
    print(f"Pearson correlation between ML score and heuristic score: {corr:.2f}")
    print("(Expect a positive, moderate-to-strong correlation -- both look at the same "
          "underlying signals. A near-zero or negative correlation would suggest the "
          "trained model isn't picking up on the same fraud patterns the rules-based "
          "heuristic was designed around, and is worth investigating before relying on it.)")

    print("\n=== Permutation importance (avg |score change| when a feature is shuffled) ===")
    importances = permutation_importance(model, X, score_min, score_max)
    for name, imp in sorted(importances.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<32} {imp:6.2f}")


if __name__ == "__main__":
    main()
