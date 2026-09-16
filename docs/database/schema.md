# Database Schema

Implemented in `backend/app/models/`. All tables use UUID string primary keys.

- **users**: id, name, email, password_hash, role (ADMIN/BUSINESS_MANAGER/ANALYST), is_active, timestamps
- **customers**: id, customer_id, name, email, account_age_days, risk_score, risk_level, total_transactions, suspicious_transactions, previous_fraud_reports, timestamps
- **transactions**: id, transaction_id, customer_id (FK), amount, currency, transaction_datetime, payment_method, ip_address, device_id, location, account_age_days, transaction_status, risk_score, risk_level, decision, anomaly_score, rule_score, created_at
- **devices**: id, device_id, device_type, first_seen, last_seen
- **ip_addresses**: id, ip_address, country, city, first_seen, last_seen
- **alerts**: id, transaction_id (FK), customer_id (FK), severity, title, reason, status, assigned_to, timestamps
- **investigation_notes**: id, alert_id (FK), analyst_id (FK), note, timestamps
- **rules**: id, name, description, rule_type, configuration (JSON), risk_weight, is_active, created_by, timestamps
- **feedback**: id, alert_id (FK), analyst_id (FK), actual_result (CONFIRMED_FRAUD/FALSE_POSITIVE), comments, created_at
- **audit_logs**: id, user_id, action, details, ip_address, created_at
  — actively written to by `app/services/audit_service.py`, called from
  login/failed-login, rule create/update/delete, alert status changes, and
  feedback submission. Viewable via `GET /api/audit-logs` (Admin-only).

Run `python -m app.db.seed` to create tables + a default admin/analyst user
and default rules for local development. Use Alembic (`alembic/`) for real
migrations once the schema stabilizes.
