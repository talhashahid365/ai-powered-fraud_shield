# Architecture Overview

```
Frontend (React/Vite)
      |
      v
FastAPI Backend  (auth, transactions, alerts, customers, rules, dashboard, reports)
      |
      v
PostgreSQL  (users, customers, transactions, devices, ip_addresses, alerts,
             investigation_notes, rules, feedback, audit_logs)
      |
      v
Risk Intelligence Services (app/services/risk_service.py orchestrates):
      Rules Engine (app/ai/rules_engine.py)
      +
      ML Anomaly Detection - Isolation Forest (app/ai/anomaly_detection.py)
      +
      Customer History (app/services/customer_service.py)
      |
      v
Risk Decision Engine (app/ai/risk_engine.py)
      |
      v
Final Risk Score / Level / Decision
      |
      v
Alerts (app/services/alert_service.py) -> Dashboard / Investigation / Reports
```

## Real-time detection flow

New Transaction -> Data Validation (Pydantic schema) -> Rule Engine ->
ML/AI Analysis -> Customer History -> Risk Engine -> Risk Score -> Decision
-> Alert / Approve / Review.

This entire flow runs synchronously inside `transaction_service.create_transaction`
today so the product works end-to-end immediately. For production scale,
move the risk pipeline into a Celery task (see `backend/app/workers/`,
currently a stub) so the `POST /api/transactions` endpoint returns quickly
and the heavier ML/rules evaluation happens asynchronously.

**Live push to the dashboard:** every transaction's decision is also broadcast
over a WebSocket (`app/services/realtime.py` + `GET /ws/live`, wired into
`transaction_service.create_transaction`) so a connected dashboard sees new
alerts and stats update the moment they're scored, instead of only on the
next manual refresh. See `frontend/src/hooks/useLiveFeed.ts` for the client
side and `frontend/src/pages/DashboardPage.tsx` for how it's consumed.

**Data Validation:** `app/schemas/transaction.py::TransactionCreate` enforces
positive/bounded amounts, well-formed IDs, a real 3-letter currency code, a
plausible IP shape, and non-future timestamps before anything reaches the
rule engine or ML model.

## Risk score (0-100) and the factors behind it

Every transaction gets a 0-100 `risk_score` derived from a weighted blend of
the rules engine (35%), the ML anomaly score (40%), and a customer behavior
score (25%) — see `app/ai/risk_engine.py::calculate_final_risk`. Thresholds
(`app/core/config.py`): 0-30 LOW, 31-70 MEDIUM, 71-100 HIGH.

Factors considered, beyond raw transaction amount:

| Factor | Where it's implemented |
| --- | --- |
| Unusual transaction amount (deviation from the customer's own average) | `risk_service._gather_context` (`amount_deviation_from_avg`) + `AMOUNT_THRESHOLD` rule |
| New device | `is_new_device` (never seen before for this customer) |
| New location | `is_new_location` — never seen before for this customer across their history (not just "different from the last transaction") |
| Multiple transactions in a short period (velocity) | `txn_count_last_5/10/30min` + `VELOCITY` rule |
| Multiple accounts using the same device | `DEVICE_SHARING` rule |
| Multiple customers using the same IP | `IP_SHARING` rule |
| Sudden change in customer behavior | `compute_behavior_score` — EMA of the customer's historical risk score blended with their suspicious-transaction ratio |
| Unusual login/activity pattern | `is_unusual_hour` — transaction time-of-day compared to the customer's own historical pattern (a proxy signal, since the platform observes transaction timestamps rather than login sessions) |
| High-value transaction from a new account | `is_new_account_high_value` — uses `account_age_days` (derived from how long the customer has existed on the platform, or an explicit override) + `NEW_ACCOUNT_HIGH_VALUE` rule |

These signals feed both the configurable rules engine (admin-editable via
`/rules`) and the ML anomaly detector's feature vector (`app/ai/anomaly_detection.py`).
A trained Isolation Forest model ships in `ml/models/isolation_forest.joblib`
(trained on generated mock data — see `ml/README.md`); until a model is
present the pipeline falls back to a documented heuristic over the same
signals so it still produces a usable score in a fresh environment. See
`ml/README.md` for the full writeup of the ML approach, what else was
considered (clustering, a supervised classifier once fraud labels exist),
and how to retrain from real data via `ml/training/train_from_database.py`.

## Role-based UI

- `frontend/src/layouts/AppLayout.tsx` filters nav items by role: "Rules
  Engine" and "Audit Logs" only appear for ADMIN. Route-level guards
  (`RoleRoute` in `App.tsx`) enforce the same restriction if someone
  navigates to the URL directly, and the backend (`require_roles`) is the
  actual source of truth either way.
- `frontend/src/pages/DashboardPage.tsx` renders a different view for
  ANALYST (an "Investigation Queue" of NEW alerts first, system stats
  below) vs. ADMIN/BUSINESS_MANAGER (system-wide stats + recent alerts).
- `frontend/src/pages/TransactionsPage.tsx` hides the CSV import control
  for ANALYST, matching the backend's `require_roles(ADMIN, BUSINESS_MANAGER)`
  on `POST /api/transactions/import-csv`.

## Fraud network visualization

`frontend/src/pages/CustomerProfilePage.tsx` renders the Customer -> Device
-> IP graph returned by `GET /api/customers/{id}/network` using
`react-force-graph-2d`: draggable/zoomable canvas, color-coded node types,
click-to-inspect. This replaced the earlier plain edge-list rendering.

## Audit logging

`backend/app/services/audit_service.py::log_action` is called from:
- `api/routes/auth.py` (LOGIN_SUCCESS, LOGIN_FAILED, USER_REGISTERED)
- `api/routes/rules.py` (RULE_CREATED, RULE_UPDATED, RULE_DELETED)
- `api/routes/alerts.py` (ALERT_STATUS_CHANGED, FEEDBACK_SUBMITTED)

View history at `GET /api/audit-logs` (Admin-only) or the `/audit-logs`
frontend page.

## Extension points still open

- `backend/app/workers/` — Celery app + tasks are defined but not yet
  called from any route; CSV import and risk scoring still run
  synchronously in the request. Wire `tasks.process_csv_import.delay(...)`
  into `api/routes/transactions.py` to move this to the background.
- `backend/app/tests/` — auth, rules engine, risk engine, audit-log, and
  transaction/CSV-import/realtime tests are included; run `pytest` to verify.
- No PDF/Excel report export yet (CSV export exists client-side for one
  report) and no actual cloud deployment has been done (Docker Compose is
  local-dev only).
- The `/ws/live` broadcast is in-process only (a single `ConnectionManager`
  in memory) — fine for one backend instance, but running multiple API
  replicas behind a load balancer would need a shared pub/sub (e.g. Redis,
  which is already a dependency for Celery) so a broadcast from one
  instance reaches clients connected to another.
