"""
Real-time push layer for the detection pipeline.

Feature 18 (Real-Time Detection) already ran its full flow synchronously on
every transaction (Validation -> Rule Engine -> ML/AI Analysis -> Customer
History -> Risk Engine -> Risk Score -> Decision -> Alert/Approve/Review, see
app/services/risk_service.py). What was missing for it to actually feel
"real-time" from a user's perspective: the frontend only ever fetched
dashboard/alert data once on page mount (see frontend/src/pages/DashboardPage.tsx),
so a new high-risk transaction scored by the pipeline was invisible to anyone
already looking at the dashboard until they manually refreshed.

This module fixes that gap with a lightweight WebSocket broadcast: every time
a transaction finishes the risk pipeline, a small JSON event is pushed to all
connected dashboard clients, who can prepend it to their live feed / bump
their alert counters without polling.

Design notes:
- `transaction_service.create_transaction` (the single choke point for both
  the manual-add API and CSV import, see app/services/transaction_service.py)
  runs on a plain sync def, executed by FastAPI in a worker thread -- it has
  no event loop of its own. `broadcast_threadsafe` bridges that by scheduling
  the actual async send onto the main event loop captured at startup via
  `asyncio.run_coroutine_threadsafe`.
- If nobody is connected (or the app is running under pytest, where no loop
  is bound), broadcasting is a cheap no-op -- it never blocks or fails
  transaction creation.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Called once from the FastAPI startup event so later threadsafe
        broadcasts know which running event loop to schedule onto."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def _broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - a broken client should never break others
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

    def broadcast_threadsafe(self, message: dict[str, Any]) -> None:
        """Safe to call from sync code running off the main event loop
        (e.g. inside a request handled in FastAPI's threadpool, or a Celery
        worker). No-ops quietly if there's no bound loop or no listeners."""
        if self._loop is None or not self._connections:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(message), self._loop)
        except Exception:  # noqa: BLE001
            # Broadcasting is a best-effort UX enhancement; it must never take
            # down the actual detection pipeline it's reporting on.
            logger.exception("Failed to schedule realtime broadcast")


manager = ConnectionManager()


def build_transaction_event(txn, customer, risk) -> dict[str, Any]:
    """Small, frontend-friendly summary of one scored transaction.

    `risk` is either the RiskCheckResponse returned by run_risk_pipeline, or
    the persisted Transaction row itself (both expose the same field names).
    """
    return {
        "type": "transaction.scored",
        "transaction": {
            "id": txn.id,
            "transaction_id": txn.transaction_id,
            "customer_id": customer.customer_id if customer else None,
            "amount": txn.amount,
            "currency": txn.currency,
            "risk_score": risk.risk_score,
            "risk_level": risk.risk_level.value if hasattr(risk.risk_level, "value") else risk.risk_level,
            "decision": risk.decision.value if hasattr(risk.decision, "value") else risk.decision,
            "created_at": txn.created_at.isoformat() if txn.created_at else None,
        },
    }
