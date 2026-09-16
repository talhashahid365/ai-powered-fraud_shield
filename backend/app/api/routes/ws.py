"""
Real-time WebSocket feed for the detection pipeline (feature 18).

Any authenticated dashboard user can open a socket at /ws/live to receive a
`transaction.scored` event the moment each transaction finishes the risk
pipeline (Validation -> Rules -> ML -> Customer History -> Risk Engine ->
Decision), instead of only seeing new activity after a manual page refresh.

Browsers can't attach an Authorization header to a WebSocket handshake, so
the access token is passed as a query parameter (`?token=...`), same pattern
as most WS-based dashboards. The token is the same short-lived JWT issued by
POST /api/auth/login and is validated exactly like on every REST route.
"""
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_access_token
from app.db.database import SessionLocal
from app.models.user import User
from app.services.realtime import manager

router = APIRouter(tags=["Realtime"])


@router.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket, token: str = Query(...)):
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == payload["sub"]).first()
    finally:
        db.close()

    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        while True:
            # This feed is server -> client only; we just need to block on a
            # receive so we notice when the client goes away.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:  # noqa: BLE001
        manager.disconnect(websocket)
