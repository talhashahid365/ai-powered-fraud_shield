# API Contracts

Base URL: `/api`. Full interactive OpenAPI/Swagger docs are auto-generated
by FastAPI at `/docs` (Swagger UI) and `/redoc` when the backend is running.

## Authentication

- `POST /api/auth/register` — create a user (name, email, password, role)
- `POST /api/auth/login` — returns `{ access_token, token_type, user }`
- `GET  /api/auth/me` — current user (requires `Authorization: Bearer <token>`)

## Transactions

- `POST /api/transactions` — create a transaction (ADMIN, BUSINESS_MANAGER, or
  an External Business API key — see below). Accepts an optional
  `account_age_days` override; when omitted it's derived automatically from
  how long the customer has existed on the platform.
- `POST /api/transactions/import-csv` — CSV import, returns import summary.
  Optional `account_age_days` column is supported alongside the required
  `transaction_id`, `customer_id`, `amount` columns.
- `GET  /api/transactions` — paginated list; filters: search, risk_level,
  payment_method, customer_id, location, page, page_size
- `GET  /api/transactions/{id}` — transaction detail (any authenticated
  caller, or an API key). Response includes `account_age_days` and
  `previous_transaction_count` for that customer.
- `GET  /api/transactions/{id}/risk` — risk explanation for a transaction

## External Business API

External e-commerce/payment systems integrate with these 5 routes directly -
no dashboard user login required. Authenticate with an API key instead of a
JWT: send `X-API-Key: <key>` on every request. (A dashboard user's Bearer
token also still works on these same routes, e.g. for testing from `/docs`.)

- `POST /api/transactions` — submit a transaction, get back its risk decision
  in the same response (ADMIN, BUSINESS_MANAGER, or any valid API key)
- `POST /api/risk-check` — create + score a transaction in one call, returns
  `{ risk_score, risk_level, decision }` (ADMIN, BUSINESS_MANAGER, or API key)
- `GET  /api/transactions/{id}` — look up a transaction by the internal `id`
  returned from the create call above (any authenticated caller, or API key)
- `GET  /api/risk/{transaction_id}` — look up risk by *your own*
  business-facing `transaction_id` (any authenticated caller, or API key)
- `POST /api/alerts/{id}/review` — update an alert's status, e.g. mark it
  `INVESTIGATING` (ADMIN, ANALYST, or any valid API key)

### Getting an API key

Only an ADMIN dashboard user can issue keys, via:

- `POST /api/api-keys` `{ "business_name": "Acme E-Commerce" }` → returns
  `{ id, business_name, api_key, key_prefix, created_at }`. **The `api_key`
  value is shown exactly once** — store it securely; it can't be retrieved
  again (only a bcrypt hash is kept server-side). Format: `fsk_live_<random>`.
- `GET /api/api-keys` — list issued keys (prefix only, never the full secret)
- `DELETE /api/api-keys/{id}` — revoke a key immediately

### Example

```bash
curl -X POST https://your-domain/api/risk-check \
  -H "X-API-Key: fsk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
        "transaction_id": "ORDER-88213",
        "customer_id": "CUST-4471",
        "amount": 1899.00,
        "currency": "USD",
        "payment_method": "CARD",
        "ip_address": "203.0.113.44",
        "device_id": "device-9f8a",
        "location": "Karachi, PK"
      }'
```

```json
{
  "risk_score": 87,
  "risk_level": "HIGH",
  "decision": "REVIEW",
  "triggered_rules": ["New device + high value"],
  "anomaly_score": 91.2,
  "risk_factors": [
    "Transaction originated from a device never seen for this customer before.",
    "ML anomaly model flagged this transaction (anomaly score 91/100)."
  ],
  "explanation": "This transaction was flagged for review because ..."
}
```

An invalid, revoked, or missing key returns `401` with
`{"success": false, "error": {"code": "INVALID_API_KEY" | "UNAUTHENTICATED", ...}}`.
API keys only work on the 5 routes above — every other endpoint (listing
transactions, rules, customers, reports, etc.) still requires a real
dashboard login.

## Alerts

- `GET  /api/alerts` — list alerts (filter by status_filter)
- `GET  /api/alerts/{id}` — alert detail
- `POST /api/alerts/{id}/review` — update alert status (ADMIN, ANALYST, or
  an External Business API key — see above)
- `POST /api/alerts/{id}/notes` — add an investigation note
- `POST /api/alerts/{id}/feedback` — mark CONFIRMED_FRAUD / FALSE_POSITIVE

## Customers

- `GET /api/customers` — list customers by risk score
- `GET /api/customers/{customer_id}` — customer profile
- `GET /api/customers/{customer_id}/risk-profile` — risk level/score, total
  & suspicious transactions, distinct devices/locations used, previous
  fraud reports; refreshed continuously on every transaction
- `POST /api/customers/{customer_id}/risk-profile/recalculate` — force a
  devices/locations recount from transaction history (e.g. after a backfill)
- `GET /api/customers/{customer_id}/transactions` — history
- `GET /api/customers/{customer_id}/network` — 1-hop fraud network graph for
  this customer only (nodes/edges: customer, device, ip)

## Fraud Network Detection

- `GET /api/fraud-network/rings` — every group of 2+ customers connected
  through a shared device/IP, directly or transitively; ranked by risk
- `GET /api/fraud-network/graph/{customer_id}` — full multi-hop
  Customer → Device → IP → Transaction → Location graph for the fraud ring
  that customer belongs to (an isolated customer just gets a single-node
  graph)
- Frontend: `/fraud-network` (ring list) and `/fraud-network/{customer_id}`
  (graph view)

## Rules Engine (Admin)

- `GET/POST /api/rules`, `PUT/DELETE /api/rules/{id}`
- Frontend: `/rules` page (Admin-only nav item)

## Audit Logs (Admin)

- `GET /api/audit-logs` — recent security-sensitive events (logins, failed
  logins, rule changes, alert status changes, feedback submissions)
- Frontend: `/audit-logs` page (Admin-only nav item)

## Dashboard & Reports

- `GET /api/dashboard/summary`, `/fraud-trend`, `/recent-alerts`
- `GET /api/reports/daily-fraud-activity`, `/monthly-fraud-activity`,
  `/high-risk-customers`, `/high-risk-transactions`, `/confirmed-fraud`,
  `/false-positives`, `/fraud-trends`, `/fraud-outcomes`,
  `/model-feedback-summary` — the seven report types cover every item in
  spec section 16; `/confirmed-fraud` and `/false-positives` are
  drill-down lists of individual alerts (vs. the aggregate counts in
  `/fraud-outcomes`), and `/fraud-trends` returns a daily time series plus
  an `increasing` / `decreasing` / `stable` trend direction over a
  configurable trailing window (`days`, default 30).
- `GET /api/reports/export/{report_type}` — downloads any of the above
  report types as CSV (`report_type` is the same slug used in the path,
  e.g. `high-risk-customers`, `fraud-trends`). Accepts the same query
  params as the corresponding JSON endpoint (`date`, `year`/`month`,
  `start_date`/`end_date`, `days`, `limit`) and streams back
  `text/csv` with a `Content-Disposition: attachment` header.

## AI Investigation Assistant

- `POST /api/investigation/ask` — `{ question, alert_id?, customer_id? }`,
  answer is grounded only in evidence queried from the database.

## Standard response shapes

List responses:
```json
{ "data": [], "page": 1, "page_size": 20, "total": 100 }
```

Error responses:
```json
{ "success": false, "error": { "code": "TRANSACTION_NOT_FOUND", "message": "..." } }
```
