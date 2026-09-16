"""
Turn analyst feedback (app/models/feedback.py: CONFIRMED_FRAUD / FALSE_POSITIVE) into a
labeled dataset for training/evaluating a supervised fraud classifier.

Every Feedback row is an analyst's ground-truth verdict on one alert, which traces back to
exactly one transaction (Feedback.alert_id -> Alert.transaction_id -> Transaction). This
script re-derives that transaction's feature vector using the *same* feature engineering as
train_from_database.py (imported from there, not duplicated, to avoid train/serve/label
skew), attaches the analyst's verdict as a 0/1 label, and writes the result to a CSV that
train_supervised_from_feedback.py (or any other tool) can train against.

Usage (run from backend/, so `app.*` imports resolve):
    cd backend
    python ../ml/training/export_feedback_dataset.py --output ../ml/data/feedback_labeled.csv

Requires DATABASE_URL to be configured the same way the backend is
(see backend/.env.example).
"""
import argparse
import csv
import os
import sys
from collections import defaultdict


def build_labeled_dataset(db):
    """
    Returns (rows, feature_names) where each row is a dict of
    {feature columns..., label, transaction_id, customer_id, alert_id, analyst_id, feedback_created_at}.

    label is 1 for CONFIRMED_FRAUD, 0 for FALSE_POSITIVE.
    """
    # Imported lazily / from here (not top-level) so this module can also be imported by
    # train_supervised_from_feedback.py without forcing sys.path setup twice.
    from app.models.alert import Alert
    from app.models.enums import FeedbackResult
    from app.models.feedback import Feedback
    from app.models.transaction import Transaction
    from train_from_database import FEATURE_NAMES, _engineer_features_for_customer

    feedback_rows = (
        db.query(Feedback, Alert)
        .join(Alert, Feedback.alert_id == Alert.id)
        .all()
    )

    if not feedback_rows:
        return [], FEATURE_NAMES

    # feedback.alert_id is unique (see app/models/feedback.py), so this is naturally
    # one label per alert / per transaction already -- no de-duplication needed.
    label_by_txn_id: dict[str, tuple] = {}
    for feedback, alert in feedback_rows:
        label_by_txn_id[alert.transaction_id] = (feedback, alert)

    target_txn_ids = set(label_by_txn_id.keys())

    # Feature engineering is per-customer and history-dependent (e.g. "transactions in the
    # last 5 minutes"), so - just like train_from_database.py - we have to load each
    # labeled transaction's *entire* customer history, not just the labeled row itself.
    customer_ids = {alert.customer_id for _, alert in label_by_txn_id.values()}
    all_customer_txns = (
        db.query(Transaction).filter(Transaction.customer_id.in_(customer_ids)).all()
    )
    by_customer = defaultdict(list)
    for txn in all_customer_txns:
        by_customer[txn.customer_id].append(txn)

    dataset_rows = []
    for customer_id, rows in by_customer.items():
        rows_sorted = sorted(rows, key=lambda t: t.transaction_datetime)
        feature_rows = _engineer_features_for_customer(rows_sorted)
        for txn, feature_row in zip(rows_sorted, feature_rows):
            if txn.id not in target_txn_ids:
                continue
            feedback, alert = label_by_txn_id[txn.id]
            out_row = dict(feature_row)
            out_row["label"] = 1 if feedback.actual_result == FeedbackResult.CONFIRMED_FRAUD else 0
            out_row["transaction_id"] = txn.transaction_id
            out_row["customer_id"] = customer_id
            out_row["alert_id"] = alert.id
            out_row["analyst_id"] = feedback.analyst_id
            out_row["feedback_created_at"] = feedback.created_at.isoformat()
            dataset_rows.append(out_row)

    return dataset_rows, FEATURE_NAMES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=None,
                         help="Defaults to ml/data/feedback_labeled.csv relative to this script.")
    args = parser.parse_args()

    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
    sys.path.insert(0, os.path.abspath(backend_dir))
    sys.path.insert(0, os.path.dirname(__file__))  # for `from train_from_database import ...`

    from app.db.database import SessionLocal

    output_path = args.output or os.path.join(os.path.dirname(__file__), "..", "data", "feedback_labeled.csv")
    output_path = os.path.abspath(output_path)

    db = SessionLocal()
    try:
        rows, feature_names = build_labeled_dataset(db)
    finally:
        db.close()

    if not rows:
        print(
            "No analyst feedback found yet (app.models.feedback.Feedback is empty). "
            "Nothing to export -- once analysts start confirming/dismissing alerts in the "
            "Investigation workflow, re-run this script."
        )
        return

    fraud_count = sum(r["label"] for r in rows)
    print(f"Exporting {len(rows)} labeled rows ({fraud_count} confirmed fraud, "
          f"{len(rows) - fraud_count} false positive) to {output_path}")

    if fraud_count == 0 or fraud_count == len(rows):
        print(
            "WARNING: every label is the same class. A classifier trained on this alone "
            "would be useless (and un-evaluable) -- wait for feedback covering both outcomes "
            "before training with train_supervised_from_feedback.py."
        )

    fieldnames = feature_names + ["label", "transaction_id", "customer_id", "alert_id", "analyst_id", "feedback_created_at"]
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("Done.")


if __name__ == "__main__":
    main()
