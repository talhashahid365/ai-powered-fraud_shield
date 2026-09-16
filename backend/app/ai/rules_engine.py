"""
Configurable fraud rules engine.

Rules are stored in the `rules` table (see app.models.rule.Rule) so that
admins can create/edit/enable/disable them without a code deployment.

Each rule evaluator receives:
    - the current transaction (as a dict of relevant fields)
    - recent transactions for the same customer/device/ip (context)
    - the rule's `configuration` dict

and returns True/False (triggered or not).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.rule import Rule
from app.models.transaction import Transaction


@dataclass
class RuleContext:
    """Everything a rule evaluator might need, pre-fetched once per transaction."""
    transaction: dict[str, Any]
    recent_customer_transactions: list[Transaction] = field(default_factory=list)
    same_device_customer_ids: set[str] = field(default_factory=set)
    same_ip_customer_ids: set[str] = field(default_factory=set)


def rule_amount_threshold(ctx: RuleContext, config: dict) -> bool:
    threshold = config.get("threshold", 5000)
    return ctx.transaction["amount"] > threshold


def rule_velocity(ctx: RuleContext, config: dict) -> bool:
    """More than N transactions within M minutes for the same customer.

    `ctx.recent_customer_transactions` holds only *prior* transactions (the
    current transaction being scored is excluded by the caller). So the
    current transaction is itself the "+1" in the window: if there are
    already `max_count` prior transactions in the window, this transaction
    makes `max_count + 1`, i.e. "more than `max_count`" total. Comparing
    with `>=` here (rather than `>`) accounts for that +1 without needing
    to touch the query that builds `recent_customer_transactions`.
    """
    max_count = config.get("max_count", 5)
    window_minutes = config.get("window_minutes", 10)
    now = ctx.transaction["transaction_datetime"]
    window_start = now - timedelta(minutes=window_minutes)
    count = sum(1 for t in ctx.recent_customer_transactions if t.transaction_datetime >= window_start)
    return count >= max_count


def rule_new_device_high_value(ctx: RuleContext, config: dict) -> bool:
    threshold = config.get("threshold", 1000)
    is_new_device = ctx.transaction.get("is_new_device", False)
    return is_new_device and ctx.transaction["amount"] > threshold


def rule_new_account_high_value(ctx: RuleContext, config: dict) -> bool:
    """A high-value transaction from an account created only recently."""
    max_age_days = config.get("max_age_days", 7)
    threshold = config.get("threshold", 500)
    account_age = ctx.transaction.get("account_age_days", 9999)
    return account_age <= max_age_days and ctx.transaction["amount"] > threshold


def rule_device_sharing(ctx: RuleContext, config: dict) -> bool:
    min_customers = config.get("min_customers", 2)
    return len(ctx.same_device_customer_ids) >= min_customers


def rule_ip_sharing(ctx: RuleContext, config: dict) -> bool:
    min_customers = config.get("min_customers", 3)
    return len(ctx.same_ip_customer_ids) >= min_customers


def rule_location_change(ctx: RuleContext, config: dict) -> bool:
    """
    True "new location" detection: has this customer ever transacted from this
    location before (across their whole recent history), not just whether it
    differs from their single most recent transaction. A customer alternating
    between two known cities should NOT trigger this on every switch.
    """
    return bool(ctx.transaction.get("is_new_location", False))


def rule_unusual_time(ctx: RuleContext, config: dict) -> bool:
    """
    Proxy for "unusual login/activity pattern": flags a transaction that lands
    far outside the customer's own typical time-of-day activity, based on their
    recent transaction history. (This platform observes transactions, not login
    sessions, so time-of-day is the closest available activity signal.)
    """
    return bool(ctx.transaction.get("is_unusual_hour", False))


# Registry mapping rule_type -> evaluator function
RULE_REGISTRY: dict[str, Callable[[RuleContext], bool]] = {
    "AMOUNT_THRESHOLD": rule_amount_threshold,
    "VELOCITY": rule_velocity,
    "NEW_DEVICE_HIGH_VALUE": rule_new_device_high_value,
    "DEVICE_SHARING": rule_device_sharing,
    "IP_SHARING": rule_ip_sharing,
    "LOCATION_CHANGE": rule_location_change,
    "NEW_ACCOUNT_HIGH_VALUE": rule_new_account_high_value,
    "UNUSUAL_TIME": rule_unusual_time,
}

DEFAULT_RULES = [
    dict(name="High amount", rule_type="AMOUNT_THRESHOLD",
         description="Flags transactions above a fixed dollar threshold.",
         configuration={"threshold": 5000}, risk_weight=25),
    dict(name="Rapid transactions", rule_type="VELOCITY",
         description="Flags more than N transactions within a short time window.",
         configuration={"max_count": 5, "window_minutes": 10}, risk_weight=30),
    dict(name="New device + high value", rule_type="NEW_DEVICE_HIGH_VALUE",
         description="Flags a high-value transaction from a device never seen before.",
         configuration={"threshold": 1000}, risk_weight=35),
    dict(name="Device sharing", rule_type="DEVICE_SHARING",
         description="Flags a device used by multiple different customer accounts.",
         configuration={"min_customers": 2}, risk_weight=25),
    dict(name="IP sharing", rule_type="IP_SHARING",
         description="Flags an IP address used by many different customer accounts.",
         configuration={"min_customers": 3}, risk_weight=20),
    dict(name="New location", rule_type="LOCATION_CHANGE",
         description="Flags a transaction from a location never seen before for this customer.",
         configuration={}, risk_weight=15),
    dict(name="New account, high value", rule_type="NEW_ACCOUNT_HIGH_VALUE",
         description="Flags a high-value transaction from an account created within the last few days.",
         configuration={"max_age_days": 7, "threshold": 500}, risk_weight=30),
    dict(name="Unusual activity time", rule_type="UNUSUAL_TIME",
         description="Flags a transaction far outside the customer's normal time-of-day activity pattern.",
         configuration={}, risk_weight=15),
]


def evaluate_rules(db: Session, ctx: RuleContext) -> tuple[float, list[str]]:
    """
    Evaluate every active rule against the given context.
    Returns (rule_score 0-100, list of triggered rule names).
    """
    rules = db.query(Rule).filter(Rule.is_active == True).all()  # noqa: E712
    total_weight = 0.0
    triggered: list[str] = []

    for rule in rules:
        evaluator = RULE_REGISTRY.get(rule.rule_type)
        if not evaluator:
            continue
        try:
            if evaluator(ctx, rule.configuration or {}):
                triggered.append(rule.name)
                total_weight += rule.risk_weight
        except Exception:
            # A misconfigured rule should never crash the pipeline.
            continue

    rule_score = min(100.0, total_weight)
    return rule_score, triggered
