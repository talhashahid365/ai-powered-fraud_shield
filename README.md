# FraudShield AI — Fraud & Risk Detection Platform

A full-stack, AI-powered fraud & risk detection platform: transaction ingestion,
a configurable rules engine, ML anomaly detection (Isolation Forest), a risk
decision engine, LLM-generated explanations, fraud alerts, an investigation
workspace, a fraud network graph, an AI investigation assistant, dashboards
and reports.

This repository is a **working scaffold**: the architecture, database schema,
API contracts, and end-to-end pipeline described in `docs/` are fully wired
up and runnable. Some areas (rich fraud-network graph UI, full CSV
background processing via Celery, complete test coverage, production
deployment configs) are stubbed with clear extension points for each team
member to build out further — see `docs/architecture/development-phases.md`.

## Project layout

```
backend/    FastAPI + SQLAlchemy + PostgreSQL API (Person 1 + Person 2)
frontend/   React + Vite + TypeScript + Tailwind UI (Person 3)
ml/         Mock data generator + Isolation Forest training pipeline
docs/       API contracts, architecture, database design
```

## Quick start (local, without Docker)

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit DATABASE_URL, SECRET_KEY, LLM keys
# Make sure PostgreSQL is running and the database in DATABASE_URL exists
python -m app.db.seed          # creates admin@fraudshield.ai / ChangeMe123!
uvicorn app.main:app --reload  # http://localhost:8000/docs
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

Log in with `admin@fraudshield.ai` / `ChangeMe123!` (change immediately in
a real deployment), `manager@fraudshield.ai` / `ChangeMe123!`, or
`analyst@fraudshield.ai` / `ChangeMe123!`.

### 3. Generate mock data + train the ML model (optional but recommended)

```bash
cd ml/data
python generate_mock_transactions.py --rows 3000 --out mock_transactions.csv

cd ../training
python train_isolation_forest.py --input ../data/mock_transactions.csv
```

The trained model is saved to `ml/models/isolation_forest.joblib` and is
automatically picked up by the backend on next restart. Until a model is
trained, the backend uses a documented heuristic fallback so the whole
pipeline still works end-to-end (see `app/ai/anomaly_detection.py`).

### 4. Docker Compose (Postgres + Redis + backend + frontend)

```bash
docker compose up --build
```

## LLM provider

Set `LLM_PROVIDER` in `backend/.env` to `claude`, `openai`, `gemini`, `local`,
or `none`. With `none` (the default), explanations are generated from a
deterministic template using the same structured risk factors — so the
product works without any LLM key configured. Add the matching API key
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`) to enable a real LLM.

## Team ownership (see docs/architecture for full detail)

- **Person 1 — Backend Core & Data**: `backend/app/models`, `backend/app/db`,
  `backend/app/api/routes/auth.py`, `transactions.py`, `alembic/`.
- **Person 2 — Risk Intelligence**: `backend/app/ai/`, `ml/`.
- **Person 3 — Frontend & Investigation**: `frontend/src/`.

## Default accounts (development only — change before any real deployment)

| Email                     | Password      | Role    |
|---------------------------|---------------|---------|
| admin@fraudshield.ai      | ChangeMe123!  | ADMIN   |
| manager@fraudshield.ai    | ChangeMe123!  | BUSINESS_MANAGER |
| analyst@fraudshield.ai    | ChangeMe123!  | ANALYST |
