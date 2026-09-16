"""
AI Investigation Assistant.

Flow: Analyst Question -> identify required data -> query DB -> gather
evidence -> LLM generates response (grounded only in that evidence).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.llm_service import answer_investigation_question
from app.api.deps import get_current_user, require_roles
from app.db.database import get_db
from app.models.alert import Alert
from app.models.enums import UserRole
from app.services.assistant_service import build_assistant_evidence, extract_device_id
from app.services.investigation_service import get_investigation_case

router = APIRouter(prefix="/api/investigation", tags=["Investigation System"])


@router.get("/case/{alert_id}")
def get_case(alert_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Full investigation case for an alert: customer info, transaction
    history, related transactions, devices, IP addresses, locations, risk
    factors, the AI explanation, related alerts, and investigation notes.
    Viewable by any authenticated user; taking investigation actions
    (notes, feedback) remains restricted to admins/analysts on their routes.
    """
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail={"success": False, "error": {"code": "ALERT_NOT_FOUND", "message": "Alert was not found"}})
    return get_investigation_case(db, alert)


class AssistantMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AssistantQuery(BaseModel):
    question: str
    alert_id: str | None = None
    customer_id: str | None = None
    device_id: str | None = None
    # Prior turns of this same chat, oldest first - lets the analyst ask
    # natural follow-ups ("what about last week?") without repeating context.
    conversation_history: list[AssistantMessage] | None = None


@router.post("/ask")
def ask_assistant(
    payload: AssistantQuery,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.ADMIN, UserRole.ANALYST)),
):
    """
    Ask the AI Investigation Assistant a free-text question, grounded in the
    platform's own transaction/customer/device data. Provide at least one of
    alert_id, customer_id, or device_id for context - a device id mentioned
    directly in the question text (e.g. "DEV-4471") also counts.
    """
    has_context = payload.alert_id or payload.customer_id or payload.device_id or extract_device_id(payload.question)
    if not has_context:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error": {
                    "code": "MISSING_CONTEXT",
                    "message": "Provide alert_id, customer_id, and/or device_id for context",
                },
            },
        )
    evidence = build_assistant_evidence(db, payload.question, payload.alert_id, payload.customer_id, payload.device_id)
    history = [m.model_dump() for m in payload.conversation_history] if payload.conversation_history else None
    answer = answer_investigation_question(payload.question, evidence, history)
    return {"answer": answer, "evidence_used": evidence}
