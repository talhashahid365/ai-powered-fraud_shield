"""
Train the Isolation Forest anomaly detector directly from this platform's
own accumulated transaction history, instead of a synthetic mock CSV.

train_isolation_forest.py (CSV-based) is useful for offline experimentation
and for bootstrapping a model before any real data exists. This script is
what should actually run periodically once the platform has real usage: it
reads straight from the `transactions` table, re-derives the *exact* same
feature vectors the live risk pipeline computes at scoring time
(app/services/risk_service.py::_gather_context), and trains + persists a
fresh model. Keeping the feature logic in one place (this file mirrors it
rather than importing FastAPI/DB session machinery into the request path)
avoids train/serve skew between what the model learned on and what it sees
in production.

Usage (run from backend/, so `app.*` imports resolve):
    cd backend
    python ../ml/training/train_from_database.py --min-rows 200

Requires DATABASE_URL to be configured the same way the backend is
(see backend/.env.example).
"""
import argparse
import os
import sys
from collections import defaultdict
from datetime import timedelta

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

FEATURE_NAMES = [
    "amount",
    "amount_deviation_from_avg",
    "txn_count_last_5min",
    "txn_count_last_10min",
    "txn_count_last_30min",
    "num_devices_used",
    "num_ips_used",
    "is_new_device",
    "is_new_location",
    "account_age_days",
    "is_new_account_high_value",
    "is_unusual_hour",
]


def _engineer_features_for_customer(rows):
    """rows: list of Transaction ORM objects for ONE customer, any order."""
    rows = sorted(rows, key=lambda t: t.transaction_datetime)
    amounts = [t.amount for t in rows]
    avg = float(np.mean(amounts))
    std = float(np.std(amounts)) or 1.0

    devices_seen: set = set()
    locations_seen: set = set()
    ips_seen: set = set()
    feature_rows = []

    for i, txn in enumerate(rows):
        prior = rows[:i]

        is_new_device = bool(txn.device_id) and txn.device_id not in devices_seen
        if txn.device_id:
            devices_seen.add(txn.device_id)

        is_new_location = bool(txn.location) and txn.location not in locations_seen
        if txn.location:
            locations_seen.add(txn.location)

        if txn.ip_address:
            ips_seen.add(txn.ip_address)

        now = txn.transaction_datetime
        count_5 = sum(1 for t in prior if t.transaction_datetime >= now - timedelta(minutes=5))
        count_10 = sum(1 for t in prior if t.transaction_datetime >= now - timedelta(minutes=10))
        count_30 = sum(1 for t in prior if t.transaction_datetime >= now - timedelta(minutes=30))

        is_new_account_high_value = txn.account_age_days <= 7 and txn.amount > max(500.0, avg * 3)

        is_unusual_hour = False
        if len(prior) >= 5:
            hours = [t.transaction_datetime.hour for t in prior]
            mean_hour = sum(hours) / len(hours)
            is_unusual_hour = abs(now.hour - mean_hour) > 6

        feature_rows.append({
            "amount": txn.amount,
            "amount_deviation_from_avg": (txn.amount - avg) / (std + 1e-6),
            "txn_count_last_5min": count_5,
            "txn_count_last_10min": count_10,
            "txn_count_last_30min": count_30,
            "num_devices_used": len(devices_seen),
            "num_ips_used": len(ips_seen),
            "is_new_device": int(is_new_device),
            "is_new_location": int(is_new_location),
            "account_age_days": txn.account_age_days,
            "is_new_account_high_value": int(is_new_account_high_value),
            "is_unusual_hour": int(is_unusual_hour),
        })

    return feature_rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-rows", type=int, default=200,
                         help="Refuse to train on fewer than this many transactions "
                              "(too little data makes Isolation Forest unreliable).")
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--output", type=str, default=None,
                         help="Defaults to app/ai/anomaly_detection.py's MODEL_PATH.")
    args = parser.parse_args()

    # Make `app.*` importable when run from the repo root as well as from backend/.
    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
    sys.path.insert(0, os.path.abspath(backend_dir))

    from app.ai.anomaly_detection import MODEL_PATH
    from app.db.database import SessionLocal
    from app.models.transaction import Transaction

    output_path = args.output or MODEL_PATH

    db = SessionLocal()
    try:
        transactions = db.query(Transaction).all()
    finally:
        db.close()

    if len(transactions) < args.min_rows:
        print(
            f"Only {len(transactions)} transactions in the database (need at least "
            f"{args.min_rows}). Not training -- the app will keep using the heuristic "
            f"fallback until enough real history has accumulated. Use "
            f"train_isolation_forest.py with generated mock data if you want a model "
            f"to experiment with sooner."
        )
        return

    by_customer = defaultdict(list)
    for txn in transactions:
        by_customer[txn.customer_id].append(txn)

    all_feature_rows = []
    for _, rows in by_customer.items():
        all_feature_rows.extend(_engineer_features_for_customer(rows))

    X = np.array([[row[f] for f in FEATURE_NAMES] for row in all_feature_rows], dtype=float)
    print(f"Training on {len(X)} feature rows from {len(transactions)} transactions "
          f"across {len(by_customer)} customers.")

    model = IsolationForest(n_estimators=200, contamination=args.contamination, random_state=42)
    model.fit(X)

    raw_scores = model.decision_function(X)
    score_min = float(raw_scores.min())
    score_max = float(raw_scores.max())
    anomalies = model.predict(X)
    print(f"Flagged {(anomalies == -1).sum()} / {len(anomalies)} as anomalous "
          f"({(anomalies == -1).mean() * 100:.1f}%)")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    joblib.dump({"model": model, "score_min": score_min, "score_max": score_max}, output_path)
    print(f"Saved model (+ calibration bounds) to {output_path}")
    print("Restart the backend (or otherwise re-instantiate AnomalyDetector) to pick it up "
          "-- the model is loaded once per process at import time.")


if __name__ == "__main__":
    main()
