"""
Unit coverage for app/ai/anomaly_detection.py -- previously this module had
no dedicated tests at all, even though it produces a score that drives 40%
of the final risk score (see app/ai/risk_engine.py).

These tests don't touch the FastAPI app or a database; they exercise
AnomalyDetector directly against small, hand-built feature vectors and a
model trained on-the-fly in a temp directory, so they run fast and don't
depend on any shipped model artifact.
"""
import numpy as np

from app.ai.anomaly_detection import AnomalyDetector, TransactionFeatures, FEATURE_NAMES


def _features(**overrides) -> TransactionFeatures:
    base = dict(
        amount=50.0,
        amount_deviation_from_avg=0.0,
        txn_count_last_5min=0,
        txn_count_last_10min=0,
        txn_count_last_30min=0,
        num_devices_used=1,
        num_ips_used=1,
        is_new_device=0,
        is_new_location=0,
        account_age_days=365,
        is_new_account_high_value=0,
        is_unusual_hour=0,
    )
    base.update(overrides)
    return TransactionFeatures(**base)


def test_to_vector_matches_declared_feature_order():
    f = _features(amount=123.0)
    vector = f.to_vector()
    assert vector.shape == (1, len(FEATURE_NAMES))
    assert vector[0][FEATURE_NAMES.index("amount")] == 123.0


def test_untrained_detector_uses_heuristic_fallback(tmp_path):
    detector = AnomalyDetector(model_path=str(tmp_path / "does_not_exist.joblib"))
    assert detector.is_trained() is False

    normal = _features()
    risky = _features(
        amount_deviation_from_avg=6.0,
        txn_count_last_10min=5,
        is_new_device=1,
        is_new_location=1,
        is_new_account_high_value=1,
        is_unusual_hour=1,
    )
    normal_score = detector.score(normal)
    risky_score = detector.score(risky)

    assert 0 <= normal_score <= 100
    assert 0 <= risky_score <= 100
    assert risky_score > normal_score


def _make_training_matrix(n_normal=150, n_outliers=10) -> np.ndarray:
    rng = np.random.default_rng(42)
    normal = rng.normal(loc=0.0, scale=1.0, size=(n_normal, len(FEATURE_NAMES)))
    normal[:, FEATURE_NAMES.index("amount")] = rng.normal(50, 10, n_normal)
    normal = np.clip(normal, 0, None)

    outliers = rng.normal(loc=0.0, scale=1.0, size=(n_outliers, len(FEATURE_NAMES)))
    outliers[:, FEATURE_NAMES.index("amount")] = rng.normal(5000, 500, n_outliers)
    outliers[:, FEATURE_NAMES.index("amount_deviation_from_avg")] = 8.0
    outliers[:, FEATURE_NAMES.index("is_new_device")] = 1
    outliers[:, FEATURE_NAMES.index("is_new_location")] = 1

    return np.vstack([normal, outliers])


def test_train_persists_model_and_calibration(tmp_path):
    model_path = str(tmp_path / "isolation_forest.joblib")
    detector = AnomalyDetector(model_path=model_path)
    assert detector.is_trained() is False

    X = _make_training_matrix()
    detector.train(X, contamination=0.1)

    assert detector.is_trained() is True
    assert detector._score_min is not None
    assert detector._score_max is not None
    assert detector._score_max > detector._score_min

    # A fresh detector instance loading from disk should behave the same way
    # (this is effectively what happens on backend process restart).
    reloaded = AnomalyDetector(model_path=model_path)
    assert reloaded.is_trained() is True
    assert reloaded._score_min == detector._score_min
    assert reloaded._score_max == detector._score_max


def test_trained_model_scores_are_calibrated_and_discriminative(tmp_path):
    model_path = str(tmp_path / "isolation_forest.joblib")
    detector = AnomalyDetector(model_path=model_path)
    detector.train(_make_training_matrix(), contamination=0.1)

    typical = _features(amount=50.0, amount_deviation_from_avg=0.0)
    extreme = _features(
        amount=6000.0,
        amount_deviation_from_avg=8.0,
        is_new_device=1,
        is_new_location=1,
        txn_count_last_5min=5,
        txn_count_last_10min=6,
    )

    typical_score = detector.score(typical)
    extreme_score = detector.score(extreme)

    assert 0 <= typical_score <= 100
    assert 0 <= extreme_score <= 100
    # The whole point of calibrating against the training distribution's own
    # min/max is that a typical point should land well below an extreme one,
    # not be squeezed into the same narrow mid-range band.
    assert extreme_score > typical_score
    assert extreme_score >= 60
    assert typical_score <= 40


def test_legacy_model_file_without_calibration_still_loads(tmp_path):
    """Older model files saved the bare IsolationForest with no calibration
    dict. AnomalyDetector must still load and score with these without
    raising, falling back to the old fixed-center approximation."""
    import joblib
    from sklearn.ensemble import IsolationForest

    X = _make_training_matrix()
    legacy_model = IsolationForest(n_estimators=50, contamination=0.1, random_state=0).fit(X)
    model_path = tmp_path / "legacy.joblib"
    joblib.dump(legacy_model, model_path)

    detector = AnomalyDetector(model_path=str(model_path))
    assert detector.is_trained() is True
    score = detector.score(_features())
    assert 0 <= score <= 100
