"""
Risk Decision Engine.

Combines:
    - Rule score        (from rules_engine.evaluate_rules)
    - ML anomaly score   (from anomaly_detection.anomaly_detector)
    - Customer behavior score (derived from Customer history)

into one final 0-100 risk score, a risk level (LOW/MEDIUM/HIGH), and a
decision (APPROVE/REVIEW/BLOCK).

Weighting is intentionally simple and documented here so it can be tuned:

    final_score = 0.35 * rule_score + 0.40 * anomaly_score + 0.25 * behavior_score

Decisions:
    - HIGH risk with a hard-triggered rule marked as "block" -> BLOCK
      (the platform never auto-blocks unless explicitly configured to)
    - HIGH risk otherwise -> REVIEW
    - MEDIUM risk -> REVIEW
    - LOW risk -> APPROVE
"""
from dataclasses import dataclass

from app.core.config import settings
from app.models.enums import Decision, RiskLevel

RULE_WEIGHT = 0.35
ANOMALY_WEIGHT = 0.40
BEHAVIOR_WEIGHT = 0.25


@dataclass
class RiskResult:
    risk_score: float
    risk_level: RiskLevel
    decision: Decision
    rule_score: float
    anomaly_score: float
    behavior_score: float
    triggered_rules: list[str]
    risk_factors: list[str]


def compute_behavior_score(customer_risk_score: float, suspicious_ratio: float) -> float:
    """
    Blend the customer's existing longer-term risk score with the ratio of
    suspicious-to-total transactions historically observed for them.
    """
    ratio_component = min(100.0, suspicious_ratio * 100 * 3)
    return float(min(100.0, 0.6 * customer_risk_score + 0.4 * ratio_component))


def determine_risk_level(score: float) -> RiskLevel:
    if score <= settings.RISK_LOW_MAX:
        return RiskLevel.LOW
    if score <= settings.RISK_MEDIUM_MAX:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


def determine_decision(level: RiskLevel, allow_auto_block: bool = False) -> Decision:
    if level == RiskLevel.HIGH:
        return Decision.BLOCK if allow_auto_block else Decision.REVIEW
    if level == RiskLevel.MEDIUM:
        return Decision.REVIEW
    return Decision.APPROVE


def build_risk_factors(
    triggered_rules: list[str],
    anomaly_score: float,
    is_new_device: bool,
    is_new_location: bool,
    is_new_account_high_value: bool,
    is_unusual_hour: bool,
    amount: float,
    customer_avg_amount: float,
    customer_min_amount: float | None = None,
    customer_max_amount: float | None = None,
    velocity_count: int = 0,
    velocity_window_minutes: int = 5,
) -> list[str]:
    factors: list[str] = []
    if customer_avg_amount and amount > customer_avg_amount * 3:
        if customer_min_amount is not None and customer_max_amount is not None and customer_min_amount < customer_max_amount:
            factors.append(
                f"Customer normally spends ${customer_min_amount:,.2f}-${customer_max_amount:,.2f}, "
                f"but this transaction is ${amount:,.2f}."
            )
        else:
            factors.append(
                f"Transaction amount (${amount:,.2f}) is far above the customer's average (${customer_avg_amount:,.2f})."
            )
    if is_new_device:
        factors.append("Transaction originated from a device never seen for this customer before.")
    if is_new_location:
        factors.append("Transaction originated from a location different from the customer's previous activity.")
    if is_new_account_high_value:
        factors.append("High-value transaction from an account that was created only recently.")
    if is_unusual_hour:
        factors.append("Transaction occurred at a time of day unusual for this customer's normal activity pattern.")
    # Named explicitly (rather than only surfacing as "Rule triggered: <name>") so a
    # business user sees the concrete count/window that drove the flag, e.g.
    # "3 transactions occurred within 5 minutes." instead of an opaque rule name.
    if velocity_count >= 3:
        factors.append(
            f"{velocity_count} transactions occurred within {velocity_window_minutes} minutes for this customer."
        )
    if anomaly_score >= 60:
        factors.append(f"ML anomaly model flagged this transaction (anomaly score {anomaly_score:.0f}/100).")
    factors.extend(f"Rule triggered: {name}" for name in triggered_rules)
    return factors


def calculate_final_risk(
    rule_score: float,
    anomaly_score: float,
    customer_risk_score: float,
    suspicious_ratio: float,
    triggered_rules: list[str],
    is_new_device: bool,
    amount: float,
    customer_avg_amount: float,
    is_new_location: bool = False,
    is_new_account_high_value: bool = False,
    is_unusual_hour: bool = False,
    allow_auto_block: bool = False,
    customer_min_amount: float | None = None,
    customer_max_amount: float | None = None,
    velocity_count: int = 0,
    velocity_window_minutes: int = 5,
) -> RiskResult:
    behavior_score = compute_behavior_score(customer_risk_score, suspicious_ratio)

    final_score = (
        RULE_WEIGHT * rule_score
        + ANOMALY_WEIGHT * anomaly_score
        + BEHAVIOR_WEIGHT * behavior_score
    )
    final_score = float(min(100.0, max(0.0, final_score)))

    level = determine_risk_level(final_score)
    decision = determine_decision(level, allow_auto_block=allow_auto_block)
    risk_factors = build_risk_factors(
        triggered_rules, anomaly_score, is_new_device, is_new_location,
        is_new_account_high_value, is_unusual_hour, amount, customer_avg_amount,
        customer_min_amount=customer_min_amount,
        customer_max_amount=customer_max_amount,
        velocity_count=velocity_count,
        velocity_window_minutes=velocity_window_minutes,
    )

    return RiskResult(
        risk_score=final_score,
        risk_level=level,
        decision=decision,
        rule_score=rule_score,
        anomaly_score=anomaly_score,
        behavior_score=behavior_score,
        triggered_rules=triggered_rules,
        risk_factors=risk_factors,
    )
