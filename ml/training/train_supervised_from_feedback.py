"""
Train and evaluate a supervised fraud classifier from accumulated analyst feedback.

This is the "long-term direction" flagged in ml/README.md and in the docstring of
evaluation/evaluate_isolation_forest.py: Isolation Forest (the current production model,
see app/ai/anomaly_detection.py) is unsupervised because at first there are no fraud
labels. Once analysts have confirmed/dismissed enough alerts through the Investigation
workflow (app/models/feedback.py), those verdicts ARE labels, and a supervised model can
be trained and evaluated with real precision/recall/AUC -- something the unsupervised
model fundamentally cannot claim.

This script does NOT automatically replace the live model. It trains + evaluates a
RandomForestClassifier against the labeled dataset built by export_feedback_dataset.py and
saves it to disk for review; wiring a supervised model into the live scoring path
(app/ai/anomaly_detection.py / app/ai/risk_engine.py) is a deliberate follow-up decision,
not something to flip on the moment enough rows exist.

Usage (run from backend/, so `app.*` imports resolve):
    cd backend
    python ../ml/training/train_supervised_from_feedback.py --min-feedback 30

Requires DATABASE_URL to be configured the same way the backend is
(see backend/.env.example).
"""
import argparse
import os
import sys

import joblib
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-feedback", type=int, default=30,
                         help="Refuse to train below this many labeled rows, and require at "
                              "least 2 examples of the minority class for cross-validated "
                              "metrics to mean anything.")
    parser.add_argument("--output", type=str, default=None,
                         help="Defaults to ml/models/supervised_feedback_classifier.joblib.")
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
    sys.path.insert(0, os.path.abspath(backend_dir))
    sys.path.insert(0, os.path.dirname(__file__))

    from app.db.database import SessionLocal
    from export_feedback_dataset import build_labeled_dataset

    output_path = args.output or os.path.join(os.path.dirname(__file__), "..", "models", "supervised_feedback_classifier.joblib")
    output_path = os.path.abspath(output_path)

    db = SessionLocal()
    try:
        rows, feature_names = build_labeled_dataset(db)
    finally:
        db.close()

    if len(rows) < args.min_feedback:
        print(
            f"Only {len(rows)} labeled alerts available (need at least {args.min_feedback}). "
            "Not training yet -- keep using the Isolation Forest model "
            "(app/ai/anomaly_detection.py) until analysts have reviewed more alerts through "
            "the Investigation workflow. Re-run this script periodically as feedback accumulates."
        )
        return

    y = np.array([r["label"] for r in rows])
    if y.sum() < 2 or (len(y) - y.sum()) < 2:
        print(
            f"Have {len(rows)} labeled rows, but only {y.sum()} confirmed fraud and "
            f"{len(y) - y.sum()} false positive -- need at least 2 of each for meaningful "
            "cross-validated evaluation. Waiting for more varied feedback before training."
        )
        return

    X = np.array([[r[f] for f in feature_names] for r in rows], dtype=float)

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import (
        precision_score, recall_score, f1_score, roc_auc_score,
        confusion_matrix, classification_report,
    )

    n_splits = min(args.folds, int(y.sum()), int(len(y) - y.sum()))
    n_splits = max(n_splits, 2)
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)

    model = RandomForestClassifier(n_estimators=300, max_depth=8, class_weight="balanced", random_state=42)

    print(f"Cross-validating on {len(rows)} labeled alerts ({int(y.sum())} confirmed fraud, "
          f"{int(len(y) - y.sum())} false positive) with {n_splits}-fold stratified CV...")

    cv_preds = cross_val_predict(model, X, y, cv=cv, method="predict")
    cv_proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]

    print("\n=== Cross-validated evaluation (held-out folds only, not train-on-self) ===")
    print(f"Precision: {precision_score(y, cv_preds, zero_division=0):.3f}")
    print(f"Recall:    {recall_score(y, cv_preds, zero_division=0):.3f}")
    print(f"F1:        {f1_score(y, cv_preds, zero_division=0):.3f}")
    try:
        print(f"ROC-AUC:   {roc_auc_score(y, cv_proba):.3f}")
    except ValueError as e:
        print(f"ROC-AUC:   could not compute ({e})")

    tn, fp, fn, tp = confusion_matrix(y, cv_preds).ravel()
    print(f"\nConfusion matrix (rows=actual, cols=predicted):")
    print(f"                 pred FALSE_POS   pred CONFIRMED_FRAUD")
    print(f"actual FALSE_POS      {tn:>6}              {fp:>6}")
    print(f"actual CONFIRMED_FRAUD {fn:>5}              {tp:>6}")
    print("\n" + classification_report(y, cv_preds, target_names=["FALSE_POSITIVE", "CONFIRMED_FRAUD"], zero_division=0))

    # Fit the final model on ALL labeled data for saving/inspection (the CV metrics above,
    # not this fit, are the honest measure of how it'll generalize).
    model.fit(X, y)
    importances = sorted(zip(feature_names, model.feature_importances_), key=lambda kv: -kv[1])
    print("=== Feature importances (full-data fit) ===")
    for name, imp in importances:
        print(f"  {name:<32} {imp:.3f}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    joblib.dump({"model": model, "feature_names": feature_names}, output_path)
    print(f"\nSaved model to {output_path}.")
    print(
        "This is an offline artifact for review, not yet wired into live scoring. To use it "
        "in production, app/ai/anomaly_detection.py (or a new supervised counterpart) needs "
        "to be updated deliberately to load and serve it, ideally after comparing these "
        "metrics against a held-out period of real alerts."
    )


if __name__ == "__main__":
    main()
