import csv
import io
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.schemas.transaction import CSVImportSummary, TransactionCreate
from app.services.customer_service import get_or_create_customer, update_customer_after_transaction
from app.services.realtime import build_transaction_event, manager as realtime_manager
from app.services.risk_service import run_risk_pipeline


def _to_naive_utc(dt: datetime) -> datetime:
    """
    Every datetime stored on Transaction/Customer (and every comparison done
    against them elsewhere in the risk pipeline) is naive UTC - the DB columns
    are plain DateTime with no timezone. The manual-entry API, however,
    receives transaction_datetime as an ISO-8601 string with a "Z"/offset
    suffix (the frontend sends `new Date(...).toISOString()`), which Pydantic
    parses into a TIMEZONE-AWARE datetime. Mixing that aware value into
    arithmetic/comparisons against naive values (e.g.
    `txn_datetime - customer.created_at` below) raises
    "TypeError: can't subtract offset-naive and offset-aware datetimes",
    which previously surfaced to the user as an opaque 500 on manual
    transaction creation whenever the Date/Time field was filled in. CSV
    import and the "leave it blank" path never hit this because
    `_parse_date`/`datetime.utcnow()` both already produce naive datetimes.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def create_transaction(db: Session, payload: TransactionCreate) -> Transaction:
    existing = db.query(Transaction).filter(Transaction.transaction_id == payload.transaction_id).first()
    if existing:
        raise ValueError(f"Transaction '{payload.transaction_id}' already exists")

    customer = get_or_create_customer(db, payload.customer_id)
    txn_datetime = _to_naive_utc(payload.transaction_datetime) if payload.transaction_datetime else datetime.utcnow()

    # Account age at the moment of THIS transaction:
    # - use the caller-supplied value if given (e.g. backfilled/imported history), else
    # - derive it from how long the customer has existed on this platform.
    # This used to always be 0 (customer.account_age_days was never populated), which
    # silently disabled the "new account" fraud signal for every transaction.
    if payload.account_age_days is not None:
        account_age_days = payload.account_age_days
    else:
        account_age_days = max(0, (txn_datetime - customer.created_at).days)

    txn = Transaction(
        transaction_id=payload.transaction_id,
        customer_id=customer.id,
        amount=payload.amount,
        currency=payload.currency,
        transaction_datetime=txn_datetime,
        payment_method=payload.payment_method,
        ip_address=payload.ip_address,
        device_id=payload.device_id,
        location=payload.location,
        account_age_days=account_age_days,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    risk_result = run_risk_pipeline(db, customer, txn)
    is_suspicious = risk_result.risk_level.value != "LOW"
    update_customer_after_transaction(db, customer, risk_result.risk_score, is_suspicious)

    if is_suspicious:
        from app.services.alert_service import create_alert_for_transaction
        create_alert_for_transaction(db, txn, customer, risk_result)

    # Step 9 of the real-time flow ("Alert / Approve / Review") is now reflected live on
    # any connected dashboard, not just on the next manual page refresh. Best-effort: never
    # let a broadcast issue affect the transaction that was already committed above.
    realtime_manager.broadcast_threadsafe(build_transaction_event(txn, customer, risk_result))

    return txn


REQUIRED_CSV_COLUMNS = {"transaction_id", "customer_id", "amount"}

# Accepts common header variations (case/underscore-insensitive, plus a few
# synonyms) instead of requiring the exact canonical column name, since a
# hand-made or export-tool CSV rarely matches the internal field name
# character-for-character (e.g. "date_time" or "Device" instead of
# "transaction_datetime" / "device_id").
COLUMN_ALIASES: dict[str, list[str]] = {
    "transaction_id": ["transactionid", "txn_id", "txnid", "id"],
    "customer_id": ["customerid", "cust_id", "custid", "customer"],
    "amount": ["amt", "value", "transaction_amount"],
    "currency": [],
    "transaction_datetime": ["date_time", "datetime", "date", "timestamp", "transaction_date"],
    "payment_method": ["method", "payment", "paymentmethod"],
    "ip_address": ["ip", "ipaddress"],
    "device_id": ["device", "deviceid"],
    "location": ["city", "loc"],
    "account_age_days": ["accountage", "account_age"],
}


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace("-", "_")


def _build_column_map(fieldnames: list[str]) -> dict[str, str]:
    """Map each canonical field name -> the actual header present in this CSV
    (if any), matching case-insensitively and through COLUMN_ALIASES."""
    normalized_to_actual = {_normalize_key(f): f for f in fieldnames}
    column_map: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for candidate in [canonical, *aliases]:
            if candidate in normalized_to_actual:
                column_map[canonical] = normalized_to_actual[candidate]
                break
    return column_map


def _get(row: dict, column_map: dict[str, str], canonical: str) -> str | None:
    actual = column_map.get(canonical)
    if not actual:
        return None
    value = row.get(actual)
    return value.strip() if isinstance(value, str) else value


def import_csv(db: Session, file_bytes: bytes) -> CSVImportSummary:
    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    column_map = _build_column_map(fieldnames)

    missing = REQUIRED_CSV_COLUMNS - set(column_map.keys())
    if missing:
        return CSVImportSummary(
            total_rows=0, successful_rows=0, failed_rows=0, duplicate_rows=0,
            errors=[f"Missing required columns: {', '.join(sorted(missing))}"],
        )

    total = success = failed = duplicates = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=1):
        total += 1
        try:
            txn_id = _get(row, column_map, "transaction_id")
            cust_id = _get(row, column_map, "customer_id")
            amount_raw = _get(row, column_map, "amount")
            if not txn_id or not cust_id or not amount_raw:
                raise ValueError("transaction_id, customer_id, and amount are required")

            age_raw = _get(row, column_map, "account_age_days")
            payload = TransactionCreate(
                transaction_id=txn_id,
                customer_id=cust_id,
                amount=float(amount_raw),
                currency=_get(row, column_map, "currency") or "USD",
                transaction_datetime=_parse_date(_get(row, column_map, "transaction_datetime")),
                payment_method=_get(row, column_map, "payment_method") or None,
                ip_address=_get(row, column_map, "ip_address") or None,
                device_id=_get(row, column_map, "device_id") or None,
                location=_get(row, column_map, "location") or None,
                account_age_days=int(age_raw) if age_raw else None,
            )
            create_transaction(db, payload)
            success += 1
        except ValueError as exc:
            if "already exists" in str(exc):
                duplicates += 1
            else:
                failed += 1
                errors.append(f"Row {i}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            errors.append(f"Row {i}: {exc}")

    return CSVImportSummary(
        total_rows=total, successful_rows=success, failed_rows=failed,
        duplicate_rows=duplicates, errors=errors[:50],
    )


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None
