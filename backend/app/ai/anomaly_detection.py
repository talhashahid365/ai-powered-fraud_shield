"""
ML anomaly detection using Isolation Forest.

This module is intentionally decoupled from the API layer: it only deals
with feature vectors in -> anomaly scores out, so the underlying model can
be swapped or retrained without touching the API/service layer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "models", "isolation_forest.joblib")

FEATURE_NAMES = [
    "amount",
    "amount_deviation_from_avg",   # (amount - customer_avg) / (customer_std + eps)
    "txn_count_last_5min",
    "txn_count_last_10min",
    "txn_count_last_30min",
    "num_devices_used",
    "num_ips_used",
    "is_new_device",                 # 0/1
    "is_new_location",               # 0/1 - location never seen before for this customer
    "account_age_days",
    "is_new_account_high_value",     # 0/1 - high amount from a recently created account
    "is_unusual_hour",               # 0/1 - time-of-day far from customer's usual pattern
]


@dataclass
class TransactionFeatures:
    amount: float
    amount_deviation_from_avg: float
    txn_count_last_5min: int
    txn_count_last_10min: int
    txn_count_last_30min: int
    num_devices_used: int
    num_ips_used: int
    is_new_device: int
    is_new_location: int
    account_age_days: int
    is_new_account_high_value: int
    is_unusual_hour: int

    def to_vector(self) -> np.ndarray:
        return np.array([[getattr(self, f) for f in FEATURE_NAMES]], dtype=float)


class AnomalyDetector:
    """Thin wrapper around a persisted IsolationForest model.

    Alongside the model itself we persist the min/max of
    ``decision_function`` scores observed on the *training* data
    ("calibration bounds"). This matters because ``decision_function``'s
    raw output isn't naturally scaled to 0-100 and its center/spread
    shifts depending on the training data and contamination parameter.
    A fixed formula like ``(0.5 - raw) * 100`` silently assumes a specific
    center (0.5) that doesn't hold in general -- in practice it gave
    ordinary, non-anomalous transactions a baseline score in the 30-40
    range instead of near 0, compressing the whole score into a narrow
    30-65 band and inflating every transaction's contribution to the
    final risk score. Scaling relative to the training distribution's own
    min/max keeps the mapping honest: the most normal transactions in
    training land near 0 and the most anomalous land near 100.
    """

    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
        self._model: IsolationForest | None = None
        self._score_min: float | None = None
        self._score_max: float | None = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.model_path):
            return
        payload = joblib.load(self.model_path)
        if isinstance(payload, dict):
            # Current format: {"model": ..., "score_min": ..., "score_max": ...}
            self._model = payload["model"]
            self._score_min = payload.get("score_min")
            self._score_max = payload.get("score_max")
        else:
            # Backwards compatibility with older model files that stored the
            # bare IsolationForest with no calibration data.
            self._model = payload
            self._score_min = None
            self._score_max = None

    def is_trained(self) -> bool:
        return self._model is not None

    def train(self, X: np.ndarray, contamination: float = 0.05) -> None:
        """Fit a fresh model on historical feature vectors and persist it,
        along with the calibration bounds needed to normalize future scores."""
        model = IsolationForest(
            n_estimators=200,
            contamination=contamination,
            random_state=42,
        )
        model.fit(X)

        raw_scores = model.decision_function(X)
        score_min = float(raw_scores.min())
        score_max = float(raw_scores.max())

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump({"model": model, "score_min": score_min, "score_max": score_max}, self.model_path)

        self._model = model
        self._score_min = score_min
        self._score_max = score_max

    def score(self, features: TransactionFeatures) -> float:
        """
        Return an anomaly score from 0 (normal) to 100 (highly anomalous).

        If no model has been trained yet, falls back to a simple heuristic
        based on amount deviation so the pipeline still produces a usable
        signal in a fresh environment (Phase 1, before a real model is
        trained on historical data).
        """
        if self._model is None:
            return self._heuristic_score(features)

        # IsolationForest.decision_function: higher = more normal.
        raw = float(self._model.decision_function(features.to_vector())[0])

        if self._score_min is not None and self._score_max is not None and self._score_max > self._score_min:
            # Min-max scale against the training distribution's own range,
            # then invert so higher = more anomalous.
            normalized = (self._score_max - raw) / (self._score_max - self._score_min) * 100
        else:
            # Legacy model file with no stored calibration bounds -- fall back
            # to the old fixed-center approximation rather than erroring out.
            normalized = (0.5 - raw) * 100

        return float(np.clip(normalized, 0, 100))

    @staticmethod
    def _heuristic_score(features: TransactionFeatures) -> float:
        score = 0.0
        score += min(40, abs(features.amount_deviation_from_avg) * 10)
        score += min(20, features.txn_count_last_10min * 4)
        score += 15 if features.is_new_device else 0
        score += 15 if features.is_new_location else 0
        score += min(10, features.num_devices_used * 2)
        score += 20 if features.is_new_account_high_value else 0
        score += 10 if features.is_unusual_hour else 0
        return float(min(100.0, score))


# Module-level singleton so the model is loaded once per process.
anomaly_detector = AnomalyDetector()
