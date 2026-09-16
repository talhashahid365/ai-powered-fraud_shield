"""
FraudShield AI - FastAPI application entrypoint.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import alerts, api_keys, audit, auth, customers, dashboard, investigation, network, notifications, reports, risk, rules, transactions, ws
from app.core.config import settings
from app.db.database import Base, engine
from app.services.realtime import manager as realtime_manager
import app.models  # noqa: F401  (ensures models are registered on Base.metadata)

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Fraud & Risk Detection Platform API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Consistent error envelope, per section 28 of the spec."""
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        return JSONResponse(status_code=exc.status_code, content=detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": "ERROR", "message": str(detail)}},
    )


@app.on_event("startup")
def on_startup() -> None:
    # For local dev convenience. In production, use Alembic migrations instead.
    # Skipped under pytest (TESTING=1) since tests use their own in-memory/SQLite session.
    import os
    if os.environ.get("TESTING") != "1":
        Base.metadata.create_all(bind=engine)


@app.on_event("startup")
async def bind_realtime_loop() -> None:
    # Captures the running event loop so transaction_service (sync code, run in FastAPI's
    # threadpool) can schedule WebSocket broadcasts back onto it via run_coroutine_threadsafe.
    import asyncio
    realtime_manager.bind_loop(asyncio.get_running_loop())


app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(risk.router)
app.include_router(api_keys.router)
app.include_router(alerts.router)
app.include_router(notifications.router)
app.include_router(customers.router)
app.include_router(network.router)
app.include_router(rules.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(investigation.router)
app.include_router(audit.router)
app.include_router(ws.router)


@app.get("/")
def root():
    return {"name": settings.APP_NAME, "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
