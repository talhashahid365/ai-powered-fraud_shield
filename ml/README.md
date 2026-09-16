# AI Anomaly Detection

## What's implemented

**Isolation Forest** (`app/ai/anomaly_detection.py`, trained by
`training/train_isolation_forest.py` or `training/train_from_database.py`)
is the production anomaly detector. It's unsupervised, which fits this
problem well: at this stage the platform has transaction data but no
reliable fraud labels (a "CONFIRMED_FRAUD" only exists once an analyst
reviews an alert via `app/models/feedback.py`), so a model that doesn't
need labels to train is the right starting point. It scores each
transaction's 12-feature vector (amount, deviation from the customer's own
average, velocity counts, new device/location flags, account age, etc.)
and returns 0-100, which feeds into `app/ai/risk_engine.py` at a 40% weight
alongside the rules engine (35%) and customer behavior score (25%).

Score calibration: `decision_function`'s raw output isn't naturally scaled
to 0-100, and its center/spread depends on the training data and
contamination setting. Both training scripts persist the min/max raw score
seen during training alongside the model, and `AnomalyDetector.score()`
min-max scales against those bounds. This keeps "normal" transactions near
0 and "anomalous" ones near 100, rather than assuming a fixed center that
silently drifts once the model is retrained on different data.

**Statistical anomaly detection** is also present, just not as a separate
model: `amount_deviation_from_avg` in the feature vector is a per-customer
z-score-style deviation (`(amount - customer_avg) / customer_std`), and
`risk_engine.build_risk_factors` surfaces it directly to business users
("Customer normally spends $X-$Y, but this transaction is $Z"). Isolation
Forest effectively learns nonlinear combinations of this statistical
signal with the others rather than thresholding it in isolation.

**Fallback heuristic**: if no model has been trained yet (fresh environment,
or too little data — `train_from_database.py` refuses to train below
`--min-rows`, default 200), `AnomalyDetector._heuristic_score` produces a
hand-weighted score from the same features so the pipeline still works
end-to-end. This is explicitly not "the ML component" — it's scaffolding so
`risk_score` isn't zero/undefined before a model exists.

## What was experimented with / considered, and why not (yet)

- **Clustering** (e.g. k-means or DBSCAN distance-to-centroid as an anomaly
  signal): reasonable alternative to Isolation Forest for this data, but
  doesn't have an obvious advantage here — clusters would mostly just
  re-discover "high amount" and "new device/location" as separating
  dimensions, which Isolation Forest already isolates directly and more
  efficiently on mixed continuous/binary features. Worth revisiting if a
  need emerges to explicitly group similar *fraud rings* (shared
  device/IP clusters) rather than score individual transactions — that's
  closer to what `DEVICE_SHARING`/`IP_SHARING` rules in
  `app/ai/rules_engine.py` already do with explicit joins instead.
- **Classification models** (e.g. logistic regression / gradient boosting
  trained to predict fraud directly): now implemented, see "Feedback-driven
  supervised model" below. It was withheld until there was labeled data to
  train and evaluate it against, to avoid a model with fabricated-looking
  metrics.

`evaluation/evaluate_isolation_forest.py` reports what CAN be checked
without labels today (score distribution, agreement with the heuristic,
permutation feature importance) and calls out where labeled evaluation
should replace it.

## Feedback-driven supervised model (model improvement over time)

Every alert an analyst resolves via the Investigation page (Confirm Fraud /
False Positive) writes a row to `feedback` (`backend/app/models/feedback.py`,
one label per alert). That's real ground truth, and two scripts turn it into
model-improvement data:

- `training/export_feedback_dataset.py` — joins `feedback` back to the
  flagged transaction, re-derives its feature vector with the *same*
  feature engineering `train_from_database.py` uses (no train/serve/label
  skew), and writes a labeled CSV to `data/feedback_labeled.csv`
  (1 = confirmed fraud, 0 = false positive).
- `training/train_supervised_from_feedback.py` — loads that same labeled
  data, trains a `RandomForestClassifier`, and reports **cross-validated**
  precision/recall/F1/ROC-AUC plus a confusion matrix and feature
  importances. Refuses to run below `--min-feedback` rows (default 30) or
  without at least 2 examples of each outcome, since evaluation metrics on
  a handful of one-sided labels aren't meaningful. Saves the fitted model
  to `models/supervised_feedback_classifier.joblib`.

Both are read-only with respect to the live pipeline: they save an offline
model for review. Isolation Forest stays the production model
(`app/ai/anomaly_detection.py`) until someone deliberately decides, based
on these metrics, to wire the supervised model into `risk_engine.py`
instead of or alongside it.

The backend also exposes `GET /api/reports/model-feedback-summary`, which
reports alert precision (share of reviewed alerts that were real fraud),
broken down by severity and by week — a lighter-weight way to see whether
there's enough feedback yet to be worth running the training script, without
leaving the app.

Run periodically (e.g. alongside `train_from_database.py`), from `backend/`:
```
python ../ml/training/export_feedback_dataset.py
python ../ml/training/train_supervised_from_feedback.py --min-feedback 30
```

## Retraining

Two entry points, both persist to `models/isolation_forest.joblib`:

- `training/train_isolation_forest.py --input <csv>` — trains from a CSV
  (e.g. `data/generate_mock_transactions.py` output). Good for offline
  experimentation and bootstrapping a model before real usage exists.
- `training/train_from_database.py` — trains from this platform's actual
  `transactions` table, re-deriving the same features the live pipeline
  computes at scoring time. This is what should run periodically once
  there's real traffic ("learn from historical transaction data" in
  production, not synthetic data). Refuses to train below `--min-rows`
  transactions (default 200) since Isolation Forest is unreliable on very
  little data.

Either way, the backend picks up a newly trained model on next process
restart (`AnomalyDetector` loads it once, at import time).
