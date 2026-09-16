"""
Training pipeline for the Isolation Forest anomaly detection model.

This script is deliberately standalone (does not import the FastAPI app)
so Person 2 can iterate on the model without spinning up the full backend.
It reads a CSV of historical transactions, engineers the same features
used at inference time (see app/ai/anomaly_detection.py), trains an
IsolationForest, evaluates it, and saves the model to ml/models/.

Usage:
    python train_isolation_forest.py --input ../data/mock_transactions.csv
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib

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


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["transaction_datetime"] = pd.to_datetime(df["transaction_datetime"])
    df = df.sort_values(["customer_id", "transaction_datetime"])

    rows = []
    for customer_id, group in df.groupby("customer_id"):
        amounts = group["amount"].tolist()
        avg = float(np.mean(amounts))
        std = float(np.std(amounts)) or 1.0
        devices_seen: set = set()
        locations_seen: set = set()
        ips_seen: set = set()
        times = group["transaction_datetime"].tolist()
        # Account age is derived the same way the backend derives it: days
        # since this customer's first transaction on the platform (their
        # "created_at"), not a hardcoded constant.
        first_seen = times[0]

        for row in group.itertuples():
            t = row.transaction_datetime
            # Strictly-prior times only. Using `times` (the whole group, past
            # AND future) here would leak information the live pipeline never
            # has at scoring time -- it only ever sees transactions that
            # already happened before the one being scored -- so training on
            # a look-ahead window would teach the model a pattern that can't
            # actually occur in production.
            prior_times = [tt for tt in times if tt < t]

            is_new_device = bool(row.device_id) and row.device_id not in devices_seen
            devices_seen.add(row.device_id)

            is_new_location = bool(row.location) and row.location not in locations_seen
            locations_seen.add(row.location)

            # num_ips_used mirrors app/services/risk_service.py._gather_context:
            # distinct IPs seen across this customer's PRIOR transactions only
            # (not including the current one). Previously this was hardcoded
            # to a constant 1 for every row, which meant the model never saw
            # any real variation in this feature and couldn't learn from it
            # at all -- despite the live pipeline always passing a real,
            # varying value at inference time.
            num_ips_used = len(ips_seen)
            if row.ip_address:
                ips_seen.add(row.ip_address)

            count_5 = sum(1 for tt in prior_times if 0 <= (t - tt).total_seconds() <= 300)
            count_10 = sum(1 for tt in prior_times if 0 <= (t - tt).total_seconds() <= 600)
            count_30 = sum(1 for tt in prior_times if 0 <= (t - tt).total_seconds() <= 1800)

            account_age_days = max(0, (t - first_seen).days)
            is_new_account_high_value = account_age_days <= 7 and row.amount > max(500.0, avg * 3)

            is_unusual_hour = False
            if len(prior_times) >= 5:
                prior_hours = [tt.hour for tt in prior_times]
                mean_hour = sum(prior_hours) / len(prior_hours)
                is_unusual_hour = abs(t.hour - mean_hour) > 6

            rows.append({
                "amount": row.amount,
                "amount_deviation_from_avg": (row.amount - avg) / (std + 1e-6),
                "txn_count_last_5min": count_5,
                "txn_count_last_10min": count_10,
                "txn_count_last_30min": count_30,
                "num_devices_used": len(devices_seen),
                "num_ips_used": num_ips_used,
                "is_new_device": int(is_new_device),
                "is_new_location": int(is_new_location),
                "account_age_days": account_age_days,
                "is_new_account_high_value": int(is_new_account_high_value),
                "is_unusual_hour": int(is_unusual_hour),
            })

    return pd.DataFrame(rows, columns=FEATURE_NAMES)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--output", type=str, default="../models/isolation_forest.joblib")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} raw transactions")

    features_df = engineer_features(df)
    print(f"Engineered {len(features_df)} feature rows with columns: {list(features_df.columns)}")

    X = features_df.values
    model = IsolationForest(n_estimators=200, contamination=args.contamination, random_state=42)
    model.fit(X)

    scores = model.decision_function(X)
    anomalies = model.predict(X)
    score_min = float(scores.min())
    score_max = float(scores.max())
    print(f"Flagged {(anomalies == -1).sum()} / {len(anomalies)} transactions as anomalous "
          f"({(anomalies == -1).mean() * 100:.1f}%)")
    print(f"Score distribution: min={score_min:.3f} max={score_max:.3f} mean={scores.mean():.3f}")
    print("NOTE: this is an unsupervised model evaluated only on separation of "
          "anomalies from normal points. Do not claim precision/recall accuracy "
          "without labeled fraud outcomes (see app/models/feedback.py) for real evaluation.")

    # Persist score_min/score_max alongside the model. app/ai/anomaly_detection.py
    # uses these to scale decision_function output into a 0-100 anomaly score
    # relative to *this* training distribution, instead of assuming a fixed
    # center that doesn't generalize across datasets/contamination settings.
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    joblib.dump({"model": model, "score_min": score_min, "score_max": score_max}, args.output)
    print(f"Saved model (+ calibration bounds) to {args.output}")


if __name__ == "__main__":
    main()
