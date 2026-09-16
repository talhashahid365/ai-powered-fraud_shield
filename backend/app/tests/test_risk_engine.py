from app.ai.risk_engine import calculate_final_risk, determine_decision, determine_risk_level
from app.models.enums import Decision, RiskLevel


def test_risk_level_boundaries():
    assert determine_risk_level(10) == RiskLevel.LOW
    assert determine_risk_level(50) == RiskLevel.MEDIUM
    assert determine_risk_level(90) == RiskLevel.HIGH


def test_decision_never_auto_blocks_by_default():
    assert determine_decision(RiskLevel.HIGH, allow_auto_block=False) == Decision.REVIEW


def test_calculate_final_risk_produces_high_for_bad_signals():
    result = calculate_final_risk(
        rule_score=90, anomaly_score=85, customer_risk_score=80, suspicious_ratio=0.5,
        triggered_rules=["High amount"], is_new_device=True, is_new_location=True,
        amount=5000, customer_avg_amount=100,
    )
    assert result.risk_level == RiskLevel.HIGH
    assert result.decision == Decision.REVIEW
