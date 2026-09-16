from datetime import datetime, timedelta

from app.ai.rules_engine import (
    RuleContext,
    rule_amount_threshold,
    rule_device_sharing,
    rule_ip_sharing,
    rule_location_change,
    rule_new_account_high_value,
    rule_new_device_high_value,
    rule_unusual_time,
    rule_velocity,
)


class _FakeTxn:
    """Minimal stand-in for a Transaction row - rule_velocity only reads .transaction_datetime."""

    def __init__(self, transaction_datetime):
        self.transaction_datetime = transaction_datetime


def test_amount_threshold_triggers_above_limit():
    ctx = RuleContext(transaction={"amount": 6000, "transaction_datetime": datetime.utcnow(), "location": "X", "is_new_device": False})
    assert rule_amount_threshold(ctx, {"threshold": 5000}) is True


def test_amount_threshold_does_not_trigger_below_limit():
    ctx = RuleContext(transaction={"amount": 100, "transaction_datetime": datetime.utcnow(), "location": "X", "is_new_device": False})
    assert rule_amount_threshold(ctx, {"threshold": 5000}) is False


def test_new_device_high_value():
    ctx = RuleContext(transaction={"amount": 2000, "transaction_datetime": datetime.utcnow(), "location": "X", "is_new_device": True})
    assert rule_new_device_high_value(ctx, {"threshold": 1000}) is True


def test_new_account_high_value_triggers_for_young_account_and_big_amount():
    ctx = RuleContext(transaction={"amount": 800, "account_age_days": 2})
    assert rule_new_account_high_value(ctx, {"max_age_days": 7, "threshold": 500}) is True


def test_new_account_high_value_does_not_trigger_for_established_account():
    ctx = RuleContext(transaction={"amount": 800, "account_age_days": 400})
    assert rule_new_account_high_value(ctx, {"max_age_days": 7, "threshold": 500}) is False


def test_location_change_uses_is_new_location_flag():
    ctx = RuleContext(transaction={"is_new_location": True})
    assert rule_location_change(ctx, {}) is True
    ctx2 = RuleContext(transaction={"is_new_location": False})
    assert rule_location_change(ctx2, {}) is False


def test_unusual_time_uses_is_unusual_hour_flag():
    ctx = RuleContext(transaction={"is_unusual_hour": True})
    assert rule_unusual_time(ctx, {}) is True
    ctx2 = RuleContext(transaction={"is_unusual_hour": False})
    assert rule_unusual_time(ctx2, {}) is False


def test_velocity_triggers_when_current_txn_makes_total_exceed_max_count():
    """Spec: 'more than 5 transactions in 10 minutes -> suspicious'.

    `recent_customer_transactions` holds only prior transactions, so 5 prior
    + the current transaction being scored = 6 total in the window, which
    is 'more than 5' and must trigger.
    """
    now = datetime(2026, 1, 1, 12, 0, 0)
    prior = [_FakeTxn(now - timedelta(minutes=m)) for m in (1, 2, 3, 4, 5)]
    ctx = RuleContext(transaction={"amount": 10, "transaction_datetime": now}, recent_customer_transactions=prior)
    assert rule_velocity(ctx, {"max_count": 5, "window_minutes": 10}) is True


def test_velocity_does_not_trigger_below_threshold():
    now = datetime(2026, 1, 1, 12, 0, 0)
    prior = [_FakeTxn(now - timedelta(minutes=m)) for m in (1, 2, 3, 4)]
    ctx = RuleContext(transaction={"amount": 10, "transaction_datetime": now}, recent_customer_transactions=prior)
    assert rule_velocity(ctx, {"max_count": 5, "window_minutes": 10}) is False


def test_velocity_ignores_transactions_outside_the_window():
    now = datetime(2026, 1, 1, 12, 0, 0)
    # 5 in-window + 3 old ones outside the 10-minute window should still just trigger once, not over-count.
    prior = [_FakeTxn(now - timedelta(minutes=m)) for m in (1, 2, 3, 4, 5)]
    prior += [_FakeTxn(now - timedelta(minutes=m)) for m in (20, 30, 45)]
    ctx = RuleContext(transaction={"amount": 10, "transaction_datetime": now}, recent_customer_transactions=prior)
    assert rule_velocity(ctx, {"max_count": 5, "window_minutes": 10}) is True


def test_device_sharing_triggers_at_min_customers():
    ctx = RuleContext(transaction={}, same_device_customer_ids={"cust-1", "cust-2"})
    assert rule_device_sharing(ctx, {"min_customers": 2}) is True


def test_device_sharing_does_not_trigger_below_min_customers():
    ctx = RuleContext(transaction={}, same_device_customer_ids={"cust-1"})
    assert rule_device_sharing(ctx, {"min_customers": 2}) is False


def test_ip_sharing_triggers_when_multiple_accounts_share_ip():
    ctx = RuleContext(transaction={}, same_ip_customer_ids={"cust-1", "cust-2", "cust-3"})
    assert rule_ip_sharing(ctx, {"min_customers": 3}) is True


def test_ip_sharing_does_not_trigger_for_single_account():
    ctx = RuleContext(transaction={}, same_ip_customer_ids={"cust-1"})
    assert rule_ip_sharing(ctx, {"min_customers": 3}) is False
